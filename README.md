# Personal Finance & Budgeting Application

A modern, responsive client-server personal finance and household budgeting application built with **SvelteKit** on the frontend, a **Python FastAPI** backend, and an embedded **SQLite 3** database running in Write-Ahead Logging (WAL) mode.

---

## Key Features

- **Multi-Account Management (US-1.1):** Track checking, savings, credit cards, and investment accounts with opening balances, opening dates, and real-time current balance calculation. Archive or close inactive accounts.
- **Unified vs. Account-Specific Views (US-1.2):** Filter transactions by individual account or view a consolidated "All Accounts" household ledger.
- **Quick Manual Entry & Split Transactions (US-1.3, US-1.4):** Log income and expenses on desktop or mobile. Split transactions across multiple categories with live real-time split sum validation.
- **Bank Statement Ingestion & Column Mapping (US-2.1, US-2.2, US-2.3):** Import CSV and QFX/OFX bank statement exports with dynamic column mapping and SHA-256 deduplication.
- **Rules Engine & Naive Bayes ML Categorization (US-3.1 - US-3.4):** Automate category assignment with priority matching rules and TF-IDF Naive Bayes machine learning with one-click confirmation.
- **Envelope Budgeting & Rolling Averages (US-4.1 - US-4.5):** Monthly envelope grid, historical month navigation (`YYYY-MM`), 3-month rolling average auto-allocation, carryover balance rollover, and one-click surplus transfer to savings.
- **Exact Integer Cents Precision:** Monetary values are stored strictly as 64-bit integers (`amount_cents`) to eliminate floating-point inaccuracies.
- **SQLite WAL Mode:** Optimized for high performance and concurrent access with `PRAGMA journal_mode=WAL;` and foreign key enforcement.

---

## Technical Architecture & Tech Stack

```mermaid
graph TD
    subgraph Client Layer (SvelteKit Frontend)
        SvelteApp["SvelteKit App (Svelte 5 Runes + Tailwind CSS v4)"]
        TanStack["@tanstack/svelte-table Ledger & Envelope Budget Grid"]
    end

    subgraph Backend Server (FastAPI)
        FastAPI["FastAPI REST API (Python 3.12+)"]
        SQLModelEngine["SQLModel / SQLAlchemy ORM"]
        MLEngine["scikit-learn Naive Bayes Model"]
        RolloverEngine["Category Rollover & Rolling Average Engine"]
    end

    subgraph Storage
        SQLite[("SQLite 3 Database\nWAL Mode Enabled, Cents Integers")]
    end

    SvelteApp -->|REST API / HTTP| FastAPI
    FastAPI --> SQLModelEngine
    FastAPI --> MLEngine
    FastAPI --> RolloverEngine
    SQLModelEngine --> SQLite
```

- **Frontend:** SvelteKit 2.0 (Svelte 5 Runes), TypeScript, Vite, Tailwind CSS v4, Lucide icons, `@tanstack/svelte-table`.
- **Backend:** Python 3.12+, FastAPI, SQLModel / SQLAlchemy 2.0, Pydantic v2, scikit-learn, uvicorn.
- **Database:** SQLite 3 with Write-Ahead Logging (`WAL`).

---

## Project Folder Structure

