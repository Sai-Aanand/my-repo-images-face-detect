"""CLI wrapper around the dataset ingestion service."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import List

from app.core.config import get_settings
from app.core.database import close_mongo_connection, connect_to_mongo
from app.services.dataset_ingestor import ingest_dataset


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk-ingest a folder of photos.")
    parser.add_argument("dataset", type=Path, help="Path to the folder containing images.")
    parser.add_argument(
        "--labels",
        type=str,
        default="",
        help="Optional comma-separated labels to attach to every ingested photo.",
    )
    return parser.parse_args(argv)


async def main(dataset: Path, labels: List[str]) -> None:
    settings = get_settings()
    settings.media_root.mkdir(parents=True, exist_ok=True)

    await connect_to_mongo()
    try:
        result = await ingest_dataset(dataset, labels)
        print(
            f"\nDone. Indexed {result['indexed']} of {result['processed']} files from {dataset}. Skipped {result['skipped']}.")
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    if not args.dataset.exists():
        raise SystemExit(f"Dataset folder not found: {args.dataset}")
    labels = [label.strip() for label in args.labels.split(",") if label.strip()]
    asyncio.run(main(args.dataset.resolve(), labels))
