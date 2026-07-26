from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from app.core.logging import get_logger
from app.ingestion.loaders.base import LoadedDocument, build_metadata

logger = get_logger(__name__)


def _extract_with_pypdf(file_path: Path) -> str:
    reader = PdfReader(str(file_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def _extract_tables(file_path: Path) -> str:
    table_blocks: list[str] = []
    with pdfplumber.open(file_path) as pdf:
        for page_index, page in enumerate(pdf.pages, start=1):
            tables = page.extract_tables() or []
            for table_index, table in enumerate(tables, start=1):
                rows = []
                for row in table:
                    cells = [cell.strip() if cell else "" for cell in row]
                    if any(cells):
                        rows.append(" | ".join(cells))
                if rows:
                    table_blocks.append(
                        f"[Table page {page_index} table {table_index}]\n" + "\n".join(rows)
                    )
    return "\n\n".join(table_blocks)


def load_pdf(file_path: Path, data_root: Path) -> LoadedDocument:
    metadata = build_metadata(file_path, data_root)
    body = _extract_with_pypdf(file_path)
    tables = _extract_tables(file_path)

    sections = [section for section in (body, tables) if section.strip()]
    if not sections:
        logger.warning("No extractable text in PDF: %s", file_path)
    text = "\n\n".join(sections)
    return LoadedDocument(metadata=metadata, text=text)
