import csv
import io
import re
import hashlib
import datetime
from typing import List, Dict, Any, Optional, Tuple
import uuid
from sqlmodel import Session, select

from ..models import Transaction, TransactionSplit, Rule, Account
from .rule_engine import run_rules_on_transaction, evaluate_rule
from .ml_engine import ml_categorizer

def compute_import_hash(account_id: uuid.UUID, date_val: datetime.date, amount_cents: int, raw_payee: str) -> str:
    payload = f"{account_id}|{date_val.isoformat()}|{amount_cents}|{raw_payee.strip()}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def parse_amount_str_to_cents(val_str: str) -> int:
    if not val_str or not val_str.strip():
        return 0
    clean = val_str.strip()
    is_negative = False
    if clean.startswith("(") and clean.endswith(")"):
        is_negative = True
        clean = clean[1:-1]
    if clean.startswith("-"):
        is_negative = True
        clean = clean[1:]
    
    clean = re.sub(r"[^\d.]", "", clean)
    if not clean:
        return 0
        
    try:
        val_float = float(clean)
        cents = int(round(val_float * 100))
        return -cents if is_negative else cents
    except ValueError:
        return 0

def parse_date_string(date_str: str, fmt: Optional[str] = None) -> datetime.date:
    clean_str = date_str.strip()
    if fmt:
        try:
            return datetime.datetime.strptime(clean_str, fmt).date()
        except ValueError:
            pass

    formats = [
        "%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d",
        "%m-%d-%Y", "%d-%m-%Y", "%b %d, %Y", "%d %b %Y"
    ]
    for f in formats:
        try:
            return datetime.datetime.strptime(clean_str, f).date()
        except ValueError:
            pass
            
    try:
        return datetime.date.fromisoformat(clean_str[:10])
    except ValueError:
        raise ValueError(f"Could not parse date string: '{date_str}'")

def parse_csv_preview(file_content_str: str) -> Dict[str, Any]:
    f = io.StringIO(file_content_str.strip())
    reader = csv.reader(f)
    headers = next(reader, None)
    if not headers:
        return {"headers": [], "sample_rows": []}
        
    headers = [h.strip().lstrip("\ufeff") for h in headers]
    sample_rows = []
    for _ in range(5):
        row = next(reader, None)
        if row is None:
            break
        row_dict = {headers[i]: row[i].strip() if i < len(row) else "" for i in range(len(headers))}
        sample_rows.append(row_dict)
        
    return {
        "headers": headers,
        "sample_rows": sample_rows
    }

def process_csv_import(
    file_content_str: str,
    account_id: uuid.UUID,
    date_col: str,
    payee_col: str,
    amount_col: Optional[str],
    debit_col: Optional[str],
    credit_col: Optional[str],
    notes_col: Optional[str],
    date_format: Optional[str],
    skip_duplicates: bool,
    session: Session
) -> Dict[str, Any]:
    account = session.get(Account, account_id)
    if not account:
        raise ValueError("Account not found")

    rules = session.exec(select(Rule).where(Rule.is_active == True).order_by(Rule.priority)).all()

    f = io.StringIO(file_content_str.strip())
    reader = csv.DictReader(f)
    if reader.fieldnames:
        reader.fieldnames = [fn.strip().lstrip("\ufeff") for fn in reader.fieldnames]

    inserted_count = 0
    duplicate_count = 0
    rules_applied_count = 0

    for row in reader:
        if not row:
            continue
            
        date_raw = row.get(date_col, "")
        payee_raw = row.get(payee_col, "")
        notes_raw = row.get(notes_col, "") if notes_col else None
        
        if not date_raw or not payee_raw:
            continue
            
        try:
            parsed_date = parse_date_string(date_raw, date_format)
        except ValueError:
            continue

        amount_cents = 0
        if amount_col and amount_col in row and row[amount_col].strip():
            amount_cents = parse_amount_str_to_cents(row[amount_col])
        elif debit_col or credit_col:
            debit_val = parse_amount_str_to_cents(row.get(debit_col, "")) if debit_col else 0
            credit_val = parse_amount_str_to_cents(row.get(credit_col, "")) if credit_col else 0
            
            if debit_val != 0:
                amount_cents = -abs(debit_val)
            elif credit_val != 0:
                amount_cents = abs(credit_val)

        if amount_cents == 0:
            continue

        import_hash = compute_import_hash(account_id, parsed_date, amount_cents, payee_raw)
        existing_tx = session.exec(select(Transaction).where(Transaction.import_hash == import_hash)).first()
        if existing_tx:
            duplicate_count += 1
            if skip_duplicates:
                continue

        tx = Transaction(
            account_id=account_id,
            date=parsed_date,
            raw_payee=payee_raw.strip(),
            normalized_payee=payee_raw.strip(),
            amount_cents=amount_cents,
            notes=notes_raw.strip() if notes_raw else None,
            cleared=True,
            import_hash=import_hash
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)

        split = TransactionSplit(
            transaction_id=tx.id,
            category_id=None,
            amount_cents=amount_cents,
            notes=tx.notes
        )
        session.add(split)

        # 1. Deterministic Priority Rules
        matched = run_rules_on_transaction(tx, rules, session)
        if matched:
            rules_applied_count += 1
        else:
            # 2. Probabilistic ML Classifier (US-3.3)
            ml_res = ml_categorizer.predict(tx.raw_payee, session)
            if ml_res["is_high_confidence"] and ml_res["suggested_category_id"]:
                split.category_id = ml_res["suggested_category_id"]
                tx.is_ml_suggested = True
                tx.ml_confidence = ml_res["confidence"]
                session.add(tx)
                session.add(split)

        session.commit()
        inserted_count += 1

    return {
        "inserted_count": inserted_count,
        "duplicate_count": duplicate_count,
        "rules_applied_count": rules_applied_count
    }

