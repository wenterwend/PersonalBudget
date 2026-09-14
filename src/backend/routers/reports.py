import csv
import io
from typing import Dict, Any, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func

from src.backend.database import get_session
from src.backend.models import Account, Transaction, TransactionSplit, Category, CategoryGroup
from src.backend.services.query_builder import execute_ast_query

router = APIRouter(prefix="/api/reports", tags=["reports"])


def serialize_transaction_with_details(tx: Transaction, session: Session) -> Dict[str, Any]:
    account = session.get(Account, tx.account_id)
    account_name = account.name if account else None

    splits = session.exec(
        select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
    ).all()

    split_list = []
    for s in splits:
        cat_name = None
        if s.category_id:
            cat = session.get(Category, s.category_id)
            if cat:
                cat_name = cat.name
        split_list.append({
            "id": str(s.id),
            "transaction_id": str(s.transaction_id),
            "category_id": str(s.category_id) if s.category_id else None,
            "category_name": cat_name,
            "amount_cents": s.amount_cents,
            "notes": s.notes,
        })

    return {
        "id": str(tx.id),
        "account_id": str(tx.account_id),
        "account_name": account_name,
        "date": tx.date.isoformat() if hasattr(tx.date, "isoformat") else str(tx.date),
        "raw_payee": tx.raw_payee,
        "normalized_payee": tx.normalized_payee,
        "amount_cents": tx.amount_cents,
        "notes": tx.notes,
        "cleared": tx.cleared,
        "import_hash": tx.import_hash,
        "is_ml_suggested": tx.is_ml_suggested,
        "ml_confidence": tx.ml_confidence,
        "created_at": tx.created_at.isoformat() if hasattr(tx.created_at, "isoformat") else str(tx.created_at),
        "is_split": len(split_list) > 1,
        "splits": split_list,
    }


@router.post("/query")
def run_custom_ast_query(
    payload: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
):
    """
    Executes a dynamic JSON AST query tree (US-5.1) and returns matching transactions.
    Accepts payload either as {"ast": {...}} or directly as the AST node dictionary.
    """
    ast_root = payload.get("ast", payload)
    try:
        transactions = execute_ast_query(session, ast_root)
        results = [serialize_transaction_with_details(tx, session) for tx in transactions]
        return {
            "count": len(results),
            "total_amount_cents": sum(tx.amount_cents for tx in transactions),
            "transactions": results,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to execute AST query: {str(e)}")


@router.post("/export-csv")
def export_query_results_csv(
    payload: Dict[str, Any] = Body(...),
    session: Session = Depends(get_session),
):
    """
    Streams query result set directly to a CSV file download (US-5.2).
    """
    ast_root = payload.get("ast", payload)
    try:
        transactions = execute_ast_query(session, ast_root)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Query error: {str(e)}")

    def generate_csv_rows():
        output = io.StringIO()
        writer = csv.writer(output)

        # Write CSV Header
        writer.writerow([
            "Transaction ID",
            "Date",
            "Account Name",
            "Raw Payee",
            "Normalized Payee",
            "Amount ($)",
            "Amount Cents",
            "Cleared",
            "Category",
            "Notes",
        ])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        # Stream transaction rows
        for tx in transactions:
            serialized = serialize_transaction_with_details(tx, session)
            cat_names = [s["category_name"] for s in serialized["splits"] if s["category_name"]]
            category_str = ", ".join(cat_names) if cat_names else "Uncategorized"

            writer.writerow([
                serialized["id"],
                serialized["date"],
                serialized["account_name"] or "",
                serialized["raw_payee"],
                serialized["normalized_payee"] or "",
                f"{serialized['amount_cents'] / 100:.2f}",
                serialized["amount_cents"],
                "Yes" if serialized["cleared"] else "No",
                category_str,
                serialized["notes"] or "",
            ])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    headers = {
        "Content-Disposition": 'attachment; filename="transaction_export.csv"',
        "Content-Type": "text/csv; charset=utf-8",
    }
    return StreamingResponse(generate_csv_rows(), headers=headers)


@router.get("/spending-by-category")
def get_spending_by_category(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns category spending breakdown for reporting charts (US-5.3).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query).all()

    category_totals: Dict[str, Dict[str, Any]] = {}
    uncategorized_cents = 0
    total_expense_cents = 0

    for tx in transactions:
        splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        ).all()

        for s in splits:
            # Only count expenses (amount < 0) or expenses assigned to non-income categories
            if s.amount_cents < 0:
                abs_amount = abs(s.amount_cents)
                total_expense_cents += abs_amount

                if s.category_id:
                    cat_id_str = str(s.category_id)
                    if cat_id_str not in category_totals:
                        cat = session.get(Category, s.category_id)
                        group_name = "Other"
                        if cat and cat.group_id:
                            group = session.get(CategoryGroup, cat.group_id)
                            if group:
                                group_name = group.name
                        category_totals[cat_id_str] = {
                            "category_id": cat_id_str,
                            "category_name": cat.name if cat else "Unknown",
                            "group_name": group_name,
                            "total_cents": 0,
                        }
                    category_totals[cat_id_str]["total_cents"] += abs_amount
                else:
                    uncategorized_cents += abs_amount

    items = list(category_totals.values())
    if uncategorized_cents > 0:
        items.append({
            "category_id": "uncategorized",
            "category_name": "Uncategorized",
            "group_name": "Other",
            "total_cents": uncategorized_cents,
        })

    # Sort descending by spent amount
    items.sort(key=lambda x: x["total_cents"], reverse=True)

    # Compute percentage
    for item in items:
        item["percentage"] = round((item["total_cents"] / total_expense_cents * 100), 1) if total_expense_cents > 0 else 0.0

    return {
        "total_expense_cents": total_expense_cents,
        "categories": items,
    }


