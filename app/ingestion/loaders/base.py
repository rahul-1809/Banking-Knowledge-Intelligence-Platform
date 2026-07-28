from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import re
import uuid


SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md", ".json"}


@dataclass
class DocumentMetadata:
    file_name: str
    category: str
    date_added: str
    doc_id: str
    source_path: str


@dataclass
class LoadedDocument:
    metadata: DocumentMetadata
    text: str


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "document"


# Ordered keyword -> category mapping used when the folder hierarchy is unavailable
_KEYWORD_CATEGORY_MAP: list[tuple[str, str]] = [
    # RBI
    ("RBI", "RBI"),
    # Compliance / AML / KYC
    ("AML", "COMPLIANCE"),
    ("SANCTION", "COMPLIANCE"),
    ("FRAUD", "COMPLIANCE"),
    ("KYC", "COMPLIANCE"),
    # Audit
    ("AUDIT", "AUDIT"),
    ("INSPECTION", "AUDIT"),
    ("OPERATIONAL_RISK", "AUDIT"),
    ("RISK_MATRIX", "AUDIT"),
    # Treasury
    ("TREASURY", "TREASURY"),
    ("ALM", "TREASURY"),
    ("LIQUIDITY", "TREASURY"),
    ("INVESTMENT", "TREASURY"),
    # Credit
    ("CREDIT", "CREDIT"),
    ("MORTGAGE", "CREDIT"),
    ("LOAN", "CREDIT"),
    ("SME", "CREDIT"),
    # SOP
    ("SOP", "SOP"),
    ("POLICY", "SOP"),
]


def infer_category(file_path: Path, data_root: Path) -> str:
    """Infer document category.

    Priority:
      1. Parent folder name inside data_root (most reliable).
      2. Keyword matching on the filename stem (fallback for uploads
         that land outside the DATA/ folder hierarchy).
      3. 'GENERAL' as last resort.
    """
    # 1. Folder-based inference (highest confidence)
    try:
        relative = file_path.relative_to(data_root)
        if len(relative.parts) > 1:
            return relative.parts[0].upper()
    except ValueError:
        pass

    # 2. Keyword-based inference on the normalised filename
    name = file_path.stem.upper().replace("-", "_").replace(" ", "_")
    for keyword, category in _KEYWORD_CATEGORY_MAP:
        if keyword in name:
            return category

    return "GENERAL"


def build_metadata(file_path: Path, data_root: Path) -> DocumentMetadata:
    file_name = file_path.name
    category = infer_category(file_path, data_root)
    doc_id = slugify(file_path.stem)
    date_added = datetime.now(timezone.utc).isoformat()
    return DocumentMetadata(
        file_name=file_name,
        category=category,
        date_added=date_added,
        doc_id=doc_id,
        source_path=str(file_path.resolve()),
    )


def chunk_point_id(doc_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{doc_id}:{chunk_index}"))
