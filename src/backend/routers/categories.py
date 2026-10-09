from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select
from pydantic import BaseModel
import uuid

from ..database import get_session
from ..models import CategoryGroup, Category

router = APIRouter(prefix="/api/categories", tags=["Categories"])

class CategoryGroupCreate(BaseModel):
    name: str
    display_order: int = 0

class CategoryGroupResponse(BaseModel):
    id: uuid.UUID
    name: str
    display_order: int
    categories: List["CategoryResponse"] = []

class CategoryCreate(BaseModel):
    group_id: uuid.UUID
    name: str
    is_income: bool = False
    is_fixed: bool = False
    is_archived: bool = False

class CategoryUpdate(BaseModel):
    group_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    is_income: Optional[bool] = None
    is_fixed: Optional[bool] = None
    is_archived: Optional[bool] = None

class CategoryResponse(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    name: str
    is_income: bool
    is_fixed: bool
    is_archived: bool

CategoryGroupResponse.model_rebuild()

@router.get("/groups", response_model=List[CategoryGroupResponse])
def list_category_groups(
    include_archived: bool = Query(False),
    session: Session = Depends(get_session)
):
    groups = session.exec(select(CategoryGroup).order_by(CategoryGroup.display_order, CategoryGroup.name)).all()
    result = []
    for g in groups:
        cat_query = select(Category).where(Category.group_id == g.id)
        if not include_archived:
            cat_query = cat_query.where(Category.is_archived == False)
        categories = session.exec(cat_query.order_by(Category.name)).all()
        
        result.append(CategoryGroupResponse(
            id=g.id,
            name=g.name,
            display_order=g.display_order,
            categories=[CategoryResponse(
                id=c.id,
                group_id=c.group_id,
                name=c.name,
                is_income=c.is_income,
                is_fixed=c.is_fixed,
                is_archived=c.is_archived
            ) for c in categories]
        ))
    return result

@router.post("/groups", response_model=CategoryGroupResponse, status_code=201)
def create_category_group(
    req: CategoryGroupCreate,
    session: Session = Depends(get_session)
):
    # Check duplicate
    existing = session.exec(select(CategoryGroup).where(CategoryGroup.name == req.name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category group with this name already exists")
        
    group = CategoryGroup(name=req.name, display_order=req.display_order)
    session.add(group)
    session.commit()
    session.refresh(group)
    return CategoryGroupResponse(
        id=group.id,
        name=group.name,
        display_order=group.display_order,
        categories=[]
    )

@router.get("", response_model=List[CategoryResponse])
def list_categories(
    include_archived: bool = Query(False),
    session: Session = Depends(get_session)
):
    query = select(Category)
    if not include_archived:
        query = query.where(Category.is_archived == False)
    categories = session.exec(query.order_by(Category.name)).all()
    return [
        CategoryResponse(
            id=c.id,
            group_id=c.group_id,
            name=c.name,
            is_income=c.is_income,
            is_fixed=c.is_fixed,
            is_archived=c.is_archived
        ) for c in categories
    ]

@router.post("", response_model=CategoryResponse, status_code=201)
def create_category(
    req: CategoryCreate,
    session: Session = Depends(get_session)
):
    group = session.get(CategoryGroup, req.group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Category group not found")
        
    category = Category(
        group_id=req.group_id,
        name=req.name,
        is_income=req.is_income,
        is_fixed=req.is_fixed,
        is_archived=req.is_archived
    )
    session.add(category)
    session.commit()
    session.refresh(category)
    return CategoryResponse(
        id=category.id,
        group_id=category.group_id,
        name=category.name,
        is_income=category.is_income,
        is_fixed=category.is_fixed,
        is_archived=category.is_archived
    )

@router.patch("/{category_id}", response_model=CategoryResponse)
def update_category(
    category_id: uuid.UUID,
    req: CategoryUpdate,
    session: Session = Depends(get_session)
):
    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
        
    if req.group_id is not None:
        group = session.get(CategoryGroup, req.group_id)
        if not group:
            raise HTTPException(status_code=404, detail="Category group not found")
            
    update_data = req.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(category, k, v)
        
    session.add(category)
    session.commit()
    session.refresh(category)
    return CategoryResponse(
        id=category.id,
        group_id=category.group_id,
        name=category.name,
        is_income=category.is_income,
        is_fixed=category.is_fixed,
        is_archived=category.is_archived
    )

@router.delete("/{category_id}")
def delete_or_archive_category(
    category_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    from sqlmodel import func
    from ..models import TransactionSplit, MonthlyBudget

    category = session.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Check if category is referenced in any TransactionSplit
    splits_count = session.exec(
        select(func.count()).select_from(TransactionSplit).where(TransactionSplit.category_id == category_id)
    ).one()

    if splits_count > 0:
        # Soft delete (archive) to preserve historical transactions
        category.is_archived = True
        session.add(category)
        session.commit()
        return {"status": "archived", "message": "Category has historical transactions and was archived."}
    else:
        # Hard delete category and any MonthlyBudget entries
        budgets = session.exec(select(MonthlyBudget).where(MonthlyBudget.category_id == category_id)).all()
        for b in budgets:
            session.delete(b)
        session.delete(category)
        session.commit()
        return {"status": "deleted", "message": "Category permanently deleted."}

class CategoryMergeRequest(BaseModel):
    target_category_id: uuid.UUID

@router.post("/{category_id}/merge")
def merge_categories(
    category_id: uuid.UUID,
    req: CategoryMergeRequest,
    session: Session = Depends(get_session)
):
    from ..models import TransactionSplit, Rule, MonthlyBudget
    
    if category_id == req.target_category_id:
        raise HTTPException(status_code=400, detail="Cannot merge category into itself")

    source_cat = session.get(Category, category_id)
    if not source_cat:
        raise HTTPException(status_code=404, detail="Source category not found")

    target_cat = session.get(Category, req.target_category_id)
    if not target_cat:
        raise HTTPException(status_code=404, detail="Target category not found")

    # 1. Reassign TransactionSplits
    source_splits = session.exec(
        select(TransactionSplit).where(TransactionSplit.category_id == category_id)
    ).all()
    for s in source_splits:
        s.category_id = target_cat.id
        session.add(s)

    # 2. Reassign Rules
    source_rules = session.exec(
        select(Rule).where(Rule.target_category_id == category_id)
    ).all()
    for r in source_rules:
        r.target_category_id = target_cat.id
        session.add(r)

    # 3. Merge MonthlyBudgets
    source_budgets = session.exec(
        select(MonthlyBudget).where(MonthlyBudget.category_id == category_id)
    ).all()
    for sb in source_budgets:
        target_b = session.exec(
            select(MonthlyBudget).where(
                MonthlyBudget.category_id == target_cat.id,
                MonthlyBudget.month == sb.month
            )
        ).first()
        if target_b:
            target_b.budgeted_cents += sb.budgeted_cents
            session.add(target_b)
            session.delete(sb)
        else:
            sb.category_id = target_cat.id
            session.add(sb)

    # 4. Delete source category
    session.delete(source_cat)
    session.commit()

    return {
        "status": "merged",
        "message": f"Category '{source_cat.name}' successfully merged into '{target_cat.name}'.",
        "source_category_id": category_id,
        "target_category_id": target_cat.id
    }

@router.delete("/groups/{group_id}")

def delete_category_group(
    group_id: uuid.UUID,
    session: Session = Depends(get_session)
):
    group = session.get(CategoryGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Category group not found")

    cats = session.exec(select(Category).where(Category.group_id == group_id)).all()
    if cats:
        raise HTTPException(status_code=400, detail="Cannot delete category group containing categories. Delete or move categories first.")

    session.delete(group)
    session.commit()
    return {"status": "deleted", "message": "Category group deleted."}
