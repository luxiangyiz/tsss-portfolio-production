"""Production-only maintenance CLI for the public knowledge index."""

import argparse
import json
import sys

from rag_app.core.config import settings, validate_runtime_security
from rag_app.langchain_components.vector_store import get_client
from rag_app.services.ingestion_service import IngestionService


def run_public_index(mode: str) -> dict:
    """Build or update only the approved public collection."""
    validate_runtime_security()
    service = IngestionService()
    preview = service.preview()

    expected = settings.public_expected_documents
    if preview["scanned_files"] != expected:
        raise RuntimeError(
            f"Expected {expected} public documents, found {preview['scanned_files']}"
        )
    if preview["included_files"] != expected:
        raise RuntimeError(
            f"Expected {expected} included documents, found {preview['included_files']}"
        )
    if preview["rejected_files"] or preview["errors"]:
        raise RuntimeError("Public content preview contains rejected files or errors")

    result = service.ingest(mode=mode, scope="public")
    if result["rejected_files"] or result["errors"]:
        raise RuntimeError("Public index build contains rejected files or errors")

    public_collection = settings.yaml_config.get("collections", {}).get("public", "kb_public")
    manifest_data = service.manifest.load()
    indexed_documents = sum(
        1
        for document in manifest_data.get("documents", {}).values()
        if public_collection in document.get("scopes", {})
    )
    if indexed_documents != expected:
        raise RuntimeError(
            f"Expected {expected} indexed public documents, found {indexed_documents}"
        )

    collection_names = {
        item.name for item in get_client().get_collections().collections
    }
    forbidden = collection_names.intersection({"kb_private", "kb_internal"})
    if forbidden:
        raise RuntimeError(f"Forbidden collections found: {sorted(forbidden)}")
    if public_collection not in collection_names:
        raise RuntimeError(f"Public collection missing: {public_collection}")

    return {
        **result,
        "collections": sorted(collection_names),
        "expected_documents": expected,
        "indexed_documents": indexed_documents,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Public RAG maintenance commands")
    subparsers = parser.add_subparsers(dest="command", required=True)
    index_parser = subparsers.add_parser("index", help="Build the public index")
    index_parser.add_argument("--scope", choices=["public"], default="public")
    index_parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="incremental",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command != "index" or args.scope != "public":
        raise RuntimeError("Only the public index is available in production")
    try:
        result = run_public_index(args.mode)
    except Exception as exc:
        print(
            json.dumps(
                {"status": "failed", "error": type(exc).__name__, "message": str(exc)},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    print(json.dumps({"status": "ok", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
