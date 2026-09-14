from datetime import date
from sqlmodel import Session, SQLModel, create_engine
from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.database import get_session
from src.backend.models import Account, AccountType, Transaction, CategoryGroup, Category, TransactionSplit

client = TestClient(app)

def test_milestone5_ast_query_csv_export_and_analytics(tmp_path):
    # Setup isolated test database engine
    db_file = tmp_path / "test_m5.db"
    test_engine = create_engine(f"sqlite:///{db_file}")
    SQLModel.metadata.create_all(test_engine)

    def get_test_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session

    # Seed test accounts, categories, and transactions
    with Session(test_engine) as session:
        acc_checking = Account(name="Primary Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
        acc_savings = Account(name="Emergency Savings", type=AccountType.SAVINGS, opening_balance_cents=500000, opening_date=date(2026, 1, 1))
        session.add(acc_checking)
        session.add(acc_savings)
        session.commit()
        session.refresh(acc_checking)
        session.refresh(acc_savings)

        group = CategoryGroup(name="Living", display_order=0)
        session.add(group)
        session.commit()
        session.refresh(group)

        cat_groceries = Category(group_id=group.id, name="Groceries", is_income=False)
        cat_salary = Category(group_id=group.id, name="Salary", is_income=True)
        session.add(cat_groceries)
        session.add(cat_salary)
        session.commit()
        session.refresh(cat_groceries)
        session.refresh(cat_salary)

        # Create transactions
        tx1 = Transaction(account_id=acc_checking.id, date=date(2026, 1, 15), raw_payee="Whole Foods Market", amount_cents=-15000, cleared=True)
        tx2 = Transaction(account_id=acc_checking.id, date=date(2026, 2, 1), raw_payee="Tech Corp Payroll", amount_cents=400000, cleared=True)
        tx3 = Transaction(account_id=acc_checking.id, date=date(2026, 2, 10), raw_payee="Trader Joe's", amount_cents=-8500, cleared=False)
        session.add(tx1)
        session.add(tx2)
        session.add(tx3)
        session.commit()

        # Add splits
        s1 = TransactionSplit(transaction_id=tx1.id, category_id=cat_groceries.id, amount_cents=-15000)
        s2 = TransactionSplit(transaction_id=tx2.id, category_id=cat_salary.id, amount_cents=400000)
        s3 = TransactionSplit(transaction_id=tx3.id, category_id=cat_groceries.id, amount_cents=-8500)
        session.add(s1)
        session.add(s2)
        session.add(s3)
        session.commit()

    # 1. Test AST Query endpoint: AND (amount_cents < 0, raw_payee contains "Foods" or "Joe")
    ast_payload = {
        "ast": {
            "operator": "AND",
            "rules": [
                {"field": "amount_cents", "operator": "lt", "value": 0},
                {
                    "operator": "OR",
                    "rules": [
                        {"field": "raw_payee", "operator": "contains", "value": "Foods"},
                        {"field": "raw_payee", "operator": "contains", "value": "Trader"}
                    ]
                }
            ]
        }
    }
    response = client.post("/api/reports/query", json=ast_payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["count"] == 2
    assert res_data["total_amount_cents"] == -23500

    # 2. Test CSV Export endpoint
    csv_response = client.post("/api/reports/export-csv", json=ast_payload)
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    csv_text = csv_response.text
    assert "Transaction ID,Date,Account Name,Raw Payee" in csv_text
    assert "Whole Foods Market" in csv_text
    assert "Trader Joe's" in csv_text

    # 3. Test Spending by Category breakdown endpoint
    cat_response = client.get("/api/reports/spending-by-category")
    assert cat_response.status_code == 200
    cat_data = cat_response.json()
    assert cat_data["total_expense_cents"] == 23500
    assert len(cat_data["categories"]) >= 1
    assert cat_data["categories"][0]["category_name"] == "Groceries"
    assert cat_data["categories"][0]["total_cents"] == 23500
    assert cat_data["categories"][0]["percentage"] == 100.0

    # 4. Test Income vs Expense trend endpoint
    inc_response = client.get("/api/reports/income-vs-expense")
    assert inc_response.status_code == 200
    inc_data = inc_response.json()
    assert inc_data["total_income_cents"] == 400000
    assert inc_data["total_expense_cents"] == 23500
    assert inc_data["total_net_savings_cents"] == 376500
    assert len(inc_data["months"]) == 2

    # 5. Test Net Worth history summary endpoint
    nw_response = client.get("/api/reports/net-worth-history")
    assert nw_response.status_code == 200
    nw_data = nw_response.json()
    # Checking: 100000 + (-15000 + 400000 - 8500) = 476500; Savings: 500000 => Total Assets = 976500
    assert nw_data["total_assets_cents"] == 976500
    assert nw_data["net_worth_cents"] == 976500

    # Clean up overrides
    app.dependency_overrides.clear()
