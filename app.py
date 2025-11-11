import requests
import os
import shutil
from pathlib import Path
import time
from typing import TypedDict, Optional
from flask import Flask, jsonify, render_template
from datetime import datetime
from dotenv import load_dotenv
from waitress import serve
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()

# --- Flask App ---
app = Flask(__name__)

# --- Configure requests session with retry logic ---
session = requests.Session()
retry_strategy = Retry(
    total=3,  # Total number of retries
    backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
    status_forcelist=[429, 500, 502, 503, 504],  # Retry on these HTTP status codes
    allowed_methods=["GET", "POST"]  # Retry on GET and POST
)
adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
session.mount("http://", adapter)
session.mount("https://", adapter)

# --- Global Variables ---
is_running = False  # Track if scraper is currently running

# --- Custom Data Types ---

done=0
cat=""
cat_done=0
cat_total=0
total=0
table_data={}

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

# --- Configuration ---

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

# --- Flask Routes ---
@app.route('/')
def home():
    """Serve the HTML dashboard."""
    return render_template('index.html')

@app.route('/start', methods=['GET', 'POST'])
def start_scraper():
    """Start the scraper."""
    global is_running
    
    if is_running:
        return jsonify({
            "status": "error",
            "message": "Scraper is already running"
        }), 400
    
    # Run scraper synchronously (blocking)
    is_running = True
    try:
        main2()
        return jsonify({
            "status": "success",
            "message": "Scraper completed successfully"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Scraper failed: {str(e)}"
        }), 500
    finally:
        is_running = False

@app.route('/status', methods=['GET'])
def get_status():
    """Return current scraper status."""
    return jsonify({
        "status": "success",
        "is_running": is_running,
        "message": f"Category: '{cat}' | Progress:  {cat_done}/{cat_total} ({cat_done / cat_total * 100 if cat_total > 0 else 0:.2f}%) | Overall Progress: {done}/{total} ({done / total * 100 if total > 0 else 0:.2f}%)" if is_running else "",
        "log_count": 0,
        "log_file_exists": False,
        "logs": []
    })
def list_table(table:str) -> dict:
    """Lists records from a NocoDB table."""
    url = f"https://db.wwmm.bhatt.jp/api/v3/data/{NOCO_VARS['Base']}/{NOCO_VARS[table]}/records"
    headers = {
        "Content-Type": "application/json",
        "xc-token": NOCO_VARS["bearer"]
    }
    data={}
    count=0
    while url:
        print(f"Getting NocoDB table {table} page {count}")
        try:
            response = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            result = response.json()
            data.update({record['id']: record for record in result.get('records', [])})
            url = result.get('next')
        except requests.exceptions.Timeout:
            print(f"Timeout listing NocoDB table {table}")
            break
        except requests.exceptions.RequestException as e:
            print(f"Error listing NocoDB table {table}: {e}")
            break
        except Exception as e:
            print(f"Unexpected error listing NocoDB: {e}")
            break
        count+=1
    return data
    

# --- NocoDB Functions ---
def post(table:str, data: dict) -> dict:
    """Posts data to a NocoDB table."""
    url = NOCO_BASE_URL.format(NOCO_VARS[table])
    headers = {
        "Content-Type": "application/json",
        "xc-token": NOCO_VARS["bearer"]
    }
    try:
        response = session.post(url, json=data, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print(f"Timeout posting to NocoDB table {table}")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"Error posting to NocoDB table {table}: {e}")
        return {}
    except Exception as e:
        print(f"Unexpected error posting to NocoDB: {e}")
        return {}

