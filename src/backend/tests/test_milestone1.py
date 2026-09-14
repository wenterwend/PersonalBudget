import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select
from sqlalchemy import text
import uuid

from src.backend.main import app
from src.backend.database import get_session
from src.backend.models import Account, AccountType, Transaction, TransactionSplit, CategoryGroup, Category

# Setup in-memory / temporary test database
TEST_DB_URL = "sqlite:///./test_budget.db"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})

@pytest.fixture(name="session", autouse=True)
def session_fixture():
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session
    SQLModel.metadata.drop_all(test_engine)

@pytest.fixture(name="client", autouse=True)
def client_fixture(session: Session):
    def get_session_override():
        return session
    app.dependency_overrides[get_session] = get_session_override
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()

def test_sqlite_wal_mode(session: Session):
    # Enable WAL explicitly on test connection and verify
    session.exec(text("PRAGMA journal_mode=WAL;"))
    res = session.exec(text("PRAGMA journal_mode;")).first()
    assert res[0].lower() == "wal"

def test_account_crud(client: TestClient):
    # 1. Create account
    create_res = client.post("/api/accounts", json={
        "name": "Checking Account",
        "type": "checking",
        "currency": "USD",
        "opening_balance_cents": 100000,
        "opening_date": "2026-01-01"
    })
    assert create_res.status_code == 201
    data = create_res.json()
    account_id = data["id"]
    assert data["name"] == "Checking Account"
    assert data["opening_balance_cents"] == 100000
    assert data["current_balance_cents"] == 100000

    # 2. List accounts
    list_res = client.get("/api/accounts")
    assert list_res.status_code == 200
    accounts = list_res.json()
    assert len(accounts) == 1

    # 3. Update account
    patch_res = client.patch(f"/api/accounts/{account_id}", json={
        "name": "Primary Checking"
    })
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Primary Checking"

    # 4. Close account
    close_res = client.patch(f"/api/accounts/{account_id}", json={
        "is_closed": True
    })
    assert close_res.status_code == 200
    assert close_res.json()["is_closed"] is True

    # 5. List without closed
    list_res2 = client.get("/api/accounts")
    assert len(list_res2.json()) == 0

    # 6. List with closed
    list_res3 = client.get("/api/accounts?include_closed=true")
    assert len(list_res3.json()) == 1

def test_transactions_and_account_filtering(client: TestClient):
    # Setup 2 accounts
    acc1 = client.post("/api/accounts", json={
        "name": "Account A", "type": "checking", "opening_balance_cents": 5000, "opening_date": "2026-01-01"
    }).json()
    acc2 = client.post("/api/accounts", json={
        "name": "Account B", "type": "savings", "opening_balance_cents": 10000, "opening_date": "2026-01-01"
    }).json()

    # Add transaction to Account A (-1000)
    client.post("/api/transactions", json={
        "account_id": acc1["id"],
        "date": "2026-01-05",
        "raw_payee": "Grocery Store",
        "amount_cents": -1000
    })

    # Add transaction to Account B (+2500)
    client.post("/api/transactions", json={
        "account_id": acc2["id"],
        "date": "2026-01-06",
        "raw_payee": "Interest Deposit",
        "amount_cents": 2500
    })

    # Verify Account A balance = 5000 - 1000 = 4000
    acc1_updated = client.get(f"/api/accounts/{acc1['id']}").json()
    assert acc1_updated["current_balance_cents"] == 4000

    # Verify Account B balance = 10000 + 2500 = 12500
    acc2_updated = client.get(f"/api/accounts/{acc2['id']}").json()
    assert acc2_updated["current_balance_cents"] == 12500

    # Test filtering transactions by account_id
    tx_a = client.get(f"/api/transactions?account_id={acc1['id']}").json()
    assert len(tx_a) == 1
    assert tx_a[0]["raw_payee"] == "Grocery Store"

    # Test unified view (no account_id filter)
    tx_all = client.get("/api/transactions").json()
    assert len(tx_all) == 2

