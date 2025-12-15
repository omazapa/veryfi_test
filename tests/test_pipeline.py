import json
import os
from pathlib import Path

import pytest
from typing import Dict, List, TypedDict

from veryfi_test import extract_cli, ocr_cli


PDF_FIXTURES = Path(__file__).resolve().parent / "veryfi_private_data"


class DatasetSpec(TypedDict):
    stem: str
    key: str
    meta: Dict[str, object]
    is_switch: bool


REQUIRED_ENV_VARS = [
    "VERYFI_API_URL",
    "VERYFI_CLIENT_ID",
    "VERYFI_CLIENT_SECRET",
    "VERYFI_USERNAME",
    "VERYFI_API_KEY",
]
MISSING_ENV = [key for key in REQUIRED_ENV_VARS if not os.environ.get(key)]

pytestmark = pytest.mark.skipif(
    bool(MISSING_ENV),
    reason=f"Missing Veryfi credentials in environment: {', '.join(MISSING_ENV)}",
)


DATASET_SPECS: List[DatasetSpec] = [
    {
        "stem": "synth-switch_v5-14",
        "key": "path",
        "meta": {"categories": ["Utilities"]},
        "is_switch": True,
    },
    {
        "stem": "synth-switch_v5-4",
        "key": "file",
        "meta": {"topics": ["Utilities", None]},
        "is_switch": True,
    },
    {
        "stem": "synth-switch_v5-68",
        "key": "document",
        "meta": {"categories": ["Utilities", "Power"]},
        "is_switch": True,
    },
    {
        "stem": "synth-switch_v5-7",
        "key": "archivo",
        "meta": {"temas": "Switch Billing"},
        "is_switch": True,
    },
    {
        "stem": "synth-switch_v5-79",
        "key": "path",
        "meta": {"category": "Infrastructure"},
        "is_switch": True,
    },
    {
        "stem": "non-switch-invoice",
        "key": "path",
        "meta": {"categories": ["Other"]},
        "is_switch": False,
    },
    {
        "stem": "non-switch-invoice2",
        "key": "path",
        "meta": {"category": None},
        "is_switch": False,
    },
]

TOTAL_DOCUMENTS = len(DATASET_SPECS)
SWITCH_STEMS = sorted(spec["stem"] for spec in DATASET_SPECS if spec["is_switch"])
NON_SWITCH_STEMS = sorted(spec["stem"] for spec in DATASET_SPECS if not spec["is_switch"])


def _expected_saved_paths(ocr_output: Path) -> list[str]:
    """Return the list of OCR JSON paths that should yield extracted payloads.

    Parameters
    ----------
    ocr_output : pathlib.Path
        Directory that stores the OCR JSON files created by the CLI.

    Returns
    -------
    list of str
        Sorted collection of JSON paths that correspond to Switch invoices.
    """

    return [str(ocr_output / f"{stem}.json") for stem in SWITCH_STEMS]


def _expected_skipped_paths(ocr_output: Path) -> dict[str, str]:
    """Return the dictionary of OCR JSON paths that must be skipped.

    Parameters
    ----------
    ocr_output : pathlib.Path
        Directory that stores the OCR JSON files created by the CLI.

    Returns
    -------
    dict
        Mapping of file path to the reason why the extractor should ignore it.
    """

    return {str(ocr_output / f"{stem}.json"): "layout mismatch" for stem in NON_SWITCH_STEMS}


def _build_manifest(tmp_dir: Path) -> Path:
    r"""Create the manifest consumed by the OCR CLI inside ``tmp_dir``.

    Parameters
    ----------
    tmp_dir : pathlib.Path
        Temporary directory where the manifest file will be stored.

    Returns
    -------
    pathlib.Path
        Path to the JSON manifest that references every PDF fixture.
    """

    entries = []
    for spec in DATASET_SPECS:
        pdf_path = PDF_FIXTURES / f"{spec['stem']}.pdf"
        assert pdf_path.is_file(), f"Missing fixture PDF: {pdf_path}"
        entry = dict(spec["meta"])
        entry[spec["key"]] = str(pdf_path)
        entries.append(entry)

    manifest_path = tmp_dir / "manifest.json"
    manifest_path.write_text(json.dumps({"documents": entries}, indent=2))
    return manifest_path


@pytest.fixture(scope="module")
def manifest_path(tmp_path_factory) -> Path:
    """Provide the manifest path shared across OCR tests.

    Parameters
    ----------
    tmp_path_factory : pytest.TempPathFactory
        Factory fixture that yields temporary directories scoped per test session.

    Returns
    -------
    pathlib.Path
        Location of the generated manifest.
    """

    manifest_dir = tmp_path_factory.mktemp("manifest-stage")
    return _build_manifest(manifest_dir)


