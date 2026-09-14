import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine
from sqlmodel.pool import StaticPool
import datetime

from src.backend.main import app
from src.backend.database import get_session
from src.backend.models import Account, AccountType, CategoryGroup, Category, Transaction, TransactionSplit, Rule, MatchField, MatchType

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


def test_uncategorized_transaction_count(client: TestClient, session: Session):
    # Setup account & categories
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_date=datetime.date(2026, 1, 1))
    cat = Category(group_id=Account().id, name="Groceries") # Dummy ID
    session.add(acc)
    session.add(cat)
    session.commit()

    # Create 1 categorized transaction and 2 uncategorized transactions
    tx1 = Transaction(account_id=acc.id, date=datetime.date(2026, 1, 10), raw_payee="Supermarket", amount_cents=-5000)
    tx2 = Transaction(account_id=acc.id, date=datetime.date(2026, 1, 11), raw_payee="Coffee Shop", amount_cents=-450)
    tx3 = Transaction(account_id=acc.id, date=datetime.date(2026, 1, 12), raw_payee="Gas Station", amount_cents=-3000)
    session.add_all([tx1, tx2, tx3])
    session.commit()

    sp1 = TransactionSplit(transaction_id=tx1.id, category_id=cat.id, amount_cents=-5000)
    sp2 = TransactionSplit(transaction_id=tx2.id, category_id=None, amount_cents=-450)
    sp3 = TransactionSplit(transaction_id=tx3.id, category_id=None, amount_cents=-3000)
    session.add_all([sp1, sp2, sp3])
    session.commit()

    response = client.get("/api/transactions/uncategorized-count")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 2


def test_rules_search_and_preview(client: TestClient, session: Session):
    acc = Account(name="Credit", type=AccountType.CREDIT, opening_date=datetime.date(2026, 1, 1))
    cat1 = Category(group_id=acc.id, name="Coffee")
    cat2 = Category(group_id=acc.id, name="Travel")
    session.add_all([acc, cat1, cat2])
    session.commit()

    # Add sample transactions
    tx1 = Transaction(account_id=acc.id, date=datetime.date(2026, 2, 1), raw_payee="Starbucks #101", amount_cents=-550)
    tx2 = Transaction(account_id=acc.id, date=datetime.date(2026, 2, 2), raw_payee="Starbucks #102", amount_cents=-600)
    tx3 = Transaction(account_id=acc.id, date=datetime.date(2026, 2, 3), raw_payee="Uber Trip", amount_cents=-1500)
    session.add_all([tx1, tx2, tx3])
    session.commit()

    # Create rules
    r1 = Rule(match_field=MatchField.RAW_PAYEE, match_type=MatchType.CONTAINS, match_value="Starbucks", target_payee="Starbucks", target_category_id=cat1.id, priority=1)
    r2 = Rule(match_field=MatchField.RAW_PAYEE, match_type=MatchType.CONTAINS, match_value="Uber", target_payee="Uber", target_category_id=cat2.id, priority=2)
    session.add_all([r1, r2])
    session.commit()

    # Test US-3.5: Rules search filtering by query
    res_search = client.get("/api/rules?q=Starbucks")
    assert res_search.status_code == 200
    rules_data = res_search.json()
    assert len(rules_data) == 1
    assert rules_data[0]["match_value"] == "Starbucks"

    # Search by category_id
    res_cat = client.get(f"/api/rules?category_id={cat2.id}")
    assert res_cat.status_code == 200
    assert len(res_cat.json()) == 1
    assert res_cat.json()[0]["match_value"] == "Uber"

    # Test US-3.7: Rule preview matching endpoint
    preview_req = {
        "match_field": "raw_payee",
        "match_type": "contains",
        "match_value": "Starbucks",
        "amount_condition": "any",
        "priority": 1
    }
    res_preview = client.post("/api/rules/preview", json=preview_req)
    assert res_preview.status_code == 200
    prev_data = res_preview.json()
    assert prev_data["match_count"] == 2
    assert len(prev_data["sample_matches"]) == 2


