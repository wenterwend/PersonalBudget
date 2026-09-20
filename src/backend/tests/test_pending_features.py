import pytest
from datetime import date
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.database import get_session, backup_database_if_exists
from src.backend.models import Account, AccountType, Transaction, TransactionSplit, CategoryGroup, Category

@pytest.fixture(name="session")
def session_fixture():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session

@pytest.fixture(name="client")
def client_fixture(session: Session):
    def get_session_override():
        return session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()

def test_database_backup_hook(tmp_path, monkeypatch):
    test_db = tmp_path / "budget_test.db"
    test_db.write_text("sample content")
    monkeypatch.setattr("src.backend.database.DATABASE_URL", f"sqlite:///{test_db}")

    backup_database_if_exists()

    backups = list(tmp_path.glob("budget_test.db.bak_*"))
    assert len(backups) == 1
    assert backups[0].read_text() == "sample content"

def test_batch_category_confirmation_us_3_8(session: Session, client: TestClient):
    # Setup account and categories
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=50000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Living")
    session.add(acc)
    session.add(group)
    session.commit()
    session.refresh(group)

    cat1 = Category(group_id=group.id, name="Groceries")
    cat2 = Category(group_id=group.id, name="Utilities")
    session.add(cat1)
    session.add(cat2)
    session.commit()
    session.refresh(cat1)
    session.refresh(cat2)

    # Seed 3 transactions with identical payee string 'Supermarket'
    tx1 = Transaction(account_id=acc.id, date=date(2026, 1, 10), raw_payee="Supermarket", amount_cents=-5000, is_ml_suggested=True, ml_confidence=0.88)
    tx2 = Transaction(account_id=acc.id, date=date(2026, 1, 15), raw_payee="Supermarket", amount_cents=-4500, is_ml_suggested=True, ml_confidence=0.88)
    tx3 = Transaction(account_id=acc.id, date=date(2026, 1, 20), raw_payee="Supermarket", amount_cents=-6000, is_ml_suggested=True, ml_confidence=0.88)
    session.add(tx1)
    session.add(tx2)
    session.add(tx3)
    session.commit()
    session.refresh(tx1)
    session.refresh(tx2)
    session.refresh(tx3)

    s1 = TransactionSplit(transaction_id=tx1.id, category_id=cat1.id, amount_cents=-5000)
    s2 = TransactionSplit(transaction_id=tx2.id, category_id=cat1.id, amount_cents=-4500)
    s3 = TransactionSplit(transaction_id=tx3.id, category_id=cat1.id, amount_cents=-6000)
    session.add(s1)
    session.add(s2)
    session.add(s3)
    session.commit()

    # Batch confirm tx1 with cat2 (Utilities)
    res = client.post(f"/api/transactions/{tx1.id}/confirm-category?batch=true", json={"category_id": str(cat2.id)})
    assert res.status_code == 200

    # Verify all 3 transactions updated category to Utilities and cleared ML suggested flags
    s1_updated = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx1.id)).first()
    s2_updated = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx2.id)).first()
    s3_updated = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx3.id)).first()

    assert s1_updated.category_id == cat2.id
    assert s2_updated.category_id == cat2.id
    assert s3_updated.category_id == cat2.id

    tx2_refreshed = session.get(Transaction, tx2.id)
    assert tx2_refreshed.is_ml_suggested is False
    assert tx2_refreshed.ml_confidence is None

def test_category_initiator_breakdown_us_5_7(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=50000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Food")
    session.add(acc)
    session.add(group)
    session.commit()
    session.refresh(group)

    cat = Category(group_id=group.id, name="Dining Out")
    session.add(cat)
    session.commit()
    session.refresh(cat)

    # Add transactions with different payees under same category
    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 5), raw_payee="Burger Shack", amount_cents=-3000)
    t2 = Transaction(account_id=acc.id, date=date(2026, 1, 12), raw_payee="Burger Shack", amount_cents=-2000)
    t3 = Transaction(account_id=acc.id, date=date(2026, 1, 20), raw_payee="Pizza Place", amount_cents=-5000)
    session.add(t1)
    session.add(t2)
    session.add(t3)
    session.commit()
    session.refresh(t1)
    session.refresh(t2)
    session.refresh(t3)

    session.add(TransactionSplit(transaction_id=t1.id, category_id=cat.id, amount_cents=-3000))
    session.add(TransactionSplit(transaction_id=t2.id, category_id=cat.id, amount_cents=-2000))
    session.add(TransactionSplit(transaction_id=t3.id, category_id=cat.id, amount_cents=-5000))
    session.commit()

    # Query breakdown for Dining Out category
    res = client.get(f"/api/reports/category-initiators?category_id={cat.id}")
    assert res.status_code == 200
    data = res.json()

    assert data["category_name"] == "Dining Out"
    assert data["total_expense_cents"] == 10000
    assert len(data["initiators"]) == 2

    # Burger Shack = 5000 (50%), Pizza Place = 5000 (50%)
    initiator_names = [i["payee"] for i in data["initiators"]]
    assert "Burger Shack" in initiator_names
    assert "Pizza Place" in initiator_names

    bs_item = next(i for i in data["initiators"] if i["payee"] == "Burger Shack")
    assert bs_item["total_cents"] == 5000
    assert bs_item["transaction_count"] == 2
    assert bs_item["percentage"] == 50.0

def test_reports_custom_date_filtering_us_5_8(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=50000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Shopping")
    session.add(acc)
    session.add(group)
    session.commit()
    session.refresh(group)

    cat = Category(group_id=group.id, name="Electronics")
    session.add(cat)
    session.commit()
    session.refresh(cat)

    # Q1 transaction
    t_q1 = Transaction(account_id=acc.id, date=date(2026, 2, 10), raw_payee="Tech Store", amount_cents=-20000)
    # Q2 transaction
    t_q2 = Transaction(account_id=acc.id, date=date(2026, 5, 15), raw_payee="Tech Store", amount_cents=-30000)

    session.add(t_q1)
    session.add(t_q2)
    session.commit()
    session.refresh(t_q1)
    session.refresh(t_q2)

    session.add(TransactionSplit(transaction_id=t_q1.id, category_id=cat.id, amount_cents=-20000))
    session.add(TransactionSplit(transaction_id=t_q2.id, category_id=cat.id, amount_cents=-30000))
    session.commit()

    # Query Q1 spending
    res_q1 = client.get("/api/reports/spending-by-category?start_date=2026-01-01&end_date=2026-03-31")
    assert res_q1.status_code == 200
    data_q1 = res_q1.json()
    assert data_q1["total_expense_cents"] == 20000

    # Query Q2 spending
    res_q2 = client.get("/api/reports/spending-by-category?start_date=2026-04-01&end_date=2026-06-30")
    assert res_q2.status_code == 200
    data_q2 = res_q2.json()
    assert data_q2["total_expense_cents"] == 30000
