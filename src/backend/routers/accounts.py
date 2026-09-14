from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
import uuid

from ..database import get_session
from ..models import Account, AccountType, Transaction

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])

class AccountCreate(SQLModel if False else object):
    pass

# We will use Pydantic / SQLModel schemas for requests/responses
from pydantic import BaseModel
from datetime import date, datetime

class AccountCreateRequest(BaseModel):
    name: str
    type: AccountType
    currency: str = "USD"
    opening_balance_cents: int = 0
    opening_date: date
    is_closed: bool = False

class AccountUpdateRequest(BaseModel):
    name: Optional[str] = None
    type: Optional[AccountType] = None
    currency: Optional[str] = None
    opening_balance_cents: Optional[int] = None
    opening_date: Optional[date] = None
    is_closed: Optional[bool] = None

class AccountResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: AccountType
    currency: str
    opening_balance_cents: int
    opening_date: date
    is_closed: bool
    created_at: datetime
    current_balance_cents: int
    transaction_count: int

@router.get("", response_model=List[AccountResponse])
def list_accounts(
    include_closed: bool = Query(False, description="Include archived/closed accounts"),
    session: Session = Depends(get_session)
):
    query = select(Account)
    if not include_closed:
        query = query.where(Account.is_closed == False)
    
    accounts = session.exec(query).all()
    result = []
    for account in accounts:
        # Sum of transaction amounts
        tx_sum_query = select(func.coalesce(func.sum(Transaction.amount_cents), 0), func.count(Transaction.id))\
            .where(Transaction.account_id == account.id)
        sum_res, count_res = session.exec(tx_sum_query).one()
        current_balance = account.opening_balance_cents + sum_res
        
        result.append(AccountResponse(
            id=account.id,
            name=account.name,
            type=account.type,
            currency=account.currency,
            opening_balance_cents=account.opening_balance_cents,
            opening_date=account.opening_date,
            is_closed=account.is_closed,
            created_at=account.created_at,
            current_balance_cents=current_balance,
            transaction_count=count_res
        ))
    return result

@router.post("", response_model=AccountResponse, status_code=210 if False else 201)
def create_account(
    req: AccountCreateRequest,
    session: Session = Depends(get_session)
):
    account = Account(
        name=req.name,
        type=req.type,
        currency=req.currency,
        opening_balance_cents=req.opening_balance_cents,
        opening_date=req.opening_date,
        is_closed=req.is_closed
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    
    return AccountResponse(
        id=account.id,
        name=account.name,
        type=account.type,
        currency=account.currency,
        opening_balance_cents=account.opening_balance_cents,
        opening_date=account.opening_date,
        is_closed=account.is_closed,
        created_at=account.created_at,
        current_balance_cents=account.opening_balance_cents,
        transaction_count=0
    )

@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    tx_sum_query = select(func.coalesce(func.sum(Transaction.amount_cents), 0), func.count(Transaction.id))\
        .where(Transaction.account_id == account.id)
    sum_res, count_res = session.exec(tx_sum_query).one()
    
    return AccountResponse(
        id=account.id,
        name=account.name,
        type=account.type,
        currency=account.currency,
        opening_balance_cents=account.opening_balance_cents,
        opening_date=account.opening_date,
        is_closed=account.is_closed,
        created_at=account.created_at,
        current_balance_cents=account.opening_balance_cents + sum_res,
        transaction_count=count_res
    )

@router.patch("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: uuid.UUID,
    req: AccountUpdateRequest,
    session: Session = Depends(get_session)
):
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
        
    update_data = req.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(account, key, value)
        
    session.add(account)
    session.commit()
    session.refresh(account)
    
    tx_sum_query = select(func.coalesce(func.sum(Transaction.amount_cents), 0), func.count(Transaction.id))\
        .where(Transaction.account_id == account.id)
    sum_res, count_res = session.exec(tx_sum_query).one()
    
    return AccountResponse(
        id=account.id,
        name=account.name,
        type=account.type,
        currency=account.currency,
        opening_balance_cents=account.opening_balance_cents,
        opening_date=account.opening_date,
        is_closed=account.is_closed,
        created_at=account.created_at,
        current_balance_cents=account.opening_balance_cents + sum_res,
        transaction_count=count_res
    )

@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # Check if transaction exists
    count = session.exec(select(func.count(Transaction.id)).where(Transaction.account_id == account_id)).one()
    if count > 0:
        raise HTTPException(status_code=400, detail="Cannot delete account with existing transactions. Archive (close) the account instead.")
        
    session.delete(account)
    session.commit()
    return None
