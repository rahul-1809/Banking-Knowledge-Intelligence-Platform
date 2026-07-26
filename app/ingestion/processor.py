from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.ingestion.chunking.splitter import TextChunk, split_text
from app.ingestion.loaders import discover_documents, load_document
from app.ingestion.loaders.base import DocumentMetadata, chunk_point_id
from app.services.retrieval.embedding import embed_texts

logger = get_logger(__name__)


def build_processed_record(
    metadata: DocumentMetadata,
    chunks: list[TextChunk],
) -> dict:
    return {
        "doc_id": metadata.doc_id,
        "metadata": asdict(metadata),
        "chunks": [{"chunk_index": chunk.chunk_index, "text": chunk.text} for chunk in chunks],
    }


def write_processed_record(processed_dir: Path, record: dict) -> Path:
    processed_dir.mkdir(parents=True, exist_ok=True)
    output_path = processed_dir / f"{record['doc_id']}.json"
    output_path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return output_path


def load_processed_record(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    if not settings.qdrant_cluster_endpoint or not settings.qdrant_api_key:
        raise ValueError(
            "QDRANT_CLUSTER_ENDPOINT and QDRANT_API_KEY must be set in the environment."
        )
    return QdrantClient(
        url=settings.qdrant_cluster_endpoint,
        api_key=settings.qdrant_api_key,
        timeout=60.0,
    )


def ensure_collection(client: QdrantClient, collection_name: str, vector_size: int, wipe: bool) -> None:
    exists = client.collection_exists(collection_name)
    if wipe and exists:
        logger.info("Wiping collection: %s", collection_name)
        client.delete_collection(collection_name)
        exists = False

    if not exists:
        logger.info("Creating collection: %s (dim=%s)", collection_name, vector_size)
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )

    # Ensure payload indexes exist for filterable fields.
    # Qdrant requires keyword indexes before filtered searches can run.
    from qdrant_client.models import PayloadSchemaType
    for field in ("category", "file_name", "doc_id"):
        try:
            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=PayloadSchemaType.KEYWORD,
            )
            logger.debug("Payload index ensured for field: %s", field)
        except Exception:  # noqa: BLE001
            # Index may already exist; Qdrant raises on duplicates.
            pass


def build_points(record: dict) -> list[PointStruct]:
    metadata = record["metadata"]
    chunks = record["chunks"]
    texts = [chunk["text"] for chunk in chunks]
    vectors = embed_texts(texts)

    points: list[PointStruct] = []
    for chunk, vector in zip(chunks, vectors):
        point_id = chunk_point_id(metadata["doc_id"], chunk["chunk_index"])
        points.append(
            PointStruct(
                id=point_id,
                vector=vector,
                payload={
                    "doc_id": metadata["doc_id"],
                    "file_name": metadata["file_name"],
                    "category": metadata["category"],
                    "date_added": metadata["date_added"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                },
            )
        )
    return points


def upsert_records(client: QdrantClient, collection_name: str, records: list[dict]) -> int:
    total_points = 0
    for record in records:
        points = build_points(record)
        if not points:
            logger.warning("No chunks to upsert for doc_id=%s", record["doc_id"])
            continue
        max_retries = 3
        for attempt in range(max_retries):
            try:
                client.upsert(collection_name=collection_name, points=points)
                break
            except Exception as exc:  # noqa: BLE001
                if attempt == max_retries - 1:
                    logger.error("Failed to upsert points for doc_id=%s after %d retries: %s", record["doc_id"], max_retries, exc)
                    raise
                import time
                logger.warning("Upsert retry %d for %s (%s)", attempt + 1, record["doc_id"], exc)
                time.sleep(2.0 * (attempt + 1))
        total_points += len(points)
        logger.info(
            "Upserted %s chunks for %s (%s)",
            len(points),
            record["doc_id"],
            record["metadata"]["file_name"],
        )
    return total_points


def process_file(file_path: Path, data_root: Path, processed_dir: Path) -> dict:
    loaded = load_document(file_path, data_root)
    chunks = split_text(loaded.text)
    record = build_processed_record(loaded.metadata, chunks)
    write_processed_record(processed_dir, record)
    logger.info(
        "Processed %s -> %s chunks (category=%s)",
        file_path.name,
        len(chunks),
        loaded.metadata.category,
    )
    return record


def process_directory(data_dir: Path, processed_dir: Path) -> list[dict]:
    files = discover_documents(data_dir)
    if not files:
        logger.warning("No supported documents found in %s", data_dir)
        return []

    records: list[dict] = []
    for file_path in files:
        records.append(process_file(file_path, data_dir, processed_dir))
    return records


def load_processed_records(processed_dir: Path) -> list[dict]:
    records: list[dict] = []
    for path in sorted(processed_dir.glob("*.json")):
        records.append(load_processed_record(path))
    return records


def run_ingestion(data_dir: Path, processed_dir: Path, wipe: bool, dry_run: bool) -> int:
    settings = get_settings()
    records = process_directory(data_dir, processed_dir)
    if not records:
        return 0

    if dry_run:
        logger.info("Dry run complete. Parsed %s documents; skipped Qdrant upload.", len(records))
        return len(records)

    client = get_qdrant_client()
    ensure_collection(
        client,
        settings.qdrant_collection_name,
        settings.embedding_dimension,
        wipe=wipe,
    )
    upsert_records(client, settings.qdrant_collection_name, records)
    return len(records)


def parse_args() -> argparse.Namespace:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Ingest banking documents into Qdrant.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(settings.data_dir),
        help="Directory containing raw documents.",
    )
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=Path(settings.processed_data_dir),
        help="Directory for intermediate JSON chunk files.",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="Delete and recreate the Qdrant collection before upload.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and write processed_data JSON without uploading to Qdrant.",
    )
    return parser.parse_args()


def main() -> None:
    setup_logging()
    args = parse_args()
    data_dir = args.data_dir.resolve()
    processed_dir = args.processed_dir.resolve()

    if not data_dir.exists():
        raise SystemExit(f"Data directory not found: {data_dir}")

    count = run_ingestion(data_dir, processed_dir, wipe=args.wipe, dry_run=args.dry_run)
    logger.info("Ingestion finished. Documents processed: %s", count)


if __name__ == "__main__":
    main()
