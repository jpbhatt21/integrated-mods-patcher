import subprocess
import shutil
import sys
import os
from pathlib import Path
import threading
# --- Dependency Check ---
def check_and_install_dependencies() -> bool:
    """Checks if required tools are installed and installs them if missing."""
    import subprocess
    
    print("Checking for required dependencies...")
    
    all_installed = True
    
    # Check if Node.js/npm is available
    try:
        result = subprocess.run(['node', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ Node.js is already installed: {result.stdout.strip()}")
        else:
            raise Exception("Node.js not found")
    except Exception:
        print("⚠ Node.js/npm not found. Installing...")
        all_installed = False
        try:
            # Install Node.js and npm using NodeSource repository
            print("Adding NodeSource repository...")
            subprocess.run("curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash -", shell=True, check=True)
            print("Installing Node.js and npm...")
            subprocess.run("sudo apt-get install -y nodejs", shell=True, check=True)
            print("✓ Node.js and npm installed successfully!")
        except subprocess.CalledProcessError as e:
            print(f"✗ Error installing Node.js: {e}")
            return False
    
    # Check if npm is available (should be installed with Node.js)
    try:
        result = subprocess.run(['npm', '--version'], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ npm is already installed: {result.stdout.strip()}")
    except Exception:
        print("✗ npm not found even after Node.js installation")
        return False
    
    # Check if unrar is available
    try:
        result = subprocess.run(['which', 'unrar'], capture_output=True, text=True)
        if result.stdout.strip():
            print("✓ unrar is already installed")
            return all_installed
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

def run_init():
    """Run npm install in the frontend folder"""
    print("Started - Initializing project")
    
    # Check and install dependencies
    if  not check_and_install_dependencies():
        print("Dependency installation failed. Exiting initialization.")
        return

    root_dir = Path(__file__).parent
    frontend_dir = root_dir / "frontend"
    
    print("\n[1/1] Running npm install in frontend folder...")
    try:
        subprocess.run(
            ["npm", "install"],
            cwd=frontend_dir,
            shell=True,
            check=True
        )
        print("✓ Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ npm install failed: {e}")
        return
    
    print("\n✓ Initialization complete!")

def run_dev():
    """Run npm run dev in frontend and python app.py in backend concurrently"""
    print("Started - Development mode")
    
    root_dir = Path(__file__).parent
    frontend_dir = root_dir / "frontend"
    backend_dir = root_dir / "backend"
    
    def run_frontend():
        print("\n[Frontend] Starting npm run dev...")
        try:
            subprocess.run(
                ["npm", "run", "dev"],
                cwd=frontend_dir,
                shell=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"✗ [Frontend] Failed: {e}")
        except KeyboardInterrupt:
            pass
    
    def run_backend():
        print("\n[Backend] Starting python app.py...")
        try:
            subprocess.run(
                ["python", "app.py"],
                cwd=backend_dir,
                shell=True,
                check=True
            )
        except subprocess.CalledProcessError as e:
            print(f"✗ [Backend] Failed: {e}")
        except KeyboardInterrupt:
            pass
    
    # Start both processes in separate threads
    frontend_thread = threading.Thread(target=run_frontend)
    backend_thread = threading.Thread(target=run_backend)
    
    frontend_thread.start()
    backend_thread.start()
    
    try:
        frontend_thread.join()
        backend_thread.join()
    except KeyboardInterrupt:
        print("\n✓ Development servers stopped by user")

def run_start():
    """Build frontend and start production server"""
    print("Started - Production mode")
    
    # Define paths
    root_dir = Path(__file__).parent
    frontend_dir = root_dir / "frontend"
    backend_dir = root_dir / "backend"
    backend_dist_dir = backend_dir / "dist"
    dist_dir = frontend_dir / "dist"
    
    # Step 1: Run npm run build in frontend folder
    print("\n[1/4] Running npm run build in frontend folder...")
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            shell=True,
            check=True,
            capture_output=True,
            text=True
        )
        print("✓ Build completed successfully")
    except subprocess.CalledProcessError as e:
        print(f"✗ Build failed: {e}")
        print(f"Error output: {e.stderr}")
        return
    
    # Step 2: Check if dist folder exists
    if not dist_dir.exists():
        print(f"✗ Error: dist folder not found at {dist_dir}")
        return
    
    # Step 3: Copy files from frontend/dist to backend
    print("\n[2/4] Copying files from frontend/dist to backend...")
    try:
        # Create backend directory if it doesn't exist
        backend_dist_dir.mkdir(exist_ok=True)
        
        # Copy all files from dist to backend
        for item in dist_dir.iterdir():
            dest = backend_dist_dir / item.name
            if item.is_file():
                shutil.copy2(item, dest)
                print(f"  Copied: {item.name}")
            elif item.is_dir():
                if dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(item, dest)
                print(f"  Copied directory: {item.name}")
        
        print("✓ Files copied successfully")
    except Exception as e:
        print(f"✗ Error copying files: {e}")
        return
    
    # Step 4: Rename HTML file to index.html in backend
    print("\n[3/4] Renaming HTML file to index.html...")
    try:
        html_files = list(backend_dir.glob("*.html"))
        if html_files:
            for html_file in html_files:
                if html_file.name != "index.html":
                    new_path = backend_dir / "index.html"
                    if new_path.exists():
                        new_path.unlink()
                    html_file.rename(new_path)
                    print(f"  Renamed: {html_file.name} -> index.html")
            print("✓ HTML file renamed successfully")
        else:
            print("  Note: No HTML file found to rename (may already be index.html)")
    except Exception as e:
        print(f"✗ Error renaming HTML file: {e}")
        return
    
    # Step 5: Run python app.py in backend
    print("\n[4/4] Running python app.py in backend...")
    try:
        # Run app.py (this will block until the server is stopped)
        subprocess.run(
            ["python", "app.py"],
            cwd=backend_dir,
            shell=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to run app.py: {e}")
    except KeyboardInterrupt:
        print("\n✓ Server stopped by user")

def print_usage():
    """Print usage information"""
    print("Usage: python server.py <command>")
    print("\nCommands:")
    print("  init   - Install frontend dependencies (npm install)")
    print("  dev    - Run development servers (frontend + backend)")
    print("  start  - Build and run production server")

def main():
    if len(sys.argv) < 2:
        print("✗ Error: Missing command argument")
        print_usage()
        sys.exit(1)
    
    command = sys.argv[1].lower()
    
    if command == "init":
        run_init()
    elif command == "dev":
        run_dev()
    elif command == "start":
        run_start()
    else:
        print(f"✗ Error: Unknown command '{command}'")
        print_usage()
        sys.exit(1)

if __name__ == "__main__":
    main()
