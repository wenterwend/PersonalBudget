import json
import datetime
from typing import List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
import uuid

from ..database import get_session
from ..models import SavedQuery, Category, Account, TransactionSplit
from ..services.query_builder import execute_ast_query

router = APIRouter(prefix="/api/queries/saved", tags=["Saved Queries"])

class SavedQueryCreateRequest(BaseModel):
    name: str
    description: Optional[str] = None
    query_ast: Any  # dict or list representation of AST

class SavedQueryUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    query_ast: Optional[Any] = None

class SavedQueryResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    query_ast: Any
    created_at: datetime.datetime
    updated_at: datetime.datetime

@router.get("", response_model=List[SavedQueryResponse])
def list_saved_queries(session: Session = Depends(get_session)):
    queries = session.exec(select(SavedQuery).order_by(SavedQuery.name)).all()
    res = []
    for q in queries:
        try:
            ast_data = json.loads(q.query_ast)
        except Exception:
            ast_data = q.query_ast
        res.append(SavedQueryResponse(
            id=q.id,
            name=q.name,
            description=q.description,
            query_ast=ast_data,
            created_at=q.created_at,
            updated_at=q.updated_at
        ))
    return res

@router.post("", response_model=SavedQueryResponse, status_code=201)
def create_saved_query(
    req: SavedQueryCreateRequest,
    session: Session = Depends(get_session)
):
    existing = session.exec(select(SavedQuery).where(SavedQuery.name == req.name.strip())).first()
    if existing:
        raise HTTPException(status_code=400, detail="Saved query with this name already exists")

    ast_str = json.dumps(req.query_ast) if isinstance(req.query_ast, (dict, list)) else str(req.query_ast)

    sq = SavedQuery(
        name=req.name.strip(),
        description=req.description.strip() if req.description else None,
        query_ast=ast_str
    )
    session.add(sq)
    session.commit()
    session.refresh(sq)

    return SavedQueryResponse(
        id=sq.id,
        name=sq.name,
        description=sq.description,
        query_ast=req.query_ast,
        created_at=sq.created_at,
        updated_at=sq.updated_at
    )

@router.get("/{query_id}", response_model=SavedQueryResponse)
def get_saved_query(
    query_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    sq = session.get(SavedQuery, query_id)
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")

    try:
        ast_data = json.loads(sq.query_ast)
    except Exception:
        ast_data = sq.query_ast

    return SavedQueryResponse(
        id=sq.id,
        name=sq.name,
        description=sq.description,
        query_ast=ast_data,
        created_at=sq.created_at,
        updated_at=sq.updated_at
    )

@router.patch("/{query_id}", response_model=SavedQueryResponse)
def update_saved_query(
    query_id: uuid.UUID,
    req: SavedQueryUpdateRequest,
    session: Session = Depends(get_session)
):
    sq = session.get(SavedQuery, query_id)
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")

    if req.name and req.name.strip() != sq.name:
        existing = session.exec(select(SavedQuery).where(SavedQuery.name == req.name.strip())).first()
        if existing and existing.id != query_id:
            raise HTTPException(status_code=400, detail="Another saved query with this name already exists")
        sq.name = req.name.strip()

    if req.description is not None:
        sq.description = req.description.strip() if req.description else None

    if req.query_ast is not None:
        sq.query_ast = json.dumps(req.query_ast) if isinstance(req.query_ast, (dict, list)) else str(req.query_ast)

    sq.updated_at = datetime.datetime.utcnow()
    session.add(sq)
    session.commit()
    session.refresh(sq)

    try:
        ast_data = json.loads(sq.query_ast)
    except Exception:
        ast_data = sq.query_ast

    return SavedQueryResponse(
        id=sq.id,
        name=sq.name,
        description=sq.description,
        query_ast=ast_data,
        created_at=sq.created_at,
        updated_at=sq.updated_at
    )

@router.delete("/{query_id}", status_code=204)
def delete_saved_query(
    query_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    sq = session.get(SavedQuery, query_id)
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")

    session.delete(sq)
    session.commit()
    return None

@router.post("/{query_id}/execute")
def execute_saved_query(
    query_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    sq = session.get(SavedQuery, query_id)
    if not sq:
        raise HTTPException(status_code=404, detail="Saved query not found")

    try:
        ast_data = json.loads(sq.query_ast)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid AST JSON: {str(e)}")

    results = execute_ast_query(session, ast_data)
    accounts = {a.id: a.name for a in session.exec(select(Account)).all()}
    categories = {c.id: c.name for c in session.exec(select(Category)).all()}

    output = []
    for tx in results:
        splits = session.exec(select(TransactionSplit).where(TransactionSplit.transaction_id == tx.id)).all()
        split_dicts = [
            {
                "id": str(s.id),
                "category_id": str(s.category_id) if s.category_id else None,
                "category_name": categories.get(s.category_id) if s.category_id else None,
                "amount_cents": s.amount_cents,
                "notes": s.notes
            } for s in splits
        ]
        output.append({
            "id": str(tx.id),
            "account_id": str(tx.account_id),
            "account_name": accounts.get(tx.account_id),
            "date": tx.date.isoformat(),
            "raw_payee": tx.raw_payee,
            "normalized_payee": tx.normalized_payee,
            "amount_cents": tx.amount_cents,
            "notes": tx.notes,
            "cleared": tx.cleared,
            "splits": split_dicts
        })
    return output