```
budget/
├── plan/
│   ├── user_stories.md          # Complete user story specifications
│   └── implementation_plan.md   # Architectural overview & milestone checklist
├── requirements.txt             # Python backend dependencies
├── README.md                    # Project documentation & setup guide
└── src/
    ├── backend/
    │   ├── main.py              # FastAPI application entrypoint & CORS
    │   ├── database.py          # SQLite engine with WAL pragma & session generator
    │   ├── models.py            # SQLModel entities (Account, Transaction, Split, Category, Rule, Budget)
    │   ├── routers/             # REST endpoints (accounts, transactions, categories, rules, ml, budgets)
    │   │   ├── accounts.py
    │   │   ├── transactions.py
    │   │   ├── categories.py
    │   │   ├── rules.py
    │   │   ├── ml.py
    │   │   └── budgets.py
    │   ├── services/            # Core business logic (rollover & N-month averages)
    │   │   └── rollover.py
    │   └── tests/
    │       ├── test_milestone1.py # Pytest suite for Milestone 1
    │       ├── test_milestone2.py # Pytest suite for Milestone 2
    │       ├── test_milestone3.py # Pytest suite for Milestone 3
    │       └── test_milestone4.py # Pytest suite for Milestone 4
    └── frontend/
        ├── package.json
        ├── vite.config.ts
        ├── postcss.config.js
        └── src/
            ├── app.css
            ├── lib/
            │   ├── api.ts       # Backend REST API fetch client
            │   ├── utils/
            │   │   └── currency.ts # Dollar/cents formatting utilities
            │   └── components/
            │       ├── ledger/  # AccountSelector, AccountModal, TransactionModal, LedgerTable
            │       ├── rules/   # RuleList, RuleModal
            │       └── budget/  # BudgetGrid, SurplusTransferModal
            └── routes/
                ├── +layout.svelte
                └── +page.svelte # Main dashboard view (Ledger, Budgeting & Rules tabs)
```

---

## Getting Started & Setup Instructions

### Prerequisites

- **Python:** 3.12+
- **Node.js:** v20+ (with `npm` v10+)

---

### 1. Backend Setup (FastAPI + SQLite)

1. Navigate to the project root:
   ```bash
   cd /path/to/budget
   ```

2. Create and activate a Python virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. Install backend dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the FastAPI backend server:
   ```bash
   uvicorn src.backend.main:app --reload --port 8000
   ```
   The backend API will be live at `http://localhost:8000`. API documentation (Swagger UI) is available at `http://localhost:8000/docs`.

---

### 2. Frontend Setup (SvelteKit)

1. Navigate to the frontend directory:
   ```bash
   cd src/frontend
   ```

2. Install Node dependencies:
   ```bash
   npm install
   ```

3. Start the SvelteKit development server:
   ```bash
   npm run dev
   ```
   The frontend UI will be accessible at `http://localhost:5173`.

4. Build for production:
   ```bash
   npm run build
   ```

---

## Linux Setup & On-Demand Startup Options

### Option 1: On-Demand Desktop Application Launcher (App Menu Icon)
To launch the app on-demand when you want to use it and automatically open your web browser:

1. Make the launch script executable:
   ```bash
   chmod +x /home/wend/all/code/budget/launch.sh
   ```

2. Create a desktop shortcut at `~/.local/share/applications/budget.desktop`:
   ```ini
   [Desktop Entry]
   Name=Budget App
   Comment=Personal Finance & Budgeting Application
   Exec=/home/wend/all/code/budget/launch.sh
   Icon=utilities-terminal
   Terminal=true
   Type=Application
   Categories=Office;Finance;
   ```
*Clicking **Budget App** in your application menu launches the app and opens `http://localhost:5173`. Closing the terminal window stops the server.*

---

### Option 2: Terminal Alias Command (`budget`)
Add an alias to `~/.bashrc`:
```bash
alias budget='cd /home/wend/all/code/budget && ./start.sh'
```
Run `budget` in your terminal to start, and press `Ctrl+C` when finished.

---

### Option 3: Systemd Background Service (Auto-Start on Boot)
To run automatically in the background on Linux boot, create `~/.config/systemd/user/budget.service`:
```ini
[Unit]
Description=Personal Finance & Budget Application
After=network.target

[Service]
Type=simple
WorkingDirectory=/home/wend/all/code/budget
ExecStart=/home/wend/all/code/budget/.venv/bin/uvicorn src.backend.main:app --host 0.0.0.0 --port 8000
Restart=always

[Install]
WantedBy=default.target
```
Enable and start the service:
```bash
systemctl --user daemon-reload
systemctl --user enable --now budget.service
```

---

## Windows Setup & On-Demand Startup Options

