"""Checks for the built site. scripts/build.py runs them after each build."""

from __future__ import annotations

import argparse
import gzip
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree

from redirects import REDIRECTS, output_file

MAX_PAGE_BYTES = 1_500_000
MAX_IMAGE_BYTES = 300_000
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
SKIP_DIR_NAMES = {"live"}
SKIP_SOURCE_DIRS = {"_site", "_freeze", ".quarto"}
LINK_ATTRS = ("href", "src", "data-src")


class _PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str, str]] = []
        self.refresh: str | None = None

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        for name in LINK_ATTRS:
            if values.get(name):
                self.links.append((tag, name, values[name]))
        if tag == "meta" and (values.get("http-equiv") or "").lower() == "refresh":
            match = re.search(r"url=(.+)$", values.get("content") or "", re.IGNORECASE)
            if match:
                self.refresh = match.group(1).strip()


def parse(page: Path) -> _PageParser:
    parser = _PageParser()
    parser.feed(page.read_text(encoding="utf-8", errors="replace"))
    return parser


def is_external(url: str) -> bool:
    return url.startswith(("//", "#", "data:", "mailto:", "javascript:", "tel:")) or bool(urlsplit(url).scheme)


def resolve(site_dir: Path, page: Path, url: str) -> Path:
    path = unquote(urlsplit(url).path)
    if not path:
        return page
    base = site_dir if path.startswith("/") else page.parent
    target = base / path.lstrip("/")
    if path.endswith("/") or target.is_dir():
        target = target / "index.html"
    return target


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def html_pages(site_dir: Path) -> list[Path]:
    return sorted(
        page
        for page in site_dir.rglob("*.html")
        if not SKIP_DIR_NAMES.intersection(page.relative_to(site_dir).parts[:-1])
    )


def check_redirects(site_dir: Path, redirects: dict[str, str] = REDIRECTS) -> list[str]:
    errors = []
    for old, new in redirects.items():
        page = output_file(site_dir, old)
        if not page.is_file():
            errors.append(f"redirect {old}: page is missing")
            continue
        target = parse(page).refresh
        if target != new:
            errors.append(f"redirect {old}: points to {target!r}, expected {new!r}")
        if not output_file(site_dir, new).is_file():
            errors.append(f"redirect {old}: target {new} does not exist")
    return errors


def check_internal_links(site_dir: Path) -> list[str]:
    errors = []
    for page in html_pages(site_dir):
        for _tag, attr, url in parse(page).links:
            if not is_external(url) and not resolve(site_dir, page, url).exists():
                errors.append(f"{rel(page, site_dir)}: broken {attr} {url}")
    return errors


def page_weight(site_dir: Path, page: Path) -> int:
    total = len(gzip.compress(page.read_bytes()))
    for tag, attr, url in parse(page).links:
        if is_external(url) or (tag, attr) not in {("script", "src"), ("link", "href")}:
            continue
        target = resolve(site_dir, page, url)
        if target.suffix in {".js", ".css"} and target.is_file():
            total += len(gzip.compress(target.read_bytes()))
    return total


def check_page_budgets(site_dir: Path, max_bytes: int = MAX_PAGE_BYTES) -> list[str]:
    blog = site_dir / "blog"
    errors = []
    for page in [blog / "index.html", *sorted(blog.glob("*/index.html"))]:
        if not page.is_file():
            errors.append(f"{rel(page, site_dir)}: page is missing")
            continue
        weight = page_weight(site_dir, page)
        if weight > max_bytes:
            errors.append(f"{rel(page, site_dir)}: {weight} bytes compressed (limit {max_bytes})")
    return errors


def check_image_sizes(blog_dir: Path, max_bytes: int = MAX_IMAGE_BYTES) -> list[str]:
    errors = []
    for image in sorted(blog_dir.rglob("*")):
        relative = image.relative_to(blog_dir)
        if not image.is_file() or image.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if relative.parts[0] in SKIP_SOURCE_DIRS:
            continue
        size = image.stat().st_size
        if size > max_bytes:
            errors.append(f"blog/{relative.as_posix()}: {size} bytes (limit {max_bytes})")
    return errors


def post_slugs(blog_dir: Path) -> set[str]:
    """Folders under blog/ whose index.qmd has a date in its front matter."""
    slugs = set()
    for qmd in blog_dir.glob("*/index.qmd"):
        match = re.match(r"---\n(.*?)\n---\n", qmd.read_text(encoding="utf-8"), re.DOTALL)
        if match and re.search(r"^date:", match.group(1), re.MULTILINE):
            slugs.add(qmd.parent.name)
    return slugs


def check_listing(site_dir: Path, slugs: set[str]) -> list[str]:
    feed = site_dir / "blog" / "index.xml"
    if not feed.is_file():
        return ["blog/index.xml: feed is missing"]
    items = set()
    for item in ElementTree.parse(feed).getroot().iter("item"):
        link = (item.findtext("link") or "").strip()
        items.add(urlsplit(link).path.removesuffix("index.html"))
    expected = {f"/blog/{slug}/" for slug in slugs}
    errors = [f"feed: post {path} is missing" for path in sorted(expected - items)]
    errors += [f"feed: {path} is not a post" for path in sorted(items - expected)]
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument("--blog", type=Path, default=Path("blog"))
    args = parser.parse_args(argv)
    errors = [
        *check_redirects(args.site),
        *check_internal_links(args.site),
        *check_page_budgets(args.site),
        *check_image_sizes(args.blog),
        *check_listing(args.site, post_slugs(args.blog)),
    ]
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)
    if errors:
        print(f"{len(errors)} site check(s) failed", file=sys.stderr)
        return 1
    print("All site checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
