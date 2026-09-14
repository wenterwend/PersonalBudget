import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel, create_engine, Session, select
import uuid

from src.backend.main import app
from src.backend.database import get_session
from src.backend.models import Account, Transaction, Rule, MatchField, MatchType, CategoryGroup, Category
from src.backend.services.ingestion import parse_qfx_ofx, compute_import_hash

TEST_DB_URL = "sqlite:///./test_budget_m2.db"
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

def test_qfx_ofx_parsing():
    raw_qfx = """
    OFXHEADER:100
    DATA:OFXSGML
    <STMTTRN>
    <TRNTYPE>DEBIT
    <DTPOSTED>20260115120000
    <TRNAMT>-45.67
    <FITID>2026011500123
    <NAME>STARBUCKS COFFEE
    <MEMO>Seattle WA
    </STMTTRN>
    <STMTTRN>
    <TRNTYPE>CREDIT
    <DTPOSTED>20260116000000
    <TRNAMT>1200.00
    <FITID>2026011600456
    <NAME>PAYROLL DEPOSIT
    </STMTTRN>
    """
    txs = parse_qfx_ofx(raw_qfx)
    assert len(txs) == 2
    assert txs[0]["raw_payee"] == "STARBUCKS COFFEE"
    assert txs[0]["amount_cents"] == -4567
    assert txs[0]["date"] == "2026-01-15"
    assert txs[1]["raw_payee"] == "PAYROLL DEPOSIT"
    assert txs[1]["amount_cents"] == 120000

