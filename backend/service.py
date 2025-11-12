from flask import json
import requests
import os
import shutil
from pathlib import Path
import time
from typing import TypedDict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import db
from sessions import get_session

session = get_session()

logs=[]
new_logs=[]
def log(message: str, level: str = "info") -> None:
    """Logs a message with a specified level."""
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    log_entry = f'[{timestamp}] [{level.upper()}] {message}'
    if(len(logs)>1000):
        logs.pop(0)
    logs.append(log_entry)
    new_logs.append(log_entry)
    print(log_entry)

def save_logs() -> None:
    """Saves logs to a file."""
    global new_logs
    
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True, parents=True)
    log_file = log_dir / f'log_{time.strftime("%Y%m%d_%H%M%S", time.localtime())}.log'
    print(f"Saving logs to {log_file}...")
    count=0
    while(True):
        if TASK=="Finished" or TASK=="Cancelled":
            break
        time.sleep(1)
        count= (count+1)%60
        if not new_logs or count!=0:
            continue
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                for entry in new_logs:
                    f.write(entry + '\n')
            new_logs = []
            print(f"Logs saved to {log_file}")
        except Exception as e:
            print(f"Error saving logs: {e}")
    
    # Save any remaining logs before exiting
    if new_logs:
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                for entry in new_logs:
                    f.write(entry + '\n')
            new_logs = []
            print(f"Final logs saved to {log_file}")
        except Exception as e:
            print(f"Error saving final logs: {e}")


    

class Category(TypedDict):
    """Represents a GameBanana category."""
    name: str
    id: int
    count: int

class Mod(TypedDict):
    """Represents a GameBanana mod with metadata."""
    id: str  # Format: "ModelName/idRow" (e.g., "Mod/524321")
    added: int  # Unix timestamp (_tsDateAdded)
    modified: int  # Unix timestamp (_tsDateModified)

class File(TypedDict):
    """Represents a downloadable file from a mod."""
    id: int  # File row ID (_idRow)
    parent_id: int # Parent mod ID (_idModRow)
    ext: str # File name
    size: int  # File size in bytes (_nFilesize)
    added: int  # Unix timestamp (_tsDateAdded)
    data: Optional[dict]  # Placeholder for additional data

REQUEST_TIMEOUT = 30
BEARER=""
TASK = "Idle"
DOWNLOAD_DIR = Path("download_temp")
EXTRACT_DIR = Path("extract_temp")
GAME = "WW"
CATEGORIES = []
MAX_THREADS = 4
SLEEP_TIME=2
TABLE_DATA={}
PROGRESS = {
    "total_files_processed": 0,
    "categories_total": 0,
    "categories_done": 0,
    "mods_total": 0,
    "mods_done": 0,
    "category": {"name":"","total":0,"done":0},
    "mods": {},
    "files": {},
    
}
 

# Gamebanana game category id
GAME_IDS = {
    "WW": 29524,
    "ZZ": 30305,
    "GI": 18140
}

API_BASE_URL = "https://gamebanana.com/apiv11{}"
API_DL_URL = "https://gamebanana.com/dl/{}"
CATEGORY_LIST_SUBURL = "/Mod/Categories?_idCategoryRow={}&_sSort=a_to_z&_bShowEmpty=false"
CATEGORY_SUBURL = "/Mod/Index?_nPerpage=50&_aFilters%5BGeneric_Category%5D={}&_sSort=Generic_Oldest&_nPage={}"
MOD_SUBURL = "/{}/ProfilePage"


def get_status():
    return {
        "current_task": TASK,
        "progress": PROGRESS,
        "logs": logs[-100:]  # Return last 100 log entries
    }

def cancel_task():
    global TASK
    if TASK in ["Idle","Finished","Cancelled"]:
        log("No running task to cancel.", level="warn")
        return False
    TASK="Stopping"
    log("Task cancellation requested.", level="info")
    return True

import requests
import re # Import regular expressions