def test_category_reparenting_and_merging(client: TestClient, session: Session):
    g1 = CategoryGroup(name="Food & Dining", display_order=1)
    g2 = CategoryGroup(name="Transportation", display_order=2)
    session.add_all([g1, g2])
    session.commit()

    cat_source = Category(group_id=g1.id, name="Coffee Shops")
    cat_target = Category(group_id=g1.id, name="Restaurants")
    session.add_all([cat_source, cat_target])
    session.commit()

    acc = Account(name="Checking", type=AccountType.CHECKING, opening_date=datetime.date(2026, 1, 1))
    session.add(acc)
    session.commit()

    tx = Transaction(account_id=acc.id, date=datetime.date(2026, 1, 15), raw_payee="Local Cafe", amount_cents=-1200)
    session.add(tx)
    session.commit()

    sp = TransactionSplit(transaction_id=tx.id, category_id=cat_source.id, amount_cents=-1200)
    rule = Rule(match_field=MatchField.RAW_PAYEE, match_type=MatchType.CONTAINS, match_value="Cafe", target_category_id=cat_source.id)
    session.add_all([sp, rule])
    session.commit()

    # Test re-parenting (US-4.7 edit/re-parent)
    patch_res = client.patch(f"/api/categories/{cat_source.id}", json={"group_id": str(g2.id), "name": "Cafes & Coffee"})
    assert patch_res.status_code == 200
    assert patch_res.json()["group_id"] == str(g2.id)
    assert patch_res.json()["name"] == "Cafes & Coffee"

    # Test Merging categories (US-4.7 merge)
    merge_res = client.post(f"/api/categories/{cat_source.id}/merge", json={"target_category_id": str(cat_target.id)})
    assert merge_res.status_code == 200
    assert merge_res.json()["status"] == "merged"

    # Verify transaction split reassigned to target category
    session.refresh(sp)
    assert sp.category_id == cat_target.id

    # Verify rule reassigned to target category
    session.refresh(rule)
    assert rule.target_category_id == cat_target.id

    # Verify source category is deleted
    assert session.get(Category, cat_source.id) is None


def test_saved_queries_and_uncategorized_ast(client: TestClient, session: Session):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_date=datetime.date(2026, 1, 1))
    cat = Category(group_id=acc.id, name="Groceries")
    session.add_all([acc, cat])
    session.commit()

    tx1 = Transaction(account_id=acc.id, date=datetime.date(2026, 3, 1), raw_payee="Target Store", amount_cents=-4500)
    tx2 = Transaction(account_id=acc.id, date=datetime.date(2026, 3, 2), raw_payee="Unsorted Market", amount_cents=-2200)
    session.add_all([tx1, tx2])
    session.commit()

    sp1 = TransactionSplit(transaction_id=tx1.id, category_id=cat.id, amount_cents=-4500)
    sp2 = TransactionSplit(transaction_id=tx2.id, category_id=None, amount_cents=-2200)
    session.add_all([sp1, sp2])
    session.commit()

    # Test US-5.5: Save Query CRUD
    query_ast = {
        "operator": "AND",
        "rules": [
            {"field": "category_id", "operator": "eq", "value": "uncategorized"}
        ]
    }
    create_res = client.post("/api/queries/saved", json={
        "name": "All Uncategorized Purchases",
        "description": "Finds all transactions with no assigned category",
        "query_ast": query_ast
    })
    assert create_res.status_code == 201
    sq_data = create_res.json()
    sq_id = sq_data["id"]
    assert sq_data["name"] == "All Uncategorized Purchases"

    # List saved queries
    list_res = client.get("/api/queries/saved")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # Execute saved query (US-5.5 & US-5.6)
    exec_res = client.post(f"/api/queries/saved/{sq_id}/execute")
    assert exec_res.status_code == 200
    results = exec_res.json()
    assert len(results) == 1
    assert results[0]["raw_payee"] == "Unsorted Market"

    # Update saved query
    update_res = client.patch(f"/api/queries/saved/{sq_id}", json={"description": "Updated description"})
    assert update_res.status_code == 200
    assert update_res.json()["description"] == "Updated description"

    # Delete saved query
    del_res = client.delete(f"/api/queries/saved/{sq_id}")
    assert del_res.status_code == 204
    assert client.get(f"/api/queries/saved/{sq_id}").status_code == 404
