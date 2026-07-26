"""JSON document loader — extracts text content from JSON structured documents."""

from __future__ import annotations

import json
from pathlib import Path

from app.ingestion.loaders.base import LoadedDocument, build_metadata


def load_json(file_path: Path, data_root: Path) -> LoadedDocument:
    """Extract text from JSON document containing title, sections, or text fields."""
    metadata = build_metadata(file_path, data_root)
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    paragraphs = []
    if isinstance(data, dict):
        if "title" in data:
            paragraphs.append(str(data["title"]))
        if "sections" in data and isinstance(data["sections"], list):
            for sec in data["sections"]:
                if isinstance(sec, dict):
                    heading = sec.get("heading", "")
                    body = sec.get("body", "")
                    paragraphs.append(f"{heading}\n{body}")
        elif "text" in data:
            paragraphs.append(str(data["text"]))
        else:
            paragraphs.append(json.dumps(data, indent=2))
    elif isinstance(data, list):
        for item in data:
            paragraphs.append(str(item))
    else:
        paragraphs.append(str(data))

    full_text = "\n\n".join(p for p in paragraphs if p).strip()
    return LoadedDocument(metadata=metadata, text=full_text)
