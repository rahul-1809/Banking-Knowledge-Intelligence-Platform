from pathlib import Path

from app.ingestion.loaders.base import LoadedDocument, build_metadata


def load_txt(file_path: Path, data_root: Path) -> LoadedDocument:
    metadata = build_metadata(file_path, data_root)
    text = file_path.read_text(encoding="utf-8").strip()
    return LoadedDocument(metadata=metadata, text=text)