def get_recr(query_params=None):
    data = []
    count=0
    response = db.get('RECORDS', bearer=BEARER, table=GAME, query_params=query_params)
    while True:
        log(f"Fetching page {count} of NocoDB table {GAME}", level="info")
        try:
            response.raise_for_status()
            result = response.json()
            data.extend({"Id": record.get('id'), **record.get('fields', {})} for record in result.get('records', []))
            url = result.get('next')
            if not url:
                break
            response = db.get(url, bearer=BEARER)
        except requests.exceptions.Timeout:
            log(f"Timeout listing NocoDB table {GAME}", level="error")
            break
        except requests.exceptions.RequestException as e:
            log(f"Error listing NocoDB table {GAME}: {e}", level="error")
            break
        except Exception as e:
            log(f"Unexpected error listing NocoDB: {e}", level="error")
            break
        count+=1
    return data


def update():
    records = list(TABLE_DATA.values())
    pass

def get_broken_files(mod):
    res=[]
    mod_id=mod['Id']
    data=json.loads(mod['Data'])
    files = {
        str(item["id"]): item for item in get_files({"id":mod_id})
    }
    for file_id, file_data in data.items():
        if file_data.get('status')=='failed' and file_data.get('reason','').startswith('err: dl/ex failed') and file_id in files:
            res.append(files[file_id])
    return res

def fix():
    broken_mods = get_recr(query_params={'where': '(Data, like, err: dl/ex failed)'})
    broken_files=[]
    file_to_mod={}
    for mod in broken_mods:
        if(mod["Id"]=="Mod/616624"):
            broken_mods=[mod]
            break
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Submit all file processing tasks
        future_to_mod = {executor.submit(get_broken_files, mod): mod for mod in broken_mods} 
        # Wait for all tasks to complete and collect results
        for future in as_completed(future_to_mod):
            original_mod = future_to_mod[future]
            try:
                files = future.result()
                if files is None:
                    files = original_mod 
                for file in files:
                    file_to_mod[file['id']]=file['parent_id']
                broken_files.extend(files)
            except Exception as e:
                log(f"Exception occurred while processing mod {original_mod['Id']}: {e}", level="error")
    
    print(f"Total broken files to fix: {len(broken_files)}, first file: {broken_files[0] if broken_files else 'N/A'}")
    fixed_files = batch_process_files(broken_files[0:1])
    mod_patch={}
    for id,data in fixed_files.items():
        mod_id = file_to_mod.get(id)
        if not mod_id:
            continue
        if mod_id not in mod_patch:
            mod_patch[mod_id]={}
        mod_patch[mod_id][str(id)] = data
    patch_data=[]
    for mod_id, files_data in mod_patch.items():
        get_mod_from_db = db.get('RECORDS', bearer=BEARER, table=GAME, record=str(mod_id))
        if not get_mod_from_db.status_code==200:
            continue
        mod_data = json.loads(get_mod_from_db.json().get('fields',{}).get('Data',"{}"))
        log(mod_data,level="info")
        # mod_data.update(files_data)
        log(mod_data,level="info")
        log(f"Fetched mod {mod_id} from DB for patching",level="info")
        patch_data.append({
            "id": mod_id,
            "fields":{
                "Data": mod_data
            }
        })
        break
    log(f"Prepared patch data for {len(patch_data)} mods. {patch_data}", level="info")
    if(patch_data):
        log(f"Prepared patch data for {len(patch_data)} mods. {patch_data}", level="info")
        res=db.patch('RECORDS', bearer=BEARER, table=GAME, data=patch_data)
        log(f"Patch response: {res.status_code} - {res.text}", level="info")
    return True



