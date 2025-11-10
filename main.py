import requests
import zipfile
import rarfile
import py7zr
import configparser
import os
import shutil
from pathlib import Path
import time

# --- Configuration ---

# A directory to store downloaded archives
DOWNLOAD_DIR = Path("download_temp")

# A directory to extract archive contents into
EXTRACT_DIR = Path("extract_temp")

# Sample category taoqi: https://gamebanana.com/apiv11/Mod/Index?_nPerpage=28&_aFilters%5BGeneric_Category%5D=30254&_sSort=Generic_Oldest&_nPage=1
# {
#     "_aMetadata": {
#         "_nRecordCount": 28,
#         "_bIsComplete": true,
#         "_nPerpage": 28
#     },
#     "_aRecords": [{
#             "_idRow": 524321,
#             "_sModelName": "Mod",
#             "_sSingularTitle": "Mod",
#             "_sProfileUrl": "https:\/\/gamebanana.com\/mods\/524321",
#             "_tsDateAdded": 1719519057,
#             "_tsDateModified": 1756576086,
#             "_bHasFiles": True,
#             "_tsDateUpdated": 1756576129,
#              ...
#         },...]
# }


# Sample mod profile: https://gamebanana.com/apiv11/Mod/524321/ProfilePage
# {
#     "_idRow": 524321,
#     "_nStatus": "0",
#     "_bIsPrivate": false,
#     "_bAccessorIsSubmitter": false,
#     "_bIsTrashed": false,
#     "_bIsWithheld": false,
#     "_sName": "Taoqi Skimpy (WWMI)",
#     "_sCommentsMode": "open",
#     "_tsDateModified": 1756576086,
#     "_tsDateAdded": 1719519057,
#     "_aFiles": [
#     {
#       "_idRow": 1508115,
#       "_sFile": "taoqiskimpy1_4.zip",
#       "_nFilesize": 40581687,
#       "_tsDateAdded": 1756576072,
#       "_nDownloadCount": 888,
#       "_sDownloadUrl": "https://gamebanana.com/dl/1508115",
#       "_sMd5Checksum": "20ac6cd483c10ffc764190e870638fc6",
#       "_sAnalysisState": "done",
#       "_sAnalysisResult": "ok",
#       "_sAnalysisResultVerbose": "File passed preliminary analysis",
#       "_sAvState": "done",
#       "_sAvResult": "clean",
#       "_bIsArchived": false,
#       "_bHasContents": true
#     },],
#     "_aArchivedFiles": [
#         {
#             "_idRow": 1555106,
#             "_sFile": "integrated_mod_manager_imm__210_x64-setupexe.zip",
#             "_nFilesize": 19858593,
#             "_tsDateAdded": 1762351571,
#             "_nDownloadCount": 260,
#             "_sDownloadUrl": "https:\/\/gamebanana.com\/dl\/1555106",
#             "_sMd5Checksum": "b919f9ef721ee7ac3e7632ea67218a71",
#             "_sAnalysisState": "done",
#             "_sAnalysisResult": "ok",
#             "_sAnalysisResultVerbose": "File passed preliminary analysis",
#             "_sAvState": "done",
#             "_sAvResult": "clean",
#             "_bIsArchived": true,
#             "_bHasContents": true,
#             "_sVersion": "2.1.0",
#             "_sDescription": "IMM v2.1.0 Setup",
#             "_aAnalysisWarnings": {
#                 "contains_exe": [
#                     "Integrated Mod Manager (IMM)_2.1.0_x64-setup.exe"
#                 ]
#             }
#         },]
 
# }
# List of URLs to download from
FILE_URLS = [
    "https://gamebanana.com/dl/1508115"
    # Add all your URLs here
]

# --- Helper Functions ---

