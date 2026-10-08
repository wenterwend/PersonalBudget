import pytest
from datetime import date
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from src.backend.main import app
from src.backend.database import get_session
from src.backend.models import Account, AccountType, Transaction, TransactionSplit, CategoryGroup, Category, MonthlyBudget

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


def test_positive_value_normalization_us_4_8(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Living")
    session.add(acc)
    session.add(group)
    session.commit()

    cat = Category(group_id=group.id, name="Groceries", is_income=False)
    session.add(cat)
    session.commit()

    # Add transactions in prior months
    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 15), raw_payee="Supermarket", amount_cents=-30000)
    t2 = Transaction(account_id=acc.id, date=date(2026, 2, 15), raw_payee="Supermarket", amount_cents=-40000)
    session.add(t1)
    session.add(t2)
    session.commit()

    session.add(TransactionSplit(transaction_id=t1.id, category_id=cat.id, amount_cents=-30000))
    session.add(TransactionSplit(transaction_id=t2.id, category_id=cat.id, amount_cents=-40000))
    session.commit()

    # Get budget grid for March 2026
    res = client.get("/api/budgets/grid?month=2026-03")
    assert res.status_code == 200
    data = res.json()

    cat_detail = data["groups"][0]["categories"][0]
    # Expense rolling 3mo average must be normalized to positive value
    assert cat_detail["rolling_3mo_avg_cents"] >= 0

    # Test rolling-averages endpoint
    res_avg = client.get("/api/budgets/rolling-averages?month=2026-03&months_back=3")
    assert res_avg.status_code == 200
    avg_data = res_avg.json()
    assert avg_data["averages"][str(cat.id)] >= 0


def test_initiator_transactions_drilldown_us_5_10(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=50000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Food")
    session.add(acc)
    session.add(group)
    session.commit()

    cat = Category(group_id=group.id, name="Coffee")
    session.add(cat)
    session.commit()

    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 5), raw_payee="Starbucks #123", normalized_payee="Starbucks", amount_cents=-500)
    t2 = Transaction(account_id=acc.id, date=date(2026, 1, 12), raw_payee="Starbucks #456", normalized_payee="Starbucks", amount_cents=-600)
    session.add(t1)
    session.add(t2)
    session.commit()

    session.add(TransactionSplit(transaction_id=t1.id, category_id=cat.id, amount_cents=-500))
    session.add(TransactionSplit(transaction_id=t2.id, category_id=cat.id, amount_cents=-600))
    session.commit()

    res = client.get(f"/api/reports/category-initiators/transactions?category_id={cat.id}&payee=Starbucks")
    assert res.status_code == 200
    data = res.json()

    assert data["count"] == 2
    assert data["total_amount_cents"] == 1100
    assert len(data["transactions"]) == 2


def test_month_over_month_comparison_us_5_11(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Utilities")
    session.add(acc)
    session.add(group)
    session.commit()

    cat = Category(group_id=group.id, name="Electric")
    session.add(cat)
    session.commit()

    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 15), raw_payee="Power Co", amount_cents=-10000)
    t2 = Transaction(account_id=acc.id, date=date(2026, 2, 15), raw_payee="Power Co", amount_cents=-12000)
    session.add(t1)
    session.add(t2)
    session.commit()

    session.add(TransactionSplit(transaction_id=t1.id, category_id=cat.id, amount_cents=-10000))
    session.add(TransactionSplit(transaction_id=t2.id, category_id=cat.id, amount_cents=-12000))
    session.commit()

    res = client.get("/api/reports/month-over-month-comparison?months_back=6")
    assert res.status_code == 200
    data = res.json()

    assert "2026-01" in data["months"]
    assert "2026-02" in data["months"]
    assert len(data["series"]) >= 1
    electric_series = next(s for s in data["series"] if s["category_name"] == "Electric")
    assert electric_series["total_cents"] == 22000


