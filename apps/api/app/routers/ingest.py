from fastapi import APIRouter, HTTPException, UploadFile

from ..config import get_settings
from ..core import ingestion, search
from ..schemas import IngestResult

router = APIRouter(tags=["ingestion"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # free-tier index is 50 MB total — keep uploads small


@router.post("/ingest", response_model=IngestResult)
async def ingest(file: UploadFile) -> IngestResult:
    if get_settings().demo_mode:
        raise HTTPException(403, "Ingestion is disabled in demo mode")

    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File exceeds {MAX_UPLOAD_BYTES // 1024 // 1024} MB limit")

    name = file.filename or "upload"
    if name.lower().endswith(".csv"):
        chunks, warnings = ingestion.chunks_from_csv(name, raw)
    elif name.lower().endswith(".pdf"):
        chunks, warnings = ingestion.chunks_from_pdf(name, raw)
    else:
        raise HTTPException(422, "Only .csv and .pdf files are supported")

    if not chunks:
        raise HTTPException(422, f"No indexable content found. Warnings: {warnings}")

    search.ensure_index()
    indexed = search.upsert_chunks(chunks)
    return IngestResult(document=name, chunks_indexed=indexed, warnings=warnings)
