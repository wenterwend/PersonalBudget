from typing import Any, Dict, List
from sqlmodel import Session, select, or_, and_
from sqlalchemy import Column
from src.backend.models import Transaction, TransactionSplit, Category, Account

def build_sqlalchemy_criterion(ast_node: Dict[str, Any]):
    """
    Recursively translates a JSON AST query node into a SQLAlchemy binary expression / criterion.
    """
    if not isinstance(ast_node, dict):
        raise ValueError("Invalid AST node: must be a dictionary")

    # Group Node (AND / OR)
    if "operator" in ast_node and ast_node.get("operator", "").upper() in ("AND", "OR"):
        rules = ast_node.get("rules", [])
        if not rules:
            # Empty group evaluates to True (1 == 1) for AND, False for OR
            return (Transaction.id == Transaction.id) if ast_node["operator"].upper() == "AND" else (Transaction.id != Transaction.id)
        
        sub_criteria = [build_sqlalchemy_criterion(r) for r in rules]
        if ast_node["operator"].upper() == "AND":
            return and_(*sub_criteria)
        else:
            return or_(*sub_criteria)

    # Leaf Rule Node
    field_name = ast_node.get("field")
    op = ast_node.get("operator")
    val = ast_node.get("value")

    if not field_name or not op:
        raise ValueError(f"Invalid rule node: missing field or operator in {ast_node}")

    # Map field names to SQLAlchemy columns
    field_map = {
        "date": Transaction.date,
        "amount_cents": Transaction.amount_cents,
        "raw_payee": Transaction.raw_payee,
        "normalized_payee": Transaction.normalized_payee,
        "account_id": Transaction.account_id,
        "cleared": Transaction.cleared,
        "category_id": TransactionSplit.category_id,
    }

    if field_name not in field_map:
        raise ValueError(f"Unsupported query field: {field_name}")

    column = field_map[field_name]

    # Convert numeric values for amount_cents if passed as string/float
    if field_name == "amount_cents" and val is not None:
        try:
            val = int(val)
        except (ValueError, TypeError):
            val = 0

    # Convert boolean for cleared
    if field_name == "cleared" and isinstance(val, str):
        val = val.lower() == "true"

    if op == "eq":
        return column == val
    elif op == "neq":
        return column != val
    elif op == "gt":
        return column > val
    elif op == "gte":
        return column >= val
    elif op == "lt":
        return column < val
    elif op == "lte":
        return column <= val
    elif op == "contains":
        return column.ilike(f"%{val}%")
    elif op == "starts_with":
        return column.ilike(f"{val}%")
    else:
        raise ValueError(f"Unsupported comparison operator: {op}")


def execute_ast_query(session: Session, ast_root: Dict[str, Any]) -> List[Transaction]:
    """
    Executes a dynamic JSON AST query against the database and returns distinct matching Transactions.
    """
    criterion = build_sqlalchemy_criterion(ast_root)

    # Left outer join TransactionSplit to allow filtering by split category_id
    statement = (
        select(Transaction)
        .outerjoin(TransactionSplit, Transaction.id == TransactionSplit.transaction_id)
        .where(criterion)
        .distinct()
        .order_by(Transaction.date.desc())
    )

    results = session.exec(statement).all()
    return results
