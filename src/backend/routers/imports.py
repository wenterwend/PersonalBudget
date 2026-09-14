from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlmodel import Session
from pydantic import BaseModel
import uuid

from ..database import get_session
from ..services.ingestion import parse_csv_preview, process_csv_import, process_qfx_import

router = APIRouter(prefix="/api/imports", tags=["Imports"])

class CSVProcessRequest(BaseModel):
    account_id: uuid.UUID
    file_content: str
    date_col: str
    payee_col: str
    amount_col: Optional[str] = None
    debit_col: Optional[str] = None
    credit_col: Optional[str] = None
    notes_col: Optional[str] = None
    date_format: Optional[str] = None
    skip_duplicates: bool = True

class QFXProcessRequest(BaseModel):
    account_id: uuid.UUID
    file_content: str
    skip_duplicates: bool = True

class CSVPreviewResponse(BaseModel):
    headers: List[str]
    sample_rows: List[Dict[str, str]]

class ImportSummaryResponse(BaseModel):
    inserted_count: int
    duplicate_count: int
    rules_applied_count: int

@router.post("/csv/preview", response_model=CSVPreviewResponse)
async def preview_csv_file(file: UploadFile = File(...)):
    if not file.filename.endswith((".csv", ".txt")):
        raise HTTPException(status_code=400, detail="Only .csv and .txt files are supported for CSV import")

    content_bytes = await file.read()
    try:
        content_str = content_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        content_str = content_bytes.decode("latin-1")

    res = parse_csv_preview(content_str)
    return CSVPreviewResponse(headers=res["headers"], sample_rows=res["sample_rows"])

@router.post("/csv/process", response_model=ImportSummaryResponse)
def process_csv_file(
    req: CSVProcessRequest,
    session: Session = Depends(get_session)
):
    try:
        res = process_csv_import(
            file_content_str=req.file_content,
            account_id=req.account_id,
            date_col=req.date_col,
            payee_col=req.payee_col,
            amount_col=req.amount_col,
            debit_col=req.debit_col,
            credit_col=req.credit_col,
            notes_col=req.notes_col,
            date_format=req.date_format,
            skip_duplicates=req.skip_duplicates,
            session=session
        )
        return ImportSummaryResponse(
            inserted_count=res["inserted_count"],
            duplicate_count=res["duplicate_count"],
            rules_applied_count=res["rules_applied_count"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/qfx/process", response_model=ImportSummaryResponse)
def process_qfx_file(
    req: QFXProcessRequest,
    session: Session = Depends(get_session)
):
    try:
        res = process_qfx_import(
            file_content_str=req.file_content,
            account_id=req.account_id,
            skip_duplicates=req.skip_duplicates,
            session=session
        )
        return ImportSummaryResponse(
            inserted_count=res["inserted_count"],
            duplicate_count=res["duplicate_count"],
            rules_applied_count=res["rules_applied_count"]
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