def test_fixed_vs_variable_breakdown_us_5_12(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Housing")
    session.add(acc)
    session.add(group)
    session.commit()

    fixed_cat = Category(group_id=group.id, name="Rent", is_fixed=True)
    var_cat = Category(group_id=group.id, name="Entertainment", is_fixed=False)
    session.add(fixed_cat)
    session.add(var_cat)
    session.commit()

    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 1), raw_payee="Landlord", amount_cents=-150000)
    t2 = Transaction(account_id=acc.id, date=date(2026, 1, 10), raw_payee="Cinema", amount_cents=-5000)
    session.add(t1)
    session.add(t2)
    session.commit()

    session.add(TransactionSplit(transaction_id=t1.id, category_id=fixed_cat.id, amount_cents=-150000))
    session.add(TransactionSplit(transaction_id=t2.id, category_id=var_cat.id, amount_cents=-5000))
    session.commit()

    res = client.get("/api/reports/fixed-vs-variable")
    assert res.status_code == 200
    data = res.json()

    assert data["fixed_expense_cents"] == 150000
    assert data["variable_expense_cents"] == 5000
    assert data["fixed_percentage"] > 90.0
    assert len(data["fixed_categories"]) == 1
    assert len(data["variable_categories"]) == 1


def test_spending_heatmap_us_5_13(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
    session.add(acc)
    session.commit()

    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 5), raw_payee="Store A", amount_cents=-5000)
    t2 = Transaction(account_id=acc.id, date=date(2026, 1, 12), raw_payee="Store B", amount_cents=-7000)
    session.add(t1)
    session.add(t2)
    session.commit()

    res = client.get("/api/reports/spending-heatmap")
    assert res.status_code == 200
    data = res.json()

    assert len(data["by_day_of_week"]) == 7
    assert len(data["by_day_of_month"]) == 31
    assert len(data["daily_heatmap"]) >= 2


def test_top_merchants_leaderboard_us_5_14(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
    session.add(acc)
    session.commit()

    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 5), raw_payee="MegaCorp", amount_cents=-50000)
    t2 = Transaction(account_id=acc.id, date=date(2026, 1, 10), raw_payee="MegaCorp", amount_cents=-30000)
    t3 = Transaction(account_id=acc.id, date=date(2026, 1, 15), raw_payee="SmallShop", amount_cents=-1000)
    session.add(t1)
    session.add(t2)
    session.add(t3)
    session.commit()

    res = client.get("/api/reports/top-merchants?limit=5&sort_by=total_amount")
    assert res.status_code == 200
    data = res.json()

    merchants = data["merchants"]
    assert len(merchants) == 2
    assert merchants[0]["payee"] == "MegaCorp"
    assert merchants[0]["total_cents"] == 80000
    assert merchants[0]["transaction_count"] == 2


def test_recurring_subscriptions_us_5_15(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
    session.add(acc)
    session.commit()

    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 15), raw_payee="Netflix", amount_cents=-1599)
    t2 = Transaction(account_id=acc.id, date=date(2026, 2, 15), raw_payee="Netflix", amount_cents=-1599)
    t3 = Transaction(account_id=acc.id, date=date(2026, 3, 15), raw_payee="Netflix", amount_cents=-1599)
    session.add(t1)
    session.add(t2)
    session.add(t3)
    session.commit()

    res = client.get("/api/reports/recurring-subscriptions")
    assert res.status_code == 200
    data = res.json()

    assert data["total_subscriptions_count"] >= 1
    netflix = next(s for s in data["subscriptions"] if s["payee"] == "Netflix")
    assert netflix["frequency"] == "Monthly"
    assert netflix["estimated_monthly_cents"] == 1599
    assert netflix["predicted_next_due_date"] is not None


