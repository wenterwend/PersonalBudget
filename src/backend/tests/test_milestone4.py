import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select

from src.backend.main import app
from src.backend.database import get_session
from src.backend.models import Account, Transaction, CategoryGroup, Category, MonthlyBudget

TEST_DB_URL = "sqlite:///./test_budget_m4.db"
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

def test_monthly_budget_allocation_and_grid(client: TestClient):
    grp = client.post("/api/categories/groups", json={"name": "Utilities"}).json()
    cat = client.post("/api/categories", json={"group_id": grp["id"], "name": "Power"}).json()

    # Set budget for 2026-02: $200.00 (20000 cents) with carryover enabled
    set_res = client.post("/api/budgets/set", json={
        "month": "2026-02",
        "category_id": cat["id"],
        "budgeted_cents": 20000,
        "carryover_enabled": True
    })
    assert set_res.status_code == 200

    grid_res = client.get("/api/budgets/grid?month=2026-02").json()
    assert grid_res["month"] == "2026-02"
    assert grid_res["previous_month"] == "2026-01"
    assert grid_res["next_month"] == "2026-03"
    assert grid_res["total_budgeted_cents"] == 20000

    power_cat = grid_res["groups"][0]["categories"][0]
    assert power_cat["name"] == "Power"
    assert power_cat["budgeted_cents"] == 20000
    assert power_cat["carryover_enabled"] is True

def test_rolling_n_month_average_spreading(client: TestClient):
    acc = client.post("/api/accounts", json={
        "name": "Checking", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()
    grp = client.post("/api/categories/groups", json={"name": "Food"}).json()
    cat = client.post("/api/categories", json={"group_id": grp["id"], "name": "Dining"}).json()

    # Log historical spending in 2026-01 (-3000), 2026-02 (-6000), 2026-03 (-9000)
    client.post("/api/transactions", json={"account_id": acc["id"], "date": "2026-01-15", "raw_payee": "Rest A", "amount_cents": -3000, "category_id": cat["id"]})
    client.post("/api/transactions", json={"account_id": acc["id"], "date": "2026-02-15", "raw_payee": "Rest B", "amount_cents": -6000, "category_id": cat["id"]})
    client.post("/api/transactions", json={"account_id": acc["id"], "date": "2026-03-15", "raw_payee": "Rest C", "amount_cents": -9000, "category_id": cat["id"]})

    # Average for 3 months prior to 2026-04 = (3000 + 6000 + 9000) / 3 = 6000 cents ($60.00)
    apply_res = client.post("/api/budgets/apply-rolling-averages?month=2026-04&months_back=3")
    assert apply_res.status_code == 200

    grid_res = client.get("/api/budgets/grid?month=2026-04").json()
    dining_cat = grid_res["groups"][0]["categories"][0]
    assert dining_cat["budgeted_cents"] == 6000

def test_category_balance_rollover_and_surplus_transfer(client: TestClient):
    checking = client.post("/api/accounts", json={
        "name": "Checking Account", "type": "checking", "opening_balance_cents": 100000, "opening_date": "2026-01-01"
    }).json()
    savings = client.post("/api/accounts", json={
        "name": "Emergency Savings", "type": "savings", "opening_balance_cents": 50000, "opening_date": "2026-01-01"
    }).json()

    grp = client.post("/api/categories/groups", json={"name": "Variable"}).json()
    cat = client.post("/api/categories", json={"group_id": grp["id"], "name": "Groceries"}).json()

    # Month 1 (2026-01): Budget $500 (50000 cents), Spend $300 (-30000 cents). Unspent surplus = +$200 (20000 cents). Enable carryover.
    client.post("/api/budgets/set", json={
        "month": "2026-01",
        "category_id": cat["id"],
        "budgeted_cents": 50000,
        "carryover_enabled": True
    })
    client.post("/api/transactions", json={
        "account_id": checking["id"], "date": "2026-01-20", "raw_payee": "Supermarket", "amount_cents": -30000, "category_id": cat["id"]
    })

    # Month 2 (2026-02): Budget $400 (40000 cents). Rollover from Jan = +20000. Total available = 40000 + 20000 = 60000 cents ($600).
    grid_m2 = client.get("/api/budgets/grid?month=2026-02").json()
    g2 = grid_m2["groups"][0]["categories"][0]
    assert g2["previous_rollover_cents"] == 20000
    assert g2["available_cents"] == 20000  # 0 budgeted + 20000 rollover

    # Transfer unspent surplus to Emergency Savings (US-4.5)
    transfer_res = client.post("/api/budgets/transfer-surplus-to-savings", json={
        "month": "2026-02",
        "category_ids": [cat["id"]],
        "target_account_id": savings["id"]
    })
    assert transfer_res.status_code == 200
    res_data = transfer_res.json()
    assert res_data["transferred_cents"] == 20000
    assert res_data["target_account_name"] == "Emergency Savings"

    # Verify Savings Account balance increased by $200 (from 50000 to 70000 cents)
    savings_updated = client.get(f"/api/accounts/{savings['id']}").json()
    assert savings_updated["current_balance_cents"] == 70000

def test_category_deletion_and_archiving_safety(client: TestClient):
    grp = client.post("/api/categories/groups", json={"name": "Custom Group"}).json()
    grp_empty = client.post("/api/categories/groups", json={"name": "Empty Group"}).json()
    cat_unused = client.post("/api/categories", json={"group_id": grp["id"], "name": "Unused Sub"}).json()
    cat_used = client.post("/api/categories", json={"group_id": grp["id"], "name": "Used Sub"}).json()

    acc = client.post("/api/accounts", json={
        "name": "Checking", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()

    client.post("/api/transactions", json={
        "account_id": acc["id"], "date": "2026-01-10", "raw_payee": "Service", "amount_cents": -1000, "category_id": cat_used["id"]
    })

    # Hard delete unused category
    del_unused = client.delete(f"/api/categories/{cat_unused['id']}")
    assert del_unused.status_code == 200
    assert del_unused.json()["status"] == "deleted"

    # Soft delete (archive) used category with transactions
    del_used = client.delete(f"/api/categories/{cat_used['id']}")
    assert del_used.status_code == 200
    assert del_used.json()["status"] == "archived"

    # Deleting an empty group should succeed
    del_grp = client.delete(f"/api/categories/groups/{grp_empty['id']}")
    assert del_grp.status_code == 200
    assert del_grp.json()["status"] == "deleted"
