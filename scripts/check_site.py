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
        parser = parse(page)
        # Skip redirect pages; check_redirects already validates their targets
        if parser.refresh is not None:
            continue
        for _tag, attr, url in parser.links:
            if not is_external(url) and not resolve(site_dir, page, url).exists():
                errors.append(f"{rel(page, site_dir)}: broken {attr} {url}")
    return errors


def page_weight(site_dir: Path, page: Path, is_post: bool = False) -> int:
    total = len(gzip.compress(page.read_bytes()))
    counted_files = set()
    for tag, attr, url in parse(page).links:
        if is_external(url) or (tag, attr) not in {("script", "src"), ("link", "href")}:
            continue
        target = resolve(site_dir, page, url)
        if target.suffix in {".js", ".css"} and target.is_file():
            total += len(gzip.compress(target.read_bytes()))
            counted_files.add(target)
    # For post pages, also count data files (.js, .mjs, .json, .csv) in the post folder
    if is_post:
        post_dir = page.parent
        data_suffixes = {".js", ".mjs", ".json", ".csv"}
        for data_file in sorted(post_dir.iterdir()):
            if data_file.is_file() and data_file.suffix in data_suffixes and data_file not in counted_files:
                total += len(gzip.compress(data_file.read_bytes()))
    return total


def check_page_budgets(site_dir: Path, max_bytes: int = MAX_PAGE_BYTES) -> list[str]:
    blog = site_dir / "blog"
    errors = []
    for page in [blog / "index.html", *sorted(blog.glob("*/index.html"))]:
        if not page.is_file():
            errors.append(f"{rel(page, site_dir)}: page is missing")
            continue
        # is_post is True for pages like blog/post/index.html, False for blog/index.html
        is_post = page.parent != blog
        weight = page_weight(site_dir, page, is_post=is_post)
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


def check_comments(site_dir: Path, slugs: set[str]) -> list[str]:
    blog = site_dir / "blog"
    errors = []
    for page in [blog / "index.html", *sorted(blog.glob("*/index.html"))]:
        if not page.is_file():
            continue
        is_post = page.parent != blog and page.parent.name in slugs
        has_comments = "giscus.app/client.js" in page.read_text(encoding="utf-8", errors="replace")
        if is_post and not has_comments:
            errors.append(f"{rel(page, site_dir)}: comments are missing")
        if not is_post and has_comments:
            errors.append(f"{rel(page, site_dir)}: comments must be off")
    return errors


GOATCOUNTER_TAG = 'data-goatcounter="https://lukeschiefelbein.goatcounter.com/count"'
ONE_URL_SCRIPT = "history.replaceState"  # blog/_includes/one-url.html
LAZY_GISCUS = 'script.dataset.loading = "lazy";'  # scripts/build.py lazy_giscus


def check_feed(site_dir: Path) -> list[str]:
    """Feed items are for feed readers: no site header, no scripts, no interactive islands."""
    errors = []
    for name in ("index.xml", "feed.xml"):
        feed = site_dir / "blog" / name
        if not feed.is_file():
            continue
        for item in ElementTree.parse(feed).getroot().iter("item"):
            title = item.findtext("title") or "?"
            description = item.findtext("description") or ""
            for part, text in (("site-header", "the site header"), ("<script", "a script"),
                               ('class="mb-cell"', "an interactive island")):
                if part in description:
                    errors.append(f"blog/{name}: item {title!r} has {text}")
    return errors


def check_page_scripts(site_dir: Path) -> list[str]:
    """In each blog page with the GoatCounter tag, the one-path script must come before the tag
    (GoatCounter and giscus read the address). A page with the giscus loader must load the comment
    frame lazily."""
    errors = []
    for page in sorted((site_dir / "blog").rglob("*.html")):
        text = page.read_text(encoding="utf-8", errors="replace")
        tag = text.find(GOATCOUNTER_TAG)
        if tag >= 0 and not 0 <= text.find(ONE_URL_SCRIPT) < tag:
            errors.append(f"{rel(page, site_dir)}: the one-path script must come before the GoatCounter tag")
        if "giscus.app/client.js" in text and LAZY_GISCUS not in text:
            errors.append(f"{rel(page, site_dir)}: the comment frame must load lazily")
        if page.parent.name == "live" and page.name == "index.html" and tag < 0:
            errors.append(f"{rel(page, site_dir)}: the live notebook has no GoatCounter tag")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--site", type=Path, default=Path("_site"))
    parser.add_argument("--blog", type=Path, default=Path("blog"))
    args = parser.parse_args(argv)
    slugs = post_slugs(args.blog)
    errors = [
        *check_redirects(args.site),
        *check_internal_links(args.site),
        *check_page_budgets(args.site),
        *check_image_sizes(args.blog),
        *check_listing(args.site, slugs),
        *check_comments(args.site, slugs),
        *check_page_scripts(args.site),
        *check_feed(args.site),
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