def test_budget_variance_us_5_16(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=100000, opening_date=date(2026, 1, 1))
    group = CategoryGroup(name="Living")
    session.add(acc)
    session.add(group)
    session.commit()

    cat1 = Category(group_id=group.id, name="Groceries") # Budget 500, spent 600 -> Over budget
    cat2 = Category(group_id=group.id, name="Dining")    # Budget 300, spent 100 -> Under budget
    session.add(cat1)
    session.add(cat2)
    session.commit()

    mb1 = MonthlyBudget(month="2026-01", category_id=cat1.id, budgeted_cents=50000)
    mb2 = MonthlyBudget(month="2026-01", category_id=cat2.id, budgeted_cents=30000)
    session.add(mb1)
    session.add(mb2)
    session.commit()

    t1 = Transaction(account_id=acc.id, date=date(2026, 1, 10), raw_payee="Supermarket", amount_cents=-60000)
    t2 = Transaction(account_id=acc.id, date=date(2026, 1, 15), raw_payee="Diner", amount_cents=-10000)
    session.add(t1)
    session.add(t2)
    session.commit()

    session.add(TransactionSplit(transaction_id=t1.id, category_id=cat1.id, amount_cents=-60000))
    session.add(TransactionSplit(transaction_id=t2.id, category_id=cat2.id, amount_cents=-10000))
    session.commit()

    res = client.get("/api/reports/budget-variance?month=2026-01")
    assert res.status_code == 200
    data = res.json()

    assert data["total_budgeted_cents"] == 80000
    assert data["total_actual_cents"] == 70000
    assert len(data["over_budget_categories"]) == 1
    assert data["over_budget_categories"][0]["category_name"] == "Groceries"
    assert len(data["under_budget_categories"]) == 1
    assert data["under_budget_categories"][0]["category_name"] == "Dining"


def test_savings_rate_runway_us_5_17(session: Session, client: TestClient):
    acc = Account(name="Checking", type=AccountType.CHECKING, opening_balance_cents=300000, opening_date=date(2026, 1, 1))
    session.add(acc)
    session.commit()

    t_inc = Transaction(account_id=acc.id, date=date(2026, 1, 1), raw_payee="Salary", amount_cents=500000)
    t_exp = Transaction(account_id=acc.id, date=date(2026, 1, 15), raw_payee="Expenses", amount_cents=-200000)
    session.add(t_inc)
    session.add(t_exp)
    session.commit()

    session.add(TransactionSplit(transaction_id=t_inc.id, category_id=None, amount_cents=500000))
    session.add(TransactionSplit(transaction_id=t_exp.id, category_id=None, amount_cents=-200000))
    session.commit()

    res = client.get("/api/reports/savings-rate-runway?months_back=12")
    assert res.status_code == 200
    data = res.json()

    assert data["liquid_assets_cents"] == 600000  # 300000 + 500000 - 200000
    assert data["overall_savings_rate_percentage"] == 60.0
    assert data["estimated_runway_months"] > 0


def test_bulk_apply_budget_us_4_9(session: Session, client: TestClient):
    group = CategoryGroup(name="Living")
    session.add(group)
    session.commit()

    cat = Category(group_id=group.id, name="Groceries")
    session.add(cat)
    session.commit()

    # Apply 12,000 cents ($120) total for Q1 (Jan, Feb, Mar) in divide mode -> 4,000 cents/month
    payload_q = {
        "category_id": str(cat.id),
        "scope_type": "quarter",
        "year": 2026,
        "quarter": 1,
        "amount_cents": 12000,
        "mode": "divide"
    }
    res_q = client.post("/api/budgets/apply-bulk", json=payload_q)
    assert res_q.status_code == 200
    data_q = res_q.json()
    assert data_q["monthly_budgeted_cents"] == 4000
    assert data_q["total_updates"] == 3

    # Check Jan 2026 budget
    mb_jan = session.exec(select(MonthlyBudget).where(MonthlyBudget.month == "2026-01").where(MonthlyBudget.category_id == cat.id)).first()
    assert mb_jan.budgeted_cents == 4000

    # Apply $500/month (50,000 cents) for Full Year 2026 in repeat mode -> 50,000 cents/month across 12 months
    payload_y = {
        "category_id": str(cat.id),
        "scope_type": "year",
        "year": 2026,
        "amount_cents": 50000,
        "mode": "repeat"
    }
    res_y = client.post("/api/budgets/apply-bulk", json=payload_y)
    assert res_y.status_code == 200
    data_y = res_y.json()
    assert data_y["monthly_budgeted_cents"] == 50000
    assert data_y["total_updates"] == 12

    mb_dec = session.exec(select(MonthlyBudget).where(MonthlyBudget.month == "2026-12").where(MonthlyBudget.category_id == cat.id)).first()
    assert mb_dec.budgeted_cents == 50000

