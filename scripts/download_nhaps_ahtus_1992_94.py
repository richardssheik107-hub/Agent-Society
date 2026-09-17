"""Resolve and download the official CTUR NHAPS 1992-94 adult main ZIP."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from zipfile import ZipFile


PAGE = "https://www.timeuse.org/ahtus/data"
DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "data/external/ahtus/nhaps_1992_94"
EXPECTED = ("USA92_94quest.sav", "USA1993hfsum.sav", "USA1993hfep.sav")
ANCHOR_TEXT = "Diaries from ages 18+, 1992-94"


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.current: str | None = None
        self.text = ""
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.current = dict(attrs).get("href")
            self.text = ""

    def handle_data(self, data: str) -> None:
        if self.current is not None:
            self.text += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.current is not None:
            self.links.append((self.text.strip(), self.current))
            self.current = None


def resolve_official_link(html: str, page: str = PAGE) -> str:
    links = Links()
    links.feed(html)
    targets = [urljoin(page, href) for text, href in links.links if text == ANCHOR_TEXT]
    if len(targets) != 1:
        raise ValueError(f"expected exactly one official NHAPS adult 1992-94 link, found {len(targets)}")
    parsed = urlparse(targets[0])
    if parsed.scheme != "https" or parsed.hostname not in {"www.timeuse.org", "timeuse.org"} or not parsed.path.startswith("/sites/default/files/ahtus/") or not parsed.path.lower().endswith(".zip"):
        raise ValueError(f"download target is not a CTUR AHTUS ZIP: {targets[0]}")
    return targets[0]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_zip(path: Path) -> dict[str, str]:
    with ZipFile(path) as archive:
        bad_member = archive.testzip()
        if bad_member is not None:
            raise ValueError(f"ZIP checksum failure: {bad_member}")
        members = archive.namelist()
        paths = {Path(name).name.lower(): name for name in members if not name.endswith("/")}
        missing = [name for name in EXPECTED if name.lower() not in paths]
        if missing:
            raise ValueError(f"DATA_SCHEMA_MISMATCH: missing {missing}; observed {members}")
        return {name: paths[name.lower()] for name in EXPECTED}


def download(root: Path, *, dry_run: bool = False) -> dict[str, object]:
    request = Request(PAGE, headers={"User-Agent": "Mozilla/5.0 (research download of public AHTUS data)"})
    with urlopen(request, timeout=30) as response:
        html = response.read().decode("utf-8")
    url = resolve_official_link(html)
    filename = Path(urlparse(url).path).name
    target = root / "raw" / filename
    plan: dict[str, object] = {"dataset": "NHAPS_AHTUS_1992_94", "official_source": PAGE, "resolved_url": url, "destination": str(target), "expected_files": list(EXPECTED)}
    if dry_run:
        return {"dry_run": True, **plan}
    target.parent.mkdir(parents=True, exist_ok=True)
    manifest_path = root / "SOURCE.json"
    prior = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else None
    if not target.exists():
        temporary = target.with_name(target.name + ".part")
        if temporary.exists():
            raise ValueError(f"partial download exists, inspect manually: {temporary}")
        request = Request(url, headers={"User-Agent": "Mozilla/5.0 (research download of public AHTUS data)"})
        try:
            with urlopen(request, timeout=45) as response, temporary.open("xb") as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            files = inspect_zip(temporary)
            temporary.replace(target)
        except Exception:
            if temporary.exists():
                temporary.unlink()
            raise
    else:
        files = inspect_zip(target)
    checksum = sha256(target)
    if prior and (prior.get("archive_sha256") != checksum or prior.get("archive_filename") != filename):
        raise ValueError("existing raw archive disagrees with SOURCE.json; refusing overwrite")
    manifest = {"dataset": "NHAPS_AHTUS_1992_94", "source_provider": "Centre for Time Use Research", "official_download_page": PAGE, "resolved_download_url": url, "download_time_utc": prior.get("download_time_utc") if prior else datetime.now(timezone.utc).isoformat(), "archive_filename": filename, "archive_sha256": checksum, "archive_bytes": target.stat().st_size, "files_contained": files}
    if not manifest_path.exists():
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return {"status": "DOWNLOAD_OK", **plan, "archive_bytes": target.stat().st_size, "sha256": checksum, "zip_file_list": files}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    print(json.dumps(download(args.root, dry_run=args.dry_run), indent=2))


if __name__ == "__main__":
    main()
