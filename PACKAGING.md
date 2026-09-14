# Packaging Budget App into a Standalone Executable

This guide explains how to package the **FastAPI + SvelteKit** Budget Application into a single standalone executable file (`.exe` for Windows or binary for Linux) that runs on systems without requiring Python or Node.js to be pre-installed.

---

## Prerequisites

1. Build the SvelteKit frontend into static HTML/CSS/JS files:
   ```bash
   cd src/frontend
   npm install -D @sveltejs/adapter-static
   ```

2. Configure `src/frontend/svelte.config.js`:
   ```javascript
   import adapter from '@sveltejs/adapter-static';

   export default {
       kit: {
           adapter: adapter({
               pages: 'build',
               assets: 'build',
               fallback: 'index.html',
               strict: true
           })
       }
   };
   ```

3. Build the frontend:
   ```bash
   npm run build
   ```

---

## Option 1: PyInstaller (Single-File `.exe` / Binary with Browser Auto-Launch)

This bundles the FastAPI backend, SQLite database logic, and static frontend assets into a single executable file. When double-clicked, it starts the backend server locally and opens your browser.

### 1. Install PyInstaller
```bash
.venv/bin/pip install pyinstaller
```

### 2. Update `src/backend/main.py` for PyInstaller Bundle Path
Add asset resolution logic in `src/backend/main.py`:
```python
import sys
import os
import webbrowser
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Determine static asset directory (works both in development and inside PyInstaller bundle)
if hasattr(sys, '_MEIPASS'):
    build_dir = os.path.join(sys._MEIPASS, "src/frontend/build")
else:
    build_dir = os.path.join(os.path.dirname(__file__), "../frontend/build")

if os.path.exists(build_dir):
    app.mount("/", StaticFiles(directory=build_dir, html=True), name="static")

# Auto-open web browser on startup
@app.on_event("startup")
def open_browser():
    webbrowser.open("http://127.0.0.1:8000")
```

### 3. Build the Standalone Executable

**On Windows (PowerShell / Command Prompt):**
```cmd
pyinstaller --noconfirm --onefile --windowed ^
  --add-data "src/frontend/build;src/frontend/build" ^
  --name BudgetApp ^
  src/backend/main.py
```

**On Linux:**
```bash
pyinstaller --noconfirm --onefile \
  --add-data "src/frontend/build:src/frontend/build" \
  --name BudgetApp \
  src/backend/main.py
```

### 4. Output
The single executable file will be generated in the `dist/` directory:
- **Windows**: `dist/BudgetApp.exe`
- **Linux**: `dist/BudgetApp`

---

## Option 2: Native Desktop Window App (Using `pywebview`)

If you want the application to run inside a native desktop window (like a standard desktop software application) instead of launching an external web browser:

### 1. Install `pywebview`
```bash
.venv/bin/pip install pywebview pyinstaller
```

### 2. Create `desktop_app.py` in Project Root
Create a launcher script named `desktop_app.py`:
```python
import threading
import uvicorn
import webview
from src.backend.main import app

def run_backend():
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

if __name__ == "__main__":
    # Start FastAPI backend in a background thread
    server_thread = threading.Thread(target=run_backend, daemon=True)
    server_thread.start()

    # Create native desktop window pointing to the app
    window = webview.create_window(
        title="Personal Budget & Finance",
        url="http://127.0.0.1:8000",
        width=1280,
        height=800,
        resizable=True
    )
    webview.start()
```

### 3. Build Desktop Executable with PyInstaller

**On Windows:**
```cmd
pyinstaller --noconfirm --onefile --windowed ^
  --add-data "src/frontend/build;src/frontend/build" ^
  --name BudgetDesktop ^
  desktop_app.py
```

**On Linux:**
```bash
pyinstaller --noconfirm --onefile --windowed \
  --add-data "src/frontend/build:src/frontend/build" \
  --name BudgetDesktop \
  desktop_app.py
```

### 4. Output
The native desktop executable will be created in `dist/`:
- **Windows**: `dist/BudgetDesktop.exe`
- **Linux**: `dist/BudgetDesktop`

Double-clicking the file launches a dedicated desktop application window without displaying any terminal prompts or requiring an external web browser.
