import csv
import io
import uuid
import datetime
from typing import Dict, Any, List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, Query, Body
from fastapi.responses import StreamingResponse
from sqlmodel import Session, select, func

from src.backend.database import get_session
from src.backend.models import Account, AccountType, Transaction, TransactionSplit, Category, CategoryGroup
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


@router.get("/category-initiators")
def get_category_initiator_breakdown(
    category_id: str = Query(..., description="Category ID or 'uncategorized'"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns category breakdown by transaction initiator (raw/normalized payee) (US-5.7).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query).all()

    initiator_totals: Dict[str, Dict[str, Any]] = {}
    total_category_expense_cents = 0

    for tx in transactions:
        splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        ).all()

        for s in splits:
            is_match = False
            if category_id == "uncategorized":
                if s.category_id is None:
                    is_match = True
            else:
                if s.category_id and str(s.category_id) == category_id:
                    is_match = True

            if is_match:
                abs_amount = abs(s.amount_cents)
                total_category_expense_cents += abs_amount

                initiator = tx.normalized_payee or tx.raw_payee or "Unknown Initiator"
                if initiator not in initiator_totals:
                    initiator_totals[initiator] = {
                        "payee": initiator,
                        "total_cents": 0,
                        "transaction_count": 0,
                    }
                initiator_totals[initiator]["total_cents"] += abs_amount
                initiator_totals[initiator]["transaction_count"] += 1

    initiators = list(initiator_totals.values())
    initiators.sort(key=lambda x: x["total_cents"], reverse=True)

    for item in initiators:
        item["percentage"] = (
            round((item["total_cents"] / total_category_expense_cents * 100), 1)
            if total_category_expense_cents > 0
            else 0.0
        )

    cat_name = "Uncategorized"
    if category_id != "uncategorized":
        try:
            cat_uuid = uuid.UUID(category_id)
            cat = session.get(Category, cat_uuid)
            if cat:
                cat_name = cat.name
        except ValueError:
            pass

    return {
        "category_id": category_id,
        "category_name": cat_name,
        "total_expense_cents": total_category_expense_cents,
        "initiators": initiators,
    }


@router.get("/category-initiators/transactions")
def get_category_initiator_transactions(
    category_id: str = Query(...),
    payee: str = Query(...),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns individual transactions for a specific payee/initiator within a category (US-5.10).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query.order_by(Transaction.date.desc())).all()

    matching_txs = []
    for tx in transactions:
        initiator = tx.normalized_payee or tx.raw_payee or "Unknown Initiator"
        if initiator.strip().lower() != payee.strip().lower():
            continue

        splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        ).all()

        is_cat_match = False
        for s in splits:
            if category_id == "uncategorized":
                if s.category_id is None:
                    is_cat_match = True
            else:
                if s.category_id and str(s.category_id) == category_id:
                    is_cat_match = True

        if is_cat_match:
            matching_txs.append(serialize_transaction_with_details(tx, session))

    return {
        "category_id": category_id,
        "payee": payee,
        "count": len(matching_txs),
        "total_amount_cents": sum(abs(tx["amount_cents"]) for tx in matching_txs),
        "transactions": matching_txs,
    }


