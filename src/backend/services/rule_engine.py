from typing import List, Optional
import uuid
from sqlmodel import Session, select
from ..models import Rule, MatchField, MatchType, Transaction, TransactionSplit

def _check_condition(field: MatchField, mtype: MatchType, val: str, raw_payee: str, amount_cents: int, notes: Optional[str]) -> bool:
    val_to_check = ""
    if field == MatchField.RAW_PAYEE:
        val_to_check = raw_payee or ""
    elif field == MatchField.NOTES:
        val_to_check = notes or ""
    elif field == MatchField.AMOUNT:
        val_to_check = str(amount_cents)

    target_match = val.strip().lower()
    candidate = val_to_check.strip().lower()

    if mtype == MatchType.EXACT:
        return candidate == target_match
    elif mtype == MatchType.STARTS_WITH:
        return candidate.startswith(target_match)
    elif mtype == MatchType.CONTAINS:
        return target_match in candidate

    return False

def evaluate_rule(rule: Rule, raw_payee: str, amount_cents: int, notes: Optional[str]) -> bool:
    if not rule.is_active:
        return False
        
    # 1. Amount Condition check (income > 0 vs expense < 0)
    cond_raw = getattr(rule, "amount_condition", "any") or "any"
    cond = (cond_raw.value if hasattr(cond_raw, "value") else str(cond_raw)).lower()
    if cond == "income" and amount_cents <= 0:
        return False
    if cond == "expense" and amount_cents >= 0:
        return False

    # 2. Primary Match Field check
    if not _check_condition(rule.match_field, rule.match_type, rule.match_value, raw_payee, amount_cents, notes):
        return False

    # 3. Secondary Match Field check (if configured)
    sec_field = getattr(rule, "secondary_match_field", None)
    sec_type = getattr(rule, "secondary_match_type", None)
    sec_val = getattr(rule, "secondary_match_value", None)
    if sec_field and sec_type and sec_val and sec_val.strip():
        if not _check_condition(sec_field, sec_type, sec_val, raw_payee, amount_cents, notes):
            return False

    return True

def run_rules_on_transaction(tx: Transaction, rules: List[Rule], session: Session) -> bool:
    # Sort active rules by priority (ascending)
    active_rules = sorted([r for r in rules if r.is_active], key=lambda r: r.priority)
    
    for rule in active_rules:
        notes_str = tx.notes or ""
        if evaluate_rule(rule, tx.raw_payee, tx.amount_cents, notes_str):
            if rule.target_payee:
                tx.normalized_payee = rule.target_payee
            if rule.target_category_id:
                # Update split category
                splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
                if splits:
                    for s in splits:
                        s.category_id = rule.target_category_id
                        session.add(s)
            session.add(tx)
            return True
    return False

def apply_rules_retroactively(session: Session, rule_id: Optional[uuid.UUID] = None) -> int:
    query_rules = select(Rule).where(Rule.is_active == True).order_by(Rule.priority)
    if rule_id:
        query_rules = query_rules.where(Rule.id == rule_id)
    rules = session.exec(query_rules).all()
    if not rules:
        return 0

    transactions = session.exec(select(Transaction)).all()
    modified_count = 0

    for tx in transactions:
        for rule in rules:
            if evaluate_rule(rule, tx.raw_payee, tx.amount_cents, tx.notes):
                changed = False
                if rule.target_payee and tx.normalized_payee != rule.target_payee:
                    tx.normalized_payee = rule.target_payee
                    changed = True
                if rule.target_category_id:
                    splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
                    for s in splits:
                        if s.category_id != rule.target_category_id:
                            s.category_id = rule.target_category_id
                            session.add(s)
                            changed = True
                if changed:
                    session.add(tx)
                    modified_count += 1
                break  # Stop at first matching rule

    session.commit()
    return modified_count
