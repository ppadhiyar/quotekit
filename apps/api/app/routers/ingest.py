from fastapi import APIRouter, Header, HTTPException, UploadFile

from ..core import access, ingestion, search
from ..schemas import IngestResult

router = APIRouter(tags=["ingestion"])

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # free-tier index is 50 MB total — keep uploads small


@router.post("/ingest", response_model=IngestResult)
async def ingest(
    file: UploadFile,
    x_admin_key: str | None = Header(default=None),
) -> IngestResult:
    if not access.is_admin(x_admin_key):
        raise HTTPException(401, "Ingestion requires the X-Admin-Key header")

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