def run():
    global PROGRESS,TASK
    if not CATEGORIES:
        log("No categories found.", level="error")
        return 0
    print(f"Fetched categories:")
    for category in CATEGORIES:
        print(f" - {category['name']} (ID: {category['id']}, Count: {category['count']})")
    print("-" * 40)
    log(f"Starting scraping for game {GAME}...", level="info")
    PROGRESS={
    "total_files_processed": 0,
    "categories_total": PROGRESS["categories_total"],
    "categories_done": 0,
    "mods_total": PROGRESS["mods_total"],
    "mods_done": 0,
    "category": {"name":"","total":0,"done":0},
    "mods": {},
    "files": {},}
    for category in CATEGORIES:
        PROGRESS["category"]["total"]=category["count"]
        PROGRESS["category"]["name"]=category["name"]
        PROGRESS["category"]["done"]=0
        PROGRESS["categories_done"]+=1
        log(f"Category: {category['name']} (ID: {category['id']}, Count: {category['count']})", level="info")
        mods = get_mods(category)
        log(f"Fetched metadata for {len(mods)} mod(s).", level="info")
        
        for mod in mods:
            if TASK == "Stopping":
                TASK="Cancelled"
                log("Task cancelled by user.", level="info")
                return
            if(TABLE_DATA.get(str(mod['id']))):
                PROGRESS["mods_done"]+=1
                PROGRESS["category"]["done"]+=1
                log(f"Skipping mod {mod['id']} as already done.", level="info")
                continue
            
            log(f"Mod : {mod}", level="info")
            files = get_files(mod)
            log(f"Mod ID {mod['id']} has {len(files)} files.", level="info")
            PROGRESS["mods"][str(mod['id'])] = {
                "total": len(files),
                "done": 0
            }
            file_data=batch_process_files(files,mod["id"])
            data ={
                "Id" : mod['id'],
                "Category" : category['name'],
                "Added": mod['added'],
                "Modified": mod['modified'],
                "Data": file_data
            }
            if( TASK == "Stopping"):
                continue
            db.post("GENERIC", bearer=BEARER, table=GAME, data=data)
            del PROGRESS["mods"][str(mod['id'])]
            PROGRESS["mods_done"]+=1
            PROGRESS["category"]["done"]+=1
            log(f"Uploaded mod {mod['id']} data to NocoDB. Sleeping for {SLEEP_TIME} seconds...", level="info")
            time.sleep(SLEEP_TIME)
    log("Scraping completed successfully!", level="finish")
    
    TASK="Finished"
    pass

def start_service(task="run",game="WW", bearer="",threads=4,sleep=2):
    global TASK, GAME, BEARER, MAX_THREADS, SLEEP_TIME

    if TASK not in ["Idle","Finished","Cancelled"]:
        log("A task is already running. Cannot start a new task.", level="warn")
        return False
    TASK = {"scrape":"Running","map":"Mapping","fix":"Fixing","update":"Updating"}[task]
    MAX_THREADS = threads
    SLEEP_TIME = sleep
    GAME = game
    BEARER = bearer
    threading.Thread(target=save_logs).start()
    if TASK == "Mapping":
        time.sleep(4)  # Simulate a medium-length task
        return True
    DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)
    EXTRACT_DIR.mkdir(exist_ok=True, parents=True)
    log(f"Starting task: {TASK} for {GAME} with a maximum of {MAX_THREADS} threads and sleep time {SLEEP_TIME}s", level="info")
    if TASK == "Fixing":
        threading.Thread(target=fix).start()
        return True
    get_cats()
    get_full_table_data()
    if TASK == "Running":
        threading.Thread(target=run).start()    
    elif TASK == "Updating":
        threading.Thread(target=update).start()

    return True

def get_cats(passive=False) -> None:
    """Initializes the CATEGORIES list with category data from GameBanana API."""
    global CATEGORIES, PROGRESS
    if passive and CATEGORIES:
        return CATEGORIES
    cats = []
    try:
        response = session.get(
            API_BASE_URL.format(CATEGORY_LIST_SUBURL.format(GAME_IDS[GAME])), 
            timeout=REQUEST_TIMEOUT
        )  
        response.raise_for_status()
        data = response.json()
        for datum in data:
            PROGRESS["categories_total"] += 1
            PROGRESS["mods_total"] += int(datum['_nItemCount'])  
            cats.append(Category(
                name=datum['_sName'],
                id=datum['_idRow'],
                count=datum['_nItemCount']
            ))
    except requests.exceptions.RequestException as e:
        log(f"Error fetching categories: {e}", level="error")
    except Exception as e:
        log(f"Unexpected error in get_cats: {e}", level="error")
        
    CATEGORIES = cats
    return cats

def get_full_table_data():
    global TABLE_DATA
    data={}
    records = get_recr()
    for record in records:
         data[record['Id']] = record
    TABLE_DATA = data
    return data
    
