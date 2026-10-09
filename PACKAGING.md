# Packaging & Deploying the Budget Application

This guide covers how to package and deploy the **FastAPI + SvelteKit** Personal Budget Application into ready-to-run distributions for **Windows** and **Linux** with a clean database—without altering or destroying the development database.

---

## Publish Packages On GitHub

The repository now includes a GitHub Actions workflow at `.github/workflows/release.yml` that builds and uploads the release artifacts automatically.

### What It Publishes

- `dist/BudgetApp-Windows-x64.zip`
- `dist/BudgetApp-Linux.tar.gz`

### How To Publish A Release

1. Commit and push your source changes to GitHub.
2. Create a version tag locally:
  ```bash
  git tag v1.0.0
  git push origin v1.0.0
  ```
3. GitHub Actions will build both packages and create a GitHub release for that tag.
4. Download links will appear under the repository's **Releases** page.

### Re-run Without A New Tag

You can also run the same workflow manually from the **Actions** tab using **Build and Release Packages** and `workflow_dispatch`.

---

## Ready-to-Use Packages in `dist/`

The following deployable packages are built and ready for distribution in the `dist/` directory:

1. **Windows 64-bit Portable Distribution**:
   - **File**: `dist/BudgetApp-Windows-x64.zip` (~73 MB)
   - **Target**: Any modern Windows 10/11 64-bit computer.
   - **Dependencies**: **Zero** (no Python, Node.js, git, or admin privileges needed).
   - **Database**: Bundled with a freshly initialized, clean `budget.db` SQLite database with complete schemas and zero records. Default starter categories are automatically populated when first opened.
   - **How Client Uses It**:
     1. Extract `BudgetApp-Windows-x64.zip` anywhere on their computer (e.g. Desktop, Documents).
     2. Double-click `Start Budget App.bat` (or `Start Budget App (Silent).vbs` for silent mode).
     3. Their default web browser opens automatically to `http://localhost:8000`.

2. **Linux 64-bit Executable**:
   - **Files**: `dist/BudgetApp-Linux` & `dist/BudgetApp-Linux.tar.gz` (~82 MB)
   - **Target**: Any modern 64-bit Linux distribution.
   - **Dependencies**: None (self-contained ELF binary bundling Python, libraries, and frontend).
   - **How to Run**:
     ```bash
     chmod +x BudgetApp-Linux
     ./BudgetApp-Linux
     ```

---

## Clean Database Isolation Guarantees

- **Dev Database Protection**: The developer's database (`./budget.db` in project root) is never modified, purged, or touched during packaging or testing. SHA256 checksums are verified before and after packaging.
- **Client Clean Slate**: Deployable packages ship with an isolated, clean SQLite database (0 accounts, 0 transactions). On initial run, SvelteKit seeds standard starter category groups (`Income`, `Living Expenses`, `Lifestyle`) and categories.

---

## How to Rebuild Packages

### 1. Rebuild the Standalone Windows Package (from Linux or Windows)
Run the automated packaging script:
```bash
.venv/bin/python scripts/package_windows.py
```
This script automatically:
1. Downloads the official Python 3.12 64-bit embeddable runtime.
2. Downloads and extracts all Windows `win_amd64` binary wheels into `Lib/site-packages`.
3. Compiles the SvelteKit static frontend (`src/frontend/build`).
4. Copies backend application code (`src/backend`).
5. Generates a fresh, isolated `budget.db`.
6. Generates `Start Budget App.bat`, `Start Budget App (Silent).vbs`, and `Stop Budget App.bat`.
7. Creates `dist/BudgetApp-Windows-x64.zip`.

### 2. Rebuild the Linux Standalone Executable
Ensure the frontend is built, then run PyInstaller:
```bash
.venv/bin/pyinstaller --noconfirm --clean --onefile \
  --add-data "src/frontend/build:frontend_build" \
  --hidden-import "uvicorn.logging" \
  --hidden-import "uvicorn.loops" \
  --hidden-import "uvicorn.loops.auto" \
  --hidden-import "uvicorn.protocols" \
  --hidden-import "uvicorn.protocols.http" \
  --hidden-import "uvicorn.protocols.http.auto" \
  --hidden-import "uvicorn.protocols.websockets" \
  --hidden-import "uvicorn.protocols.websockets.auto" \
  --hidden-import "uvicorn.lifespan" \
  --hidden-import "uvicorn.lifespan.on" \
  --name BudgetApp-Linux \
  run_app.py
```

### 3. Build a Single-File `.exe` on a Windows Machine
If the client or developer prefers a single `.exe` executable file rather than an unzipped portable folder, run:
```cmd
build_windows_exe.bat
```
This produces `dist/BudgetApp.exe`.