@router.get("/month-over-month-comparison")
def get_month_over_month_comparison(
    category_ids: Optional[str] = Query(None, description="Comma-separated category UUIDs"),
    months_back: int = Query(6, ge=1, le=24),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns month-over-month category spending comparison (US-5.11).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query.order_by(Transaction.date)).all()

    filter_cat_ids = set()
    if category_ids:
        filter_cat_ids = {c.strip() for c in category_ids.split(",") if c.strip()}

    matrix: Dict[str, Dict[str, int]] = {}
    categories_meta: Dict[str, str] = {}

    for tx in transactions:
        month_str = tx.date.strftime("%Y-%m")
        if month_str not in matrix:
            matrix[month_str] = {}

        splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        ).all()

        for s in splits:
            if s.amount_cents < 0:
                abs_amt = abs(s.amount_cents)
                cat_id_str = str(s.category_id) if s.category_id else "uncategorized"

                if filter_cat_ids and cat_id_str not in filter_cat_ids:
                    continue

                if cat_id_str not in categories_meta:
                    if cat_id_str == "uncategorized":
                        categories_meta[cat_id_str] = "Uncategorized"
                    else:
                        cat = session.get(Category, s.category_id)
                        categories_meta[cat_id_str] = cat.name if cat else "Unknown"

                matrix[month_str][cat_id_str] = matrix[month_str].get(cat_id_str, 0) + abs_amt

    sorted_months = sorted(matrix.keys())
    if months_back and len(sorted_months) > months_back:
        sorted_months = sorted_months[-months_back:]

    series = []
    for cat_id, cat_name in categories_meta.items():
        data_points = []
        cat_total = 0
        for m in sorted_months:
            val = matrix.get(m, {}).get(cat_id, 0)
            data_points.append({"month": m, "amount_cents": val})
            cat_total += val
        series.append({
            "category_id": cat_id,
            "category_name": cat_name,
            "total_cents": cat_total,
            "data_points": data_points
        })

    series.sort(key=lambda x: x["total_cents"], reverse=True)

    return {
        "months": sorted_months,
        "series": series
    }


@router.get("/fixed-vs-variable")
def get_fixed_vs_variable_breakdown(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns fixed vs. variable expense breakdown report (US-5.12).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query).all()

    fixed_cents = 0
    variable_cents = 0
    uncategorized_cents = 0
    total_expense_cents = 0

    fixed_categories: Dict[str, Dict[str, Any]] = {}
    variable_categories: Dict[str, Dict[str, Any]] = {}

    for tx in transactions:
        splits = session.exec(
            select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        ).all()

        for s in splits:
            if s.amount_cents < 0:
                abs_amt = abs(s.amount_cents)
                total_expense_cents += abs_amt

                if not s.category_id:
                    uncategorized_cents += abs_amt
                else:
                    cat = session.get(Category, s.category_id)
                    if cat:
                        cat_id_str = str(cat.id)
                        if cat.is_fixed:
                            fixed_cents += abs_amt
                            if cat_id_str not in fixed_categories:
                                fixed_categories[cat_id_str] = {"category_id": cat_id_str, "name": cat.name, "total_cents": 0}
                            fixed_categories[cat_id_str]["total_cents"] += abs_amt
                        else:
                            variable_cents += abs_amt
                            if cat_id_str not in variable_categories:
                                variable_categories[cat_id_str] = {"category_id": cat_id_str, "name": cat.name, "total_cents": 0}
                            variable_categories[cat_id_str]["total_cents"] += abs_amt
                    else:
                        uncategorized_cents += abs_amt

    fixed_list = sorted(list(fixed_categories.values()), key=lambda x: x["total_cents"], reverse=True)
    variable_list = sorted(list(variable_categories.values()), key=lambda x: x["total_cents"], reverse=True)

    fixed_pct = round((fixed_cents / total_expense_cents * 100), 1) if total_expense_cents > 0 else 0.0
    variable_pct = round((variable_cents / total_expense_cents * 100), 1) if total_expense_cents > 0 else 0.0
    uncategorized_pct = round((uncategorized_cents / total_expense_cents * 100), 1) if total_expense_cents > 0 else 0.0

    return {
        "total_expense_cents": total_expense_cents,
        "fixed_expense_cents": fixed_cents,
        "variable_expense_cents": variable_cents,
        "uncategorized_expense_cents": uncategorized_cents,
        "fixed_percentage": fixed_pct,
        "variable_percentage": variable_pct,
        "uncategorized_percentage": uncategorized_pct,
        "fixed_categories": fixed_list,
        "variable_categories": variable_list
    }


