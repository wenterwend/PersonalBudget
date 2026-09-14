from typing import List, Optional, Dict, Any
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from pydantic import BaseModel
import uuid

from ..database import get_session
from ..models import MonthlyBudget, CategoryGroup, Category, Account, Transaction, TransactionSplit
from ..services.rollover import (
    get_previous_month_str,
    get_actual_spent_for_category,
    calculate_rolling_n_month_average,
    calculate_category_available_cents
)

router = APIRouter(prefix="/api/budgets", tags=["Budgets"])

class SetBudgetRequest(BaseModel):
    month: str  # YYYY-MM
    category_id: uuid.UUID
    budgeted_cents: Optional[int] = None
    carryover_enabled: Optional[bool] = None

class CategoryBudgetDetail(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    name: str
    is_income: bool
    budgeted_cents: int
    actual_cents: int
    previous_rollover_cents: int
    available_cents: int
    carryover_enabled: bool
    rolling_3mo_avg_cents: int

class CategoryGroupBudgetDetail(BaseModel):
    id: uuid.UUID
    name: str
    display_order: int
    total_budgeted_cents: int
    total_actual_cents: int
    total_available_cents: int
    categories: List[CategoryBudgetDetail]

class MonthlyBudgetGridResponse(BaseModel):
    month: str
    previous_month: str
    next_month: str
    total_income_cents: int
    total_budgeted_cents: int
    total_actual_cents: int
    total_available_cents: int
    groups: List[CategoryGroupBudgetDetail]

class TransferSurplusRequest(BaseModel):
    month: str  # YYYY-MM
    category_ids: List[uuid.UUID]
    target_account_id: uuid.UUID

@router.get("/grid", response_model=MonthlyBudgetGridResponse)
def get_monthly_budget_grid(
    month: str = Query(..., description="Month in YYYY-MM format"),
    session: Session = Depends(get_session)
):
    prev_month = get_previous_month_str(month)
    
    # Calculate next month
    y, m = map(int, month.split("-"))
    next_month = f"{y + 1}-01" if m == 12 else f"{y}-{m + 1:02d}"

    groups = session.exec(select(CategoryGroup).order_by(CategoryGroup.display_order, CategoryGroup.name)).all()
    memo_cache = {}

    group_details = []
    grand_total_income = 0
    grand_total_budgeted = 0
    grand_total_actual = 0
    grand_total_available = 0

    for g in groups:
        categories = session.exec(select(Category).where(Category.group_id == g.id).where(Category.is_archived == False).order_by(Category.name)).all()
        cat_details = []
        
        group_budgeted = 0
        group_actual = 0
        group_available = 0

        for c in categories:
            mb = session.exec(
                select(MonthlyBudget)
                .where(MonthlyBudget.month == month)
                .where(MonthlyBudget.category_id == c.id)
            ).first()

            budgeted_cents = mb.budgeted_cents if mb else 0
            carryover_enabled = mb.carryover_enabled if mb else False
            
            actual_cents = get_actual_spent_for_category(c.id, month, session)
            
            # Previous rollover
            prev_mb = session.exec(
                select(MonthlyBudget)
                .where(MonthlyBudget.month == prev_month)
                .where(MonthlyBudget.category_id == c.id)
            ).first()
            
            prev_rollover = 0
            if prev_mb and prev_mb.carryover_enabled:
                prev_rollover = calculate_category_available_cents(c.id, prev_month, session, memo_cache)

            available_cents = budgeted_cents + prev_rollover + actual_cents
            rolling_3mo = calculate_rolling_n_month_average(c.id, month, 3, session)

            cat_details.append(CategoryBudgetDetail(
                id=c.id,
                group_id=c.group_id,
                name=c.name,
                is_income=c.is_income,
                budgeted_cents=budgeted_cents,
                actual_cents=actual_cents,
                previous_rollover_cents=prev_rollover,
                available_cents=available_cents,
                carryover_enabled=carryover_enabled,
                rolling_3mo_avg_cents=rolling_3mo
            ))

            group_budgeted += budgeted_cents
            group_actual += actual_cents
            group_available += available_cents

            if c.is_income:
                grand_total_income += actual_cents

        group_details.append(CategoryGroupBudgetDetail(
            id=g.id,
            name=g.name,
            display_order=g.display_order,
            total_budgeted_cents=group_budgeted,
            total_actual_cents=group_actual,
            total_available_cents=group_available,
            categories=cat_details
        ))

        grand_total_budgeted += group_budgeted
        grand_total_actual += group_actual
        grand_total_available += group_available

    return MonthlyBudgetGridResponse(
        month=month,
        previous_month=prev_month,
        next_month=next_month,
        total_income_cents=grand_total_income,
        total_budgeted_cents=grand_total_budgeted,
        total_actual_cents=grand_total_actual,
        total_available_cents=grand_total_available,
        groups=group_details
    )

@router.post("/set")
def set_monthly_budget(
    req: SetBudgetRequest,
    session: Session = Depends(get_session)
):
    category = session.get(Category, req.category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    mb = session.exec(
        select(MonthlyBudget)
        .where(MonthlyBudget.month == req.month)
        .where(MonthlyBudget.category_id == req.category_id)
    ).first()

    if not mb:
        mb = MonthlyBudget(
            month=req.month,
            category_id=req.category_id,
            budgeted_cents=req.budgeted_cents if req.budgeted_cents is not None else 0,
            carryover_enabled=req.carryover_enabled if req.carryover_enabled is not None else False
        )
        session.add(mb)
    else:
        if req.budgeted_cents is not None:
            mb.budgeted_cents = req.budgeted_cents
        if req.carryover_enabled is not None:
            mb.carryover_enabled = req.carryover_enabled
        session.add(mb)

    session.commit()
    session.refresh(mb)
    return {"status": "ok", "month": mb.month, "category_id": mb.category_id, "budgeted_cents": mb.budgeted_cents, "carryover_enabled": mb.carryover_enabled}

@router.get("/rolling-averages")
def get_rolling_averages(
    month: str = Query(...),
    months_back: int = Query(3, ge=1, le=24),
    session: Session = Depends(get_session)
):
    categories = session.exec(select(Category).where(Category.is_archived == False)).all()
    averages = {}
    for c in categories:
        averages[str(c.id)] = calculate_rolling_n_month_average(c.id, month, months_back, session)
    return {"month": month, "months_back": months_back, "averages": averages}

@router.post("/apply-rolling-averages")
def apply_rolling_averages(
    month: str = Query(...),
    months_back: int = Query(3, ge=1, le=24),
    session: Session = Depends(get_session)
):
    categories = session.exec(select(Category).where(Category.is_archived == False)).all()
    updated_count = 0

    for c in categories:
        avg_cents = calculate_rolling_n_month_average(c.id, month, months_back, session)
        
        # Expenses are typically stored negative in transactions; targets e.g. positive budget amount
        target_budget = abs(avg_cents) if not c.is_income else avg_cents

        mb = session.exec(
            select(MonthlyBudget)
            .where(MonthlyBudget.month == month)
            .where(MonthlyBudget.category_id == c.id)
        ).first()

        if not mb:
            mb = MonthlyBudget(month=month, category_id=c.id, budgeted_cents=target_budget)
            session.add(mb)
        else:
            mb.budgeted_cents = target_budget
            session.add(mb)
        updated_count += 1

    session.commit()
    return {"status": "ok", "updated_count": updated_count, "months_back": months_back}

@router.post("/transfer-surplus-to-savings")
def transfer_surplus_to_savings(
    req: TransferSurplusRequest,
    session: Session = Depends(get_session)
):
    account = session.get(Account, req.target_account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Target savings account not found")

    total_surplus_transferred = 0
    transferred_categories = []

    for cat_id in req.category_ids:
        cat = session.get(Category, cat_id)
        if not cat:
            continue
            
        avail = calculate_category_available_cents(cat_id, req.month, session)
        if avail > 0:
            total_surplus_transferred += avail
            transferred_categories.append(cat.name)
            
            # Reduce budgeted amount for this category by surplus or zero out rollover
            mb = session.exec(
                select(MonthlyBudget)
                .where(MonthlyBudget.month == req.month)
                .where(MonthlyBudget.category_id == cat_id)
            ).first()
            if mb:
                mb.budgeted_cents = max(0, mb.budgeted_cents - avail)
                session.add(mb)

    if total_surplus_transferred > 0:
        # Create transfer deposit transaction into savings account
        tx = Transaction(
            account_id=req.target_account_id,
            date=date.today(),
            raw_payee=f"Budget Surplus Transfer ({', '.join(transferred_categories)})",
            normalized_payee="Surplus Transfer",
            amount_cents=total_surplus_transferred,
            notes=f"Auto-transfer of unspent budget surpluses for {req.month}",
            cleared=True
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)

        split = TransactionSplit(
            transaction_id=tx.id,
            category_id=None,
            amount_cents=total_surplus_transferred,
            notes=tx.notes
        )
        session.add(split)
        session.commit()

    return {
        "status": "ok",
        "transferred_cents": total_surplus_transferred,
        "target_account_name": account.name,
        "transferred_categories": transferred_categories
    }
