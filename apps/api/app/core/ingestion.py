"""Document ingestion: normalize price lists (CSV/PDF) into indexable chunks.

Tabular data is the hard part of contractor price lists — a naive text split
destroys the row structure that maps items to prices. Each row becomes its own
chunk so a price can never be attributed to the wrong item.
"""

import csv
import io
import logging
import re
from uuid import uuid4

from ..config import get_settings

logger = logging.getLogger(__name__)


def chunks_from_csv(filename: str, raw: bytes) -> tuple[list[dict], list[str]]:
    """One chunk per row; the content string is what gets embedded."""
    warnings: list[str] = []
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
    chunks: list[dict] = []

    for i, row in enumerate(reader):
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
        item = row.get("item") or row.get("description") or row.get("name")
        price_raw = row.get("unit_price") or row.get("price") or row.get("rate")
        unit = row.get("unit") or "each"

        if not item or not price_raw:
            warnings.append(f"row {i + 2}: missing item or price, skipped")
            continue

        price_match = re.search(r"[\d,]+\.?\d*", price_raw)
        if not price_match:
            warnings.append(f"row {i + 2}: unparseable price '{price_raw}', skipped")
            continue
        unit_price = float(price_match.group().replace(",", ""))

        notes = row.get("notes", "")
        content = f"{item} — {unit_price:.2f} per {unit}" + (f". {notes}" if notes else "")
        chunks.append(
            {
                "chunk_id": str(uuid4()),
                "document": filename,
                "content": content,
                "item_name": item,
                "unit": unit,
                "unit_price": unit_price,
            }
        )
    return chunks, warnings


def chunks_from_pdf(filename: str, raw: bytes) -> tuple[list[dict], list[str]]:
    """PDF path: Azure Document Intelligence when configured (keeps tables
    intact), pypdf text extraction as the zero-cost fallback."""
    s = get_settings()
    if s.azure_docintel_endpoint and s.azure_docintel_api_key:
        return _chunks_via_document_intelligence(filename, raw)
    return _chunks_via_pypdf(filename, raw)


def _chunks_via_document_intelligence(filename: str, raw: bytes) -> tuple[list[dict], list[str]]:
    from azure.ai.documentintelligence import DocumentIntelligenceClient
    from azure.core.credentials import AzureKeyCredential

    s = get_settings()
    client = DocumentIntelligenceClient(
        endpoint=s.azure_docintel_endpoint,
        credential=AzureKeyCredential(s.azure_docintel_api_key),
    )
    poller = client.begin_analyze_document("prebuilt-layout", body=raw)
    result = poller.result()

    chunks: list[dict] = []
    warnings: list[str] = []

    # Tables: one chunk per row, headers prepended for context.
    for table in result.tables or []:
        headers = [c.content for c in table.cells if c.row_index == 0]
        rows: dict[int, list[str]] = {}
        for cell in table.cells:
            if cell.row_index == 0:
                continue
            rows.setdefault(cell.row_index, []).append(cell.content)
        for values in rows.values():
            paired = ", ".join(
                f"{h}: {v}" for h, v in zip(headers, values) if v
            ) or " | ".join(values)
            chunks.append(
                {
                    "chunk_id": str(uuid4()),
                    "document": filename,
                    "content": paired,
                    "item_name": values[0] if values else None,
                    "unit": None,
                    "unit_price": None,
                }
            )

    # Paragraph content outside tables (terms, notes, disclaimers).
    for para in result.paragraphs or []:
        text = para.content.strip()
        if len(text) > 40:
            chunks.append(
                {
                    "chunk_id": str(uuid4()),
                    "document": filename,
                    "content": text,
                    "item_name": None,
                    "unit": None,
                    "unit_price": None,
                }
            )

    if not chunks:
        warnings.append("Document Intelligence returned no tables or paragraphs")
    return chunks, warnings


def _chunks_via_pypdf(filename: str, raw: bytes) -> tuple[list[dict], list[str]]:
    from pypdf import PdfReader

    warnings = [
        (
            "Using pypdf fallback — table structure may be lossy. "
            "Configure Document Intelligence for production ingestion."
        )
    ]
    reader = PdfReader(io.BytesIO(raw))
    chunks: list[dict] = []
    for page_num, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        # Line-based chunking: price list lines are usually self-contained.
        for line in text.splitlines():
            line = line.strip()
            if len(line) > 15 and re.search(r"\d", line):
                # document stays the bare filename so replace-on-reupload can
                # match every chunk; the page marker lives in the content.
                chunks.append(
                    {
                        "chunk_id": str(uuid4()),
                        "document": filename,
                        "content": f"[page {page_num}] {line}",
                        "item_name": None,
                        "unit": None,
                        "unit_price": None,
                    }
                )
    return chunks, warnings