@router.get("/spending-heatmap")
def get_spending_heatmap(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns day-of-week and monthly date heatmap visualization data (US-5.13).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query).all()

    day_names = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    by_day_of_week = {i: {"day_index": i, "day_name": day_names[i], "total_cents": 0, "count": 0} for i in range(7)}
    by_day_of_month = {i: {"day_number": i, "total_cents": 0, "count": 0} for i in range(1, 32)}
    daily_totals: Dict[str, Dict[str, Any]] = {}

    for tx in transactions:
        if tx.amount_cents < 0:
            abs_amt = abs(tx.amount_cents)

            dow = int(tx.date.strftime("%w"))
            dom = tx.date.day
            date_str = tx.date.isoformat()

            by_day_of_week[dow]["total_cents"] += abs_amt
            by_day_of_week[dow]["count"] += 1

            by_day_of_month[dom]["total_cents"] += abs_amt
            by_day_of_month[dom]["count"] += 1

            if date_str not in daily_totals:
                daily_totals[date_str] = {"date": date_str, "total_cents": 0, "count": 0}
            daily_totals[date_str]["total_cents"] += abs_amt
            daily_totals[date_str]["count"] += 1

    dow_list = [by_day_of_week[i] for i in range(7)]
    dom_list = [by_day_of_month[i] for i in range(1, 32)]
    daily_list = sorted(list(daily_totals.values()), key=lambda x: x["date"])

    return {
        "by_day_of_week": dow_list,
        "by_day_of_month": dom_list,
        "daily_heatmap": daily_list
    }


@router.get("/top-merchants")
def get_top_merchants_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    sort_by: str = Query("total_amount"),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    session: Session = Depends(get_session),
):
    """
    Returns top merchant & payee leaderboard (US-5.14).
    """
    query = select(Transaction)
    if start_date:
        query = query.where(Transaction.date >= date.fromisoformat(start_date))
    if end_date:
        query = query.where(Transaction.date <= date.fromisoformat(end_date))

    transactions = session.exec(query).all()

    merchants: Dict[str, Dict[str, Any]] = {}

    for tx in transactions:
        if tx.amount_cents < 0:
            abs_amt = abs(tx.amount_cents)
            payee = tx.normalized_payee or tx.raw_payee or "Unknown Merchant"

            if payee not in merchants:
                merchants[payee] = {
                    "payee": payee,
                    "total_cents": 0,
                    "transaction_count": 0,
                    "categories": {},
                }

            merchants[payee]["total_cents"] += abs_amt
            merchants[payee]["transaction_count"] += 1

            splits = session.exec(
                select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
            ).all()

            for s in splits:
                if s.category_id:
                    cat = session.get(Category, s.category_id)
                    cat_name = cat.name if cat else "Unknown"
                    merchants[payee]["categories"][cat_name] = merchants[payee]["categories"].get(cat_name, 0) + abs(s.amount_cents)

    result = []
    for m, data in merchants.items():
        primary_cat = "Uncategorized"
        if data["categories"]:
            primary_cat = max(data["categories"].items(), key=lambda x: x[1])[0]

        avg_cents = int(round(data["total_cents"] / data["transaction_count"])) if data["transaction_count"] > 0 else 0

        result.append({
            "payee": m,
            "total_cents": data["total_cents"],
            "transaction_count": data["transaction_count"],
            "average_cents": avg_cents,
            "primary_category": primary_cat,
        })

    if sort_by == "frequency":
        result.sort(key=lambda x: (x["transaction_count"], x["total_cents"]), reverse=True)
    else:
        result.sort(key=lambda x: (x["total_cents"], x["transaction_count"]), reverse=True)

    return {
        "sort_by": sort_by,
        "limit": limit,
        "merchants": result[:limit]
    }