# --- Dependency Check ---
def check_and_install_dependencies() -> bool:
    """Checks if unrar is installed and installs it from source if missing."""
    import subprocess
    
    print("Checking for required extraction tools...")
    
    # Check if unrar is available
    try:
        result = subprocess.run(['which', 'unrar'], capture_output=True, text=True)
        if result.stdout.strip():
            print("✓ unrar is already installed")
            return True
    except Exception:
        pass
    
    # unrar not found, install it
    print("⚠ unrar not found. Installing from source...")
    print("This may take a few minutes and requires sudo privileges.")
    
    commands = [
        "sudo apt-get install p7zip-full unzip unrar-free -y",
        "wget https://www.rarlab.com/rar/unrarsrc-5.6.4.tar.gz",
        "tar -xvzf unrarsrc-5.6.4.tar.gz",
        "cd unrar && make lib",
        "cd unrar && sudo make install-lib",
        "sudo ldconfig",
        "rm -rf unrar unrarsrc-5.6.4.tar.gz"
    ]
    
    try:
        # Install p7zip-full and unzip
        print("Installing p7zip-full and unzip...")
        subprocess.run(commands[0], shell=True, check=True)
        
        # Download unrar source
        print("Downloading unrar source...")
        subprocess.run(commands[1], shell=True, check=True)
        
        # Extract
        print("Extracting...")
        subprocess.run(commands[2], shell=True, check=True)
        
        # Build library
        print("Building unrar library...")
        subprocess.run(commands[3], shell=True, check=True)
        
        # Install library
        print("Installing unrar library...")
        subprocess.run(commands[4], shell=True, check=True)
        
        # Update library cache
        print("Updating library cache...")
        subprocess.run(commands[5], shell=True, check=True)
        
        # Cleanup
        print("Cleaning up...")
        subprocess.run(commands[6], shell=True, check=True)
        
        print("✓ unrar installed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"✗ Error during installation: {e}")
        print("You may need to install unrar manually.")
        return False
    except Exception as e:
        print(f"✗ Unexpected error: {e}")
        return False

# --- Helper Functions ---
def get_cats(game: str) -> None:
    """Initializes the CATEGORIES list with category data from GameBanana API."""
    global total
    cats = []
    try:
        response = session.get(
            API_BASE_URL.format(CATEGORY_LIST_SUBURL.format(GAME_IDS[game])), 
            timeout=REQUEST_TIMEOUT
        )  
        response.raise_for_status()
        data = response.json()
        for datum in data:
            total += int(datum['_nItemCount'])
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
        print(f"Error fetching mod profile data: {e}")
    except Exception as e:
        print(f"Unexpected error in get_files: {e}")
    if files:
        files.sort(key=lambda x: x['added'])
    return files[0:SAMPLE_LIMIT] if DEBUG_MODE else files

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
    print(f"Downloading {url}...")
    save_path = DOWNLOAD_DIR / name
    try:
        response = session.get(url, stream=True, timeout=REQUEST_TIMEOUT)
        # Check for HTTP errors (e.g., 404 Not Found)
        response.raise_for_status() 
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:  # filter out keep-alive chunks
                    f.write(chunk)
        print("Download complete.")
        return True
    except requests.exceptions.Timeout:
        print(f"Timeout downloading {url}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error downloading {url}: {e}")
        return False

def extract_file(name:str) -> bool:
    """Extracts a .zip, .rar, or .7z file to a target directory using command-line tools."""
    import subprocess
    
    print(f"Extracting {name}...")
    src = DOWNLOAD_DIR / name
    tgt = EXTRACT_DIR / Path(name).stem
    # Ensure the extraction directory exists
    tgt.mkdir(exist_ok=True, parents=True)
    
    try:
        if src.suffix == '.zip':
            # Use unzip command
            result = subprocess.run(
                ['unzip', '-q', '-o', str(src), '-d', str(tgt)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
        elif src.suffix == '.rar':
            # Use unrar command (supports RAR5 format)
            result = subprocess.run(
                ['unrar', 'x', '-y', '-o+', str(src), str(tgt) + '/'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
        elif src.suffix == '.7z':
            # Use 7z command from p7zip-full
            result = subprocess.run(
                ['7z', 'x', str(src), f'-o{str(tgt)}', '-y'],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
        else:
            print(f"Unsupported file type: {src.suffix}")
            return False
        
        # Check if extraction was successful (0 or 1 for unzip warnings)
        if result.returncode not in [0, 1]:
            print(f"Error extracting {src.name} (exit code: {result.returncode})")
            if result.stderr:
                print(f"  stderr: {result.stderr}")
            if result.stdout:
                print(f"  stdout: {result.stdout}")
            return False
            
        print("Extraction complete.")
        return True
    
    except subprocess.TimeoutExpired:
        print(f"Timeout extracting {src.name} (took more than 5 minutes)")
        return False
    except FileNotFoundError as e:
        print(f"Error: Required extraction tool not found.")
        print("Install with: sudo apt install unzip unrar p7zip-full")
        return False
    except Exception as e:
        print(f"Error extracting {src.name}: {e}")
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
            print(f"Error reading {path.name} with alternate encoding: {e}")
            return {
                "name": path.name,
                "content": ""
            }
    except Exception as e:
        print(f"Error reading INI file {path.name}: {e}")
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
    return post("ini", ini_data)

def cleanup(name:str):
    """Deletes the specified file and directory."""
    print("Cleaning up temporary files...")
    archive_path = DOWNLOAD_DIR / name
    extracted_dir = EXTRACT_DIR / Path(name).stem
    try:
        if archive_path and archive_path.exists():
            os.remove(archive_path)
            print(f"Deleted {archive_path.name}")
        
        if extracted_dir and extracted_dir.exists():
            shutil.rmtree(extracted_dir)
            print(f"Deleted directory {extracted_dir.name}")       
    except OSError as e:
        print(f"Error during cleanup: {e}")

def process_file(file: File):
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
        if not download_file(API_DL_URL.format(file['id']), name) or not extract_file(name):
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
        print(f"An unexpected error occurred for {file['id']}: {e}") 
    finally:
        # 5. Delete zip/unzipped data (runs even if errors occurred)
        cleanup(name)
        print("-" * 40)
    return file


def batch_process_files(files: list[File]):
    """Process files concurrently using a thread pool."""
    processed_files = {}
    
    # Use ThreadPoolExecutor for concurrent processing
    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        # Submit all file processing tasks
        future_to_file = {executor.submit(process_file, file): file for file in files}
        
        # Wait for all tasks to complete and collect results
        for future in as_completed(future_to_file):
            original_file = future_to_file[future]
            try:
                file = future.result()
                if file is None:
                    file = original_file
                
                if file["data"]["status"] == "success":
                    print(f"Processed file {file['id']} successfully with {file['data']['ini_count']} INI files.")
                else:
                    print(f"Failed to process file {file['id']}: {file['data']['reason']}")
                
                processed_files[file["id"]] = file["data"]
            except Exception as e:
                print(f"Exception occurred while processing file {original_file['id']}: {e}")
                processed_files[original_file["id"]] = {
                    "status": "failed",
                    "reason": f"err: exception - {e}",
                    "added": original_file["added"]
                }
    
    return processed_files


def main2():
    """Main scraper function."""
    global is_running, cat, cat_done, cat_total, done
    try:
        DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)
        EXTRACT_DIR.mkdir(exist_ok=True, parents=True)
        cats=get_cats(GAME)
        # response = requests.get("https://db.wwmm.bhatt.jp/api/v2/tables/{}/records/count".format(NOCO_VARS[GAME]), headers={
        #     "xc-token": NOCO_VARS["bearer"]
        # })
        # prev_done = response.json().get("count", 0)
        table_data=list_table(GAME)
        print(f"Previous done: {len(table_data)}")
        if not cats:
            print("No categories found.")
            return 0
        print(f"Fetched categories:")
        for catg in cats:
            print(f" - {catg['name']} (ID: {catg['id']}, Count: {catg['count']})")
        print("-" * 40)
        print(f"Starting scraping for game {GAME}...")
        for catg in cats:
            cat_total=catg["count"]
            # if(done+cat_total<=prev_done):
            #     done+=cat_total
            #     cat_done=cat_total
            #     print(f"Skipping category {catg['name']} as already done.")
            #     continue
            cat=catg["name"]
            cat_done=0
            print(f"Category: {catg['name']} (ID: {catg['id']}, Count: {catg['count']})")
            mods = get_mods(catg)
            print(f"Fetched metadata for {len(mods)} mod(s).")
            for mod in mods:
                if(mod['id']!="Mod/592745" and table_data.get(str(mod['id']))):
                    done+=1
                    cat_done+=1
                    print(f"Skipping mod {mod['id']} as already done.")
                    continue
                print(f"Mod : {mod}")
                files = get_files(mod)
                print(f"Mod ID {mod['id']} has {len(files)} files.")
                file_data=batch_process_files(files)
                data ={
                    "Id" : mod['id'],
                    "Category" : catg['name'],
                    "Added": mod['added'],
                    "Modified": mod['modified'],
                    "Data": file_data
                }
                post(GAME, data)
                cat_done+=1
                done+=1
                print(f"Uploaded mod {mod['id']} data to NocoDB. Sleeping for {SLEEP_BETWEEN_DOWNLOADS} seconds...")
                time.sleep(SLEEP_BETWEEN_DOWNLOADS)
        print("Scraping completed successfully!")
    except Exception as e:
        print(f"Error in main2: {e}")
    finally:
        is_running = False

if __name__ == "__main__":
    # Check dependencies on startup
    print("=" * 50)
    print("GameBanana Scraper - Flask Server Starting")
    print("=" * 50)
    
    if not check_and_install_dependencies():
        print("⚠ Warning: Could not verify all dependencies.")
        print("Some extractions may fail.")
    
    print("=" * 50)
    print("Flask server is ready")
    print("Use /start to begin scraping")
    print("Use /status to check status")
    print("=" * 50)
    
    # Start Flask app with Waitress (production-ready WSGI server)
    print("Starting Waitress server on http://0.0.0.0:5000")
    serve(app, host='0.0.0.0', port=5000, threads=4)