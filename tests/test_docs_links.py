import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def check_site():
    script = Path(__file__).parents[1] / "scripts/check_docs_links.py"
    spec = importlib.util.spec_from_file_location("check_docs_links", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.check_site


def test_local_pages_assets_and_fragments(check_site, tmp_path):
    (tmp_path / "index.html").write_text(
        '<a href="guide.html#usage">Guide</a><img src="logo.svg">'
        '<a href="https://example.com/">External</a>'
    )
    (tmp_path / "guide.html").write_text(
        '<h1 id="usage">Usage</h1><a href="index.html">Home</a>'
    )
    (tmp_path / "logo.svg").write_text("<svg></svg>")
    assert check_site(tmp_path) == (2, 3)


@pytest.mark.parametrize(
    ("markup", "reason"),
    [
        ('<a href="missing.html">Missing</a>', "missing file"),
        ('<img src="missing.svg">Missing</img>', "missing file"),
        ('<a href="#missing">Missing</a>', "missing anchor"),
        ('<a href="guide/">Directory</a>', "directory URL"),
        ('<a href="/guide.html">Absolute</a>', "root-relative"),
        ('<a href="../outside.html">Outside</a>', "outside site"),
    ],
)
def test_broken_file_navigation_fails(check_site, tmp_path, markup, reason):
    (tmp_path / "index.html").write_text(markup)
    with pytest.raises(ValueError, match=reason):
        check_site(tmp_path)


def test_site_needs_entry_page(check_site, tmp_path):
    with pytest.raises(ValueError, match="index.html"):
        check_site(tmp_path)