@router.get("/recurring-subscriptions")
def get_recurring_subscriptions_tracker(
    session: Session = Depends(get_session),
):
    """
    Detects recurring subscriptions and regular bills with predicted upcoming due dates (US-5.15).
    """
    transactions = session.exec(select(Transaction).where(Transaction.amount_cents < 0).order_by(Transaction.date)).all()

    payee_txs: Dict[str, List[Transaction]] = {}
    for tx in transactions:
        payee = tx.normalized_payee or tx.raw_payee or "Unknown"
        payee_clean = payee.strip()
        if payee_clean not in payee_txs:
            payee_txs[payee_clean] = []
        payee_txs[payee_clean].append(tx)

    subscriptions = []
    for payee, tx_list in payee_txs.items():
        if len(tx_list) < 2:
            continue

        months = {tx.date.strftime("%Y-%m") for tx in tx_list}
        if len(months) < 2:
            continue

        amounts = [abs(tx.amount_cents) for tx in tx_list]
        avg_amt = sum(amounts) / len(amounts)
        max_diff = max(abs(a - avg_amt) for a in amounts)
        if avg_amt > 0 and (max_diff / avg_amt) > 0.35:
            continue

        sorted_txs = sorted(tx_list, key=lambda x: x.date)
        gaps = [(sorted_txs[i].date - sorted_txs[i-1].date).days for i in range(1, len(sorted_txs))]
        avg_gap = sum(gaps) / len(gaps)

        frequency = "Monthly"
        if 20 <= avg_gap <= 40:
            frequency = "Monthly"
        elif 340 <= avg_gap <= 390:
            frequency = "Annual"
        elif 6 <= avg_gap <= 10:
            frequency = "Weekly"
        else:
            frequency = "Regular"

        last_tx = sorted_txs[-1]
        next_due = last_tx.date + datetime.timedelta(days=int(round(avg_gap)))

        monthly_cost_cents = int(round(avg_amt))
        if frequency == "Annual":
            monthly_cost_cents = int(round(avg_amt / 12))
        elif frequency == "Weekly":
            monthly_cost_cents = int(round(avg_amt * 4.33))

        annual_cost_cents = monthly_cost_cents * 12

        cat_name = "Uncategorized"
        splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == last_tx.id)).all()
        for s in splits:
            if s.category_id:
                cat = session.get(Category, s.category_id)
                if cat:
                    cat_name = cat.name

        subscriptions.append({
            "payee": payee,
            "category_name": cat_name,
            "average_amount_cents": int(round(avg_amt)),
            "frequency": frequency,
            "estimated_monthly_cents": monthly_cost_cents,
            "estimated_annual_cents": annual_cost_cents,
            "last_charge_date": last_tx.date.isoformat(),
            "predicted_next_due_date": next_due.isoformat(),
            "transaction_count": len(tx_list)
        })

    subscriptions.sort(key=lambda x: x["estimated_monthly_cents"], reverse=True)

    total_monthly = sum(s["estimated_monthly_cents"] for s in subscriptions)
    total_annual = sum(s["estimated_annual_cents"] for s in subscriptions)

    return {
        "total_subscriptions_count": len(subscriptions),
        "total_estimated_monthly_cents": total_monthly,
        "total_estimated_annual_cents": total_annual,
        "subscriptions": subscriptions
    }