def test_split_transactions(client: TestClient):
    # Create account and category group / categories
    acc = client.post("/api/accounts", json={
        "name": "Credit Card", "type": "credit", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()

    grp = client.post("/api/categories/groups", json={"name": "Living Expenses"}).json()
    cat1 = client.post("/api/categories", json={"group_id": grp["id"], "name": "Groceries"}).json()
    cat2 = client.post("/api/categories", json={"group_id": grp["id"], "name": "Household Goods"}).json()

    # 1. Test invalid split sum (amount is -5000, splits sum to -4000) -> HTTP 400
    bad_res = client.post("/api/transactions", json={
        "account_id": acc["id"],
        "date": "2026-01-10",
        "raw_payee": "Target Superstore",
        "amount_cents": -5000,
        "splits": [
            {"category_id": cat1["id"], "amount_cents": -3000},
            {"category_id": cat2["id"], "amount_cents": -1000}
        ]
    })
    assert bad_res.status_code == 400
    assert "Split amounts sum" in bad_res.json()["detail"]

    # 2. Test valid split sum (amount is -5000, splits sum to -5000) -> HTTP 201
    good_res = client.post("/api/transactions", json={
        "account_id": acc["id"],
        "date": "2026-01-10",
        "raw_payee": "Target Superstore",
        "amount_cents": -5000,
        "splits": [
            {"category_id": cat1["id"], "amount_cents": -3500, "notes": "Food Items"},
            {"category_id": cat2["id"], "amount_cents": -1500, "notes": "Cleaning supplies"}
        ]
    })
    assert good_res.status_code == 201
    tx_data = good_res.json()
    assert tx_data["is_split"] is True
    assert len(tx_data["splits"]) == 2
    assert tx_data["splits"][0]["amount_cents"] == -3500
    assert tx_data["splits"][1]["amount_cents"] == -1500


def test_transaction_update_date_and_category(client: TestClient):
    """Verify that PATCH /api/transactions/{id} supports date strings and category_id updates."""
    # 1. Setup account and categories
    acc_res = client.post("/api/accounts", json={
        "name": "Update Test Checking",
        "type": "checking",
        "opening_balance_cents": 100000,
        "opening_date": "2026-01-01"
    })
    acc_id = acc_res.json()["id"]

    group_res = client.post("/api/categories/groups", json={"name": "Test Update Group"})
    group_id = group_res.json()["id"]

    cat1_res = client.post("/api/categories", json={"group_id": group_id, "name": "Old Category", "is_income": False})
    cat1_id = cat1_res.json()["id"]

    cat2_res = client.post("/api/categories", json={"group_id": group_id, "name": "New Custom Category", "is_income": False})
    cat2_id = cat2_res.json()["id"]

    # 2. Create transaction
    tx_res = client.post("/api/transactions", json={
        "account_id": acc_id,
        "date": "2026-01-05",
        "raw_payee": "Initial Payee",
        "amount_cents": -2500,
        "category_id": cat1_id
    })
    assert tx_res.status_code == 201
    tx_id = tx_res.json()["id"]
    assert tx_res.json()["splits"][0]["category_id"] == cat1_id

    # 3. Update transaction date and category (emulating frontend edit form)
    patch_res = client.patch(f"/api/transactions/{tx_id}", json={
        "account_id": acc_id,
        "date": "2026-09-04",
        "raw_payee": "Updated Payee",
        "amount_cents": -3000,
        "category_id": cat2_id
    })
    assert patch_res.status_code == 200, patch_res.text
    updated_tx = patch_res.json()
    assert updated_tx["date"] == "2026-09-04"
    assert updated_tx["raw_payee"] == "Updated Payee"
    assert updated_tx["amount_cents"] == -3000
    assert updated_tx["splits"][0]["category_id"] == cat2_id
    assert updated_tx["splits"][0]["category_name"] == "New Custom Category"

