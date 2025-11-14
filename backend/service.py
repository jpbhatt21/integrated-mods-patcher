from flask import json
import requests
import os
import shutil
from pathlib import Path
from datetime import datetime
import time
from typing import TypedDict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import db
from sessions import get_session
from ini_parser import parse_ini_by_hash, print_parsed_ini
session = get_session()
good=[]
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

VERSIONS=[1.1,1.2,1.3,1.4,2.0,2.1,2.2,2.3,2.4,2.5,2.6,2.7]
VERSION_TIME=[1719532800, 1723680000, 1727568000, 1731542400, 1735776000, 1739404800, 1743033600, 1745884800, 1749686400, 1753315200, 1756339200,1759968000]
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



def get_recr(query_params=None,table=GAME):
    data = []
    count=0
    response = db.get('RECORDS', bearer=BEARER, table=table, query_params=query_params)
    while TASK!="Stopping":
        log(f"Fetching page {count} of NocoDB table {table}", level="info")
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
    global PROGRESS, TASK
    broken_mods = get_recr(query_params={'where': '(Data, like, err: dl/ex failed)'})
    
    broken_files=[]
    mod_to_files={}
    file_to_mod={}
    print(f"Total broken mods to fix: {len(broken_mods)}")
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
                mod_to_files[original_mod['Id']]={
                    file['id']:True for file in files
                }
                for file in files:
                    file_to_mod[file['id']]=file['parent_id']
                broken_files.extend(files)
            except Exception as e:
                log(f"Exception occurred while processing mod {original_mod['Id']}: {e}", level="error")
    PROGRESS["mods_total"] = len(mod_to_files.keys())
    PROGRESS["mods_done"] = 0
    print(f"Total broken files to fix: {len(broken_files)}, first file: {broken_files[0] if broken_files else 'N/A'}")
    fixed_files={}
    for i in range(0,len(broken_files),MAX_THREADS):
        target = broken_files[i:i+MAX_THREADS]
        PROGRESS["categories_total"] = len(target)
        PROGRESS["categories_done"] = 0
        if TASK=="Stopping":
            break
        fixed = batch_process_files(target)
        print(f"Target files batch {i//MAX_THREADS + 1}: {[file['id'] for file in target]}")
        print(f"Fixed files batch {i//MAX_THREADS + 1}: {fixed}")
        if TASK=="Stopping":
            break
        for j in target:
            if j['id'] in fixed:
                # print(f"File {j['id']} fixed data: {fixed[j['id']]}")
                if j['parent_id'] not in fixed_files:
                    fixed_files[j['parent_id']]={}
                fixed_files[j['parent_id']][j['id']] = fixed[j['id']]
            del mod_to_files[j['parent_id']][j['id']]
            # print(mod_to_files)
            if(mod_to_files[j['parent_id']]=={}):
                PROGRESS["mods_done"]+=1
                log(f"All files fixed for mod {j['parent_id']}", level="info")
                mod_data = db.get('RECORDS', bearer=BEARER, table=GAME, record=j['parent_id'])
                if not mod_data.status_code==200:
                    log(f"Failed to fetch mod {j['parent_id']} from DB for patching",level="error")
                    continue
                # print(f"Mod data fetched: {mod_data.json()}")
                mod_json = json.loads(mod_data.json().get('fields',{}).get('Data',"{}"))
                # print(f"Mod JSON data: {mod_json}")
                mod_json.update(fixed_files[j['parent_id']])
                # print(f"Updated Mod JSON data: {mod_json}")
                patch_res = db.patch('RECORDS', bearer=BEARER, table=GAME, data=[{
                    "id": j['parent_id'],
                    "fields":{
                        "Data": mod_json
                    }
                }])
                print(f"Patch response for mod {j['parent_id']}: {patch_res.status_code}")
                if patch_res.status_code == 200:
                    log(f"Successfully patched mod {j['parent_id']}", level="info")
                del fixed_files[j['parent_id']]
        if SLEEP_TIME>0:
            log(f"Sleeping for {SLEEP_TIME} seconds before next batch...", level="info")
            time.sleep(SLEEP_TIME)
  
    if TASK=="Stopping":
        TASK="Cancelled"
        log("Task cancelled by user.", level="info")
    else:    
        TASK="Finished"
    return True

