import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select

from src.backend.main import app
from src.backend.database import get_session
from src.backend.models import Account, Transaction, CategoryGroup, Category
from src.backend.services.ml_engine import ml_categorizer

TEST_DB_URL = "sqlite:///./test_budget_m3.db"
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

def test_ml_model_training_and_prediction(client: TestClient, session: Session):
    acc = client.post("/api/accounts", json={
        "name": "ML Account", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()

    grp = client.post("/api/categories/groups", json={"name": "Lifestyle"}).json()
    cat_coffee = client.post("/api/categories", json={"group_id": grp["id"], "name": "Coffee & Dining"}).json()
    cat_gas = client.post("/api/categories", json={"group_id": grp["id"], "name": "Gasoline"}).json()

    # Seed training dataset (historical confirmed transactions)
    for payee in ["STARBUCKS STORE #102", "STARBUCKS CAFE", "STARBUCKS #405"]:
        client.post("/api/transactions", json={
            "account_id": acc["id"], "date": "2026-01-10", "raw_payee": payee, "amount_cents": -500, "category_id": cat_coffee["id"]
        })

    for payee in ["SHELL OIL #99", "SHELL GAS STATION", "SHELL SERVICE CENTER"]:
        client.post("/api/transactions", json={
            "account_id": acc["id"], "date": "2026-01-10", "raw_payee": payee, "amount_cents": -3500, "category_id": cat_gas["id"]
        })

    # Train model
    retrain_res = client.post("/api/ml/retrain")
    assert retrain_res.status_code == 200
    assert retrain_res.json()["is_trained"] is True

    # Test prediction for "STARBUCKS DOWNTOWN"
    pred = ml_categorizer.predict("STARBUCKS DOWNTOWN", session)
    assert pred["is_high_confidence"] is True
    assert str(pred["suggested_category_id"]) == cat_coffee["id"]
    assert pred["confidence"] >= 0.85

def test_ml_suggestion_during_ingestion_and_one_click_confirmation(client: TestClient, session: Session):
    acc = client.post("/api/accounts", json={
        "name": "Ingest Account", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()

    grp = client.post("/api/categories/groups", json={"name": "Utilities"}).json()
    cat_power = client.post("/api/categories", json={"group_id": grp["id"], "name": "Electricity"}).json()
    cat_water = client.post("/api/categories", json={"group_id": grp["id"], "name": "Water Utility"}).json()

    # Seed training data
    for _ in range(3):
        client.post("/api/transactions", json={
            "account_id": acc["id"], "date": "2026-01-01", "raw_payee": "CITY POWER LIGHT & ELECTRIC", "amount_cents": -12000, "category_id": cat_power["id"]
        })
        client.post("/api/transactions", json={
            "account_id": acc["id"], "date": "2026-01-01", "raw_payee": "MUNICIPAL WATER DISTRICT", "amount_cents": -4500, "category_id": cat_water["id"]
        })

    client.post("/api/ml/retrain")

    # Ingest new CSV statement without rules
    csv_data = "Date,Payee,Amount\n2026-02-15,CITY POWER LIGHT BILL,-135.00\n"
    proc_res = client.post("/api/imports/csv/process", json={
        "account_id": acc["id"],
        "file_content": csv_data,
        "date_col": "Date",
        "payee_col": "Payee",
        "amount_col": "Amount"
    }).json()
    assert proc_res["inserted_count"] == 1

    # Verify transaction auto-assigned category via ML (is_ml_suggested=True)
    tx_list = client.get(f"/api/transactions?account_id={acc['id']}").json()
    new_tx = [t for t in tx_list if t["raw_payee"] == "CITY POWER LIGHT BILL"][0]
    assert new_tx["is_ml_suggested"] is True
    assert new_tx["ml_confidence"] >= 0.85
    assert new_tx["splits"][0]["category_id"] == cat_power["id"]

    # Test One-Click Category Confirmation
    conf_res = client.post(f"/api/transactions/{new_tx['id']}/confirm-category")
    assert conf_res.status_code == 200
    confirmed_tx = conf_res.json()
    assert confirmed_tx["is_ml_suggested"] is False
    assert confirmed_tx["ml_confidence"] is None
