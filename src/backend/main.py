from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import os
import sys

from .database import init_db
from .routers import accounts, categories, transactions, rules, imports, ml, budgets, reports, queries

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(
    title="Personal Finance & Budgeting API",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local SvelteKit frontend (Vite port 5173 / 3000 / 4173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(transactions.router)
app.include_router(rules.router)
app.include_router(imports.router)
app.include_router(ml.router)
app.include_router(budgets.router)
app.include_router(reports.router)
app.include_router(queries.router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Backend engine is healthy"}


# Locate frontend build directory
frontend_dir = None
if hasattr(sys, '_MEIPASS'):
    for sub in ["frontend_build", "src/frontend/build", "build"]:
        candidate = os.path.join(sys._MEIPASS, sub)
        if os.path.isdir(candidate):
            frontend_dir = candidate
            break
else:
    candidates = [
        os.path.join(os.path.dirname(__file__), "../frontend/build"),
        os.path.join(os.path.dirname(__file__), "frontend_build"),
        os.path.join(os.getcwd(), "frontend_build"),
        os.path.join(os.getcwd(), "src", "frontend", "build")
    ]
    for c in candidates:
        if os.path.isdir(c):
            frontend_dir = os.path.abspath(c)
            break

if frontend_dir and os.path.isdir(frontend_dir):
    app_assets = os.path.join(frontend_dir, "_app")
    if os.path.isdir(app_assets):
        app.mount("/_app", StaticFiles(directory=app_assets), name="frontend_app_assets")

    index_file = os.path.join(frontend_dir, "index.html")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        if full_path:
            target_path = os.path.join(frontend_dir, full_path)
            if os.path.isfile(target_path):
                return FileResponse(target_path)
        if os.path.isfile(index_file):
            return FileResponse(index_file)
        return {"error": "Frontend assets not found"}

