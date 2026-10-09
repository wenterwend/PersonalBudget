import os
import sys
import time
import webbrowser
import threading
import uvicorn

# Ensure the project root and current working directory are in sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Resolve default DATABASE_URL to a clean local file if not specified
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "sqlite:///./budget.db"

def open_browser():
    time.sleep(1.2)
    try:
        webbrowser.open("http://127.0.0.1:8000")
    except Exception:
        pass

def main():
    threading.Thread(target=open_browser, daemon=True).start()
    
    print("==================================================================")
    print("      Personal Budget & Finance Application is Running!          ")
    print("      URL:      http://127.0.0.1:8000                            ")
    print("      Database: " + os.environ.get("DATABASE_URL", ""))
    print("==================================================================")
    print("Close this console window / press Ctrl+C to stop the application.")
    print()
    
    from src.backend.main import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")

if __name__ == "__main__":
    main()
