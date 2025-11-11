from flask import json
import requests
import os
from pathlib import Path
from dotenv import load_dotenv
from typing import TypedDict, Optional
load_dotenv()
session = requests.Session()

class Category(TypedDict):
    """Represents a GameBanana category."""
    name: str
    id: int
    count: int
# A directory to store downloaded archives
DOWNLOAD_DIR = Path("download_temp")

# A directory to extract archive contents into
EXTRACT_DIR = Path("extract_temp")

# Selected Game (from .env)
GAME = os.getenv("GAME", "WW")

# Debugging (from .env)
DEBUG_MODE = os.getenv("DEBUG_MODE", "False").lower() == "true"

# Sample Limit (from .env)
SAMPLE_LIMIT = int(os.getenv("SAMPLE_LIMIT", "1"))

# Sleep to avoid rate limiting or ip bans
SLEEP_BETWEEN_DOWNLOADS = 2

# Request timeout (seconds)
REQUEST_TIMEOUT = 60

# Maximum number of concurrent threads for file processing
MAX_THREADS = 4


# Gamebanana game category id
GAME_IDS = {
    "WW": 29524,
    "ZZ": 30305,
    "GI": 18140
}

# NocoDB Configuration (from .env)
NOCO_BASE_URL = os.getenv("NOCO_BASE_URL", "https://db.wwmm.bhatt.jp/api/v1/db/data/noco/pnifvzk8oa0fglo/{}")
NOCO_VARS = {
    "Base": os.getenv("NOCO_BASE", ""),
    "WW": os.getenv("NOCO_WW", ""),
    "ZZ": os.getenv("NOCO_ZZ", ""),
    "GI": os.getenv("NOCO_GI", ""),
    "ini": os.getenv("NOCO_INI", ""),
    "bearer": os.getenv("NOCO_BEARER", "")
}

# GameBanana API URLs
API_BASE_URL = "https://gamebanana.com/apiv11{}"
API_DL_URL = "https://gamebanana.com/dl/{}"
CATEGORY_LIST_SUBURL = "/Mod/Categories?_idCategoryRow={}&_sSort=a_to_z&_bShowEmpty=false"
CATEGORY_SUBURL = "/Mod/Index?_nPerpage=50&_aFilters%5BGeneric_Category%5D={}&_sSort=Generic_Oldest&_nPage={}"
MOD_SUBURL = "/{}/ProfilePage"
class Mod(TypedDict):
    """Represents a GameBanana mod with metadata."""
    id: str  # Format: "ModelName/idRow" (e.g., "Mod/524321")
    added: int  # Unix timestamp (_tsDateAdded)
    modified: int  # Unix timestamp (_tsDateModified)
def get_cats(game: str) -> None:
    """Initializes the CATEGORIES list with category data from GameBanana API."""
    cats = []
    try:
        response = session.get(
            API_BASE_URL.format(CATEGORY_LIST_SUBURL.format(GAME_IDS[game])), 
            timeout=REQUEST_TIMEOUT
        )  
        response.raise_for_status()
        data = response.json()
        for datum in data:
            cats.append(Category(
                name=datum['_sName'],
                id=datum['_idRow'],
                count=datum['_nItemCount']
            ))
    except requests.exceptions.RequestException as e:
        print(f"Error fetching categories: {e}")
    except Exception as e:
        print(f"Unexpected error in get_cats: {e}")
    return cats
