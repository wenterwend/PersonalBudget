#!/usr/bin/env python3
import os
import sys
import shutil
import urllib.request
import zipfile
import subprocess
import hashlib

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(ROOT_DIR, "dist")
PKG_DIR = os.path.join(DIST_DIR, "BudgetApp-Windows-x64")
CACHE_DIR = os.path.join(ROOT_DIR, ".build_cache")
WHL_CACHE = os.path.join(CACHE_DIR, "win_whls")
PYTHON_BIN = sys.executable

PYTHON_EMBED_URL = "https://www.python.org/ftp/python/3.12.8/python-3.12.8-embed-amd64.zip"
PYTHON_EMBED_ZIP = os.path.join(CACHE_DIR, "python-3.12.8-embed-amd64.zip")

def get_file_hash(filepath):
    if not os.path.exists(filepath):
        return None
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def ensure_dirs():
    os.makedirs(DIST_DIR, exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(WHL_CACHE, exist_ok=True)
    if os.path.exists(PKG_DIR):
        shutil.rmtree(PKG_DIR)
    os.makedirs(PKG_DIR, exist_ok=True)

def download_python_embed():
    if not os.path.exists(PYTHON_EMBED_ZIP) or os.path.getsize(PYTHON_EMBED_ZIP) == 0:
        print(f"Downloading Windows embedded Python from {PYTHON_EMBED_URL}...")
        urllib.request.urlretrieve(PYTHON_EMBED_URL, PYTHON_EMBED_ZIP)
    else:
        print("Using cached Windows embedded Python archive.")

    target_py_dir = os.path.join(PKG_DIR, "python")
    os.makedirs(target_py_dir, exist_ok=True)
    print("Extracting embedded Python...")
    with zipfile.ZipFile(PYTHON_EMBED_ZIP, 'r') as zip_ref:
        zip_ref.extractall(target_py_dir)

    # Enable import site and configure search path in python312._pth
    pth_file = os.path.join(target_py_dir, "python312._pth")
    if os.path.exists(pth_file):
        with open(pth_file, "r") as f:
            lines = f.readlines()
        new_lines = []
        for line in lines:
            if line.strip() == "#import site":
                new_lines.append("import site\n")
            else:
                new_lines.append(line)
        # Ensure Lib/site-packages, . and .. are included
        extra_paths = ["Lib\\site-packages\n", "..\n"]
        for ep in extra_paths:
            if ep not in new_lines:
                new_lines.append(ep)
        with open(pth_file, "w") as f:
            f.writelines(new_lines)

def download_and_install_wheels():
    packages = [
        "fastapi==0.141.1",
        "uvicorn==0.52.4",
        "sqlmodel==0.0.42",
        "SQLAlchemy==2.0.52",
        "scikit-learn==1.9.1",
        "scipy==1.18.1",
        "numpy==2.5.3",
        "python-multipart==0.0.32",
        "python-dotenv==1.2.3",
        "joblib==1.6.0",
        "pydantic==2.13.5",
        "pydantic_core==2.46.5",
        "starlette==1.6.0",
        "anyio==4.15.1",
        "typing-extensions==4.16.0",
        "typing-inspection==0.4.4",
        "annotated-types==0.8.0",
        "annotated-doc==0.0.5",
        "click==8.5.0",
        "h11==0.16.0",
        "idna==3.19",
        "threadpoolctl==3.6.0",
        "narwhals==2.26.0",
        "cloudpickle==3.1.2",
        "greenlet==3.5.5",
    ]

    print("Downloading Windows x64 binary wheels...")
    cmd = [
        PYTHON_BIN, "-m", "pip", "download",
        "--dest", WHL_CACHE,
        "--only-binary=:all:",
        "--platform", "win_amd64",
        "--python-version", "312",
        "--implementation", "cp",
        "--abi", "cp312"
    ] + packages
    subprocess.check_call(cmd)

    target_site_packages = os.path.join(PKG_DIR, "python", "Lib", "site-packages")
    os.makedirs(target_site_packages, exist_ok=True)

    print("Extracting wheels into standalone site-packages...")
    whl_files = [os.path.join(WHL_CACHE, f) for f in os.listdir(WHL_CACHE) if f.endswith(".whl")]
    for whl in whl_files:
        with zipfile.ZipFile(whl, "r") as zf:
            zf.extractall(target_site_packages)
    print(f"Extracted {len(whl_files)} wheels into site-packages.")


def copy_application_code():
    print("Copying backend and static frontend...")
    # 1. Frontend
    frontend_build_src = os.path.join(ROOT_DIR, "src", "frontend", "build")
    frontend_build_dest = os.path.join(PKG_DIR, "frontend_build")
    if not os.path.exists(frontend_build_src):
        raise RuntimeError("src/frontend/build does not exist! Please run npm run build first.")
    shutil.copytree(frontend_build_src, frontend_build_dest)

    # 2. Backend
    src_dest = os.path.join(PKG_DIR, "src")
    os.makedirs(src_dest, exist_ok=True)
    shutil.copy2(os.path.join(ROOT_DIR, "src", "__init__.py"), os.path.join(src_dest, "__init__.py"))
    shutil.copytree(os.path.join(ROOT_DIR, "src", "backend"), os.path.join(src_dest, "backend"),
                    ignore=shutil.ignore_patterns("__pycache__", "tests"))

def create_clean_database():
    print("Generating a fresh, clean SQLite database...")
    clean_db_path = os.path.join(PKG_DIR, "budget.db")
    if os.path.exists(clean_db_path):
        os.remove(clean_db_path)

    # Run Python in a subprocess with explicit DATABASE_URL pointing to the new clean db
    code = f"""
import os
os.environ["DATABASE_URL"] = "sqlite:///{clean_db_path}"
import src.backend.models
from src.backend.database import init_db
init_db()
print("Clean DB initialized successfully.")
"""
    env = os.environ.copy()
    env["PYTHONPATH"] = ROOT_DIR
    subprocess.check_call([PYTHON_BIN, "-c", code], env=env)
    print(f"Clean database created at {clean_db_path} ({os.path.getsize(clean_db_path)} bytes).")

def create_launchers_and_entrypoint():
    print("Writing entrypoint script and Windows batch launchers...")
    
    # 1. run_app.py
    run_app_content = """import os
import sys
import time
import webbrowser
import threading
import uvicorn

# Ensure current directory is on sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set clean default database path to local folder if not explicitly configured
if "DATABASE_URL" not in os.environ:
    local_db = os.path.join(BASE_DIR, "budget.db")
    os.environ["DATABASE_URL"] = f"sqlite:///{local_db}"

def open_browser():
    time.sleep(1.2)
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

def main():
    threading.Thread(target=open_browser, daemon=True).start()
    
    from src.backend.main import app
    print("==================================================================")
    print("      Personal Budget & Finance Application is Running!          ")
    print("      URL:      http://127.0.0.1:8000                            ")
    print("      Database: " + os.environ.get("DATABASE_URL", ""))
    print("==================================================================")
    print("Close this console window when you are done to stop the app.")
    print()
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
"""
    with open(os.path.join(PKG_DIR, "run_app.py"), "w") as f:
        f.write(run_app_content)

    # 2. Start Budget App.bat
    bat_content = """@echo off
title Personal Budget & Finance App
cd /d "%~dp0"
echo ==================================================================
echo         Personal Budget & Finance Application
echo ==================================================================
echo.
echo Starting application server...
echo Your default web browser will open automatically at:
echo http://localhost:8000
echo.
echo (Keep this window open while using the app. Close it to stop.)
echo ==================================================================
echo.
python\\python.exe run_app.py
pause
"""
    with open(os.path.join(PKG_DIR, "Start Budget App.bat"), "w", newline="\r\n") as f:
        f.write(bat_content)

    # 3. Start Budget App (Silent).vbs
    vbs_content = """Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
WshShell.Run "python\\pythonw.exe run_app.py", 0, False
"""
    with open(os.path.join(PKG_DIR, "Start Budget App (Silent).vbs"), "w", newline="\r\n") as f:
        f.write(vbs_content)

    # 4. Stop Budget App.bat
    stop_bat = """@echo off
title Stop Budget App
echo Stopping any running Budget App instances...
taskkill /f /im python.exe /fi "WINDOWTITLE eq Personal Budget*" 2>nul
taskkill /f /im pythonw.exe 2>nul
echo Done. Application stopped.
timeout /t 2 /nobreak >nul
"""
    with open(os.path.join(PKG_DIR, "Stop Budget App.bat"), "w", newline="\r\n") as f:
        f.write(stop_bat)

    # 5. README.txt
    readme_content = """==================================================================
           Personal Budget & Household Finance App
==================================================================

STANDALONE PORTABLE WINDOWS EDITION
No installation, Python, Node.js, or administrative rights required.

HOW TO RUN:
1. Double-click "Start Budget App.bat".
2. Your default web browser will automatically open to:
   http://localhost:8000
3. The app is completely self-contained and stores your financial data
   in the local "budget.db" file in this folder.
4. When finished, simply close the console window.

ALTERNATIVE (SILENT BACKGROUND MODE):
- Double-click "Start Budget App (Silent).vbs" to launch without an open console window.
- When done, double-click "Stop Budget App.bat" to stop the server.

DATA & BACKUPS:
- Your clean database starts with zero accounts and zero transactions.
- All default categories (Income, Living Expenses, Lifestyle) are initialized.
- Backups are stored in this same folder.
==================================================================
"""
    with open(os.path.join(PKG_DIR, "README.txt"), "w", newline="\r\n") as f:
        f.write(readme_content)

def create_zip_archive():
    zip_dest = os.path.join(DIST_DIR, "BudgetApp-Windows-x64.zip")
    if os.path.exists(zip_dest):
        os.remove(zip_dest)
    print(f"Creating standalone archive: {zip_dest}...")
    shutil.make_archive(os.path.join(DIST_DIR, "BudgetApp-Windows-x64"), "zip", DIST_DIR, "BudgetApp-Windows-x64")
    print(f"Archive created! Size: {os.path.getsize(zip_dest) / (1024*1024):.2f} MB")

def main():
    dev_db_path = os.path.join(ROOT_DIR, "budget.db")
    initial_dev_db_hash = get_file_hash(dev_db_path)
    print(f"Dev database SHA256 before packaging: {initial_dev_db_hash}")

    ensure_dirs()
    download_python_embed()
    download_and_install_wheels()
    copy_application_code()
    create_clean_database()
    create_launchers_and_entrypoint()
    create_zip_archive()

    final_dev_db_hash = get_file_hash(dev_db_path)
    print(f"Dev database SHA256 after packaging:  {final_dev_db_hash}")
    if initial_dev_db_hash != final_dev_db_hash:
        raise RuntimeError("CRITICAL ERROR: Dev database was modified during packaging!")
    print("\nSUCCESS: Windows standalone deployable package created successfully with zero impact on dev database!")

if __name__ == "__main__":
    main()
