from pathlib import Path

from app.ingestion.loaders.base import SUPPORTED_EXTENSIONS, LoadedDocument
from app.ingestion.loaders.docx_loader import load_docx
from app.ingestion.loaders.pdf_loader import load_pdf
from app.ingestion.loaders.txt_loader import load_txt


from app.ingestion.loaders.json_loader import load_json


def load_document(file_path: Path, data_root: Path) -> LoadedDocument:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return load_pdf(file_path, data_root)
    if suffix == ".docx":
        return load_docx(file_path, data_root)
    if suffix in (".txt", ".md"):
        return load_txt(file_path, data_root)
    if suffix == ".json":
        return load_json(file_path, data_root)
    raise ValueError(f"Unsupported file type: {suffix}")


def discover_documents(data_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(data_dir.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(path)
    return files
