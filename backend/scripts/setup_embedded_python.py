import os
import sys
import argparse
import urllib.request
import zipfile
import shutil
import subprocess
from pathlib import Path

def get_backend_dir():
    # Attempt to find backend directory based on current working dir
    cwd = Path.cwd()
    if (cwd / "backend").is_dir():
        return cwd / "backend"
    elif cwd.name == "backend":
        return cwd
    # Maybe run from backend/scripts
    if cwd.name == "scripts" and cwd.parent.name == "backend":
        return cwd.parent
    
    # Fallback: assume script is in backend/scripts
    return Path(__file__).resolve().parent.parent

def setup_embedded_python(args):
    backend_dir = get_backend_dir()
    dist_dir = backend_dir / "dist"
    python_dir = dist_dir / "python"
    
    print(f"Backend directory: {backend_dir}")
    print(f"Dist directory: {dist_dir}")
    
    if not args.no_clean and dist_dir.exists():
        print(f"Cleaning dist directory: {dist_dir}")
        shutil.rmtree(dist_dir)
        
    dist_dir.mkdir(parents=True, exist_ok=True)
    python_dir.mkdir(parents=True, exist_ok=True)
    
    version = args.python_version
    try:
        major, minor, _ = version.split('.')
    except ValueError:
        print("Error: Invalid python version format. Expected format: MAJOR.MINOR.PATCH (e.g., 3.11.9)")
        sys.exit(1)
        
    zip_url = f"https://www.python.org/ftp/python/{version}/python-{version}-embed-amd64.zip"
    zip_path = dist_dir / f"python-{version}-embed.zip"
    
    print(f"Downloading embedded Python {version} from {zip_url}...")
    try:
        urllib.request.urlretrieve(zip_url, zip_path)
    except Exception as e:
        print(f"Failed to download Python: {e}")
        sys.exit(1)
        
    print(f"Extracting to {python_dir}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(python_dir)
        
    print("Cleaning up zip file...")
    zip_path.unlink()

    # Add the backend root (the parent of python/) to the module search path.
    # Embedded Python ignores PYTHONPATH and cwd for imports — only entries in
    # the ._pth file count — so without this, `from llm import ...` inside
    # server.py fails even though llm.py sits right next to it.
    pth_file = python_dir / f"python{major}{minor}._pth"
    if pth_file.exists():
        print(f"Adding backend root to module search path in {pth_file.name}...")
        with open(pth_file, 'r') as f:
            lines = f.readlines()
        if not any(line.strip() == ".." for line in lines):
            # Insert right after the zip entry so backend source is found early.
            insert_at = 1 if lines else 0
            lines.insert(insert_at, "..\n")
            with open(pth_file, 'w') as f:
                f.writelines(lines)

    # Uncomment import site in pythonXX._pth
    pth_file = python_dir / f"python{major}{minor}._pth"
    if pth_file.exists():
        print(f"Enabling site-packages in {pth_file.name}...")
        with open(pth_file, 'r') as f:
            lines = f.readlines()
        with open(pth_file, 'w') as f:
            for line in lines:
                if line.strip() == "#import site":
                    f.write("import site\n")
                else:
                    f.write(line)
    else:
        print(f"Warning: {pth_file.name} not found. site-packages may not work.")
        
    # Download get-pip.py
    get_pip_url = "https://bootstrap.pypa.io/get-pip.py"
    get_pip_path = dist_dir / "get-pip.py"
    
    print(f"Downloading get-pip.py from {get_pip_url}...")
    try:
        urllib.request.urlretrieve(get_pip_url, get_pip_path)
    except Exception as e:
        print(f"Failed to download get-pip.py: {e}")
        sys.exit(1)
        
    python_exe = python_dir / "python.exe"
    
    print("Installing pip...")
    try:
        subprocess.run([str(python_exe), str(get_pip_path)], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Failed to install pip: {e}")
        sys.exit(1)
        
    print("Cleaning up get-pip.py...")
    get_pip_path.unlink()
    
    # Install core dependencies
    requirements_txt = backend_dir / "requirements.txt"
    if requirements_txt.exists():
        print(f"Installing core dependencies from {requirements_txt}...")
        try:
            subprocess.run([str(python_exe), "-m", "pip", "install", "-r", str(requirements_txt)], check=True)
        except subprocess.CalledProcessError as e:
            print(f"Failed to install dependencies: {e}")
            sys.exit(1)
    else:
        print(f"Warning: {requirements_txt} not found. Skipping dependency installation.")
        
    # Copy backend source files — all top-level modules, so new files
    # (e.g. tools/) ship without editing this list.
    files_to_copy = [p.name for p in backend_dir.glob("*.py")]
    files_to_copy += ["requirements.txt", "requirements-optional.txt"]
    
    print(f"Copying source files to {dist_dir}...")
    for file_name in files_to_copy:
        src = backend_dir / file_name
        dst = dist_dir / file_name
        if src.exists():
            print(f"Copying {file_name}...")
            shutil.copy2(src, dst)
        else:
            print(f"Warning: Source file {file_name} not found in {backend_dir}")

    # Copy local packages (subdirectories with .py modules).
    for dir_name in ["tools"]:
        src = backend_dir / dir_name
        dst = dist_dir / dir_name
        if src.exists():
            print(f"Copying {dir_name}/...")
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"), dirs_exist_ok=True)
        else:
            print(f"Warning: Package directory {dir_name} not found in {backend_dir}")
            
    print("Embedded Python setup complete!")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Setup embedded Python for Salieri AI backend")
    parser.add_argument('--no-clean', action='store_true', help="Do not clean the dist directory before starting")
    parser.add_argument('--python-version', default='3.11.9', help="Python version to download (default: 3.11.9)")
    args = parser.parse_args()
    setup_embedded_python(args)