def parse_qfx_ofx(file_content_str: str) -> List[Dict[str, Any]]:
    raw_content = file_content_str
    trn_blocks = re.findall(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|$)", raw_content, re.DOTALL | re.IGNORECASE)
    
    parsed_transactions = []
    for block in trn_blocks:
        def get_tag_value(tag_name: str) -> Optional[str]:
            match = re.search(rf"<{tag_name}>([^<\r\n]+)", block, re.IGNORECASE)
            if match:
                return match.group(1).strip()
            return None

        dtposted = get_tag_value("DTPOSTED")
        trnamt = get_tag_value("TRNAMT")
        fitid = get_tag_value("FITID")
        name = get_tag_value("NAME") or get_tag_value("PAYEE")
        memo = get_tag_value("MEMO")

        if not dtposted or not trnamt:
            continue

        date_digits = re.sub(r"\D", "", dtposted)[:8]
        if len(date_digits) == 8:
            formatted_date = f"{date_digits[:4]}-{date_digits[4:6]}-{date_digits[6:8]}"
        else:
            formatted_date = datetime.date.today().isoformat()

        amount_cents = parse_amount_str_to_cents(trnamt)
        payee = name or memo or "QFX Transaction"

        parsed_transactions.append({
            "date": formatted_date,
            "raw_payee": payee,
            "amount_cents": amount_cents,
            "fitid": fitid,
            "notes": memo if name and memo != name else None
        })

    return parsed_transactions

def process_qfx_import(
    file_content_str: str,
    account_id: uuid.UUID,
    skip_duplicates: bool,
    session: Session
) -> Dict[str, Any]:
    account = session.get(Account, account_id)
    if not account:
        raise ValueError("Account not found")

    parsed_txs = parse_qfx_ofx(file_content_str)
    rules = session.exec(select(Rule).where(Rule.is_active == True).order_by(Rule.priority)).all()

    inserted_count = 0
    duplicate_count = 0
    rules_applied_count = 0

    for item in parsed_txs:
        parsed_date = datetime.date.fromisoformat(item["date"])
        amount_cents = item["amount_cents"]
        raw_payee = item["raw_payee"]

        import_hash = compute_import_hash(account_id, parsed_date, amount_cents, raw_payee)
        existing = session.exec(select(Transaction).where(Transaction.import_hash == import_hash)).first()
        if existing:
            duplicate_count += 1
            if skip_duplicates:
                continue

        tx = Transaction(
            account_id=account_id,
            date=parsed_date,
            raw_payee=raw_payee,
            normalized_payee=raw_payee,
            amount_cents=amount_cents,
            notes=item.get("notes"),
            cleared=True,
            import_hash=import_hash
        )
        session.add(tx)
        session.commit()
        session.refresh(tx)

        split = TransactionSplit(
            transaction_id=tx.id,
            category_id=None,
            amount_cents=amount_cents,
            notes=tx.notes
        )
        session.add(split)

        matched = run_rules_on_transaction(tx, rules, session)
        if matched:
            rules_applied_count += 1
        else:
            ml_res = ml_categorizer.predict(tx.raw_payee, session)
            if ml_res["is_high_confidence"] and ml_res["suggested_category_id"]:
                split.category_id = ml_res["suggested_category_id"]
                tx.is_ml_suggested = True
                tx.ml_confidence = ml_res["confidence"]
                session.add(tx)
                session.add(split)

        session.commit()
        inserted_count += 1

    return {
        "inserted_count": inserted_count,
        "duplicate_count": duplicate_count,
        "rules_applied_count": rules_applied_count
    }