@router.get("/income-vs-expense")
def get_income_vs_expense(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns monthly income vs. expense trends for charts (US-5.3).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query).all()

    monthly_stats: Dict[str, Dict[str, int]] = {}

    for tx in transactions:
        month_key = tx.date.strftime("%Y-%m")
        if month_key not in monthly_stats:
            monthly_stats[month_key] = {"income_cents": 0, "expense_cents": 0}

        splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        ).all()

        for s in splits:
            if s.amount_cents > 0:
                monthly_stats[month_key]["income_cents"] += s.amount_cents
            else:
                monthly_stats[month_key]["expense_cents"] += abs(s.amount_cents)

    sorted_months = sorted(monthly_stats.keys())
    trend = []

    for m in sorted_months:
        inc = monthly_stats[m]["income_cents"]
        exp = monthly_stats[m]["expense_cents"]
        trend.append({
            "month": m,
            "income_cents": inc,
            "expense_cents": exp,
            "net_savings_cents": inc - exp,
        })

    return {
        "months": trend,
        "total_income_cents": sum(t["income_cents"] for t in trend),
        "total_expense_cents": sum(t["expense_cents"] for t in trend),
        "total_net_savings_cents": sum(t["net_savings_cents"] for t in trend),
    }


@router.get("/net-worth-history")
def get_net_worth_summary(
    session: Session = Depends(get_session),
):
    """
    Returns current net worth summary across liquid asset & credit/loan accounts (US-5.3).
    """
    accounts = session.exec(select(Account).where(Account.is_closed == False)).all()

    account_summaries = []
    total_assets_cents = 0
    total_liabilities_cents = 0

    for a in accounts:
        # Sum transaction amounts
        tx_sum = session.exec(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.account_id == a.id)
        ).one()

        current_balance = a.opening_balance_cents + tx_sum

        if current_balance >= 0:
            total_assets_cents += current_balance
        else:
            total_liabilities_cents += abs(current_balance)

        account_summaries.append({
            "id": str(a.id),
            "name": a.name,
            "type": a.type.value if hasattr(a.type, "value") else str(a.type),
            "current_balance_cents": current_balance,
        })

    net_worth_cents = total_assets_cents - total_liabilities_cents

    return {
        "net_worth_cents": net_worth_cents,
        "total_assets_cents": total_assets_cents,
        "total_liabilities_cents": total_liabilities_cents,
        "accounts": account_summaries,
    }