def map():
    global PROGRESS, TASK
    if(not GAME == "WW"):
        log("Mapping is only supported for WW game.", level="error")
        TASK="Cancelled"
        return
    PROGRESS["categories_total"]=0
    PROGRESS["categories_done"]=0
    for mod in TABLE_DATA.values():
        if TASK=="Stopping":
            break
        log(f"Mapping mod {mod['id']}", level="info")
        res=analyze_mod(mod)
        PROGRESS["mods_done"]+=1
        PROGRESS["categories_total"] += 1
        if res:
            PROGRESS["categories_done"] += 1


    if TASK=="Stopping":
        TASK="Cancelled"
        log("Task cancelled by user.", level="info")
    else:    
        TASK="Finished"
    with open('hashes_map.json', 'w', encoding='utf-8') as f:
        json.dump(good, f, indent=4)

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
    if( TASK=="Stopping"):
        TASK="Cancelled"
        log("Task cancelled by user.", level="info")
        return
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
    
    if TASK=="Stopping":
        TASK="Cancelled"
        log("Task cancelled by user.", level="info")
    else:    
        TASK="Finished"
    pass

def start_service(task="run",game="WW", bearer="",threads=4,sleep=2):
    global TASK, GAME, BEARER, MAX_THREADS, SLEEP_TIME,PROGRESS

    if TASK not in ["Idle","Finished","Cancelled"]:
        log("A task is already running. Cannot start a new task.", level="warn")
        return False
    TASK = {"scrape":"Running","map":"Mapping","fix":"Fixing","update":"Updating"}[task]
    MAX_THREADS = threads
    SLEEP_TIME = sleep
    GAME = game
    BEARER = bearer
    PROGRESS={
    "total_files_processed": 0,
    "categories_total":0,
    "categories_done": 0,
    "mods_total": 0,
    "mods_done": 0,
    "category": {"name":"","total":0,"done":0},
    "mods": {},
    "files": {},}
    threading.Thread(target=save_logs).start()
    
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
    if TASK == "Mapping":
        threading.Thread(target=map).start()
    elif TASK == "Stopping":
        TASK="Cancelled"
        log("Task cancelled by user.", level="info")

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
    records = get_recr()
   
    TABLE_DATA = {
        record["Id"]: {
            key.lower(): value for key, value in record.items()
        } for record in records
    }
    return TABLE_DATA
    
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
    global PROGRESS, TASK
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
                if(TASK == "Fixing"):
                    PROGRESS["categories_done"] += 1
                processed_files[file["id"]] = file["data"]
            except Exception as e:
                log(f"Exception occurred while processing file {original_file['id']}: {e}", level="error")
                processed_files[original_file["id"]] = {
                    "status": "failed",
                    "reason": f"err: exception - {e}",
                    "added": original_file["added"]
                }
    return processed_files

def add_ver(a,b,c,d)->float:
    return round((a*b + c*d)/(b+d),3)

def _parse_mod_data(mod: Mod) -> Optional[list]:
    """Parse and validate mod data JSON."""
    try:
        mod["data"] = json.loads(mod["data"])
    except Exception as e:
        log(f"Error parsing mod data JSON for mod {mod['id']}: {e}", level="error")
        return None
    
    if not mod["data"]:
        log("No data to analyze.", level="info")
        return None
    
    # Convert data from dict {id:data} to array, filter by status=="success"
    return [{**v, "id": k} for k, v in mod["data"].items() if v.get("status") == "success"]


def _get_file_version(file_added: int) -> float:
    """Determine the version based on file added timestamp."""
    file_version = file_added
    for i in range(len(VERSION_TIME)):
        if file_added >= VERSION_TIME[i]:
            file_version = VERSIONS[i]
    return file_version


def _group_files_by_version(files: list) -> dict:
    """Group files by their version."""
    files_grouped_by_version = {}
    for file in files:
        file_added = file.get("added", 0)
        file_version = _get_file_version(file_added)
        
        if file_version not in files_grouped_by_version:
            files_grouped_by_version[file_version] = []
        files_grouped_by_version[file_version].append(file)
    
    return files_grouped_by_version


def _fetch_ini_files(mod_id: str) -> dict:
    """Fetch and parse INI files for a mod."""
    prefix = f"{GAME}/{mod_id}/"
    return {
        file["Id"].replace(prefix, ""): {
            "name": file["Name"],
            "data": parse_ini_by_hash(file["Data"])
        }
        for file in get_recr(query_params={'where': f"(Id, like, {prefix})"}, table="INI")
    }


