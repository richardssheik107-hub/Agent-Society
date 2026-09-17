from pathlib import Path
from zipfile import ZipFile

import pytest

from scripts.download_nhaps_ahtus_1992_94 import inspect_zip, resolve_official_link


def test_resolve_only_exact_ctur_adult_package():
    html = '<a href="/sites/default/files/ahtus/public/4931/usa1993-dec2009.zip">Diaries from ages 18+, 1992-94</a><a href="/child.zip">Diaries from ages 0-17, 1992-94</a>'
    assert resolve_official_link(html) == "https://www.timeuse.org/sites/default/files/ahtus/public/4931/usa1993-dec2009.zip"
    with pytest.raises(ValueError):
        resolve_official_link('<a href="https://evil.example/usa1993.zip">Diaries from ages 18+, 1992-94</a>')


def test_expected_three_sav_members(tmp_path: Path):
    archive_path = tmp_path / "official.zip"
    with ZipFile(archive_path, "w") as archive:
        for name in ("USA92_94quest.sav", "USA1993hfsum.sav", "USA1993hfep.sav"):
            archive.writestr("package/" + name, b"fixture")
    assert len(inspect_zip(archive_path)) == 3
