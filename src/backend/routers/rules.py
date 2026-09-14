from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from pydantic import BaseModel
import uuid

from ..database import get_session
from ..models import Rule, MatchField, MatchType, AmountCondition, Category
from ..services.rule_engine import apply_rules_retroactively

router = APIRouter(prefix="/api/rules", tags=["Rules"])

class RuleCreateRequest(BaseModel):
    priority: int = 0
    match_field: MatchField = MatchField.RAW_PAYEE
    match_type: MatchType = MatchType.CONTAINS
    match_value: str
    amount_condition: AmountCondition = AmountCondition.ANY
    secondary_match_field: Optional[MatchField] = None
    secondary_match_type: Optional[MatchType] = None
    secondary_match_value: Optional[str] = None
    target_payee: Optional[str] = None
    target_category_id: Optional[uuid.UUID] = None
    is_active: bool = True

class RuleUpdateRequest(BaseModel):
    priority: Optional[int] = None
    match_field: Optional[MatchField] = None
    match_type: Optional[MatchType] = None
    match_value: Optional[str] = None
    amount_condition: Optional[AmountCondition] = None
    secondary_match_field: Optional[MatchField] = None
    secondary_match_type: Optional[MatchType] = None
    secondary_match_value: Optional[str] = None
    target_payee: Optional[str] = None
    target_category_id: Optional[uuid.UUID] = None
    is_active: Optional[bool] = None

class RuleResponse(BaseModel):
    id: uuid.UUID
    priority: int
    match_field: MatchField
    match_type: MatchType
    match_value: str
    amount_condition: AmountCondition
    secondary_match_field: Optional[MatchField]
    secondary_match_type: Optional[MatchType]
    secondary_match_value: Optional[str]
    target_payee: Optional[str]
    target_category_id: Optional[uuid.UUID]
    target_category_name: Optional[str]
    is_active: bool

@router.get("", response_model=List[RuleResponse])
def list_rules(session: Session = Depends(get_session)):
    rules = session.exec(select(Rule).order_by(Rule.priority, Rule.match_value)).all()
    categories = {c.id: c.name for c in session.exec(select(Category)).all()}
    
    return [
        RuleResponse(
            id=r.id,
            priority=r.priority,
            match_field=r.match_field,
            match_type=r.match_type,
            match_value=r.match_value,
            amount_condition=r.amount_condition,
            secondary_match_field=r.secondary_match_field,
            secondary_match_type=r.secondary_match_type,
            secondary_match_value=r.secondary_match_value,
            target_payee=r.target_payee,
            target_category_id=r.target_category_id,
            target_category_name=categories.get(r.target_category_id) if r.target_category_id else None,
            is_active=r.is_active
        ) for r in rules
    ]

@router.post("", response_model=RuleResponse, status_code=201)
def create_rule(
    req: RuleCreateRequest,
    apply_retroactive: bool = Query(False, description="Apply new rule to historical transactions immediately"),
    session: Session = Depends(get_session)
):
    if req.target_category_id:
        cat = session.get(Category, req.target_category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Target category not found")

    rule = Rule(
        priority=req.priority,
        match_field=req.match_field,
        match_type=req.match_type,
        match_value=req.match_value.strip(),
        amount_condition=req.amount_condition,
        secondary_match_field=req.secondary_match_field,
        secondary_match_type=req.secondary_match_type,
        secondary_match_value=req.secondary_match_value.strip() if req.secondary_match_value else None,
        target_payee=req.target_payee.strip() if req.target_payee else None,
        target_category_id=req.target_category_id,
        is_active=req.is_active
    )
    session.add(rule)
    session.commit()
    session.refresh(rule)

    if apply_retroactive and rule.is_active:
        apply_rules_retroactively(session, rule_id=rule.id)

    cat_name = None
    if rule.target_category_id:
        cat = session.get(Category, rule.target_category_id)
        cat_name = cat.name if cat else None

    return RuleResponse(
        id=rule.id,
        priority=rule.priority,
        match_field=rule.match_field,
        match_type=rule.match_type,
        match_value=rule.match_value,
        amount_condition=rule.amount_condition,
        secondary_match_field=rule.secondary_match_field,
        secondary_match_type=rule.secondary_match_type,
        secondary_match_value=rule.secondary_match_value,
        target_payee=rule.target_payee,
        target_category_id=rule.target_category_id,
        target_category_name=cat_name,
        is_active=rule.is_active
    )

@router.patch("/{rule_id}", response_model=RuleResponse)
def update_rule(
    rule_id: uuid.UUID,
    req: RuleUpdateRequest,
    apply_retroactive: bool = Query(False),
    session: Session = Depends(get_session)
):
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    if req.target_category_id is not None:
        cat = session.get(Category, req.target_category_id)
        if not cat:
            raise HTTPException(status_code=404, detail="Target category not found")

    update_data = req.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(rule, k, v)

    session.add(rule)
    session.commit()
    session.refresh(rule)

    if apply_retroactive and rule.is_active:
        apply_rules_retroactively(session, rule_id=rule.id)

    cat_name = None
    if rule.target_category_id:
        cat = session.get(Category, rule.target_category_id)
        cat_name = cat.name if cat else None

    return RuleResponse(
        id=rule.id,
        priority=rule.priority,
        match_field=rule.match_field,
        match_type=rule.match_type,
        match_value=rule.match_value,
        amount_condition=rule.amount_condition,
        secondary_match_field=rule.secondary_match_field,
        secondary_match_type=rule.secondary_match_type,
        secondary_match_value=rule.secondary_match_value,
        target_payee=rule.target_payee,
        target_category_id=rule.target_category_id,
        target_category_name=cat_name,
        is_active=rule.is_active
    )

@router.delete("/{rule_id}", status_code=204)
def delete_rule(
    rule_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    session.delete(rule)
    session.commit()
    return None

@router.post("/{rule_id}/apply")
def apply_single_rule(
    rule_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    rule = session.get(Rule, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")

    updated_count = apply_rules_retroactively(session, rule_id=rule.id)
    return {"status": "ok", "rule_id": rule_id, "updated_transactions_count": updated_count}

@router.post("/apply-all")
def apply_all_rules(session: Session = Depends(get_session)):
    updated_count = apply_rules_retroactively(session, rule_id=None)
    return {"status": "ok", "updated_transactions_count": updated_count}