def _collect_version_inis(files_grouped_by_version: dict, inis: dict) -> list:
    """Collect INI data for files in a version."""
    version_inis = []
    for file in files_grouped_by_version:
        ini_count = file.get("ini_count", 0)
        inis_data = []
        for i in range(ini_count):
            ini_id = f"{file['id']}/{i}"
            if ini_id in inis:
                inis_data.append(inis[ini_id])
        version_inis.append({
            "file_id": file['id'],
            "inis": inis_data
        })
    return version_inis


def _merge_version_inis(version_inis: list) -> dict:
    """Merge INI data for a version, handling duplicates."""
    merged_data = {}
    for file in version_inis:
        for i, ini in enumerate(file["inis"]):
            exists = [k for k in merged_data.keys() if k.startswith(ini["name"])]
            key = ini["name"]
            
            if i != 0 and exists:
                key += f'_{i}'
            
            if not exists or key not in merged_data:
                merged_data[key] = ini["data"]
            elif ini["data"] != merged_data[exists[0]]:
                merged_data[key].update(ini["data"])
    
    return merged_data


def _group_inis_by_version(files_grouped_by_version: dict, inis: dict) -> dict:
    """Group and merge INI files by version."""
    inis_grouped_by_version = {}
    for version, files in files_grouped_by_version.items():
        version_inis = _collect_version_inis(files, inis)
        inis_grouped_by_version[version] = _merge_version_inis(version_inis)
    
    return inis_grouped_by_version


def _group_inis_by_name(inis_grouped_by_version: dict) -> dict:
    """Reorganize INI data by name across versions."""
    inis_grouped_by_name = {}
    for version, files in inis_grouped_by_version.items():
        for name, ini in files.items():
            if name not in inis_grouped_by_name:
                inis_grouped_by_name[name] = {}
            inis_grouped_by_name[name][str(version)] = ini
    
    return inis_grouped_by_name


def _build_next_candidates(hash_list: list, current_obj: dict) -> dict:
    """Build next version candidates for a hash."""
    candidates = [x for x in hash_list if x["ver"] >= current_obj["ver"] and x["hash"] != current_obj["hash"]]
    next_versions = {}
    
    for candidate in candidates:
        if candidate["ver"] not in next_versions:
            next_versions[candidate["ver"]] = {}
        if candidate["hash"] not in next_versions[candidate["ver"]]:
            next_versions[candidate["ver"]][candidate["hash"]] = 0
        next_versions[candidate["ver"]][candidate["hash"]] += 1
    
    return next_versions


def _merge_hash_data(hashes: dict, hash_key: str, version: str, next_data: dict, mod_id: str) -> None:
    """Merge hash data into the hashes dictionary."""
    if hash_key in hashes:
        if version in hashes[hash_key]:
            hashes[hash_key][version]["mod"].append(mod_id)
            # Merge next version data
            for ver_key in next_data.keys():
                if ver_key in hashes[hash_key][version]["next"]:
                    for hash_id in next_data[ver_key].keys():
                        if hash_id in hashes[hash_key][version]["next"][ver_key]:
                            hashes[hash_key][version]["next"][ver_key][hash_id] += next_data[ver_key][hash_id]
                        else:
                            hashes[hash_key][version]["next"][ver_key][hash_id] = next_data[ver_key][hash_id]
                else:
                    hashes[hash_key][version]["next"][ver_key] = next_data[ver_key]
        else:
            hashes[hash_key][version] = {
                "next": next_data,
                "mod": [mod_id]
            }
    else:
        hashes[hash_key] = {
            version: {
                "next": next_data,
                "mod": [mod_id]
            }
        }


def _process_hash_mappings(inis_grouped_by_name: dict, mod_id: str) -> dict:
    """Process INI data to build hash version mappings."""
    hashes = {}
    
    for file, data in inis_grouped_by_name.items():
        keys = {}
        # Build keys mapping for each version
        for ver, ini in data.items():
            for key, hash_val in ini.items():
                if key not in keys:
                    keys[key] = {}
                if hash_val not in keys[key]:
                    keys[key][hash_val] = ver
        
        # Process each key's hash mappings
        for key, hash_versions in keys.items():
            if len(hash_versions) < 2:
                continue
            
            hash_list = [{"hash": k, "ver": v} for k, v in hash_versions.items()]
            hash_list.sort(key=lambda x: float(x["ver"]))
            
            for hash_obj in hash_list:
                next_data = _build_next_candidates(hash_list, hash_obj)
                _merge_hash_data(hashes, hash_obj["hash"], hash_obj["ver"], next_data, mod_id)
    
    return hashes