### Prerequisites for Windows
- **Python 3.12+**: Download from [python.org](https://www.python.org/downloads/) (Ensure *"Add Python to PATH"* is checked during installation).
- **Node.js v20+**: Download from [nodejs.org](https://nodejs.org/).

### 1. Initial Setup (PowerShell / Command Prompt)

1. Open PowerShell or Command Prompt in the project folder:
   ```cmd
   cd C:\path\to\budget
   ```

2. Create and activate a Python virtual environment:
   ```cmd
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. Install Python dependencies:
   ```cmd
   pip install -r requirements.txt
   ```

4. Install Node.js frontend dependencies:
   ```cmd
   cd src\frontend
   npm install
   cd ..\..
   ```

---

### 2. On-Demand Launch Options on Windows

#### Option A: Double-Click Launcher (`launch.bat`)
Double-click `launch.bat` in the project root folder. 
- It automatically starts the FastAPI backend (Port 8000) and SvelteKit frontend (Port 5173).
- Opens your browser to `http://localhost:5173`.
- Closing the command prompt window stops the application when you're finished.

#### Option B: Desktop Shortcut
1. Right-click `launch.bat` -> **Send to** -> **Desktop (create shortcut)**.
2. Rename the shortcut to **Budget App**.
3. Double-click the desktop shortcut whenever you want to use your budget.

#### Option C: Windows Startup (Auto-Start on Boot)
To run automatically when Windows starts up:
1. Press `Win + R`, type `shell:startup`, and press **Enter**.
2. Paste a copy (or shortcut) of `launch.bat` into the Startup folder.

---

## Standalone Executable Packaging Guide

For instructions on building a single standalone `.exe` or native desktop application (using PyInstaller or PyWebView), see the [Packaging Guide](file:///home/wend/all/code/budget/PACKAGING.md).

---

## Running Automated Tests

Backend unit tests use `pytest` and test SQLite WAL initialization, Account CRUD, Ingestion & Deduplication, Rules & ML Categorization, and Envelope Budgeting & Surplus Transfers.

Run tests from the project root:

```bash
PYTHONPATH=. .venv/bin/pytest -v
```

---

## Progressive Implementation Milestones

- [x] **Milestone 1: Core Foundation & Ledger Backend (US-1.1, US-1.2, US-1.3, US-1.4)**
  - SQLite WAL Database Setup & SQLModel Entities
  - Multi-Account Management CRUD
  - Unified vs. Account-Specific Views & Ledger Table
  - Quick Manual Entry & Split Transaction Validation Modal
- [x] **Milestone 2: Bank Statement Ingestion & Deterministic Rules (US-2.1, US-2.2, US-2.3, US-3.1, US-3.2)**
  - CSV & QFX/OFX File Statement Parsers
  - Interactive CSV Column Mapper UI & Live Preview Table
  - SHA-256 Hash Duplicate Detection & Override Support
  - Deterministic Priority Rule Engine & Retroactive Execution
- [x] **Milestone 3: scikit-learn Naive Bayes Categorizer (US-3.3, US-3.4)**
  - TfidfVectorizer + MultinomialNB Machine Learning Engine
  - Automatic High-Confidence Category Assignment (>= 70%)
  - Visual ML Confidence Badge & One-Click Confirmation UI Button
  - Continuous Background Model Retraining Loop
- [x] **Milestone 4: Budget Planning & Rolling Averages (US-4.1, US-4.2, US-4.3, US-4.4, US-4.5)**
  - Category Hierarchy & Group Breakdown
  - Multi-Month Average Spreading ($\text{TargetBudget} = \frac{1}{N}\sum \text{ActualSpent}$)
  - Historical Month Navigation (`YYYY-MM`)
  - Category Balance Rollover ($\text{Available} = \text{Budgeted} + \text{Rollover}_{M-1} + \text{Actual}$)
  - Category Surplus Transfer to Savings Accounts
- [x] **Milestone 5: Visual Query Builder, Dashboards & PWA Deployment (US-5.1 - US-6.2)**
  - Custom Visual AST Query Builder & Nested Boolean Logic
  - Streaming CSV Export Engine
  - Interactive Financial Reports & Dashboards (Spending by Category, Cashflow Trends, Net Worth)
  - Dedicated `@media print` Layout & PDF Report Generation
  - Mobile Progressive Web App (`manifest.json` & PWA Meta Tags)
  - Concurrent Multi-User Access (SQLite WAL & `PRAGMA busy_timeout=5000;`)

---

## License

MIT License.

