import requests
import os
import shutil
from pathlib import Path
import time
from typing import TypedDict, Optional
from flask import Flask, jsonify, render_template
import threading
from datetime import datetime
from dotenv import load_dotenv
from waitress import serve

# Load environment variables
load_dotenv()

# --- Flask App ---
app = Flask(__name__)

# --- Global Variables ---
logs = []  # Store recent logs
log_lock = threading.Lock()  # Thread-safe log updates
LOG_FILE = Path("scraper.log")
is_running = False  # Track if scraper is currently running

# --- Custom Data Types ---


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
SLEEP_BETWEEN_DOWNLOADS = 10


# Gamebanana game category id
GAME_IDS = {
    "WW": 29524,
    "ZZ": 30305
}

# NocoDB Configuration (from .env)
NOCO_BASE_URL = os.getenv("NOCO_BASE_URL", "https://db.wwmm.bhatt.jp/api/v1/db/data/noco/pnifvzk8oa0fglo/{}")
NOCO_VARS = {
    "WW": os.getenv("NOCO_WW", ""),
    "ZZ": os.getenv("NOCO_ZZ", ""),
    "ini": os.getenv("NOCO_INI", ""),
    "bearer": os.getenv("NOCO_BEARER", "")
}

# GameBanana API URLs
API_BASE_URL = "https://gamebanana.com/apiv11{}"
API_DL_URL = "https://gamebanana.com/dl/{}"
CATEGORY_LIST_SUBURL = "/Mod/Categories?_idCategoryRow={}&_sSort=a_to_z&_bShowEmpty=false"
CATEGORY_SUBURL = "/Mod/Index?_nPerpage=50&_aFilters%5BGeneric_Category%5D={}&_sSort=Generic_Oldest&_nPage={}"
MOD_SUBURL = "/{}/ProfilePage"