def _flatten_hash_data(hashes: dict) -> dict:
    """Flatten hash data structure for storage."""
    for hash_key in hashes.keys():
        for ver in hashes[hash_key].keys():
            hashes[hash_key][ver] = {
                **hashes[hash_key][ver]["next"],
                "mod": list(set(hashes[hash_key][ver]["mod"]))
            }
    return hashes


def _merge_existing_hash_data(existing_data: dict, new_data: dict) -> dict:
    """Merge new hash data into existing data."""
    for hash_ver in new_data.keys():
        if hash_ver in existing_data:
            for ver in new_data[hash_ver].keys():
                if ver == "mod":
                    existing_data[hash_ver][ver] = list(set(existing_data[hash_ver][ver] + new_data[hash_ver]["mod"]))
                    continue
                
                if ver in existing_data[hash_ver]:
                    for key in new_data[hash_ver][ver].keys():
                        if key in existing_data[hash_ver][ver]:
                            existing_data[hash_ver][ver][key] += new_data[hash_ver][ver][key]
                        else:
                            existing_data[hash_ver][ver][key] = new_data[hash_ver][ver][key]
                else:
                    existing_data[hash_ver][ver] = new_data[hash_ver][ver]
        else:
            existing_data[hash_ver] = new_data[hash_ver]
    
    return existing_data


def _upsert_hash(hash_key: str, hash_data: dict) -> None:
    """Insert or update hash data in the database."""
    res = db.post('GENERIC', bearer=BEARER, table="WWH", data={
        "Hash": hash_key,
        "Data": json.dumps(hash_data)
    })
    
    if res.status_code == 200:
        log(f"Upserted hash {hash_key} successfully.", level="info")
    else:
        # Try to update existing record
        res = db.get('RECORDS', bearer=BEARER, table="WWH", record=hash_key)
        if res.status_code == 200:
            record = res.json().get('fields', {})
            existing_data = json.loads(record.get('Data', '{}'))
            
            merged_data = _merge_existing_hash_data(existing_data, hash_data)
            
            patch_res = db.patch('RECORDS', bearer=BEARER, table="WWH", data=[{
                "id": hash_key,
                "fields": {
                    "Data": merged_data
                }
            }])
            
            if patch_res.status_code == 200:
                log(f"Patched existing hash {hash_key} successfully.", level="info")
            else:
                log(f"Failed to patch existing hash {hash_key}: {patch_res.status_code} - {patch_res.text}", level="error")


def analyze_mod(mod: Mod) -> bool:
    """Analyze a mod to build hash version mappings."""
    global PROGRESS, TASK, good
    
    # Parse and validate mod data
    parsed_data = _parse_mod_data(mod)
    if parsed_data is None:
        return False
    
    mod["data"] = parsed_data
    
    # Group files by version
    files_grouped_by_version = _group_files_by_version(mod["data"])
    
    if len(files_grouped_by_version) < 2:
        log("Not enough versions to map.", level="info")
        return False
    
    # Fetch and process INI files
    inis = _fetch_ini_files(mod['id'])
    inis_grouped_by_version = _group_inis_by_version(files_grouped_by_version, inis)
    inis_grouped_by_name = _group_inis_by_name(inis_grouped_by_version)
    
    # Build hash mappings
    hashes = _process_hash_mappings(inis_grouped_by_name, mod['id'])
    
    # Update progress
    PROGRESS["total_files_processed"] += len(inis)
    
    # Flatten hash data
    hashes = _flatten_hash_data(hashes)
    good.append(hashes)
    
    # Upsert hash data to database
    for hash_key, hash_obj in hashes.items():
        if TASK == "Stopping":
            break
        _upsert_hash(hash_key, hash_obj)
    
    if TASK == "Stopping":
        return False
    
    # Save to temp file for debugging
    with open("temp.json", "w", encoding="utf-8") as f:
        json.dump(hashes, f, ensure_ascii=False, indent=4)
    
    return True