from fastapi import APIRouter, Depends
from sqlmodel import Session
from pydantic import BaseModel

from ..database import get_session
from ..services.ml_engine import ml_categorizer

router = APIRouter(prefix="/api/ml", tags=["Machine Learning"])

class MLStatusResponse(BaseModel):
    is_trained: bool
    classes_count: int

@router.get("/status", response_model=MLStatusResponse)
def get_ml_status():
    return MLStatusResponse(
        is_trained=ml_categorizer.is_trained,
        classes_count=len(ml_categorizer.classes_) if ml_categorizer.is_trained else 0
    )

@router.post("/retrain")
def retrain_ml_model(session: Session = Depends(get_session)):
    success = ml_categorizer.train(session)
    return {
        "status": "ok" if success else "insufficient_data",
        "is_trained": ml_categorizer.is_trained,
        "classes_count": len(ml_categorizer.classes_) if ml_categorizer.is_trained else 0
    }
