from typing import List, Optional, Dict, Any
import datetime as dt
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, or_, and_
from pydantic import BaseModel, Field
import uuid

from ..database import get_session
from ..models import Transaction, TransactionSplit, Account, Category
from ..services.ml_engine import ml_categorizer

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

class SplitInput(BaseModel):
    category_id: Optional[uuid.UUID] = None
    amount_cents: int
    notes: Optional[str] = None

class TransactionCreateRequest(BaseModel):
    account_id: uuid.UUID
    date: dt.date
    raw_payee: str
    normalized_payee: Optional[str] = None
    amount_cents: int
    notes: Optional[str] = None
    cleared: bool = True
    category_id: Optional[uuid.UUID] = None
    splits: Optional[List[SplitInput]] = None

class TransactionUpdateRequest(BaseModel):
    account_id: Optional[uuid.UUID] = None
    date: Optional[dt.date] = None
    raw_payee: Optional[str] = None
    normalized_payee: Optional[str] = None
    amount_cents: Optional[int] = None
    notes: Optional[str] = None
    cleared: Optional[bool] = None
    category_id: Optional[uuid.UUID] = None
    splits: Optional[List[SplitInput]] = None

class ConfirmCategoryRequest(BaseModel):
    category_id: Optional[uuid.UUID] = None

class SplitResponse(BaseModel):
    id: uuid.UUID
    transaction_id: uuid.UUID
    category_id: Optional[uuid.UUID]
    category_name: Optional[str]
    amount_cents: int
    notes: Optional[str]

class TransactionResponse(BaseModel):
    id: uuid.UUID
    account_id: uuid.UUID
    account_name: Optional[str]
    date: dt.date
    raw_payee: str
    normalized_payee: Optional[str]
    amount_cents: int
    notes: Optional[str]
    cleared: bool
    import_hash: Optional[str]
    is_ml_suggested: bool
    ml_confidence: Optional[float]
    created_at: dt.datetime
    is_split: bool
    splits: List[SplitResponse]

@router.get("", response_model=List[TransactionResponse])
def list_transactions(
    account_id: Optional[uuid.UUID] = Query(None, description="Filter by account ID; omit for All Accounts"),
    start_date: Optional[dt.date] = Query(None),
    end_date: Optional[dt.date] = Query(None),
    category_id: Optional[uuid.UUID] = Query(None),
    search: Optional[str] = Query(None),
    cleared: Optional[bool] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: Session = Depends(get_session)
):
    query = select(Transaction)
    
    if account_id:
        query = query.where(Transaction.account_id == account_id)
    if start_date:
        query = query.where(Transaction.date >= start_date)
    if end_date:
        query = query.where(Transaction.date <= end_date)
    if cleared is not None:
        query = query.where(Transaction.cleared == cleared)
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                Transaction.raw_payee.ilike(search_pattern),
                Transaction.normalized_payee.ilike(search_pattern),
                Transaction.notes.ilike(search_pattern)
            )
        )
    if category_id:
        query = query.join(TransactionSplit).where(TransactionSplit.category_id == category_id).distinct()
        
    query = query.order_by(Transaction.date.desc(), Transaction.created_at.desc()).offset(offset).limit(limit)
    transactions = session.exec(query).all()
    
    accounts = {a.id: a.name for a in session.exec(select(Account)).all()}
    categories = {c.id: c.name for c in session.exec(select(Category)).all()}
    
    result = []
    for tx in transactions:
        splits_query = select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)
        tx_splits = session.exec(splits_query).all()
        
        split_responses = [
            SplitResponse(
                id=s.id,
                transaction_id=s.transaction_id,
                category_id=s.category_id,
                category_name=categories.get(s.category_id) if s.category_id else None,
                amount_cents=s.amount_cents,
                notes=s.notes
            ) for s in tx_splits
        ]
        
        result.append(TransactionResponse(
            id=tx.id,
            account_id=tx.account_id,
            account_name=accounts.get(tx.account_id),
            date=tx.date,
            raw_payee=tx.raw_payee,
            normalized_payee=tx.normalized_payee,
            amount_cents=tx.amount_cents,
            notes=tx.notes,
            cleared=tx.cleared,
            import_hash=tx.import_hash,
            is_ml_suggested=tx.is_ml_suggested,
            ml_confidence=tx.ml_confidence,
            created_at=tx.created_at,
            is_split=len(tx_splits) > 1,
            splits=split_responses
        ))
        
    return result

