"""Download only official BLS 2025 single-year files, preserving immutable raw ZIPs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen


BASE = "https://www.bls.gov/tus/datafiles/"
FILES = ("atusact-2025.zip", "atusresp-2025.zip", "atusrost-2025.zip", "atuswho-2025.zip")
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data/external/atus/2025"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(root: Path) -> dict[str, object]:
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    source_path = root / "SOURCE.json"
    prior = json.loads(source_path.read_text(encoding="utf-8")) if source_path.exists() else {}
    prior_files = {entry["name"]: entry for entry in prior.get("files", [])}
    records = []
    for name in FILES:
        target = raw / name
        url = BASE + name
        if target.exists():
            current = sha256(target)
            if name in prior_files and current != prior_files[name]["sha256"]:
                raise ValueError(f"checksum mismatch for existing raw file {target}; refusing overwrite")
        else:
            temporary = raw / (name + ".part")
            if temporary.exists():
                raise ValueError(f"partial download exists: {temporary}; inspect manually")
            request = Request(url, headers={"User-Agent": "AgentSociety-ResearchB1/1.0 (ATUS public research; contact via GitHub repository)"})
            try:
                with urlopen(request, timeout=30) as response, temporary.open("xb") as output:
                    while chunk := response.read(1024 * 1024):
                        output.write(chunk)
                temporary.replace(target)
            except Exception:
                if temporary.exists():
                    temporary.unlink()
                raise
            current = sha256(target)
        records.append({"name": name, "url": url, "size_bytes": target.stat().st_size, "sha256": current})
    result = {"source": "U.S. Bureau of Labor Statistics ATUS 2025 single-year microdata", "source_page": "https://www.bls.gov/tus/data/datafiles-2025.htm", "download_date": prior.get("download_date") or datetime.now(timezone.utc).date().isoformat(), "source_year": 2025, "files": records}
    if source_path.exists() and prior != result:
        raise ValueError("SOURCE.json exists but disagrees with files; inspect manually")
    if not source_path.exists():
        source_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    print(json.dumps(download(args.root), indent=2))


if __name__ == "__main__":
    main()
