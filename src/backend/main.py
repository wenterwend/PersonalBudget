from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from .database import init_db
from .routers import accounts, categories, transactions, rules, imports, ml, budgets, reports

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

@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Backend engine is healthy"}