def get_mods(category: Category) -> list[Mod]:
    """Fetches mod URLs from a GameBanana category API endpoint."""
    mods: list[Mod] = []
    # print(category)
    for i in range(0,category['count'],50):
        # print (API_BASE_URL.format(CATEGORY_SUBURL.format(category['id'],i//50 +1 )))
        try:
            response = session.get(
                API_BASE_URL.format(CATEGORY_SUBURL.format(category['id'],i//50 +1 )), 
                timeout=REQUEST_TIMEOUT
            )
            response.raise_for_status()
            data = response.json()
            records = data.get('_aRecords', [])
            for record in records:
                mods.append(Mod(
                    id=record.get('_sModelName') + "/" +str(record.get('_idRow')),
                    added=record.get('_tsDateAdded',0),
                    modified=record.get('_tsDateModified',0)
                ))
        except requests.exceptions.RequestException as e:
            print(f"Error fetching category data for page {i//50 + 1}: {e}")
        except Exception as e:
            print(f"Unexpected error in get_mods: {e}")
    print(f"Fetched {len(mods)} mods from category {category['name']} count {category['count']}.")
    sort_by_date_difference(mods)
    return mods[0:SAMPLE_LIMIT] if DEBUG_MODE else mods
def sort_by_date_difference(records: list[Mod]) -> list[Mod]:
    """
    Sorts an array of mod records by the biggest difference between 
    _tsDateModified and _tsDateAdded (descending order).
    
    Args:
        records: List of mod records containing _tsDateModified and _tsDateAdded
        
    Returns:
        Sorted list with biggest differences first
    """
    return sorted(
        records, 
        key=lambda record: record.get('modified', 0) - record.get('added', 0),
        reverse=True
    )

def get(mod: Mod) -> Optional[bytes]:
    """Downloads the mod archive from GameBanana."""
    dl_url = API_DL_URL.format(mod['id'])
    try:
        response = session.get(dl_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.content
    except requests.exceptions.RequestException as e:
        print(f"Error downloading mod {mod['id']}: {e}")
    return None


version=[1.1,1.2,1.3,1.4,2.0,2.1,2.2,2.3,2.4,2.5,2.6,2.7]
version_time=[1719532800, 1723680000, 1727568000, 1731542400, 1735776000, 1739404800, 1743033600, 1745884800, 1749686400, 1753315200, 1756339200,1759968000]
print(len(version))
print(len(version_time))
def main():
    valid=0
    cats = get_cats(GAME)
    cats.sort(key=lambda c: c['count'], reverse=True)
    cat = cats[0]
    mods = get_mods(cat)
    print(f"Total mods to process: {len(mods)}")
    for mod in mods:
        url = f"https://db.wwmm.bhatt.jp/api/v3/data/{NOCO_VARS['Base']}/{NOCO_VARS[GAME]}/records/{mod['id'].replace('/', '%2F')}"
        headers = {
            "Content-Type": "application/json",
            "xc-token": NOCO_VARS["bearer"]
        }
        response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        data = response.json()
        data={
            "id": mod['id'],
            # **data['record']['fields'] but make the keys start with lowercase
            **{k[0].lower() + k[1:]: v for k, v in data['fields'].items()}
        }
        data["data"] = json.loads(data["data"])
        #convert data["data"] from dict {id:data} to an array , filter by status=="success"
        data["data"] = [{**v, "id": k} for k, v in data["data"].items() if v.get("status")=="success"]
        if len(data["data"])<2:
            continue
        valid+=1
        version_wise={}
        #group by version, using data["data"]'s "added" field to determine version
        for file in data["data"]:
            file_added = file.get("added", 0)
            file_version = 1.0
            for i in range(len(version_time)):
                if file_added >= version_time[i]:
                    file_version = version[i]
            if file_version not in version_wise:
                version_wise[file_version] = []
            version_wise[file_version].append(file)
        print(version_wise)
    print(f"Total valid mods with successful files: {valid} out of {len(mods)}")

def single(id="Mod/534215"):
    mod = Mod(
        id=id,
        added=0,
        modified=0
    )
    url = f"https://db.wwmm.bhatt.jp/api/v3/data/{NOCO_VARS['Base']}/{NOCO_VARS[GAME]}/records/{mod['id'].replace('/', '%2F')}"
    headers = {
        "Content-Type": "application/json",
        "xc-token": NOCO_VARS["bearer"]
    }
    response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    data = response.json()
    data={
        "id": mod['id'],
        # **data['record']['fields'] but make the keys start with lowercase
        **{k[0].lower() + k[1:]: v for k, v in data['fields'].items()}
    }
    data["data"] = json.loads(data["data"])
    #convert data["data"] from dict {id:data} to an array , filter by status=="success"
    data["data"] = [{**v, "id": k} for k, v in data["data"].items() if v.get("status")=="success"]
    print(data)
    version_wise={}
    #group by version, using data["data"]'s "added" field to determine version
    for file in data["data"]:
        file_added = file.get("added", 0)
        file_version = 1.0
        for i in range(len(version_time)):
            if file_added >= version_time[i]:
                file_version = version[i]
        if file_version not in version_wise:
            version_wise[file_version] = []
        version_wise[file_version].append(file)
    print(version_wise)
if __name__ == "__main__":
    single("Mod/534215")