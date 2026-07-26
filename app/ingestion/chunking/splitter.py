from dataclasses import dataclass


DEFAULT_CHUNK_SIZE = 1100
DEFAULT_CHUNK_OVERLAP = 150


@dataclass
class TextChunk:
    chunk_index: int
    text: str


def split_paragraphs(text: str) -> list[str]:
    raw_paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if raw_paragraphs:
        return raw_paragraphs
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return [" ".join(lines)] if lines else []


def _overlap_paragraphs(paragraphs: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or not paragraphs:
        return []

    selected: list[str] = []
    total = 0
    for paragraph in reversed(paragraphs):
        extra = len(paragraph) + (2 if selected else 0)
        if total + extra > overlap and selected:
            break
        selected.insert(0, paragraph)
        total += extra
    return selected


def _flush_chunk(chunks: list[str], current: list[str]) -> list[str]:
    if current:
        chunks.append("\n\n".join(current))
    return []


def split_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[TextChunk]:
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return []

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        paragraph_len = len(paragraph)
        if paragraph_len > chunk_size:
            current = _flush_chunk(chunks, current)
            current_len = 0
            start = 0
            while start < paragraph_len:
                end = min(start + chunk_size, paragraph_len)
                chunks.append(paragraph[start:end])
                if end >= paragraph_len:
                    break
                start = max(end - chunk_overlap, start + 1)
            continue

        projected = current_len + paragraph_len + (2 if current else 0)
        if projected <= chunk_size:
            current.append(paragraph)
            current_len = projected
        else:
            chunks.append("\n\n".join(current))
            current = _overlap_paragraphs(current, chunk_overlap)
            current_len = sum(len(part) for part in current) + 2 * max(len(current) - 1, 0)
            current.append(paragraph)
            current_len += paragraph_len + (2 if len(current) > 1 else 0)

    if current:
        chunks.append("\n\n".join(current))

    return [TextChunk(chunk_index=index, text=chunk) for index, chunk in enumerate(chunks)]