def get_mods(category: Category) -> list[Mod]:
    """Fetches mod URLs from a GameBanana category API endpoint."""
    mods: list[Mod] = []
    for i in range(0,category['count'],50):
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
            log(f"Error fetching category data for page {i//50 + 1}: {e}", level="error")
        except Exception as e:
            log(f"Unexpected error in get_mods: {e}", level="error")
    log(f"Fetched {len(mods)} mods from category {category['name']} count {category['count']}.", level="info")
    sort_by_date_difference(mods)
    return mods

def get_files(mod: Mod) -> list[File]:
    """Fetches file download URLs from a GameBanana mod profile API endpoint."""
    files: list[File] = [] 
    #file format: url:_sDownloadUrl, id:_idRow, size:_nFilesize, date_added:_tsDateAdded, 
    try:
        response = session.get(
            API_BASE_URL.format(MOD_SUBURL.format(mod['id'])), 
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        records = data.get('_aFiles', []) + data.get('_aArchivedFiles', [])
        for file in records:
            download_url = file.get('_sDownloadUrl')
            if download_url:
                files.append(File(
                    id=file.get('_idRow'),
                    parent_id=mod['id'],
                    ext=file.get('_sFile').split('.')[-1],
                    size=file.get('_nFilesize'),
                    added=file.get('_tsDateAdded'),
                ))
    except requests.exceptions.RequestException as e:
        log(f"Error fetching mod profile data: {e}", level="error")
    except Exception as e:
        log(f"Unexpected error in get_files: {e}", level="error")
        
    if files:
        files.sort(key=lambda x: x['added'])
    return files

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

def download_file(url: str, name: str) -> bool:
    """Downloads a file from a URL to a specific path."""
    log(f"Downloading {url}...", level="info")
    
    save_path = DOWNLOAD_DIR / name
    try:
        response = session.get(url, stream=True, timeout=REQUEST_TIMEOUT)
        # Check for HTTP errors (e.g., 404 Not Found)
        response.raise_for_status() 
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive chunks
                    f.write(chunk)
        log("Download complete.", level="info")
        
        return True
    except requests.exceptions.Timeout:
        log(f"Timeout downloading {url}", level="error")
        
        return False
    except requests.exceptions.RequestException as e:
        log(f"Error downloading {url}: {e}", level="error")
        return False
    except Exception as e:
        log(f"Unexpected error downloading {url}: {e}", level="error")
        return False

def extract_file(name:str) -> bool:
    """Extracts a .zip, .rar, or .7z file to a target directory using 7z command-line tool."""
    import subprocess
    
    log(f"Extracting {name}...", level="info")
    src = DOWNLOAD_DIR / name
    tgt = EXTRACT_DIR / Path(name).stem
    # Ensure the extraction directory exists
    tgt.mkdir(exist_ok=True, parents=True)
    
    try:
        # Use 7z for all archive types (.zip, .rar, .7z)
        result = subprocess.run(
            ['7z', 'x', str(src), f'-o{str(tgt)}', '-y'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        # Check if extraction was successful
        if result.returncode not in [0, 1]:
            log(f"Error extracting {src.name} (exit code: {result.returncode})", level="error")
            
            if result.stderr:
                log(f"  stderr: {result.stderr}", level="error")
            if result.stdout:
                log(f"  stdout: {result.stdout}", level="error")
            return False
            
        log("Extraction complete.", level="info")
        
        return True
    
    except subprocess.TimeoutExpired:
        log(f"Timeout extracting {src.name} (took more than 5 minutes)", level="error")
        
        return False
    except FileNotFoundError as e:
        log(f"Error: 7z command not found.", level="error")
        log("Install with: sudo apt install p7zip-full", level="error")
        return False
    except Exception as e:
        log(f"Error extracting {src.name}: {e}", level="error")
        return False

def read_ini(path: Path) -> dict:
    """
    Reads an INI file as plain text and returns its name and content.
    
    Args:
        path: Path to the INI file
        
    Returns:
        Dictionary with 'name' (filename) and 'content' (file contents as string)
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        return {
            "name": path.name,
            "content": content
        }
    except UnicodeDecodeError:
        # Try with different encoding if UTF-8 fails
        try:
            with open(path, 'r', encoding='latin-1') as f:
                content = f.read()
            return {
                "name": path.name,
                "content": content
            }
        except Exception as e:
            log(f"Error reading {path.name} with alternate encoding: {e}", level="error")
            
            return {
                "name": path.name,
                "content": ""
            }
    except Exception as e:
        log(f"Error reading INI file {path.name}: {e}", level="error")
        
        return {
            "name": path.name,
            "content": ""
        }

def process_ini(id:str,path: Path) -> dict:
    ini = read_ini(path)
    return {
        "Id": id,
        "Name": ini.get("name", ""),
        "Data": ini.get("content", "")
    }

def upload_ini(ini_data: dict) -> dict:
    if TASK == "Stopping":
        return
    return db.post("GENERIC", bearer=BEARER, table="INI", data=ini_data)

def cleanup(name:str):
    """Deletes the specified file and directory."""
    log("Cleaning up temporary files...", level="info")
    
    archive_path = DOWNLOAD_DIR / name
    extracted_dir = EXTRACT_DIR / Path(name).stem
    try:
        if archive_path and archive_path.exists():
            os.remove(archive_path)
            log(f"Deleted {archive_path.name}", level="info")
        
        if extracted_dir and extracted_dir.exists():
            shutil.rmtree(extracted_dir)
            log(f"Deleted directory {extracted_dir.name}", level="info")
    except OSError as e:
        log(f"Error during cleanup: {e}", level="error")
        

def process_file(file: File, mod_id="") -> Optional[File]:
    global PROGRESS
    PROGRESS["files"][str(file['id'])] = {}
    if mod_id:
        PROGRESS["mods"][str(mod_id)]["done"] += 1
    log(f"Processing file ID {file['id']} (Size: {file['size']} bytes)...", level="info")
    name = f'{file["id"]}.{file["ext"]}'
    file["data"]={
        "status":"failed",
        "reason":"err: dl/ex failed",
        "added":file["added"]
    }
    if file["size"] > 1024*1024*1024:  # Skip files larger than 100MB
        file['data']['reason']="err: too large"
        return file
    try:
       
        if TASK == "Stopping" or not download_file(API_DL_URL.format(file['id']), name) or not extract_file(name):
            return file
        ini_files = list((EXTRACT_DIR/Path(name).stem).rglob("*.ini"))
        if len(ini_files) == 0:
            file['data']['reason']="no ini"
            return file
        for i in range(len(ini_files)):
            id = f"{GAME}/{file['parent_id']}/{file['id']}/{i}"
            upload_ini(process_ini(id, ini_files[i]))
        file["data"]["status"]="success"
        file["data"]["ini_count"]=len(ini_files)
        del file["data"]["reason"]
    except Exception as e:
        file['data']['reason']=f"err: {e}"
        log(f"An unexpected error occurred for {file['id']}: {e}", level="error") 
        
    finally:
        # 5. Delete zip/unzipped data (runs even if errors occurred)
        cleanup(name)
        print("-" * 40)
        PROGRESS["total_files_processed"] += 1
        del PROGRESS["files"][str(file['id'])]
    return file


def batch_process_files(files: list[File], mod_id="") -> dict:
    """Process files concurrently using a thread pool."""
    processed_files = {}
    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Submit all file processing tasks
        future_to_file = {executor.submit(process_file, file, mod_id): file for file in files}
        
        # Wait for all tasks to complete and collect results
        for future in as_completed(future_to_file):
            original_file = future_to_file[future]
            try:
                file = future.result()
                if file is None:
                    file = original_file
                
                if file["data"]["status"] == "success":
                    log(f"Processed file {file['id']} successfully with {file['data']['ini_count']} INI files.", level="info")
                else:
                    log(f"Failed to process file {file['id']}: {file['data']['reason']}", level="warn")
                
                processed_files[file["id"]] = file["data"]
            except Exception as e:
                log(f"Exception occurred while processing file {original_file['id']}: {e}", level="error")
                processed_files[original_file["id"]] = {
                    "status": "failed",
                    "reason": f"err: exception - {e}",
                    "added": original_file["added"]
                }
    return processed_files