@router.post("", response_model=TransactionResponse, status_code=201)
def create_transaction(
    req: TransactionCreateRequest,
    session: Session = Depends(get_session)
):
    account = session.get(Account, req.account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    if req.splits and len(req.splits) > 0:
        split_sum = sum(s.amount_cents for s in req.splits)
        if split_sum != req.amount_cents:
            raise HTTPException(
                status_code=400,
                detail=f"Split amounts sum ({split_sum}) must equal transaction amount ({req.amount_cents})"
            )
        splits_to_create = req.splits
    else:
        splits_to_create = [SplitInput(category_id=req.category_id, amount_cents=req.amount_cents, notes=req.notes)]

    for s in splits_to_create:
        if s.category_id:
            cat = session.get(Category, s.category_id)
            if not cat:
                raise HTTPException(status_code=404, detail=f"Category {s.category_id} not found")

    tx = Transaction(
        account_id=req.account_id,
        date=req.date,
        raw_payee=req.raw_payee,
        normalized_payee=req.normalized_payee or req.raw_payee,
        amount_cents=req.amount_cents,
        notes=req.notes,
        cleared=req.cleared
    )
    session.add(tx)
    session.commit()
    session.refresh(tx)
    
    created_splits = []
    for s in splits_to_create:
        split_obj = TransactionSplit(
            transaction_id=tx.id,
            category_id=s.category_id,
            amount_cents=s.amount_cents,
            notes=s.notes
        )
        session.add(split_obj)
        created_splits.append(split_obj)
        
    session.commit()
    for s in created_splits:
        session.refresh(s)
        
    categories = {c.id: c.name for c in session.exec(select(Category)).all()}

    # Trigger ML retraining if categorized manually
    if any(s.category_id for s in created_splits):
        ml_categorizer.train(session)

    return TransactionResponse(
        id=tx.id,
        account_id=tx.account_id,
        account_name=account.name,
        date=tx.date,
        raw_payee=tx.raw_payee,
        normalized_payee=tx.normalized_payee,
        amount_cents=tx.amount_cents,
        notes=tx.notes,
        cleared=tx.cleared,
        import_hash=tx.import_hash,
        is_ml_suggested=tx.is_ml_suggested,
        ml_confidence=tx.ml_confidence,
        created_at=tx.created_at,
        is_split=len(created_splits) > 1,
        splits=[
            SplitResponse(
                id=s.id,
                transaction_id=s.transaction_id,
                category_id=s.category_id,
                category_name=categories.get(s.category_id) if s.category_id else None,
                amount_cents=s.amount_cents,
                notes=s.notes
            ) for s in created_splits
        ]
    )

@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    tx = session.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    account = session.get(Account, tx.account_id)
    splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
    categories = {c.id: c.name for c in session.exec(select(Category)).all()}
    
    return TransactionResponse(
        id=tx.id,
        account_id=tx.account_id,
        account_name=account.name if account else None,
        date=tx.date,
        raw_payee=tx.raw_payee,
        normalized_payee=tx.normalized_payee,
        amount_cents=tx.amount_cents,
        notes=tx.notes,
        cleared=tx.cleared,
        import_hash=tx.import_hash,
        is_ml_suggested=tx.is_ml_suggested,
        ml_confidence=tx.ml_confidence,
        created_at=tx.created_at,
        is_split=len(splits) > 1,
        splits=[
            SplitResponse(
                id=s.id,
                transaction_id=s.transaction_id,
                category_id=s.category_id,
                category_name=categories.get(s.category_id) if s.category_id else None,
                amount_cents=s.amount_cents,
                notes=s.notes
            ) for s in splits
        ]
    )

@router.patch("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: uuid.UUID,
    req: TransactionUpdateRequest,
    session: Session = Depends(get_session)
):
    tx = session.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    if req.account_id is not None:
        acc = session.get(Account, req.account_id)
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
            
    new_amount = req.amount_cents if req.amount_cents is not None else tx.amount_cents
    category_changed = False
    
    if req.splits is not None:
        category_changed = True
        if len(req.splits) > 0:
            split_sum = sum(s.amount_cents for s in req.splits)
            if split_sum != new_amount:
                raise HTTPException(
                    status_code=400,
                    detail=f"Split amounts sum ({split_sum}) must equal transaction amount ({new_amount})"
                )
            splits_to_update = req.splits
        else:
            splits_to_update = [SplitInput(category_id=None, amount_cents=new_amount, notes=req.notes or tx.notes)]
            
        old_splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
        for os in old_splits:
            session.delete(os)
        session.commit()
        
        for s in splits_to_update:
            if s.category_id:
                cat = session.get(Category, s.category_id)
                if not cat:
                    raise HTTPException(status_code=404, detail=f"Category {s.category_id} not found")
            split_obj = TransactionSplit(
                transaction_id=tx.id,
                category_id=s.category_id,
                amount_cents=s.amount_cents,
                notes=s.notes
            )
            session.add(split_obj)
    elif req.category_id is not None or req.amount_cents is not None:
        splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
        if req.category_id is not None:
            cat = session.get(Category, req.category_id)
            if not cat:
                raise HTTPException(status_code=404, detail=f"Category {req.category_id} not found")
            category_changed = True

        if len(splits) == 1:
            if req.amount_cents is not None:
                splits[0].amount_cents = req.amount_cents
            if req.category_id is not None:
                splits[0].category_id = req.category_id
            session.add(splits[0])
        elif len(splits) == 0:
            split_obj = TransactionSplit(
                transaction_id=tx.id,
                category_id=req.category_id,
                amount_cents=new_amount,
                notes=req.notes or tx.notes
            )
            session.add(split_obj)
        else:
            split_sum = sum(s.amount_cents for s in splits)
            if req.amount_cents is not None and split_sum != req.amount_cents:
                raise HTTPException(
                    status_code=400,
                    detail=f"Updated amount ({req.amount_cents}) does not match existing split total ({split_sum}). Please provide updated splits."
                )
            if req.category_id is not None:
                old_splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
                for os in old_splits:
                    session.delete(os)
                session.commit()
                split_obj = TransactionSplit(
                    transaction_id=tx.id,
                    category_id=req.category_id,
                    amount_cents=new_amount,
                    notes=req.notes or tx.notes
                )
                session.add(split_obj)

    update_data = req.model_dump(exclude_unset=True, exclude={"splits", "category_id"})
    for k, v in update_data.items():
        setattr(tx, k, v)
        
    if category_changed:
        tx.is_ml_suggested = False
        tx.ml_confidence = None

    session.add(tx)
    session.commit()
    session.refresh(tx)

    # Retrain ML model if confirmed or updated manually
    if category_changed or not tx.is_ml_suggested:
        ml_categorizer.train(session)
    
    return get_transaction(tx.id, session=session)

@router.post("/{transaction_id}/confirm-category", response_model=TransactionResponse)
def confirm_category(
    transaction_id: uuid.UUID,
    req: Optional[ConfirmCategoryRequest] = None,
    session: Session = Depends(get_session)
):
    tx = session.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
    
    if req and req.category_id:
        cat = session.get(Category, req.category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Category not found")
        if splits:
            splits[0].category_id = req.category_id
            session.add(splits[0])

    # Clear ML suggestion flag and confidence
    tx.is_ml_suggested = False
    tx.ml_confidence = None
    session.add(tx)
    session.commit()
    session.refresh(tx)

    # Retrain ML model in background
    ml_categorizer.train(session)

    return get_transaction(tx.id, session=session)

@router.get("/{transaction_id}/suggestions")
def get_transaction_suggestions(
    transaction_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    tx = session.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    prediction = ml_categorizer.predict(tx.raw_payee, session)
    return {
        "transaction_id": tx.id,
        "raw_payee": tx.raw_payee,
        "suggestions": prediction["top_suggestions"]
    }

@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(
    transaction_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    tx = session.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
        
    splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
    for s in splits:
        session.delete(s)
        
    session.delete(tx)
    session.commit()
    return None