@pytest.fixture(scope="module")
def ocr_result(tmp_path_factory, manifest_path):
    """Run the OCR CLI once and expose its side effects.

    Parameters
    ----------
    tmp_path_factory : pytest.TempPathFactory
        Factory used to create a fresh directory for the OCR JSON.
    manifest_path : pathlib.Path
        Manifest pointing to every PDF fixture.

    Returns
    -------
    dict
        Exit code, output directory, and list of generated JSON files.
    """

    output_dir = tmp_path_factory.mktemp("ocr-output")
    exit_code = ocr_cli.main(
        [
            str(manifest_path),
            "--output-ocr-dir",
            str(output_dir),
        ]
    )
    files = sorted(output_dir.glob("*.json"))
    return {"exit_code": exit_code, "output_dir": output_dir, "files": files}


@pytest.fixture(scope="module")
def extraction_result(ocr_result, tmp_path_factory):
    """Run the extraction CLI using the OCR JSON generated in ``ocr_result``.

    Parameters
    ----------
    ocr_result : dict
        Result dictionary produced by the :func:`ocr_result` fixture.
    tmp_path_factory : pytest.TempPathFactory
        Factory used to create the destination directory for extracted payloads.

    Returns
    -------
    dict
        Extractor summary and path to the directory containing the outputs.
    """

    output_dir = tmp_path_factory.mktemp("extract-output")
    summary = extract_cli.run_extraction(Path(ocr_result["output_dir"]), output_dir)
    return {"summary": summary, "output_dir": output_dir}


@pytest.fixture(scope="module")
def pipeline_report_path(ocr_result, extraction_result, tmp_path_factory):
    """Generate a JSON report that combines OCR and extraction stages.

    Parameters
    ----------
    ocr_result : dict
        Result dictionary produced by the :func:`ocr_result` fixture.
    extraction_result : dict
        Result dictionary produced by the :func:`extraction_result` fixture.
    tmp_path_factory : pytest.TempPathFactory
        Factory used to create the directory where the report will be written.

    Returns
    -------
    pathlib.Path
        Location of the JSON report.
    """

    report_dir = tmp_path_factory.mktemp("pipeline-report")
    report_path = report_dir / "report.json"
    summary = extraction_result["summary"]
    report_payload = {
        "ocr_files": [str(path) for path in ocr_result["files"]],
        "extracted_files": summary["saved"],
        "skipped_files": summary["skipped"],
        "total_documents": TOTAL_DOCUMENTS,
    }
    report_path.write_text(json.dumps(report_payload, indent=2))
    return report_path


def test_ocr_cli_runs_successfully(ocr_result):
    """Ensure the OCR CLI ran without errors and produced the expected files."""
    assert ocr_result["exit_code"] == 0, "OCR CLI failed to finish"
    assert len(ocr_result["files"]) == TOTAL_DOCUMENTS, "Unexpected number of OCR JSON files"


def test_ocr_payloads_are_well_formed(ocr_result):
    """Validate the structure of every OCR JSON payload."""
    assert ocr_result["files"], "OCR CLI did not produce any JSON files"
    for result_file in ocr_result["files"]:
        payload = json.loads(result_file.read_text())
        assert {"file", "document_id", "veryfi_response"} <= payload.keys()
        assert payload["veryfi_response"].get("ocr_text"), f"OCR payload missing text: {result_file}"


def test_extraction_cli_runs_successfully(ocr_result, extraction_result):
    """Ensure the extraction CLI processed all files and respected layout filters."""
    summary = extraction_result["summary"]
    assert summary["processed"] == TOTAL_DOCUMENTS
    expected_saved = _expected_saved_paths(Path(ocr_result["output_dir"]))
    expected_skipped = _expected_skipped_paths(Path(ocr_result["output_dir"]))
    assert summary["saved"] == expected_saved
    assert summary["skipped"] == expected_skipped


def test_extracted_payloads_are_well_formed(ocr_result, extraction_result):
    """Inspect the per-document extracted payloads for correctness."""
    extract_dir = extraction_result["output_dir"]
    expected_saved = _expected_saved_paths(Path(ocr_result["output_dir"]))
    for saved_source in expected_saved:
        extracted_path = extract_dir / f"extracted_{Path(saved_source).name}"
        assert extracted_path.is_file(), f"Missing extracted payload: {extracted_path}"
        payload = json.loads(extracted_path.read_text())
        assert payload["source"] == saved_source
        assert payload["vendor_name"] == "Switch"
        assert payload["line_items"], "Line items should not be empty"


def test_pipeline_report_generated(pipeline_report_path):
    """Verify that the pipeline report was written and print its contents."""
    assert pipeline_report_path.is_file(), "Pipeline report was not written"
    report = json.loads(pipeline_report_path.read_text())
    assert report["total_documents"] == TOTAL_DOCUMENTS
    assert len(report["ocr_files"]) == TOTAL_DOCUMENTS
    assert set(report["extracted_files"]).isdisjoint(report["skipped_files"].keys())
    print(json.dumps(report, indent=2))