# --- Logging Functions ---
def log(message: str):
    """Thread-safe logging to both array and console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    
    with log_lock:
        logs.append(log_entry)
    
    print(log_entry)  # Still print to console for debugging

def save_logs_to_file():
    """Periodically save logs to file and clear the array."""
    while True:
        print("Log-saving thread sleeping...")
        time.sleep(60)  # Wait 60 seconds
        
        with log_lock:
            print("Log-saving thread woke up, checking logs...")
            if logs:

                # Append logs to file
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    for log_entry in logs:
                        f.write(log_entry + '\n')
                
                
                # Clear the logs array
                logs.clear()
                log(f"Saved {len(logs)} logs to file and cleared array")

# --- Flask Routes ---
@app.route('/')
def home():
    """Serve the HTML dashboard."""
    return render_template('index.html')

@app.route('/start', methods=['GET', 'POST'])
def start_scraper():
    """Start the scraper in a background thread."""
    global is_running
    
    if is_running:
        return jsonify({
            "status": "error",
            "message": "Scraper is already running"
        }), 400
    
    is_running = True
    
    # Start scraper in background thread
    thread = threading.Thread(target=run_main2, daemon=True)
    thread.start()
    
    return jsonify({
        "status": "success",
        "message": "Scraper started successfully"
    })



@app.route('/status', methods=['GET'])
def get_status():
    """Return current scraper status."""
    all_logs = []
    # Read from log file
    if LOG_FILE.exists():
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            file_logs = f.readlines()
            all_logs.extend([line.strip() for line in file_logs])
    
    # Add current logs array (in reverse order)
    with log_lock:
        all_logs.extend(logs.copy())
    return jsonify({
        "status": "success",
        "is_running": is_running,
        "log_count": len(logs),
        "log_file_exists": LOG_FILE.exists(),
        "logs": all_logs

    })

# --- NocoDB Functions ---
def post(table:str, data: dict) -> dict:
    """Posts data to a NocoDB table."""
    url = NOCO_BASE_URL.format(NOCO_VARS[table])
    headers = {
        "Content-Type": "application/json",
        "xc-token": NOCO_VARS["bearer"]
    }
    try:
        response = requests.post(url, json=data, headers=headers, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        log(f"Error posting to NocoDB table {table}: {e}")
        return {}

# --- Dependency Check ---
def check_and_install_dependencies() -> bool:
    """Checks if unrar is installed and installs it from source if missing."""
    import subprocess
    
    log("Checking for required extraction tools...")
    
    # Check if unrar is available
    try:
        result = subprocess.run(['which', 'unrar'], capture_output=True, text=True)
        if result.stdout.strip():
            log("✓ unrar is already installed")
            return True
    except Exception:
        pass
    return True
    # unrar not found, install it
    log("⚠ unrar not found. Installing from source...")
    log("This may take a few minutes and requires sudo privileges.")
    
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
        log("Installing p7zip-full and unzip...")
        subprocess.run(commands[0], shell=True, check=True)
        
        # Download unrar source
        log("Downloading unrar source...")
        subprocess.run(commands[1], shell=True, check=True)
        
        # Extract
        log("Extracting...")
        subprocess.run(commands[2], shell=True, check=True)
        
        # Build library
        log("Building unrar library...")
        subprocess.run(commands[3], shell=True, check=True)
        
        # Install library
        log("Installing unrar library...")
        subprocess.run(commands[4], shell=True, check=True)
        
        # Update library cache
        log("Updating library cache...")
        subprocess.run(commands[5], shell=True, check=True)
        
        # Cleanup
        log("Cleaning up...")
        subprocess.run(commands[6], shell=True, check=True)
        
        log("✓ unrar installed successfully!")
        return True
        
    except subprocess.CalledProcessError as e:
        log(f"✗ Error during installation: {e}")
        log("You may need to install unrar manually.")
        return False
    except Exception as e:
        log(f"✗ Unexpected error: {e}")
        return False

# --- Helper Functions ---
def get_cats(game: str) -> None:
    """Initializes the CATEGORIES list with category data from GameBanana API."""
    cats = []
    response = requests.get(API_BASE_URL.format(CATEGORY_LIST_SUBURL.format(GAME_IDS[game])), timeout=30)  
    response.raise_for_status()
    data = response.json()
    for datum in data:
        cats.append(Category(
            name=datum['_sName'],
            id=datum['_idRow'],
            count=datum['_nItemCount']
        )) 
    return cats

def get_mods(category: Category) -> list[Mod]:
    """Fetches mod URLs from a GameBanana category API endpoint."""
    mods: list[Mod] = []
    # print(category)
    for i in range(0,category['count'],50):
        # print (API_BASE_URL.format(CATEGORY_SUBURL.format(category['id'],i//50 +1 )))
        try:
            response = requests.get(API_BASE_URL.format(CATEGORY_SUBURL.format(category['id'],i//50 +1 )), timeout=30)
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
            log(f"Error fetching category data: {e}")
    log(f"Fetched {len(mods)} mods from category {category['name']} count {category['count']}.")
    sort_by_date_difference(mods)
    return mods[0:SAMPLE_LIMIT] if DEBUG_MODE else mods

def get_files(mod: Mod) -> list[File]:
    """Fetches file download URLs from a GameBanana mod profile API endpoint."""
    files: list[File] = [] 
    #file format: url:_sDownloadUrl, id:_idRow, size:_nFilesize, date_added:_tsDateAdded, 
    try:
        response = requests.get(API_BASE_URL.format(MOD_SUBURL.format(mod['id'])), timeout=30)
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
        log(f"Error fetching mod profile data: {e}")
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
    log(f"Downloading {url}...")
    save_path = DOWNLOAD_DIR / name
    try:
        response = requests.get(url, stream=True, timeout=30)
        # Check for HTTP errors (e.g., 404 Not Found)
        response.raise_for_status() 
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        log("Download complete.")
        return True
    except requests.exceptions.RequestException as e:
        log(f"Error downloading {url}: {e}")
        return False

def extract_file(name:str) -> bool:
    """Extracts a .zip, .rar, or .7z file to a target directory using command-line tools."""
    import subprocess
    
    log(f"Extracting {name}...")
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
                text=True
            )
        elif src.suffix == '.rar':
            # Use unrar command (supports RAR5 format)
            result = subprocess.run(
                ['unrar', 'x', '-y', '-o+', str(src), str(tgt) + '/'],
                capture_output=True,
                text=True
            )
        elif src.suffix == '.7z':
            # Use 7z command from p7zip-full
            result = subprocess.run(
                ['7z', 'x', str(src), f'-o{str(tgt)}', '-y'],
                capture_output=True,
                text=True
            )
        else:
            log(f"Unsupported file type: {src.suffix}")
            return False
        
        # Check if extraction was successful (0 or 1 for unzip warnings)
        if result.returncode not in [0, 1]:
            log(f"Error extracting {src.name} (exit code: {result.returncode})")
            if result.stderr:
                log(f"  stderr: {result.stderr}")
            if result.stdout:
                log(f"  stdout: {result.stdout}")
            return False
            
        log("Extraction complete.")
        return True
        
    except FileNotFoundError as e:
        log(f"Error: Required extraction tool not found.")
        log("Install with: sudo apt install unzip unrar p7zip-full")
        return False
    except Exception as e:
        log(f"Error extracting {src.name}: {e}")
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
            log(f"Error reading {path.name} with alternate encoding: {e}")
            return {
                "name": path.name,
                "content": ""
            }
    except Exception as e:
        log(f"Error reading INI file {path.name}: {e}")
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
    log("Cleaning up temporary files...")
    archive_path = DOWNLOAD_DIR / name
    extracted_dir = EXTRACT_DIR / Path(name).stem
    try:
        if archive_path and archive_path.exists():
            os.remove(archive_path)
            log(f"Deleted {archive_path.name}")
        
        if extracted_dir and extracted_dir.exists():
            shutil.rmtree(extracted_dir)
            log(f"Deleted directory {extracted_dir.name}")       
    except OSError as e:
        log(f"Error during cleanup: {e}")

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
        log(f"An unexpected error occurred for {file['id']}: {e}") 
    finally:
        # 5. Delete zip/unzipped data (runs even if errors occurred)
        cleanup(name)
        log("-" * 40)
    return file


def batch_process_files(files: list[File]):
    """Process files asynchronously using threads."""
    import concurrent.futures
    import threading
    
    processed_files = {}
    lock = threading.Lock()  # For thread-safe dictionary updates
    
    def process_and_store(file: File):
        """Wrapper function to process a file and store results safely."""
        log(f"Processing file: {file['id']}")
        file = process_file(file) or file
        
        if file["data"]["status"] == "success":
            log(f"Processed file {file['id']} successfully with {file['data']['ini_count']} INI files.")
        else:
            log(f"Failed to process file {file['id']}: {file['data']['reason']}")
        
        # Thread-safe update of processed_files
        with lock:
            processed_files[file["id"]] = file["data"]
    
    # Use ThreadPoolExecutor to process files concurrently
    # max_workers=5 means up to 5 files can be processed simultaneously
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all file processing tasks
        futures = [executor.submit(process_and_store, file) for file in files]
        
        # Wait for all tasks to complete
        concurrent.futures.wait(futures)
        
        # Check for exceptions in any thread
        for future in futures:
            try:
                future.result()  # This will raise any exception that occurred
            except Exception as e:
                log(f"Thread execution error: {e}")
    
    return processed_files


def main2():
    """Main scraper function."""
    global is_running
    try:
        DOWNLOAD_DIR.mkdir(exist_ok=True, parents=True)
        EXTRACT_DIR.mkdir(exist_ok=True, parents=True)
        cats=get_cats(GAME)
        if not cats:
            log("No categories found.")
            return 0
        log (f"Fetched categories:")
        for cat in cats:
            log (f" - {cat['name']} (ID: {cat['id']}, Count: {cat['count']})")
        log("-" * 40)
        log(f"Starting scraping for game {GAME}...")
        for cat in cats:
            log(f"Category: {cat['name']} (ID: {cat['id']}, Count: {cat['count']})")
            mods = get_mods(cat)
            log(f"Fetched metadata for {len(mods)} mod(s).")
            for mod in mods:
                log(f"Mod : {mod}")
                files = get_files(mod)
                log(f"Mod ID {mod['id']} has {len(files)} files.")
                file_data=batch_process_files(files)
                data ={
                    "Id" : mod['id'],
                    "Category" : cat['name'],
                    "Added": mod['added'],
                    "Modified": mod['modified'],
                    "Data": file_data
                }
                post(GAME, data)
                log(f"Uploaded mod {mod['id']} data to NocoDB. Sleeping for {SLEEP_BETWEEN_DOWNLOADS} seconds...")
                time.sleep(SLEEP_BETWEEN_DOWNLOADS)
        log("Scraping completed successfully!")
    except Exception as e:
        log(f"Error in main2: {e}")
    finally:
        is_running = False

def run_main2():
    """Wrapper to run main2 with is_running flag."""
    global is_running
    is_running = True
    log("Starting scraper...")
    main2()
    log("Scraper finished.")
    is_running = False
    
if __name__ == "__main__":
    # Start log-saving thread
    log_thread = threading.Thread(target=save_logs_to_file, daemon=True)
    log_thread.start()
    log("Log-saving thread started")
    
    # Check dependencies on startup
    log("=" * 50)
    log("GameBanana Scraper - Flask Server Starting")
    log("=" * 50)
    
    if not check_and_install_dependencies():
        log("⚠ Warning: Could not verify all dependencies.")
        log("Some extractions may fail.")
    
    log("=" * 50)
    log("Flask server is ready")
    log("Use /start to begin scraping")
    log("Use /progress to view logs")
    log("Use /status to check status")
    log("=" * 50)
    
    # Start Flask app with Waitress (production-ready WSGI server)
    log("Starting Waitress server on http://0.0.0.0:5000")
    serve(app, host='0.0.0.0', port=5000, threads=4)