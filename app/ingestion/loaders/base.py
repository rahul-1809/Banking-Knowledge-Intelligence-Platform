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


def infer_category(file_path: Path, data_root: Path) -> str:
    try:
        relative = file_path.relative_to(data_root)
        if len(relative.parts) > 1:
            return relative.parts[0].upper()
    except ValueError:
        pass

    name = file_path.stem.upper()
    for token in ("RBI", "SOP", "KYC", "AML", "CREDIT", "POLICY"):
        if token in name:
            return token if token != "POLICY" else "SOP"
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