def test_csv_preview_and_import_mapping(client: TestClient):
    # Setup Account
    acc = client.post("/api/accounts", json={
        "name": "Import Checking", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()

    csv_data = "Transaction Date,Description,Amount,Notes\n2026-02-01,WALMART SUPERSTORE,-85.50,Grocery shopping\n2026-02-02,SHELL OIL,-35.00,Gasoline\n"

    # 1. Preview
    files = {"file": ("bank.csv", csv_data.encode("utf-8"), "text/csv")}
    prev_res = client.post("/api/imports/csv/preview", files=files)
    assert prev_res.status_code == 200
    preview = prev_res.json()
    assert "Transaction Date" in preview["headers"]
    assert "Description" in preview["headers"]
    assert len(preview["sample_rows"]) == 2

    # 2. Process CSV Import with column mapping
    proc_res = client.post("/api/imports/csv/process", json={
        "account_id": acc["id"],
        "file_content": csv_data,
        "date_col": "Transaction Date",
        "payee_col": "Description",
        "amount_col": "Amount",
        "notes_col": "Notes",
        "skip_duplicates": True
    })
    assert proc_res.status_code == 200
    summary = proc_res.json()
    assert summary["inserted_count"] == 2
    assert summary["duplicate_count"] == 0

    # Verify transactions in DB
    tx_list = client.get(f"/api/transactions?account_id={acc['id']}").json()
    assert len(tx_list) == 2
    assert tx_list[0]["raw_payee"] == "SHELL OIL"
    assert tx_list[0]["amount_cents"] == -3500
    assert tx_list[1]["raw_payee"] == "WALMART SUPERSTORE"
    assert tx_list[1]["amount_cents"] == -8550

def test_sha256_duplicate_detection(client: TestClient):
    acc = client.post("/api/accounts", json={
        "name": "Dup Account", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()

    csv_data = "Date,Payee,Amount\n2026-02-10,CHEVRON GAS,-40.00\n"

    # First import
    res1 = client.post("/api/imports/csv/process", json={
        "account_id": acc["id"],
        "file_content": csv_data,
        "date_col": "Date",
        "payee_col": "Payee",
        "amount_col": "Amount"
    }).json()
    assert res1["inserted_count"] == 1
    assert res1["duplicate_count"] == 0

    # Re-import same data -> duplicate detected
    res2 = client.post("/api/imports/csv/process", json={
        "account_id": acc["id"],
        "file_content": csv_data,
        "date_col": "Date",
        "payee_col": "Payee",
        "amount_col": "Amount",
        "skip_duplicates": True
    }).json()
    assert res2["inserted_count"] == 0
    assert res2["duplicate_count"] == 1

def test_rule_definition_and_retroactive_application(client: TestClient):
    acc = client.post("/api/accounts", json={
        "name": "Rule Test Account", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()
    grp = client.post("/api/categories/groups", json={"name": "Auto Expenses"}).json()
    cat = client.post("/api/categories", json={"group_id": grp["id"], "name": "Fuel & Gas"}).json()

    # Log 2 transactions with raw payee "CHEVRON #1234 AUSTIN"
    client.post("/api/transactions", json={
        "account_id": acc["id"], "date": "2026-02-01", "raw_payee": "CHEVRON #1234 AUSTIN", "amount_cents": -4500
    })
    client.post("/api/transactions", json={
        "account_id": acc["id"], "date": "2026-02-05", "raw_payee": "CHEVRON #5678 DALLAS", "amount_cents": -5000
    })

    # Verify initially uncategorized
    txs_before = client.get(f"/api/transactions?account_id={acc['id']}").json()
    assert txs_before[0]["splits"][0]["category_id"] is None

    # Create Rule (contains "CHEVRON") -> target payee "Chevron", target category "Fuel & Gas" with apply_retroactive=True
    rule_res = client.post("/api/rules?apply_retroactive=true", json={
        "priority": 1,
        "match_field": "raw_payee",
        "match_type": "contains",
        "match_value": "CHEVRON",
        "target_payee": "Chevron Gas",
        "target_category_id": cat["id"]
    })
    assert rule_res.status_code == 201

    # Verify both transactions retroactively updated!
    txs_after = client.get(f"/api/transactions?account_id={acc['id']}").json()
    assert txs_after[0]["normalized_payee"] == "Chevron Gas"
    assert txs_after[0]["splits"][0]["category_id"] == cat["id"]
    assert txs_after[1]["normalized_payee"] == "Chevron Gas"
    assert txs_after[1]["splits"][0]["category_id"] == cat["id"]


def test_multi_condition_rules_income_vs_expense(client: TestClient):
    """Verify rules with amount_condition (income vs expense) correctly distinguish paychecks from purchases."""
    acc = client.post("/api/accounts", json={
        "name": "Company Checking", "type": "checking", "opening_balance_cents": 0, "opening_date": "2026-01-01"
    }).json()

    grp = client.post("/api/categories/groups", json={"name": "Work & Life"}).json()
    cat_salary = client.post("/api/categories", json={"group_id": grp["id"], "name": "Salary & Payroll", "is_income": True}).json()
    cat_store = client.post("/api/categories", json={"group_id": grp["id"], "name": "Store Purchases", "is_income": False}).json()

    # Rule 1: ABC company + Income Only -> Salary
    client.post("/api/rules", json={
        "priority": 1,
        "match_field": "raw_payee",
        "match_type": "contains",
        "match_value": "ABC company",
        "amount_condition": "income",
        "target_payee": "ABC Corp Payroll",
        "target_category_id": cat_salary["id"]
    })

    # Rule 2: ABC company + Expense Only -> Store Purchases
    client.post("/api/rules", json={
        "priority": 2,
        "match_field": "raw_payee",
        "match_type": "contains",
        "match_value": "ABC company",
        "amount_condition": "expense",
        "target_payee": "ABC Corp Store",
        "target_category_id": cat_store["id"]
    })

    # Post Paycheck (income: +$3,000.00)
    paycheck_tx = client.post("/api/transactions", json={
        "account_id": acc["id"], "date": "2026-02-01", "raw_payee": "ABC company direct deposit", "amount_cents": 300000
    }).json()

    # Post Purchase (expense: -$25.00)
    purchase_tx = client.post("/api/transactions", json={
        "account_id": acc["id"], "date": "2026-02-02", "raw_payee": "ABC company retail store", "amount_cents": -2500
    }).json()

    # Run rules on both transactions
    client.post("/api/rules/apply-all")

    # Fetch updated transactions
    tx_paycheck_updated = client.get(f"/api/transactions/{paycheck_tx['id']}").json()
    tx_purchase_updated = client.get(f"/api/transactions/{purchase_tx['id']}").json()

    # Paycheck should match Rule 1 (Salary)
    assert tx_paycheck_updated["normalized_payee"] == "ABC Corp Payroll"
    assert tx_paycheck_updated["splits"][0]["category_id"] == cat_salary["id"]
    assert tx_paycheck_updated["splits"][0]["category_name"] == "Salary & Payroll"

    # Purchase should match Rule 2 (Store Purchases)
    assert tx_purchase_updated["normalized_payee"] == "ABC Corp Store"
    assert tx_purchase_updated["splits"][0]["category_id"] == cat_store["id"]
    assert tx_purchase_updated["splits"][0]["category_name"] == "Store Purchases"

