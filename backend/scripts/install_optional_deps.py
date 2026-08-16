import os
import sys
import argparse
import subprocess
from pathlib import Path

def find_python_exe(provided_dir):
    if provided_dir:
        python_exe = Path(provided_dir) / "python.exe"
        if python_exe.exists():
            return python_exe
        print(f"Error: python.exe not found in provided directory {provided_dir}")
        sys.exit(1)
        
    # Check common locations relative to script
    script_dir = Path(__file__).resolve().parent
    
    # If in backend/scripts, look in ../dist/python/python.exe
    candidate_1 = script_dir.parent / "dist" / "python" / "python.exe"
    
    # If in an installed app, maybe ../python/python.exe or similar
    candidate_2 = script_dir.parent / "python" / "python.exe"
    
    # Also check backend/dist/python/python.exe if we're in root
    candidate_3 = Path.cwd() / "backend" / "dist" / "python" / "python.exe"
    
    for candidate in [candidate_1, candidate_2, candidate_3]:
        if candidate.exists():
            return candidate
            
    return None

def install_deps(args):
    python_exe = find_python_exe(args.python_dir)
    if not python_exe:
        print("Error: Could not locate embedded python.exe.")
        print("Please specify its location with --python-dir.")
        sys.exit(1)
        
    print(f"Using embedded Python at: {python_exe}")
    
    if args.packages:
        print(f"Installing specific packages: {', '.join(args.packages)}")
        cmd = [str(python_exe), "-m", "pip", "install"] + args.packages
    else:
        # Need to find requirements-optional.txt
        script_dir = Path(__file__).resolve().parent
        req_file = script_dir.parent / "requirements-optional.txt"
        
        if not req_file.exists():
            # Check in dist folder
            req_file = script_dir.parent / "dist" / "requirements-optional.txt"
            
        if not req_file.exists():
            # Check cwd
            req_file = Path.cwd() / "requirements-optional.txt"
            
        if not req_file.exists():
            # Check backend
            req_file = Path.cwd() / "backend" / "requirements-optional.txt"
            
        if not req_file.exists():
            print("Error: requirements-optional.txt not found.")
            print("Please run from the project root or use --packages.")
            sys.exit(1)
            
        print(f"Installing dependencies from: {req_file}")
        cmd = [str(python_exe), "-m", "pip", "install", "-r", str(req_file)]
        
    print("Running installation...")
    try:
        subprocess.run(cmd, check=True)
        print("Installation completed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"\nError: Package installation failed (exit code {e.returncode}).")
        print("This could be due to missing system dependencies like Visual C++ Build Tools")
        print("which are required by some packages (e.g., PyAudio).")
        sys.exit(1)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Install optional dependencies for Salieri AI backend")
    parser.add_argument('--python-dir', help="Path to the directory containing embedded python.exe")
    parser.add_argument('--packages', nargs='+', help="Specific packages to install instead of using requirements-optional.txt")
    args = parser.parse_args()
    install_deps(args)
