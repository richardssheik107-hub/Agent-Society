"""Inspect official NHAPS AHTUS SPSS metadata before implementing any adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts.download_nhaps_ahtus_1992_94 import DEFAULT_ROOT, EXPECTED, inspect_zip, sha256


DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "run/human_data/nhaps_ahtus_1992_94"


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", encoding="utf-8")


def inspect(root: Path, output: Path) -> dict[str, object]:
    try:
        import pyreadstat
    except ImportError as error:
        raise RuntimeError("pyreadstat required: uv run --with-requirements scripts/requirements-human-data.txt") from error
    source = json.loads((root / "SOURCE.json").read_text(encoding="utf-8"))
    archive_path = root / "raw" / source["archive_filename"]
    if sha256(archive_path) != source["archive_sha256"]:
        raise ValueError("raw archive SHA256 mismatch")
    members = inspect_zip(archive_path)
    work = root / "processed/work"
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)
    reports = {}
    with ZipFile(archive_path) as archive:
        for kind, name in zip(("background", "summary", "episode"), EXPECTED):
            member = members[name]
            target = work / Path(member).name
            if not target.exists():
                with archive.open(member) as source_file, target.open("xb") as target_file:
                    shutil.copyfileobj(source_file, target_file)
            else:
                with archive.open(member) as source_file:
                    digest = hashlib.sha256()
                    for chunk in iter(lambda: source_file.read(1024 * 1024), b""):
                        digest.update(chunk)
                if sha256(target) != digest.hexdigest():
                    raise ValueError(f"processed copy differs from immutable ZIP member: {target}")
            _, meta = pyreadstat.read_sav(str(target), metadataonly=True, apply_value_formats=False)
            report = {"source_archive_sha256": source["archive_sha256"], "source_member": member, "extracted_sha256": sha256(target), "rows": meta.number_rows, "columns": meta.column_names, "column_labels": dict(zip(meta.column_names, meta.column_labels)), "readstat_dtypes": meta.readstat_variable_types, "value_labels": meta.variable_value_labels, "reader": f"pyreadstat {pyreadstat.__version__}"}
            reports[kind] = report
            _write_json(output / f"schema_{kind}.json", report)
    _write_json(output / "schema_report.json", {"dataset": "NHAPS_AHTUS_1992_94", "source_archive_sha256": source["archive_sha256"], "files": {kind: {"member": report["source_member"], "rows": report["rows"], "columns": len(report["columns"])} for kind, report in reports.items()}})
    return {kind: {"rows": report["rows"], "columns": report["columns"]} for kind, report in reports.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(inspect(args.root, args.output), indent=2))


if __name__ == "__main__":
    main()