def download_file(url: str, save_path: Path) -> bool:
    """Downloads a file from a URL to a specific path."""
    print(f"Downloading {url}...")
    try:
        response = requests.get(url, stream=True, timeout=30)
        # Check for HTTP errors (e.g., 404 Not Found)
        response.raise_for_status() 
        
        with open(save_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        print("Download complete.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error downloading {url}: {e}")
        return False

def extract_file(archive_path: Path, extract_to: Path) -> bool:
    """Extracts a .zip, .rar, or .7z file to a target directory."""
    print(f"Extracting {archive_path.name}...")
    
    # Ensure the extraction directory exists
    extract_to.mkdir(exist_ok=True, parents=True)
    
    try:
        if archive_path.suffix == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zf:
                zf.extractall(extract_to)
        elif archive_path.suffix == '.rar':
            # This requires the 'unrar' command-line utility
            with rarfile.RarFile(archive_path, 'r') as rf:
                rf.extractall(extract_to)
        elif archive_path.suffix == '.7z':
            with py7zr.SevenZipFile(archive_path, 'r') as szf:
                szf.extractall(extract_to)
        else:
            print(f"Unsupported file type: {archive_path.suffix}")
            return 0
            
        print("Extraction complete.")
        return 1
    except zipfile.BadZipFile:
        print(f"Error: {archive_path.name} is a corrupted zip file.")
    except rarfile.BadRarFile:
        print(f"Error: {archive_path.name} is a corrupted rar file.")
    except rarfile.RarCannotExec:
        print("Error: 'unrar' command not found. See install commands in __main__.")
    except py7zr.Bad7zFile:
        print(f"Error: {archive_path.name} is a corrupted 7z file.")
    except Exception as e:
        print(f"Error extracting {archive_path.name}: {e}")
    
    return 0

def process_ini_file(ini_path: Path):
    """Loads and processes a single .ini file."""
    print(f"  -> Processing {ini_path.name}...")
    try:
        config = configparser.ConfigParser(interpolation=None)
        # Read with UTF-8 encoding to handle potential special characters
        config.read(ini_path, encoding='utf-8')

        # --- YOUR INI PROCESSING LOGIC GOES HERE ---
        
        # Example: Read a value
        if 'Settings' in config and 'SomeKey' in config['Settings']:
            value = config['Settings']['SomeKey']
            print(f"    Found [Settings][SomeKey]: {value}")

        # Example: Iterate over all sections and keys
        # for section in config.sections():
        #     print(f"    Section: [{section}]")
        #     for key in config[section]:
        #         print(f"      {key} = {config[section][key]}")
                
        # --- END OF YOUR LOGIC ---

    except configparser.Error as e:
        print(f"Error parsing INI file {ini_path}: {e}")
    except Exception as e:
        print(f"Error processing {ini_path}: {e}")

def cleanup(archive_path: Path, extracted_dir: Path):
    """Deletes the specified file and directory."""
    print("Cleaning up temporary files...")
    try:
        if archive_path and archive_path.exists():
            os.remove(archive_path)
            print(f"Deleted {archive_path.name}")
        
        if extracted_dir and extracted_dir.exists():
            shutil.rmtree(extracted_dir)
            print(f"Deleted directory {extracted_dir.name}")
            
    except OSError as e:
        print(f"Error during cleanup: {e}")

# --- Main Execution ---

def main(FILE_URLS=FILE_URLS):
    # Ensure base directories exist
    DOWNLOAD_DIR.mkdir(exist_ok=True)
    EXTRACT_DIR.mkdir(exist_ok=True)
    success_count = 0
    
    print(f"Starting process. URLs to process: {len(FILE_URLS)}")
    print("-" * 40)

    for url in FILE_URLS:
        download_path = None
        specific_extract_dir = None
        
        try:
            # Get a file name from the URL
            file_name = url.split('/')[-1]
            if not file_name:
                print(f"Skipping invalid URL: {url}")
                continue
                
            download_path = DOWNLOAD_DIR / file_name
            
            # Create a unique extraction folder for this archive
            # e.g., "archive1.zip" extracts to "extract_temp/archive1"
            extract_folder_name = Path(file_name).stem
            specific_extract_dir = EXTRACT_DIR / extract_folder_name

            # 1. Download
            if not download_file(url, download_path):
                continue  # Skip to next URL if download fails

            # 2. Extract
            if extract_file(download_path, specific_extract_dir) == 0:
                continue  # Skip to next URL if extraction fails
            success_count += 1

            # 3. Search for .ini files
            # .rglob("*.ini") searches recursively (in all subfolders)
            print(f"Searching for .ini files in {specific_extract_dir}...")
            ini_files = list(specific_extract_dir.rglob("*.ini"))
            
            if not ini_files:
                print("No .ini files found.")
            else:
                print(f"Found {len(ini_files)} .ini file(s).")
                # 4. Process .ini files
                for ini_path in ini_files:
                    process_ini_file(ini_path)

        except Exception as e:
            print(f"An unexpected error occurred for {url}: {e}")
        
        finally:
            # 5. Delete zip/unzipped data (runs even if errors occurred)
            cleanup(download_path, specific_extract_dir)
            print("-" * 40)
            time.sleep(1) # Optional: short pause between downloads

    print("All tasks complete.")
    return success_count

if __name__ == "__main__":
    # 1. Install Python libraries:
    # pip install requests rarfile py7zr
    #
    # 2. Install the 'unrar' system utility:
    #
    #    For Windows:
    #    Install unrar and add 'unrar' to system path if it's not already there
    #    This is often needed on Windows if 'unrar' isn't in PATH
    #    rarfile.UNRAR_TOOL = r"C:\Program Files\WinRAR\UnRAR.exe"
    #
    #    For Debian/Ubuntu-based systems (like Mint, Pop!_OS):
    #    sudo apt update
    #    sudo apt install unrar
    #
    #    For Fedora-based systems:
    #    sudo dnf install unrar
    #
    #    For Arch-based systems (like Manjaro):
    #    sudo pacman -S unrar
    #
    # -------------------------------------------------------------
    print("Initiating test run...")
    success_count = main(
      [ "https://getsamplefiles.com/download/zip/sample-1.zip",
        "https://getsamplefiles.com/download/rar/sample-1.rar",
        "https://getsamplefiles.com/download/7z/sample-1.7z"]
    )
    if(success_count == 3):
        print("All test files extracted successfully!")
    else:
        print(f"Unexpected result: {success_count}/3 files extracted successfully.")
        quit(1)
    main()