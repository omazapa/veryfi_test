"""Command-line helper to upload documents to Veryfi."""

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

from veryfi import Client  # type: ignore[import-untyped]

from .config import VeryfiCredentials, load_credentials


@dataclass(frozen=True)
class DocumentJob:
    """Represents a single entry in the manifest file.

    Attributes
    ----------
    path : pathlib.Path
        Filesystem path to the document that should be processed.
    categories : list of str or None, optional
        Category labels associated with the document, if any.
    """

    path: Path
    categories: List[str] | None = None


def _build_client(creds: VeryfiCredentials) -> Client:
    """Instantiate the official Veryfi client honoring custom API URLs.

    Parameters
    ----------
    creds : VeryfiCredentials
        Credential bundle with the API endpoint and keys.

    Returns
    -------
    veryfi.Client
        Client ready to send OCR requests.
    """

    base_url = creds.api_url.rstrip("/")
    if not base_url.endswith("/api"):
        base_url = f"{base_url}/api"
    base_url = f"{base_url.rstrip('/')}/"
    return Client(
        creds.client_id,
        creds.client_secret,
        creds.username,
        creds.api_key,
        base_url=base_url,
    )


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Return parsed CLI arguments.

    Parameters
    ----------
    argv : Sequence[str], optional
        Custom argument vector; defaults to ``sys.argv`` when ``None``.

    Returns
    -------
    argparse.Namespace
        Namespaced values for manifest path, output directory, and env file.
    """
    parser = argparse.ArgumentParser(description="Upload documents defined in a JSON manifest to the Veryfi OCR API.")
    parser.add_argument(
        "manifest",
        type=Path,
        help="Path to a JSON file that lists each document and its categories.",
    )
    parser.add_argument(
        "--output-ocr-dir",
        dest="output_dir",
        type=Path,
        default=Path("outputs-ocr"),
        help="Directory where JSON responses will be stored (default: ./outputs-ocr).",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Optional path to a dotenv file with Veryfi credentials (defaults to .env).",
    )
    return parser.parse_args(argv)


def _normalize_categories(value: object, *, job_index: int) -> List[str] | None:
    """Normalize raw category values to a list of strings.

    Parameters
    ----------
    value : object
        Raw value from the manifest (string, iterable, or ``None``).
    job_index : int
        Position of the manifest entry; used to render helpful errors.

    Returns
    -------
    list of str or None
        Cleaned category labels ready to send to Veryfi.

    Raises
    ------
    ValueError
        If the provided value cannot be interpreted as categories.
    """

    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, Iterable):
        result: List[str] = []
        for raw in value:
            if raw is None:
                continue
            result.append(str(raw))
        if not result:
            return None
        return result
    raise ValueError(f"Job #{job_index}: categories/topics must be a string or list.")


def _load_manifest(manifest_path: Path) -> List[DocumentJob]:
    """Parse and validate the manifest file.

    Parameters
    ----------
    manifest_path : pathlib.Path
        JSON file describing the documents to process.

    Returns
    -------
    list of DocumentJob
        Sanitized jobs including paths and optional categories.

    Raises
    ------
    FileNotFoundError
        If the manifest does not exist.
    ValueError
        If the manifest structure is invalid or empty.
    """

    if not manifest_path.is_file():
        raise FileNotFoundError(manifest_path)

    raw_data = json.loads(manifest_path.read_text())
    documents = raw_data
    if isinstance(raw_data, dict) and "documents" in raw_data:
        documents = raw_data["documents"]

    if not isinstance(documents, list):
        raise ValueError("Manifest must be a list or contain a 'documents' list.")

    jobs: List[DocumentJob] = []
    for index, item in enumerate(documents, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Job #{index}: entries must be objects.")

        file_path = item.get("path") or item.get("file") or item.get("document") or item.get("archivo")
        if not file_path:
            raise ValueError(f"Job #{index}: missing 'path' field.")

        raw_categories = item.get("categories") or item.get("topics") or item.get("temas") or item.get("category")
        categories = _normalize_categories(raw_categories, job_index=index)
        jobs.append(DocumentJob(Path(str(file_path)), categories))

    if not jobs:
        raise ValueError("Manifest did not contain any documents.")

    return jobs


def _save_response(output_dir: Path, source_path: Path, payload: dict) -> Path:
    """Write the API response to disk next to the source file name.

    Parameters
    ----------
    output_dir : pathlib.Path
        Directory where responses should be stored.
    source_path : pathlib.Path
        Original document path used to derive the output file name.
    payload : dict
        JSON-serializable content to persist.

    Returns
    -------
    pathlib.Path
        Path to the file that was written.
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{source_path.stem}.json"
    output_path.write_text(json.dumps(payload, indent=2))
    return output_path


def main(argv: Sequence[str] | None = None) -> int:
    """Program entry point.

    Parameters
    ----------
    argv : Sequence[str], optional
        Optional argument list useful for testing.

    Returns
    -------
    int
        Zero when all documents succeed, otherwise non-zero.
    """

    args = _parse_args(argv)
    try:
        creds = load_credentials(env_file=args.env_file)
    except RuntimeError as exc:
        print(f"Credential error: {exc}", file=sys.stderr)
        return 1

    manifest_path = args.manifest.expanduser()
    try:
        jobs = _load_manifest(manifest_path)
    except (OSError, ValueError) as exc:
        print(f"Manifest error: {exc}", file=sys.stderr)
        return 1

    client = _build_client(creds)
    exit_code = 0
    output_dir = Path(args.output_dir).expanduser()

    for job in jobs:
        path = job.path.expanduser()
        if not path.is_file():
            print(f"File not found: {path}", file=sys.stderr)
            exit_code = 1
            continue

        try:
            response = client.process_document(str(path), categories=job.categories)
        except Exception as exc:  # pragma: no cover - depends on API responses
            print(f"Upload failed for {path}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        doc_id = None
        if isinstance(response, dict):
            doc_id = response.get("id")

        payload = {
            "file": str(path),
            "document_id": doc_id,
            "veryfi_response": response,
        }
        saved_path = _save_response(output_dir, path, payload)

        if doc_id is not None:
            print(f"Processed {path} (document id: {doc_id}) -> {saved_path}")
        else:
            print(f"Processed {path} -> {saved_path}")

    return exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
