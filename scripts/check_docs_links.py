"""Check local pages, fragments, and assets in a generated documentation site."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class _Page(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: list[str] = []
        self.anchors: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is None:
                continue
            if name in {"href", "src"}:
                self.references.append(value)
            if name == "id" or (tag == "a" and name == "name"):
                self.anchors.add(value)


def check_site(site_dir: Path) -> tuple[int, int]:
    """Return page and local-reference counts, or raise for broken file navigation.

    External URLs are not fetched. The server-oriented 404 page is excluded.
    """
    root = site_dir.resolve()
    if not (root / "index.html").is_file():
        raise ValueError(f"{root}: missing index.html")
    pages: dict[Path, _Page] = {}
    for path in sorted(root.rglob("*.html")):
        if path.name == "404.html":
            continue
        parser = _Page()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path] = parser
    failures: list[str] = []
    count = 0
    for path, page in pages.items():
        for reference in page.references:
            url = urlsplit(reference)
            if url.scheme in {"https", "http", "mailto", "tel", "data"}:
                continue
            count += 1
            destination = unquote(url.path)
            target = (path.parent / destination).resolve() if destination else path
            reason = None
            if url.scheme or url.netloc:
                reason = "unsupported URL for local-file navigation"
            elif destination.startswith("/"):
                reason = "root-relative URL"
            elif not target.is_relative_to(root):
                reason = "target outside site"
            elif destination.endswith("/") or target.is_dir():
                reason = "directory URL instead of a file"
            elif not target.is_file():
                reason = "missing file"
            elif (
                url.fragment
                and target in pages
                and unquote(url.fragment) not in pages[target].anchors
            ):
                reason = "missing anchor"
            if reason:
                failures.append(f"{path.relative_to(root)}: {reference!r}: {reason}")
    if failures:
        raise ValueError("Invalid documentation links:\n" + "\n".join(failures))
    return len(pages), count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site_dir", nargs="?", type=Path, default=Path("site"))
    args = parser.parse_args()
    try:
        pages, references = check_site(args.site_dir)
    except ValueError as exc:
        parser.exit(1, f"{exc}\n")
    print(f"Checked {pages} pages and {references} local links and assets.")


if __name__ == "__main__":
    main()
