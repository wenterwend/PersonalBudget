import datetime
from typing import List, Dict, Any, Optional
import uuid
from sqlmodel import Session, select, func
from ..models import MonthlyBudget, Category, CategoryGroup, Transaction, TransactionSplit

def get_previous_month_str(month_str: str) -> str:
    # month_str format: YYYY-MM
    year, month = map(int, month_str.split("-"))
    if month == 1:
        return f"{year - 1}-12"
    else:
        return f"{year}-{month - 1:02d}"

def get_month_date_range(month_str: str) -> tuple[datetime.date, datetime.date]:
    year, month = map(int, month_str.split("-"))
    start_date = datetime.date(year, month, 1)
    if month == 12:
        end_date = datetime.date(year + 1, 1, 1) - datetime.timedelta(days=1)
    else:
        end_date = datetime.date(year, month + 1, 1) - datetime.timedelta(days=1)
    return start_date, end_date

def get_actual_spent_for_category(category_id: uuid.UUID, month_str: str, session: Session) -> int:
    start_date, end_date = get_month_date_range(month_str)
    query = select(func.coalesce(func.sum(TransactionSplit.amount_cents), 0))\
        .join(Transaction, TransactionSplit.transaction_id == Transaction.id)\
        .where(TransactionSplit.category_id == category_id)\
        .where(Transaction.date >= start_date)\
        .where(Transaction.date <= end_date)
    return session.exec(query).one()

def calculate_rolling_n_month_average(category_id: uuid.UUID, current_month_str: str, months_back: int, session: Session) -> int:
    if months_back <= 0:
        return 0
        
    curr = current_month_str
    total_spent = 0
    
    for _ in range(months_back):
        curr = get_previous_month_str(curr)
        total_spent += get_actual_spent_for_category(category_id, curr, session)
        
    return int(round(total_spent / months_back))

def calculate_category_available_cents(
    category_id: uuid.UUID,
    month_str: str,
    session: Session,
    memo_cache: Optional[Dict[tuple[uuid.UUID, str], int]] = None
) -> int:
    if memo_cache is None:
        memo_cache = {}
        
    cache_key = (category_id, month_str)
    if cache_key in memo_cache:
        return memo_cache[cache_key]

    # Get budget entry for current month
    mb = session.exec(
        select(MonthlyBudget)
        .where(MonthlyBudget.month == month_str)
        .where(MonthlyBudget.category_id == category_id)
    ).first()

    budgeted_cents = mb.budgeted_cents if mb else 0
    actual_cents = get_actual_spent_for_category(category_id, month_str, session)

    # Calculate previous month rollover if enabled in previous month
    prev_month_str = get_previous_month_str(month_str)
    prev_mb = session.exec(
        select(MonthlyBudget)
        .where(MonthlyBudget.month == prev_month_str)
        .where(MonthlyBudget.category_id == category_id)
    ).first()

    prev_rollover = 0
    if prev_mb and prev_mb.carryover_enabled:
        # Recursively get available cents from previous month
        prev_available = calculate_category_available_cents(category_id, prev_month_str, session, memo_cache)
        prev_rollover = prev_available

    available = budgeted_cents + prev_rollover + actual_cents
    memo_cache[cache_key] = available
    return available