@router.get("/budget-variance")
def get_budget_variance_report(
    month: str = Query(..., description="Month in YYYY-MM format"),
    session: Session = Depends(get_session),
):
    """
    Returns budget variance report comparing target budgeted vs actual spent per category (US-5.16).
    """
    categories = session.exec(select(Category).where(Category.is_archived == False).where(Category.is_income == False)).all()

    over_budget = []
    under_budget = []
    on_track = []

    total_budgeted_cents = 0
    total_actual_cents = 0
    total_over_cents = 0
    total_under_cents = 0

    from src.backend.services.rollover import get_actual_spent_for_category
    from src.backend.models import MonthlyBudget

    for cat in categories:
        mb = session.exec(
            select(MonthlyBudget).where(MonthlyBudget.month == month).where(MonthlyBudget.category_id == cat.id)
        ).first()

        budgeted = mb.budgeted_cents if mb else 0
        actual = abs(get_actual_spent_for_category(cat.id, month, session))

        variance = budgeted - actual
        total_budgeted_cents += budgeted
        total_actual_cents += actual

        item = {
            "category_id": str(cat.id),
            "category_name": cat.name,
            "budgeted_cents": budgeted,
            "actual_cents": actual,
            "variance_cents": variance,
            "percentage_used": round((actual / budgeted * 100), 1) if budgeted > 0 else (100.0 if actual > 0 else 0.0)
        }

        if actual > budgeted:
            over_diff = actual - budgeted
            total_over_cents += over_diff
            over_budget.append(item)
        elif actual < budgeted:
            under_diff = budgeted - actual
            total_under_cents += under_diff
            under_budget.append(item)
        else:
            on_track.append(item)

    over_budget.sort(key=lambda x: abs(x["variance_cents"]), reverse=True)
    under_budget.sort(key=lambda x: x["variance_cents"], reverse=True)

    return {
        "month": month,
        "total_budgeted_cents": total_budgeted_cents,
        "total_actual_cents": total_actual_cents,
        "net_variance_cents": total_budgeted_cents - total_actual_cents,
        "total_over_budget_cents": total_over_cents,
        "total_under_budget_cents": total_under_cents,
        "over_budget_categories": over_budget,
        "under_budget_categories": under_budget,
        "on_track_categories": on_track
    }


@router.get("/savings-rate-runway")
def get_savings_rate_and_runway(
    months_back: int = Query(6, ge=1, le=24),
    session: Session = Depends(get_session),
):
    """
    Returns net savings rate % and estimated liquid financial runway in months (US-5.17).
    """
    today = date.today()
    
    # Calculate start of month months_back ago
    year = today.year
    month = today.month - months_back
    while month <= 0:
        month += 12
        year -= 1
    start_date = date(year, month, 1)

    liquid_accounts = session.exec(
        select(Account).where(Account.is_closed == False).where(Account.type.in_([AccountType.CHECKING, AccountType.SAVINGS]))
    ).all()

    liquid_assets_cents = 0
    for a in liquid_accounts:
        tx_sum = session.exec(
            select(func.coalesce(func.sum(Transaction.amount_cents), 0)).where(Transaction.account_id == a.id)
        ).one()
        liquid_assets_cents += (a.opening_balance_cents + tx_sum)

    txs = session.exec(
        select(Transaction).where(Transaction.date >= start_date)
    ).all()

    monthly_data: Dict[str, Dict[str, int]] = {}
    for tx in txs:
        m_key = tx.date.strftime("%Y-%m")
        if m_key not in monthly_data:
            monthly_data[m_key] = {"income": 0, "expense": 0}

        splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
        for s in splits:
            if s.amount_cents > 0:
                monthly_data[m_key]["income"] += s.amount_cents
            else:
                monthly_data[m_key]["expense"] += abs(s.amount_cents)

    sorted_months = sorted(monthly_data.keys())
    trends = []
    total_income = 0
    total_expense = 0

    for m in sorted_months:
        inc = monthly_data[m]["income"]
        exp = monthly_data[m]["expense"]
        net_savings = inc - exp
        rate = round((net_savings / inc * 100), 1) if inc > 0 else 0.0

        total_income += inc
        total_expense += exp

        trends.append({
            "month": m,
            "income_cents": inc,
            "expense_cents": exp,
            "net_savings_cents": net_savings,
            "savings_rate_percentage": rate
        })

    avg_monthly_expense_cents = int(round(total_expense / len(sorted_months))) if sorted_months else 0
    overall_savings_rate = round(((total_income - total_expense) / total_income * 100), 1) if total_income > 0 else 0.0

    runway_months = round(liquid_assets_cents / avg_monthly_expense_cents, 1) if avg_monthly_expense_cents > 0 else (999.0 if liquid_assets_cents > 0 else 0.0)

    return {
        "liquid_assets_cents": liquid_assets_cents,
        "average_monthly_expense_cents": avg_monthly_expense_cents,
        "estimated_runway_months": runway_months,
        "overall_savings_rate_percentage": overall_savings_rate,
        "monthly_trends": trends
    }


