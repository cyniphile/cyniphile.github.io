# Blog Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace three blog repos with one fast site in `cyniphile.github.io`. The landing page stays at `/`, a Quarto blog is at `/blog/`, the GP post has precomputed interactivity, and all old URLs redirect.

**Architecture:** `site-root/` holds static files that the build copies to `/`. `blog/` is a Quarto project. Python runs at build time (frozen), and Observable JS only connects precomputed data to charts. `scripts/build.py` renders the blog, exports marimo live notebooks, copies the static files, writes redirect pages from one list, and runs `scripts/check_site.py`. GitHub Actions runs the build and deploys `_site/` to GitHub Pages.

**Tech Stack:** Quarto 1.10.18 (Jupyter engine, Observable JS, Observable Plot), Python 3.13 with uv, numpy, marimo 0.25 (live notebook export), pytest, Node 22 (`node --test`), Pillow and ffmpeg (one-time media conversion), GitHub Actions and GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-09-28-blog-consolidation-design.md`

## Global Constraints

- Repo: `~/self/cyniphile.github.io`, branch `blog-consolidation`. The default branch is `master`. Do not push to `master` before Task 16. (GitHub Pages publishes `master` as it is until the cutover.)
- Quarto version: exactly 1.10.18, on the laptop and in CI.
- Python: 3.13 or later. Packages come from `uv.lock`. Run all Python with `uv run`.
- Post budget: the HTML with its local scripts, styles and data must be less than 1.5 MB compressed. Images and `/live/` folders are not included.
- Each image in `blog/` must be less than 300 KB.
- Phone targets (Chrome emulation with Fast 4G, 4× CPU slowdown, empty cache): the first text of each post shows in less than 2 s. The GP widgets work in less than 3 s.
- JavaScript does no vector or matrix math. Short scalar formulas are permitted: μ + σ·z, the RBF formula for one pair of points, and the 2×2 Cholesky formula.
- Python does all other math, in `blog/gaussian-processes/gp_data.py`, with fixed seeds from `np.random.default_rng`.
- A stored set has 50 samples: `POOL = 50` in Python and `POOL_SIZE = 50` in JavaScript.
- Colors: red `#c33f3f`, teal `#52c2c7`, dark teal `#1b7f86` (links in the light theme), yellow-green `#cdd63e`, text gray `#403f3f`.
- The GoatCounter tag on each page: `<script data-goatcounter="https://lukeschiefelbein.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>`
- Site URL: `https://www.lukeschiefelbein.com`. The Quarto `site-url` is `https://www.lukeschiefelbein.com/blog`.
- Each change to GitHub settings, each push, and each action on an external site needs the owner's approval first.
- Text for the owner (README, messages, PR text) uses ASD-STE100 Simplified Technical English.
- Commit messages end with the line `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Bad text in the GP "Points" box** (letters, empty text, extra commas, more than 30 numbers). Expected behavior: a clear message, and the page continues to work. Test: Task 10, the `parsePoints` tests.
2. **Covariance inputs that give an invalid matrix** (Σ₁₂² > Σ₁₁·Σ₂₂), a zero variance, or an empty number box. Expected behavior: an error message or a correct flat cloud, and never NaN points. Test: Task 10, the `mvn2` tests.
3. **More than 50 clicks on a "New Sample" button**, also for the same ℓ in the double plot. Expected behavior: the chart stops at 50 samples, with no error. Test: Task 10, the `addSample` and `picksToSamples` tests.
4. **An old URL with an encoded space** (`/blog/election%20fraud/...`) **or a trailing slash**. Expected behavior: the redirect page is at the exact file that GitHub Pages serves. Test: Task 1, the `output_file` tests.
5. **A future post or static file at an old URL path.** Expected behavior: the build stops. It does not replace the real page with a redirect. Test: Task 1, the `write_redirects` collision test.

Also covered: extreme ℓ values that give a nearly singular covariance matrix (Task 9, the finite-values tests).

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock` | Python tooling and ignored build output | 1 |
| `tests/conftest.py` | Puts `scripts/` and `blog/gaussian-processes/` on `sys.path` for tests | 1 |
| `scripts/redirects.py` | The list of old URL paths, and the redirect pages | 1 |
| `scripts/check_site.py` | All automatic checks of the built `_site/` | 2, 13 |
| `scripts/build.py` | The full build: render, export, copy, redirects, feed copy, checks | 3 |
| `site-root/` | The landing page, 404 page, CNAME, robots.txt, sitemap.xml | 4, 5 |
| `design/` | GIMP source files that the site does not publish | 4 |
| `blog/_quarto.yml`, `blog/theme-*.scss`, `blog/_includes/goatcounter.html`, `blog/images/` | The Quarto site: navigation, themes, analytics, logo | 6, 13 |
| `blog/index.qmd`, `blog/about/index.qmd`, `blog/subscribe/index.qmd` | The post list, About page and Subscribe page | 6, 13 |
| `scripts/migrate_fastpages.py` | One-time converter of the 3 fastpages posts | 7 |
| `blog/abortion/`, `blog/voter-fraud/`, `blog/biology-rust/` | The 3 migrated posts and their images | 8 |
| `blog/gaussian-processes/gp_data.py` | All GP math and precomputed data | 9 |
| `blog/gaussian-processes/wiring.js`, `wiring.test.mjs` | JavaScript helpers for the widgets, and their tests | 10 |
| `blog/gaussian-processes/index.qmd`, `gp-posterior.jpg` | The GP post | 11 |
| `blog/gaussian-processes/live.py` | The unchanged marimo notebook, exported to `/blog/gaussian-processes/live/` | 12 |
| `.github/workflows/publish.yml`, `README.md` | CI build and deploy, and instructions for the owner | 14 |

---

### Task 1: Python tooling and the redirect list

**Files:**
- Create: `.gitignore`, `.python-version`, `pyproject.toml`, `uv.lock` (made by uv)
- Create: `tests/conftest.py`, `tests/test_redirects.py`
- Create: `scripts/redirects.py`

**Interfaces:**
- Consumes: nothing.
- Produces: in `scripts/redirects.py`:
  - `SITE_URL: str = "https://www.lukeschiefelbein.com"`
  - `REDIRECTS: dict[str, str]` (old URL path → new URL path)
  - `output_file(site_dir: Path, url_path: str) -> Path`
  - `redirect_page(new_path: str) -> str`
  - `write_redirects(site_dir: Path, redirects: dict[str, str] = REDIRECTS) -> list[Path]` (raises `FileExistsError` if a file already exists at an old path)

- [ ] **Step 1: Make sure you are on the work branch**

Run: `cd ~/self/cyniphile.github.io && git switch blog-consolidation && git status --short --branch`
Expected: `## blog-consolidation` and no changed files.

- [ ] **Step 2: Write the tooling files**

`.gitignore`:

```gitignore
# Build output
/_site/
/blog/_site/
/blog/.quarto/
**/*.quarto_ipynb

# Python
.venv/
__pycache__/
.pytest_cache/

# Local tools
.DS_Store
.claude/worktrees/
```

`.python-version`:

```text
3.13
```

`pyproject.toml`:

```toml
[project]
name = "lukeschiefelbein-site"
version = "0.1.0"
description = "Build tools for www.lukeschiefelbein.com"
requires-python = ">=3.13"
dependencies = [
    "numpy>=2.2",
    "ipykernel>=6.29",
    "nbclient>=0.10",
    "nbformat>=5.10",
    "pyyaml>=6.0",
    "marimo>=0.25.0",
]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "pillow>=11.0",
    "matplotlib>=3.9",
]

[tool.uv]
package = false

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Install the packages**

Run: `uv sync`
Expected: uv makes `.venv/` and `uv.lock`, and it prints `Installed N packages` with no error.

- [ ] **Step 4: Write the failing tests**

`tests/conftest.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "blog" / "gaussian-processes"))
```

`tests/test_redirects.py`:

```python
import pytest

from redirects import REDIRECTS, SITE_URL, output_file, redirect_page, write_redirects


def test_output_file_for_a_directory_url(tmp_path):
    assert output_file(tmp_path, "/blog/search/") == tmp_path / "blog" / "search" / "index.html"


def test_output_file_for_a_file_url(tmp_path):
    url = "/blog/abortion/politics/2020/10/20/abortion.html"
    assert output_file(tmp_path, url) == tmp_path / "blog/abortion/politics/2020/10/20/abortion.html"


def test_output_file_decodes_an_encoded_space(tmp_path):
    url = "/blog/election%20fraud/politics/2020/11/12/voter-fraud.html"
    expected = tmp_path / "blog" / "election fraud" / "politics/2020/11/12/voter-fraud.html"
    assert output_file(tmp_path, url) == expected


def test_redirect_page_points_to_the_new_path():
    page = redirect_page("/blog/abortion/")
    assert '<meta http-equiv="refresh" content="0; url=/blog/abortion/">' in page
    assert f'<link rel="canonical" href="{SITE_URL}/blog/abortion/">' in page
    assert '<a href="/blog/abortion/">' in page


def test_write_redirects_writes_one_page_for_each_old_url(tmp_path):
    written = write_redirects(tmp_path)
    assert len(written) == len(REDIRECTS)
    for old, new in REDIRECTS.items():
        assert f"url={new}" in output_file(tmp_path, old).read_text(encoding="utf-8")


def test_write_redirects_refuses_to_replace_a_real_page(tmp_path):
    page = output_file(tmp_path, "/blog/search/")
    page.parent.mkdir(parents=True)
    page.write_text("a real page", encoding="utf-8")
    with pytest.raises(FileExistsError, match="/blog/search/"):
        write_redirects(tmp_path)
    assert page.read_text(encoding="utf-8") == "a real page"
    assert not output_file(tmp_path, "/marimo-blog/").exists()
```

- [ ] **Step 5: Run the tests to see them fail**

Run: `uv run pytest tests/test_redirects.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'redirects'`.

- [ ] **Step 6: Write the implementation**

`scripts/redirects.py`:

```python
"""Old URL paths of the site, and the redirect pages that send readers to the new paths."""

from __future__ import annotations

import html
from pathlib import Path
from urllib.parse import unquote

SITE_URL = "https://www.lukeschiefelbein.com"

REDIRECTS: dict[str, str] = {
    "/blog/search/": "/blog/",
    "/blog/categories/": "/blog/",
    "/blog/abortion/politics/2020/10/20/abortion.html": "/blog/abortion/",
    "/blog/election%20fraud/politics/2020/11/12/voter-fraud.html": "/blog/voter-fraud/",
    "/blog/programming/rust/biology/2021/12/01/biology-rust.html": "/blog/biology-rust/",
    "/marimo-blog/": "/blog/gaussian-processes/",
    "/marimo-blog/apps/Intro_to_Gaussian_Process_Regression.html": "/blog/gaussian-processes/",
}


def output_file(site_dir: Path, url_path: str) -> Path:
    """Return the file that GitHub Pages serves for url_path."""
    relative = unquote(url_path).lstrip("/")
    if url_path.endswith("/"):
        relative += "index.html"
    return site_dir / relative


def redirect_page(new_path: str) -> str:
    """Return an HTML page that sends browsers and search engines to new_path."""
    target = html.escape(new_path, quote=True)
    canonical = html.escape(SITE_URL + new_path, quote=True)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Page moved</title>\n"
        f'<link rel="canonical" href="{canonical}">\n'
        f'<meta http-equiv="refresh" content="0; url={target}">\n'
        "</head>\n"
        "<body>\n"
        f'<p>This page moved to <a href="{target}">{canonical}</a>.</p>\n'
        "</body>\n"
        "</html>\n"
    )


def write_redirects(site_dir: Path, redirects: dict[str, str] = REDIRECTS) -> list[Path]:
    """Write a redirect page at each old path. Stop if a real page is already there."""
    collisions = [old for old in redirects if output_file(site_dir, old).exists()]
    if collisions:
        raise FileExistsError(f"Real pages exist at old URLs: {', '.join(collisions)}")
    written = []
    for old, new in redirects.items():
        page = output_file(site_dir, old)
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(redirect_page(new), encoding="utf-8")
        written.append(page)
    return written
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `uv run pytest tests/test_redirects.py -v`
Expected: `6 passed`.

- [ ] **Step 8: Commit**

```bash
git add .gitignore .python-version pyproject.toml uv.lock tests/conftest.py tests/test_redirects.py scripts/redirects.py
git commit -m "build: add Python tooling and the redirect list for old URLs

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Site checks

**Files:**
- Create: `scripts/check_site.py`
- Create: `tests/test_check_site.py`

**Interfaces:**
- Consumes: `REDIRECTS`, `SITE_URL`, `output_file`, `write_redirects` from `scripts/redirects.py` (Task 1).
- Produces: in `scripts/check_site.py` (each check returns a list of error strings; an empty list means OK):
  - `check_redirects(site_dir: Path, redirects: dict[str, str] = REDIRECTS) -> list[str]`
  - `check_internal_links(site_dir: Path) -> list[str]`
  - `check_page_budgets(site_dir: Path, max_bytes: int = MAX_PAGE_BYTES) -> list[str]`
  - `check_image_sizes(blog_dir: Path, max_bytes: int = MAX_IMAGE_BYTES) -> list[str]`
  - `post_slugs(blog_dir: Path) -> set[str]`
  - `check_listing(site_dir: Path, slugs: set[str]) -> list[str]`
  - `main(argv: list[str] | None = None) -> int` (0 = all checks passed, 1 = a check failed; options `--site` and `--blog`)

- [ ] **Step 1: Write the failing tests**

`tests/test_check_site.py`:

```python
import os
from pathlib import Path

from check_site import (
    check_image_sizes,
    check_internal_links,
    check_listing,
    check_page_budgets,
    check_redirects,
    main,
    post_slugs,
)
from redirects import output_file, write_redirects


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def site_with_targets(site: Path) -> Path:
    for new in ["/blog/", "/blog/abortion/", "/blog/voter-fraud/", "/blog/biology-rust/", "/blog/gaussian-processes/"]:
        write(output_file(site, new), "page")
    return site


def test_redirects_pass_when_all_pages_exist(tmp_path):
    site = site_with_targets(tmp_path)
    write_redirects(site)
    assert check_redirects(site) == []


def test_redirects_report_a_missing_page(tmp_path):
    site = site_with_targets(tmp_path)
    assert "redirect /marimo-blog/: page is missing" in check_redirects(site)


def test_redirects_report_a_wrong_target(tmp_path):
    site = site_with_targets(tmp_path)
    write_redirects(site)
    write(output_file(site, "/marimo-blog/"), '<meta http-equiv="refresh" content="0; url=/blog/">')
    assert check_redirects(site) == [
        "redirect /marimo-blog/: points to '/blog/', expected '/blog/gaussian-processes/'"
    ]


def test_redirects_report_a_missing_target(tmp_path):
    write_redirects(tmp_path)
    assert "redirect /blog/search/: target /blog/ does not exist" in check_redirects(tmp_path)


def test_internal_links_find_a_broken_link(tmp_path):
    write(
        tmp_path / "index.html",
        '<a href="/blog">b</a> <a href="https://example.com">e</a> <a href="#top">t</a>'
        ' <script src="//gc.zgo.at/count.js"></script>',
    )
    write(tmp_path / "blog/index.html", '<a href="./post/">p</a> <img src="missing.png">')
    write(
        tmp_path / "blog/post/index.html",
        '<a href="../index.html">up</a> <img src="my%20image.png"> <video data-src="/img/clip.mp4"></video>',
    )
    write(tmp_path / "blog/post/my image.png", "x")
    write(tmp_path / "img/clip.mp4", "x")
    assert check_internal_links(tmp_path) == ["blog/index.html: broken src missing.png"]


def test_internal_links_skip_live_notebooks(tmp_path):
    write(tmp_path / "blog/gp/live/index.html", '<script src="./assets/missing.js"></script>')
    assert check_internal_links(tmp_path) == []


def test_page_budget_counts_local_scripts(tmp_path):
    write(tmp_path / "blog/index.html", '<script src="big.js"></script>')
    (tmp_path / "blog/big.js").write_bytes(os.urandom(5000))
    errors = check_page_budgets(tmp_path, max_bytes=4000)
    assert len(errors) == 1
    assert errors[0].startswith("blog/index.html: ")
    assert check_page_budgets(tmp_path, max_bytes=100_000) == []


def test_page_budget_reports_a_missing_post_list(tmp_path):
    assert check_page_budgets(tmp_path) == ["blog/index.html: page is missing"]


def test_image_sizes(tmp_path):
    (tmp_path / "post").mkdir()
    (tmp_path / "post/big.png").write_bytes(b"0" * 301)
    (tmp_path / "post/small.webp").write_bytes(b"0" * 10)
    (tmp_path / "_freeze").mkdir()
    (tmp_path / "_freeze/big.png").write_bytes(b"0" * 999)
    assert check_image_sizes(tmp_path, max_bytes=300) == ["blog/post/big.png: 301 bytes (limit 300)"]


def test_post_slugs_only_count_pages_with_a_date(tmp_path):
    write(tmp_path / "abortion/index.qmd", "---\ntitle: A\ndate: '2020-10-20'\n---\ntext\n")
    write(tmp_path / "about/index.qmd", "---\ntitle: About\n---\ntext\n")
    assert post_slugs(tmp_path) == {"abortion"}


FEED = (
    '<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel>'
    "<title>Blog</title><link>https://www.lukeschiefelbein.com/blog/</link>{items}</channel></rss>"
)


def test_listing_matches_the_posts(tmp_path):
    items = "".join(
        f"<item><title>{slug}</title><link>https://www.lukeschiefelbein.com/blog/{slug}/index.html</link></item>"
        for slug in ["abortion", "about"]
    )
    write(tmp_path / "blog/index.xml", FEED.format(items=items))
    assert check_listing(tmp_path, {"abortion", "voter-fraud"}) == [
        "feed: post /blog/voter-fraud/ is missing",
        "feed: /blog/about/ is not a post",
    ]


def test_main_returns_1_for_an_empty_site(tmp_path, capsys):
    assert main(["--site", str(tmp_path / "_site"), "--blog", str(tmp_path / "blog")]) == 1
    assert "site check(s) failed" in capsys.readouterr().err
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_check_site.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'check_site'`.

- [ ] **Step 3: Write the implementation**

`scripts/check_site.py`:

```python
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
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_check_site.py -v`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/check_site.py tests/test_check_site.py
git commit -m "build: add automatic checks for the built site

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Build script

**Files:**
- Create: `scripts/build.py`
- Create: `tests/test_build.py`

**Interfaces:**
- Consumes: `write_redirects` (Task 1). `check_site.main` (Task 2).
- Produces: in `scripts/build.py`:
  - `run(cmd: list[str], cwd: Path) -> None` (raises `subprocess.CalledProcessError` on failure)
  - `live_notebooks(blog_dir: Path, site_dir: Path) -> list[tuple[Path, Path]]`
  - `copy_tree(src: Path, dst: Path) -> None`
  - `copy_feed(site_dir: Path) -> None` (raises `FileNotFoundError` without `blog/index.xml`)
  - `build(root: Path = ROOT) -> int` (the exit code of the checks)
  - Command line: `uv run scripts/build.py`

- [ ] **Step 1: Write the failing tests**

`tests/test_build.py`:

```python
import subprocess
from pathlib import Path

import pytest

import build


def fake_repo(root: Path) -> Path:
    (root / "blog/gaussian-processes").mkdir(parents=True)
    (root / "blog/gaussian-processes/live.py").write_text("", encoding="utf-8")
    (root / "blog/abortion").mkdir()
    (root / "blog/abortion/index.qmd").write_text("", encoding="utf-8")
    (root / "site-root").mkdir()
    (root / "site-root/index.html").write_text("landing", encoding="utf-8")
    return root


def fake_quarto_output(root: Path) -> None:
    out = root / "blog/_site"
    out.mkdir(parents=True)
    (out / "index.html").write_text("post list", encoding="utf-8")
    (out / "index.xml").write_text("<rss/>", encoding="utf-8")


def test_live_notebooks_map_each_live_py_to_a_live_folder(tmp_path):
    root = fake_repo(tmp_path)
    assert build.live_notebooks(root / "blog", root / "_site") == [
        (root / "blog/gaussian-processes/live.py", root / "_site/blog/gaussian-processes/live/index.html")
    ]


def test_copy_feed_copies_the_quarto_feed(tmp_path):
    (tmp_path / "blog").mkdir()
    (tmp_path / "blog/index.xml").write_text("<rss/>", encoding="utf-8")
    build.copy_feed(tmp_path)
    assert (tmp_path / "blog/feed.xml").read_text(encoding="utf-8") == "<rss/>"


def test_copy_feed_fails_without_a_feed(tmp_path):
    with pytest.raises(FileNotFoundError):
        build.copy_feed(tmp_path)


def test_build_runs_all_steps_in_order(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)
    (root / "_site").mkdir()
    (root / "_site/stale.html").write_text("old", encoding="utf-8")
    calls = []

    def fake_run(cmd, cwd):
        calls.append(cmd[:2])
        if cmd[:2] == ["quarto", "render"]:
            fake_quarto_output(root)

    monkeypatch.setattr(build, "run", fake_run)
    monkeypatch.setattr(build.check_site, "main", lambda argv: 0)
    assert build.build(root) == 0
    assert calls == [["quarto", "render"], ["marimo", "export"]]
    site = root / "_site"
    assert not (site / "stale.html").exists()
    assert (site / "index.html").read_text(encoding="utf-8") == "landing"
    assert (site / "blog/index.html").read_text(encoding="utf-8") == "post list"
    assert (site / "blog/feed.xml").read_text(encoding="utf-8") == "<rss/>"
    assert (site / "blog/abortion/politics/2020/10/20/abortion.html").is_file()


def test_build_returns_1_when_a_check_fails(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)

    def fake_run(cmd, cwd):
        if cmd[0] == "quarto":
            fake_quarto_output(root)

    monkeypatch.setattr(build, "run", fake_run)
    monkeypatch.setattr(build.check_site, "main", lambda argv: 1)
    assert build.build(root) == 1


def test_build_stops_when_a_command_fails(tmp_path, monkeypatch):
    root = fake_repo(tmp_path)

    def failing_run(cmd, cwd):
        raise subprocess.CalledProcessError(1, cmd)

    monkeypatch.setattr(build, "run", failing_run)
    with pytest.raises(subprocess.CalledProcessError):
        build.build(root)
    assert not (root / "_site/index.html").exists()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_build.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'build'`.

- [ ] **Step 3: Write the implementation**

`scripts/build.py`:

```python
"""Build the full site into _site/: the Quarto blog, marimo live notebooks, static files and redirects."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import check_site
from redirects import write_redirects

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def live_notebooks(blog_dir: Path, site_dir: Path) -> list[tuple[Path, Path]]:
    """Each blog/<slug>/live.py becomes _site/blog/<slug>/live/index.html."""
    return [
        (src, site_dir / "blog" / src.parent.name / "live" / "index.html")
        for src in sorted(blog_dir.glob("*/live.py"))
    ]


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def copy_feed(site_dir: Path) -> None:
    """Keep the old feed URL /blog/feed.xml for current RSS subscribers."""
    feed = site_dir / "blog" / "index.xml"
    if not feed.is_file():
        raise FileNotFoundError(f"Quarto did not write the feed {feed}")
    shutil.copyfile(feed, site_dir / "blog" / "feed.xml")


def build(root: Path = ROOT) -> int:
    site = root / "_site"
    blog = root / "blog"
    shutil.rmtree(site, ignore_errors=True)
    run(["quarto", "render", "blog"], cwd=root)
    copy_tree(blog / "_site", site / "blog")
    for src, out in live_notebooks(blog, site):
        run(
            ["marimo", "export", "html-wasm", str(src), "--mode", "run", "--no-show-code",
             "--execute", "-o", str(out), "-f"],
            cwd=root,
        )
    copy_tree(root / "site-root", site)
    write_redirects(site)
    copy_feed(site)
    return check_site.main(["--site", str(site), "--blog", str(blog)])


if __name__ == "__main__":
    sys.exit(build())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest -v`
Expected: all tests pass (`24 passed`).

- [ ] **Step 5: Commit**

```bash
git add scripts/build.py tests/test_build.py
git commit -m "build: add the full build script

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Landing page in `site-root/`, with small fixes

**Files:**
- Move: `index.html`, `404.html`, `CNAME`, `googledd6e83b608092f4a.html`, `css/`, `img/` → `site-root/`
- Move: `site-root/img/frontpage.xcf`, `site-root/img/frontpage_responsive.xcf` → `design/`
- Delete: `sitemap.xml` (the 2020 file)
- Modify: `site-root/index.html`, `site-root/img/favicon_package_v0.16/site.webmanifest`, `site-root/img/favicon_package_v0.16/browserconfig.xml`
- Create: `site-root/robots.txt`, `site-root/sitemap.xml`
- Create: `tests/test_site_root.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `site-root/` (copied to `/` by `build.py`). The landing page links to `/blog/` and `/blog/about/`.

- [ ] **Step 1: Write the failing tests**

`tests/test_site_root.py`:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_ROOT = ROOT / "site-root"
GOATCOUNTER = (
    '<script data-goatcounter="https://lukeschiefelbein.goatcounter.com/count" '
    'async src="//gc.zgo.at/count.js"></script>'
)


def read(name: str) -> str:
    return (SITE_ROOT / name).read_text(encoding="utf-8")


def test_landing_page_fixes():
    html = read("index.html")
    assert "relative_url" not in html
    assert "kit.fontawesome.com" not in html
    assert "UA-52542530" not in html
    assert GOATCOUNTER in html
    assert 'href="/blog/"' in html
    assert 'href="/blog/about/"' in html


def test_robots_lists_both_sitemaps():
    text = read("robots.txt")
    assert "Sitemap: https://www.lukeschiefelbein.com/sitemap.xml" in text
    assert "Sitemap: https://www.lukeschiefelbein.com/blog/sitemap.xml" in text


def test_root_sitemap_lists_the_landing_page():
    assert "<loc>https://www.lukeschiefelbein.com/</loc>" in read("sitemap.xml")


def test_favicon_files_use_the_real_icon_paths():
    assert '"/img/favicon_package_v0.16/android-chrome-144x144.png"' in read("img/favicon_package_v0.16/site.webmanifest")
    assert '"/img/favicon_package_v0.16/mstile-150x150.png"' in read("img/favicon_package_v0.16/browserconfig.xml")


def test_design_sources_are_not_published():
    assert not list(SITE_ROOT.rglob("*.xcf"))
    assert (ROOT / "design" / "frontpage.xcf").is_file()
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_site_root.py -v`
Expected: FAIL with `FileNotFoundError` for `site-root/index.html`.

- [ ] **Step 3: Move the files**

```bash
mkdir -p site-root design
git mv index.html 404.html CNAME googledd6e83b608092f4a.html css img site-root/
git mv site-root/img/frontpage.xcf site-root/img/frontpage_responsive.xcf design/
git rm -q sitemap.xml
```

- [ ] **Step 4: Replace `site-root/index.html`**

The look does not change. The changes: `<html>` and charset tags, the fixed `mask-icon` link, GoatCounter in place of Universal Analytics, no Font Awesome script, `alt` text, and trailing slashes on the two links.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Luke Schiefelbein</title>
  <link rel="canonical" href="https://www.lukeschiefelbein.com/">
  <link rel="apple-touch-icon" sizes="152x152" href="img/favicon_package_v0.16/apple-touch-icon.png">
  <link rel="icon" type="image/png" sizes="32x32" href="img/favicon_package_v0.16/favicon-32x32.png">
  <link rel="icon" type="image/png" sizes="16x16" href="img/favicon_package_v0.16/favicon-16x16.png">
  <link rel="manifest" href="img/favicon_package_v0.16/site.webmanifest">
  <link rel="mask-icon" href="img/favicon_package_v0.16/safari-pinned-tab.svg" color="#5bbad5">
  <meta name="description" content="I write and code. I grew up on a cattle ranch in Minnesota and now live in New York.">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <script data-goatcounter="https://lukeschiefelbein.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Lato:wght@900&display=swap" rel="stylesheet">
  <link rel="stylesheet" type="text/css" href="css/style.css">
</head>
<body>
<div id="content">
  <div id="block">
    <img src="img/frontpage-wobble.png" id="big" alt="Luke Schiefelbein, with colored wavy lines">
    <img src="img/frontpage_responsive.png" id="small" alt="Luke Schiefelbein, with colored wavy lines">
    <div class="links">
      <a style="font-family: 'Lato', sans-serif;" href="/blog/">blog</a>
      <a style="font-family: 'Lato', sans-serif;" href="/blog/about/">about</a>
    </div>
  </div>
</div>
</body>
</html>
```

- [ ] **Step 5: Write `robots.txt` and `sitemap.xml`**

`site-root/robots.txt`:

```text
User-agent: *
Allow: /

Sitemap: https://www.lukeschiefelbein.com/sitemap.xml
Sitemap: https://www.lukeschiefelbein.com/blog/sitemap.xml
```

`site-root/sitemap.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://www.lukeschiefelbein.com/</loc>
  </url>
</urlset>
```

- [ ] **Step 6: Fix the icon paths in the favicon files**

`site-root/img/favicon_package_v0.16/site.webmanifest`:

```json
{
    "name": "Luke Schiefelbein",
    "short_name": "Luke S.",
    "icons": [
        {
            "src": "/img/favicon_package_v0.16/android-chrome-144x144.png",
            "sizes": "144x144",
            "type": "image/png"
        }
    ],
    "theme_color": "#ffffff",
    "background_color": "#ffffff",
    "display": "standalone"
}
```

`site-root/img/favicon_package_v0.16/browserconfig.xml`:

```xml
<?xml version="1.0" encoding="utf-8"?>
<browserconfig>
    <msapplication>
        <tile>
            <square150x150logo src="/img/favicon_package_v0.16/mstile-150x150.png"/>
            <TileColor>#da532c</TileColor>
        </tile>
    </msapplication>
</browserconfig>
```

- [ ] **Step 7: Run the tests to see them pass**

Run: `uv run pytest tests/test_site_root.py -v`
Expected: `5 passed`.

- [ ] **Step 8: Compare the look with the live site**

Run: `python3 -m http.server 8766 -d site-root` (stop it with Ctrl+C when done).
Open `http://127.0.0.1:8766/` and `https://www.lukeschiefelbein.com/` side by side, at desktop width and at phone width (390 px).
Expected: the same image and the same two links in the same places.

- [ ] **Step 9: Commit**

```bash
git add -A site-root design tests/test_site_root.py
git commit -m "site: move the landing page to site-root and fix small errors

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

`git status --short` must show no remaining changes after this commit.

---

### Task 5: Random 404 page

**Files:**
- Create: `site-root/img/404-fire.mp4` (from the old blog GIF)
- Replace: `site-root/404.html`
- Modify: `tests/test_site_root.py`

**Interfaces:**
- Consumes: `site-root/` (Task 4).
- Produces: `site-root/404.html`, with element ids `v-ascii` and `v-gif`.

- [ ] **Step 1: Add the failing tests**

Add to the end of `tests/test_site_root.py`:

```python
import re


def test_404_has_two_versions_and_the_ascii_version_is_the_default():
    html = read("404.html")
    assert '<div id="v-ascii">' in html
    assert '<div id="v-gif" hidden>' in html
    assert "Inquiry is fatal to certainty." in html
    assert "Page not found :(" in html


def test_404_loads_the_video_only_when_it_is_chosen():
    html = read("404.html")
    assert 'data-src="/img/404-fire.mp4"' in html
    assert 'src="/img/404-fire.mp4"' not in html.replace('data-src="/img/404-fire.mp4"', "")
    assert (SITE_ROOT / "img" / "404-fire.mp4").is_file()


def test_404_uses_absolute_local_paths():
    html = read("404.html")
    for url in re.findall(r'(?:src|href|data-src)="([^"]+)"', html):
        if not url.startswith(("http", "//")):
            assert url.startswith("/"), url


def test_404_counts_visits():
    assert GOATCOUNTER in read("404.html")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_site_root.py -v`
Expected: the 4 new tests FAIL (the current `404.html` has no `v-ascii` element).

- [ ] **Step 3: Convert the GIF to a looping video**

```bash
ffmpeg -y -loglevel error -i ~/self/blog/images/ezgif-4-8e06e988e74d.gif \
  -movflags +faststart -pix_fmt yuv420p -c:v libx264 -crf 23 -an site-root/img/404-fire.mp4
ls -l site-root/img/404-fire.mp4
```

Expected: a file much smaller than the 3.8 MB GIF (the GIF is 600 × 338, 30 frames at 10 fps).

Compare frame 15 of both files:

```bash
ffmpeg -y -loglevel error -i ~/self/blog/images/ezgif-4-8e06e988e74d.gif -vf "select=eq(n\,15)" -frames:v 1 "${TMPDIR:-/tmp}/gif15.png"
ffmpeg -y -loglevel error -i site-root/img/404-fire.mp4 -vf "select=eq(n\,15)" -frames:v 1 "${TMPDIR:-/tmp}/mp415.png"
```

Open both PNG files. Expected: they look the same.
If they do not look the same, use the GIF: run `cp ~/self/blog/images/ezgif-4-8e06e988e74d.gif site-root/img/404-fire.gif && git rm -q --cached site-root/img/404-fire.mp4; rm site-root/img/404-fire.mp4`. Then, in Step 4 and in the tests, use `/img/404-fire.gif`, and change the `<video ...></video>` element to `<img data-src="/img/404-fire.gif" width="600" height="338" alt="A server rack on fire">`.

- [ ] **Step 4: Replace `site-root/404.html`**

The ASCII art is the same as in the current file.

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>404: Not Found</title>
  <link rel="icon" type="image/png" sizes="32x32" href="/img/favicon_package_v0.16/favicon-32x32.png">
  <script data-goatcounter="https://lukeschiefelbein.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
  <style>
    body { margin: 0 16px; }
    #v-ascii .art { font-family: "Courier New", Courier, monospace; white-space: pre; overflow-x: auto; }
    #v-ascii .message { font-size: 23px; }
    #v-gif { margin: 10px auto; max-width: 600px; text-align: center; font-family: Helvetica, Arial, sans-serif; }
    #v-gif h1 { margin: 30px 0; font-size: 4em; line-height: 1; letter-spacing: -1px; }
    #v-gif video, #v-gif img { max-width: 100%; height: auto; }
  </style>
</head>
<body>
<div id="v-ascii">
<div class="art">

      ___________________          __________________________________
    .'                   \        / Inquiry is fatal to certainty.   \
   |                      \       \                 -- Will Durant   /
  /;~~~~~~L~A~S~~V~E~G~A~S~\       ----------------------------------
  |_________________________;
  .mm ',                     ',
  mMM   '.                     ',
  mM)    ,%=====================`
 =MM====+OOO000OOO   OOOO000OO
  (@)    OOO0000OO . OO000OOOO
   |      0000OOO , \ O000OOO          ~    ~ ~
    \.            '..'     .       ~ ~ ~  ~
     \                    .       ~  ~  ~ ~
      ',           ____  .       ~ ~ ~  ~ ~
      |  .        '---\\'       ~~~ ~~ ~
      |    ' .        ,\\     ~~~ ~~
     /Yy       ' .___.  \\  ~~ ~
    /YYYy           yYy\ **~
.uUUU\YYYy          YYYY\u.
UUUUUU\YYYYy        YYYY/UUUUuu.
</div>
<div class="message">
<h1>404: Not Found</h1>
<h2>Return to <a href="/">lukeschiefelbein.com</a></h2>
</div>
</div>

<div id="v-gif" hidden>
  <h1>404</h1>
  <p><strong>Page not found :(</strong></p>
  <video data-src="/img/404-fire.mp4" autoplay loop muted playsinline width="600" height="338"></video>
  <p><a href="/">Return to lukeschiefelbein.com</a></p>
</div>

<script>
  // Show one of the two versions at random. Load the video only for version B.
  if (Math.random() < 0.5) {
    const version = document.getElementById("v-gif");
    const media = version.querySelector("[data-src]");
    media.src = media.dataset.src;
    document.getElementById("v-ascii").hidden = true;
    version.hidden = false;
  }
</script>
</body>
</html>
```

- [ ] **Step 5: Run the tests to see them pass**

Run: `uv run pytest tests/test_site_root.py -v`
Expected: `9 passed`.

- [ ] **Step 6: See both versions in a browser**

Run: `python3 -m http.server 8766 -d site-root`, then open `http://127.0.0.1:8766/404.html` and reload it 6 times.
Expected: both versions show at least once. Version B plays the video in a loop. With JavaScript turned off, only version A shows.

- [ ] **Step 7: Commit**

```bash
git add site-root/404.html site-root/img/404-fire.* tests/test_site_root.py
git commit -m "site: show the ASCII or the GIF 404 page at random

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Quarto blog skeleton

> **Changed during execution (owner direction, 2026-09-29):** Task 6b replaced the look of this task (themes, navbar, logo, dark mode, About template) with the old fastpages look in light mode only. See spec section 8.6. The rest of this task (install, project, render list, freeze, GoatCounter) stays.

**Files:**
- Create: `blog/_quarto.yml`, `blog/theme-light.scss`, `blog/theme-dark.scss`, `blog/_includes/goatcounter.html`
- Create: `blog/images/logo-wobble.png`, `blog/images/bull.png`
- Create: `blog/index.qmd`, `blog/about/index.qmd`, `blog/subscribe/index.qmd`

**Interfaces:**
- Consumes: `site-root/img/frontpage-wobble.png` and `site-root/img/favicon_package_v0.16/apple-touch-icon.png` (Task 4).
- Produces: a Quarto website project in `blog/` that writes `blog/_site/`. The post list `blog/index.qmd` lists `*/index.qmd` pages, except the pages with the titles About and Subscribe. It writes the feed `blog/_site/index.xml`.

- [ ] **Step 1: Install Quarto 1.10.18 (no admin password)**

```bash
mkdir -p ~/.local/opt/quarto-1.10.18 ~/.local/bin
curl -fsSL -o "${TMPDIR:-/tmp}/quarto-1.10.18-macos.tar.gz" \
  https://github.com/quarto-dev/quarto-cli/releases/download/v1.10.18/quarto-1.10.18-macos.tar.gz
tar -xzf "${TMPDIR:-/tmp}/quarto-1.10.18-macos.tar.gz" -C ~/.local/opt/quarto-1.10.18
ln -sf "$(find ~/.local/opt/quarto-1.10.18 -path '*/bin/quarto' -type f | head -1)" ~/.local/bin/quarto
quarto --version
```

Expected: `1.10.18`.

- [ ] **Step 2: Check that Quarto finds the Python kernel**

Run: `uv run quarto check jupyter`
Expected: the output shows the Python from `.venv` and the kernel `python3`, with no error.

- [ ] **Step 3: Make the two images**

```bash
mkdir -p blog/images blog/_includes
cp site-root/img/favicon_package_v0.16/apple-touch-icon.png blog/images/bull.png
uv run python - <<'EOF'
import numpy as np
from PIL import Image

pixels = np.array(Image.open("site-root/img/frontpage-wobble.png").convert("RGBA"))[150:2050, 0:1600]
pixels[pixels[..., :3].min(axis=2) > 235, 3] = 0  # white background becomes transparent
lines = Image.fromarray(pixels)
lines = lines.crop(lines.getchannel("A").getbbox())
height = 96
logo = lines.resize((round(lines.width * height / lines.height), height), Image.LANCZOS)
logo.save("blog/images/logo-wobble.png", optimize=True)
print(logo.size)
EOF
```

Expected: a size of approximately `(122, 96)`. Open `blog/images/logo-wobble.png`. It shows only the red, teal and yellow-green lines, with no text and a transparent background.

- [ ] **Step 4: Write the project configuration and theme files**

`blog/_quarto.yml`:

```yaml
project:
  type: website
  render:
    - "**/*.qmd"

website:
  title: "Luke Schiefelbein"
  site-url: https://www.lukeschiefelbein.com/blog
  description: "Luke Schiefelbein writes about science, code and other things."
  open-graph: true
  twitter-card:
    creator: "@dj_rump_roast"
  search: true
  navbar:
    logo: images/logo-wobble.png
    logo-alt: "Colored wavy lines"
    logo-href: /
    title: "Luke Schiefelbein"
    right:
      - text: Blog
        href: index.qmd
      - text: About
        href: about/index.qmd
      - text: Subscribe
        href: subscribe/index.qmd
      - icon: rss
        href: index.xml
        aria-label: RSS feed

format:
  html:
    theme:
      light: [cosmo, theme-light.scss]
      dark: [darkly, theme-dark.scss]
    html-math-method: katex
    toc: true
    code-fold: true
    include-in-header: _includes/goatcounter.html

execute:
  freeze: auto
```

`blog/theme-light.scss`:

```scss
/*-- scss:defaults --*/
$primary: #1b7f86;
$link-color: #1b7f86;
$navbar-bg: #ffffff;
$navbar-fg: #403f3f;

/*-- scss:rules --*/
.navbar {
  border-bottom: 3px solid #cdd63e;
}

.navbar-brand img {
  max-height: 32px;
}

.about-image {
  image-rendering: pixelated;
}
```

`blog/theme-dark.scss`:

```scss
/*-- scss:defaults --*/
$primary: #52c2c7;
$link-color: #52c2c7;
$navbar-bg: #222222;
$navbar-fg: #e6e6e6;

/*-- scss:rules --*/
.navbar {
  border-bottom: 3px solid #cdd63e;
}

.navbar-brand img {
  max-height: 32px;
}

.about-image {
  image-rendering: pixelated;
}
```

`blog/_includes/goatcounter.html`:

```html
<script data-goatcounter="https://lukeschiefelbein.goatcounter.com/count" async src="//gc.zgo.at/count.js"></script>
```

- [ ] **Step 5: Write the three pages**

`blog/index.qmd`:

```markdown
---
title: "Blog"
listing:
  contents:
    - "*/index.qmd"
  exclude:
    title: "{About,Subscribe}"
  sort: "date desc"
  type: default
  categories: true
  sort-ui: false
  filter-ui: false
  fields: [image, date, title, description, categories]
  feed:
    items: 100
page-layout: full
title-block-banner: false
toc: false
---
```

`blog/about/index.qmd`:

```markdown
---
title: "About"
image: ../images/bull.png
about:
  template: trestles
  image-width: 10em
  links:
    - icon: twitter-x
      text: Twitter
      href: https://twitter.com/dj_rump_roast
    - icon: linkedin
      text: LinkedIn
      href: https://www.linkedin.com/in/lucas-schiefelbein/
    - icon: film
      text: IMDb
      href: https://www.imdb.com/user/ur27147194/
    - icon: book
      text: Goodreads
      href: https://www.goodreads.com/user/show/30189655-luke-schiefelbein
    - icon: music-note-beamed
      text: SoundCloud
      href: https://soundcloud.com/rump_roast
    - icon: github
      text: GitHub
      href: https://github.com/cyniphile
toc: false
---

I'm interested in a lot of things. I've written a [couple](https://writers.coverfly.com/profile/lukeschiefelbein) [movies](https://www.imdb.com/name/nm11624600/), [news articles](https://www.forbes.com/sites/lukeschiefelbein/), [electronic music](https://soundcloud.com/rump_roast), and [code](https://github.com/cyniphile) (usually for data science).

This website is powered by [Quarto](https://quarto.org).
```

`blog/subscribe/index.qmd`:

````markdown
---
title: "Subscribe"
toc: false
---

Get new posts by email:

```{=html}
<form action="https://lukeschiefelbein.us7.list-manage.com/subscribe/post?u=87bdb0aa63eaacd17f4e3ebd7&amp;id=b8799b10d7" method="post" target="_blank" class="d-flex gap-2 my-3" style="max-width: 32rem">
  <input type="email" name="EMAIL" class="form-control" placeholder="email address" aria-label="Email address" required>
  <!-- Mailchimp bot trap: real people do not fill in this field. -->
  <div style="position: absolute; left: -5000px;" aria-hidden="true"><input type="text" name="b_87bdb0aa63eaacd17f4e3ebd7_b8799b10d7" tabindex="-1" value=""></div>
  <button type="submit" class="btn btn-primary">Subscribe</button>
</form>
```

Or follow the blog with the [RSS feed](../index.xml).
````

- [ ] **Step 6: Render the skeleton**

Run: `uv run quarto render blog`
Expected: Quarto renders `index.qmd`, `about/index.qmd` and `subscribe/index.qmd` with no error. Then run `ls blog/_site/index.html blog/_site/about/index.html blog/_site/subscribe/index.html blog/_site/index.xml`. Expected: all 4 files exist.

(Do not run `scripts/build.py` yet. It needs the posts from Task 8.)

- [ ] **Step 7: Look at the pages**

Run: `uv run quarto preview blog`. Open the 3 pages. Use the switch in the navigation bar to see light mode and dark mode.
Expected:
- The logo shows the wavy lines on a white bar (light mode) and on a dark bar (dark mode), with a yellow-green line under the bar.
- The About page shows the pixel bull (sharp, not blurry) and 6 links with icons.
- The Subscribe page shows one email field and a Subscribe button.
- The post list is empty.

- [ ] **Step 8: Commit**

```bash
git add blog/_quarto.yml blog/theme-light.scss blog/theme-dark.scss blog/_includes blog/images blog/index.qmd blog/about blog/subscribe
git commit -m "blog: add the Quarto site with post list, About and Subscribe pages

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Converter for the fastpages posts

**Files:**
- Create: `scripts/migrate_fastpages.py`
- Create: `tests/test_migrate_fastpages.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: in `scripts/migrate_fastpages.py`:
  - `split_front_matter(text: str) -> tuple[dict, str]`
  - `post_date(filename: str) -> str`
  - `image_name(old: str) -> str`
  - `convert_footnotes(body: str) -> str`
  - `convert_youtube(body: str) -> str`
  - `remove_twitter_script(body: str) -> str`
  - `replace_dead_chart(body: str) -> str`
  - `convert_images(body: str, final_name: Callable[[str], str]) -> tuple[str, list[str]]`
  - `final_image_name(images_dir: Path, old: str) -> str`
  - `save_image(src: Path, dst: Path) -> None`
  - `convert_post(src: Path, images_dir: Path, out_dir: Path) -> Path`
  - Command line: `uv run scripts/migrate_fastpages.py --old-blog ~/self/blog --out blog`

- [ ] **Step 1: Write the failing tests**

`tests/test_migrate_fastpages.py`:

```python
import pytest
from PIL import Image

import migrate_fastpages as m


def test_post_date_pads_the_month_and_day():
    assert m.post_date("2021-12-1-biology-rust.md") == "2021-12-01"
    assert m.post_date("2020-10-20-abortion.md") == "2020-10-20"


def test_image_name_makes_simple_lowercase_names():
    assert m.image_name("Stright ticket ballot.jpg") == "stright-ticket-ballot.jpg"
    assert m.image_name("Abortion_Hurts_Women_(32676869635).jpg") == "abortion-hurts-women-32676869635.jpg"
    assert m.image_name("biology-rust/Schermata-2021-11-16-alle-15.51.28.png") == "schermata-2021-11-16-alle-15-51-28.png"


def test_convert_footnotes():
    body = (
        "certainly simple{% fn 2 %}, it works.\n\n"
        '{{ "Even the term “pro-life” is loaded." | fndetail: 2 }}\n'
        "{{ 'There is <a href=\"https://x.org\">little evidence</a>.' |  fndetail: 4 }}\n"
    )
    assert m.convert_footnotes(body) == (
        "certainly simple[^2], it works.\n\n"
        "[^2]: Even the term “pro-life” is loaded.\n"
        '[^4]: There is <a href="https://x.org">little evidence</a>.\n'
    )


def test_convert_youtube_keeps_the_start_time():
    body = (
        '<iframe width="560" height="315" src="https://www.youtube.com/embed/_80d95hMjC4?start=386" '
        'frameborder="0" allowfullscreen></iframe>\n'
        '<iframe width="560" height="315" src="https://www.youtube.com/embed/Ztu5Y5obWPk" frameborder="0"></iframe>'
    )
    assert m.convert_youtube(body) == (
        '{{< video https://www.youtube.com/embed/_80d95hMjC4 start="386" >}}\n'
        "{{< video https://www.youtube.com/embed/Ztu5Y5obWPk >}}"
    )


def test_remove_twitter_script_keeps_the_quote():
    body = (
        '<blockquote class="twitter-tweet"><p>Tweet text</p></blockquote> '
        '<script async src="https://platform.twitter.com/widgets.js" charset="utf-8"></script>\n'
    )
    assert m.remove_twitter_script(body) == '<blockquote class="twitter-tweet"><p>Tweet text</p></blockquote>\n'


def test_replace_dead_chart():
    body = (
        "Before.\n\n"
        "<!-- _interactive chart removed temporarily_  -->\n"
        '<div class="holds-the-iframe"><iframe id="myIframe" src="https://abortion-blog.herokuapp.com/" '
        'title="loading interactive plot..."></iframe></div>\n'
        "<script>\n  iFrameResize({ log: true }, '#myIframe')\n</script>\n\nAfter."
    )
    assert m.replace_dead_chart(body) == f"Before.\n\n{m.DEAD_CHART_NOTE}\n\nAfter."


def test_convert_images_handles_spaces_titles_and_extra_spaces():
    body = (
        '![]({{ site.baseurl }}/images/Stright ticket ballot.jpg "A ballot. https://commons.wikimedia.org")\n'
        "![]({{ site.baseurl }}/images/randolph.png )\n"
        "![fraud](https://example.com/external.jpg)\n"
    )
    new_body, found = m.convert_images(body, m.image_name)
    assert new_body == (
        '![](stright-ticket-ballot.jpg "A ballot. https://commons.wikimedia.org")\n'
        "![](randolph.png)\n"
        "![fraud](https://example.com/external.jpg)\n"
    )
    assert found == ["Stright ticket ballot.jpg", "randolph.png"]


def test_final_image_name_uses_webp_for_large_files(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "MAX_IMAGE_BYTES", 100)
    (tmp_path / "big shot.png").write_bytes(b"0" * 101)
    (tmp_path / "small.png").write_bytes(b"0" * 99)
    assert m.final_image_name(tmp_path, "big shot.png") == "big-shot.webp"
    assert m.final_image_name(tmp_path, "small.png") == "small.png"


def test_save_image_resizes_wide_images_to_webp(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "MAX_WIDTH", 100)
    Image.new("RGB", (300, 150), "teal").save(tmp_path / "wide.png")
    m.save_image(tmp_path / "wide.png", tmp_path / "out/wide.webp")
    with Image.open(tmp_path / "out/wide.webp") as out:
        assert out.format == "WEBP"
        assert out.size == (100, 50)


def test_save_image_fails_when_the_webp_is_still_too_large(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "MAX_IMAGE_BYTES", 10)
    Image.new("RGB", (50, 50), "teal").save(tmp_path / "a.png")
    with pytest.raises(ValueError, match="still larger"):
        m.save_image(tmp_path / "a.png", tmp_path / "a.webp")


def test_convert_post_writes_quarto_front_matter_and_copies_images(tmp_path):
    images = tmp_path / "old/images"
    images.mkdir(parents=True)
    Image.new("RGB", (20, 20), "red").save(images / "Header Image.png")
    Image.new("RGB", (20, 20), "blue").save(images / "chart.png")
    post = tmp_path / "old/_posts/2020-11-12-voter-fraud.md"
    post.parent.mkdir(parents=True)
    post.write_text(
        "---\n"
        "keywords: voting, fraud\n"
        "description: A close look.\n"
        "title: The State That Commits More Election Fraud\n"
        "toc: true\n"
        "badges: true\n"
        "comments: true\n"
        "categories: [election fraud, politics]\n"
        "image: images/Header Image.png\n"
        "layout: notebook\n"
        "---\n\n"
        "Text{% fn 1 %}.\n\n![]({{ site.baseurl }}/images/chart.png)\n\n"
        '{{ "A note." | fndetail: 1 }}\n',
        encoding="utf-8",
    )
    out = m.convert_post(post, images, tmp_path / "blog/voter-fraud")
    text = out.read_text(encoding="utf-8")
    assert text.startswith(
        "---\n"
        "title: The State That Commits More Election Fraud\n"
        "description: A close look.\n"
        "date: '2020-11-12'\n"
        "categories:\n"
        "- election fraud\n"
        "- politics\n"
        "keywords:\n"
        "- voting\n"
        "- fraud\n"
        "image: header-image.png\n"
        "toc: true\n"
        "---\n"
    )
    assert "Text[^1]." in text
    assert "![](chart.png)" in text
    assert "[^1]: A note." in text
    assert (tmp_path / "blog/voter-fraud/header-image.png").is_file()
    assert (tmp_path / "blog/voter-fraud/chart.png").is_file()


def test_convert_post_stops_on_unknown_liquid_tags(tmp_path):
    post = tmp_path / "2020-01-02-x.md"
    post.write_text("---\ntitle: X\n---\n{% include warning.html %}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Liquid"):
        m.convert_post(post, tmp_path, tmp_path / "out")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_migrate_fastpages.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'migrate_fastpages'`.

- [ ] **Step 3: Write the implementation**

`scripts/migrate_fastpages.py`:

```python
"""One-time converter: fastpages (Jekyll) posts to Quarto posts in blog/<slug>/index.qmd."""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path

import yaml
from PIL import Image

MAX_IMAGE_BYTES = 300_000
MAX_WIDTH = 1600

POSTS = {
    "2020-10-20-abortion.md": "abortion",
    "2020-11-12-voter-fraud.md": "voter-fraud",
    "2021-12-1-biology-rust.md": "biology-rust",
}

DEAD_CHART_NOTE = "::: {.callout-note}\nThe interactive chart for this post is no longer online.\n:::"


def split_front_matter(text: str) -> tuple[dict, str]:
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        raise ValueError("the post has no front matter")
    return yaml.safe_load(match.group(1)), text[match.end():]


def post_date(filename: str) -> str:
    year, month, day = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})-", filename).groups()
    return f"{year}-{int(month):02d}-{int(day):02d}"


def image_name(old: str) -> str:
    """'Stright ticket ballot.jpg' -> 'stright-ticket-ballot.jpg'. Folders are dropped."""
    path = Path(old)
    stem = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
    return stem + path.suffix.lower()


def convert_footnotes(body: str) -> str:
    body = re.sub(r"\{%\s*fn\s+(\d+)\s*%\}", r"[^\1]", body)
    return re.sub(
        r"\{\{\s*([\"'])(.*?)\1\s*\|\s*fndetail:\s*(\d+)\s*\}\}",
        lambda match: f"[^{match.group(3)}]: {match.group(2)}",
        body,
        flags=re.DOTALL,
    )


def convert_youtube(body: str) -> str:
    def video(match: re.Match) -> str:
        start = f' start="{match.group(2)}"' if match.group(2) else ""
        return f"{{{{< video https://www.youtube.com/embed/{match.group(1)}{start} >}}}}"

    return re.sub(
        r'<iframe[^>]*src="https://www\.youtube\.com/embed/([\w-]+)(?:\?start=(\d+))?"[^>]*>\s*</iframe>',
        video,
        body,
        flags=re.DOTALL,
    )


def remove_twitter_script(body: str) -> str:
    return re.sub(
        r'\s*<script async src="https://platform\.twitter\.com/widgets\.js" charset="utf-8"></script>',
        "",
        body,
    )


def replace_dead_chart(body: str) -> str:
    return re.sub(
        r'(<!--[^>]*-->\s*)?<div class="holds-the-iframe">.*?abortion-blog\.herokuapp\.com.*?</script>',
        DEAD_CHART_NOTE,
        body,
        flags=re.DOTALL,
    )


def convert_images(body: str, final_name: Callable[[str], str]) -> tuple[str, list[str]]:
    """Point {{ site.baseurl }}/images/... links at files in the post folder.

    Returns the new body and the old image paths (relative to the old images/ folder).
    """
    found: list[str] = []

    def link(match: re.Match) -> str:
        alt, old, title = match.group(1), match.group(2).strip(), match.group(3)
        found.append(old)
        title_part = f' "{title}"' if title else ""
        return f"![{alt}]({final_name(old)}{title_part})"

    new_body = re.sub(
        r'!\[([^\]]*)\]\(\{\{\s*site\.baseurl\s*\}\}/images/([^")]+?)\s*(?:"([^"]*)")?\s*\)',
        link,
        body,
    )
    return new_body, found


def needs_webp(src: Path) -> bool:
    return src.suffix.lower() in {".png", ".jpg", ".jpeg"} and src.stat().st_size > MAX_IMAGE_BYTES


def final_image_name(images_dir: Path, old: str) -> str:
    name = image_name(old)
    return str(Path(name).with_suffix(".webp")) if needs_webp(images_dir / old) else name


def save_image(src: Path, dst: Path) -> None:
    """Copy a small image. Convert a large one to WebP that is at most MAX_WIDTH wide."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.suffix != ".webp":
        shutil.copyfile(src, dst)
        return
    with Image.open(src) as image:
        if image.width > MAX_WIDTH:
            image = image.resize((MAX_WIDTH, round(image.height * MAX_WIDTH / image.width)), Image.LANCZOS)
        for quality in (85, 75, 65, 55):
            image.save(dst, "WEBP", quality=quality, method=6)
            if dst.stat().st_size <= MAX_IMAGE_BYTES:
                return
    raise ValueError(f"{src} is still larger than {MAX_IMAGE_BYTES} bytes as WebP")


def convert_front_matter(meta: dict, date: str, image: str | None) -> dict:
    out = {
        "title": meta["title"],
        "description": meta.get("description", ""),
        "date": date,
        "categories": list(meta.get("categories", [])),
    }
    if meta.get("keywords"):
        out["keywords"] = [word.strip() for word in str(meta["keywords"]).split(",")]
    if image:
        out["image"] = image
    out["toc"] = bool(meta.get("toc", False))
    return out


def convert_post(src: Path, images_dir: Path, out_dir: Path) -> Path:
    meta, body = split_front_matter(src.read_text(encoding="utf-8"))

    def rename(old: str) -> str:
        return final_image_name(images_dir, old)

    body, found = convert_images(body, rename)
    body = replace_dead_chart(remove_twitter_script(convert_youtube(convert_footnotes(body))))
    if re.search(r"\{\{(?!<)|\{%", body):
        raise ValueError(f"{src.name}: unconverted Liquid tags remain")
    header = meta["image"].removeprefix("images/") if meta.get("image") else None
    front = convert_front_matter(meta, post_date(src.name), rename(header) if header else None)
    out_dir.mkdir(parents=True, exist_ok=True)
    text = "---\n" + yaml.safe_dump(front, sort_keys=False, allow_unicode=True, width=1000) + "---\n" + body
    (out_dir / "index.qmd").write_text(text, encoding="utf-8")
    for old in dict.fromkeys(found + ([header] if header else [])):
        save_image(images_dir / old, out_dir / rename(old))
    return out_dir / "index.qmd"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-blog", type=Path, required=True, help="the old fastpages repo")
    parser.add_argument("--out", type=Path, default=Path("blog"))
    args = parser.parse_args(argv)
    for filename, slug in POSTS.items():
        path = convert_post(args.old_blog / "_posts" / filename, args.old_blog / "images", args.out / slug)
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_migrate_fastpages.py -v`
Expected: `12 passed`.

- [ ] **Step 5: Commit**

```bash
git add scripts/migrate_fastpages.py tests/test_migrate_fastpages.py
git commit -m "build: add a converter for the old fastpages posts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Move the three old posts

**Files:**
- Create (with the converter): `blog/abortion/`, `blog/voter-fraud/`, `blog/biology-rust/` (each with `index.qmd` and images)
- Modify: `blog/abortion/index.qmd` (description)

**Interfaces:**
- Consumes: `scripts/migrate_fastpages.py` (Task 7), `scripts/build.py` (Task 3), the Quarto project (Task 6).
- Produces: 3 posts with dates, at `/blog/abortion/`, `/blog/voter-fraud/` and `/blog/biology-rust/`.

- [ ] **Step 1: Run the converter**

Run: `uv run scripts/migrate_fastpages.py --old-blog ~/self/blog --out blog`
Expected:

```text
wrote blog/abortion/index.qmd
wrote blog/voter-fraud/index.qmd
wrote blog/biology-rust/index.qmd
```

- [ ] **Step 2: Remove the chart reference from the abortion description**

In `blog/abortion/index.qmd`, in the front matter, change the description:
- from: `... Partisan rhetoric dominates our news media (see the interactive chart below) and conversations. ...`
- to: `... Partisan rhetoric dominates our news media and conversations. ...`

- [ ] **Step 3: Check the external images**

```bash
grep -ohE '!\[[^]]*\]\(https?://[^ )"]+' blog/abortion/index.qmd blog/voter-fraud/index.qmd blog/biology-rust/index.qmd \
  | sed -E 's/.*\((https?:[^ )"]+).*/\1/' \
  | while read -r url; do printf "%s %s\n" "$(curl -s -o /dev/null -m 20 -w '%{http_code}' "$url")" "$url"; done
```

Expected: `200` for each image. If an image gives `404`, delete that image line from the post and tell the owner which image it was.

- [ ] **Step 4: Build the full site for the first time**

Run: `uv run scripts/build.py`
Expected: the build ends with `2 site check(s) failed`. The only errors are these two, because the GP post comes in Task 11:

```text
ERROR: redirect /marimo-blog/: target /blog/gaussian-processes/ does not exist
ERROR: redirect /marimo-blog/apps/Intro_to_Gaussian_Process_Regression.html: target /blog/gaussian-processes/ does not exist
```

If other errors show, correct them before you continue. (For example, an image larger than 300 KB means that `save_image` did not run for that file.)

- [ ] **Step 5: Look at the posts**

Run: `python3 -m http.server 8765 -d _site`, then open `http://127.0.0.1:8765/blog/`. Use a phone width (390 px) and a desktop width.
Expected:
- The post list shows the 3 posts with the newest first, each with its image, date, description and categories.
- Each post shows its images, and the footnote numbers link to the notes at the end.
- The YouTube players work, and the abortion post videos start at 6:26 and 4:31.
- The tweets show as quotes with a link.
- The abortion post shows the note "The interactive chart for this post is no longer online." at the place of the old chart.
- `http://127.0.0.1:8765/blog/abortion/politics/2020/10/20/abortion.html` goes to `/blog/abortion/`.

- [ ] **Step 6: Commit**

```bash
git add blog/abortion blog/voter-fraud blog/biology-rust
git commit -m "blog: move the three fastpages posts to Quarto

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: GP data module

> **Replaced 2026-10-01** (owner direction): the marimo → blog converter does this work. See `docs/superpowers/specs/2026-10-01-marimo-to-blog-design.md`. Do not implement this task.

**Files:**
- Create: `blog/gaussian-processes/gp_data.py`
- Create: `tests/test_gp_data.py`

**Interfaces:**
- Consumes: nothing.
- Produces: in `blog/gaussian-processes/gp_data.py`:
  - `SEED = 42`, `POOL = 50`, `JITTER = 1e-6`
  - `rbf(xa, xb, ell) -> np.ndarray`
  - `sample_pool(mean, cov, n=POOL, seed=SEED) -> np.ndarray` (shape `(n, len(mean))`)
  - `gp_posterior(y_train, x_train, x_test, ell=1.0) -> tuple[np.ndarray, np.ndarray]`
  - `page_data() -> dict` with these keys and shapes (lists of floats):
    - `regression`: `{"x": [10], "a": {...}, "b": {...}}`; each of `a` and `b` has `points` [10], `ols` [10], `truth` [10], `lines` [50][10], `betas` [50][2]
    - `hist`: `{"z": [5000]}`
    - `mvn2`: `{"z": [2500][2], "reference": [2500][2]}`
    - `iid`: `{"d1": [50][1], "d2": [50][2], "d3": [50][3], "d50": [50][50]}`
    - `fuzzy`: `{"x": [50], "ells": [1..30], "pools": {"1": [50][50], ..., "30": [50][50]}}`
    - `pi`: `{"x": [3], "labels": [3 str], "cov": [3][3], "pool": [50][3]}`
    - `real50`: `{"x": [50], "labels": [50 str], "cov": [50][50], "pool": [50][50]}`
    - `double`: `{"x": [50], "ells": [0.05, 0.1, ..., 2.0] (40), "pools": [40][50][50]}`
    - `post`: `{"x": [50], "labels": [50 str], "known": {"x": [15], "y": [15]}, "truth": {"x": [50], "y": [50]}, "mean": [50], "cov": [50][50], "pool": [50][50], "many": [500][50]}`

- [ ] **Step 1: Write the failing tests**

`tests/test_gp_data.py`:

```python
import gzip
import json

import numpy as np
import pytest

import gp_data


def test_rbf_is_one_on_the_diagonal_and_symmetric():
    x = np.linspace(0, 5, 7)
    k = gp_data.rbf(x, x, 1.5)
    assert np.allclose(np.diag(k), 1.0)
    assert np.allclose(k, k.T)


def test_rbf_known_value():
    assert gp_data.rbf([0.0], [1.0], 1.0)[0, 0] == pytest.approx(np.exp(-0.5))


def test_sample_pool_is_deterministic():
    cov = gp_data.rbf(np.arange(5), np.arange(5), 2.0)
    first = gp_data.sample_pool(np.zeros(5), cov, n=4, seed=7)
    second = gp_data.sample_pool(np.zeros(5), cov, n=4, seed=7)
    assert first.shape == (4, 5)
    assert np.array_equal(first, second)


@pytest.mark.parametrize(
    ("x", "ell"),
    [(np.linspace(0, 50, 50), 30.0), (np.linspace(-1, 1, 50), 2.0), (np.linspace(-1, 1, 50), 0.05)],
)
def test_sample_pool_is_finite_for_extreme_length_scales(x, ell):
    pool = gp_data.sample_pool(np.zeros(len(x)), gp_data.rbf(x, x, ell))
    assert np.isfinite(pool).all()


def test_gp_posterior_goes_through_the_training_data():
    x = np.array([0.0, 1.0, 2.5])
    y = np.array([1.0, -0.5, 0.3])
    mean, cov = gp_data.gp_posterior(y, x, x, ell=1.0)
    assert np.allclose(mean, y, atol=1e-6)
    assert np.allclose(np.diag(cov), 0.0, atol=1e-6)


def test_page_data_has_the_expected_shapes():
    data = gp_data.page_data()
    assert len(data["regression"]["a"]["lines"]) == 50
    assert len(data["regression"]["b"]["betas"][0]) == 2
    assert len(data["hist"]["z"]) == 5000
    assert len(data["mvn2"]["z"]) == 2500
    assert len(data["iid"]["d50"]) == 50 and len(data["iid"]["d50"][0]) == 50
    assert sorted(int(key) for key in data["fuzzy"]["pools"]) == list(range(1, 31))
    assert data["double"]["ells"][0] == 0.05 and data["double"]["ells"][-1] == 2.0
    assert len(data["double"]["ells"]) == 40
    assert len(data["double"]["pools"]) == 40 and len(data["double"]["pools"][0]) == 50
    assert len(data["post"]["pool"]) == 50 and len(data["post"]["many"]) == 500
    assert len(data["post"]["known"]["x"]) == 15


def test_page_data_is_finite_and_fits_the_budget():
    text = json.dumps(gp_data.page_data(), allow_nan=False)
    assert len(gzip.compress(text.encode())) < 800_000
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `uv run pytest tests/test_gp_data.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'gp_data'`.

- [ ] **Step 3: Write the implementation**

`blog/gaussian-processes/gp_data.py`:

```python
"""Precomputed data for the Gaussian process post.

All random numbers come from fixed seeds, so each build gives the same data.
A sample is mean + L @ z, where L is the Cholesky factor of the covariance.
All length scales use the same z, so the curves change smoothly when the reader moves a slider.
"""

from __future__ import annotations

import numpy as np

SEED = 42
POOL = 50
JITTER = 1e-6

HOUSING_X = [
    9.34825241, 9.67438030, 11.7250505, 5.99427279, 10.7375146, 3.87950162, 2.71045131,
    7.35740185, 9.13638194, 10.5863164, 7.42074188, 12.0328572, 5.15531137, 0.324806136,
    0.00132962952,
]
HOUSING_Y = [
    295011.54177245, 291803.4301587, 302340.03191297, 254244.52812629, 288037.40660445,
    225340.17067212, 235462.67258466, 291158.36183822, 297052.11645609, 287514.83630223,
    292359.62730391, 310157.34073017, 233483.05286424, 209630.56264745, 200039.88887763,
]


def rbf(xa, xb, ell):
    """RBF kernel: the covariance between each point in xa and each point in xb."""
    xa = np.asarray(xa, dtype=float).reshape(-1)
    xb = np.asarray(xb, dtype=float).reshape(-1)
    return np.exp(-0.5 / ell**2 * (xa[:, None] - xb[None, :]) ** 2)


def sample_pool(mean, cov, n=POOL, seed=SEED):
    """Draw n samples of N(mean, cov). The same seed gives the same standard-normal draws."""
    mean = np.asarray(mean, dtype=float)
    cov = np.asarray(cov, dtype=float)
    chol = np.linalg.cholesky(cov + JITTER * np.eye(len(cov)))
    z = np.random.default_rng(seed).standard_normal((n, len(cov)))
    return mean + z @ chol.T


def gp_posterior(y_train, x_train, x_test, ell=1.0):
    """Mean and covariance of a zero-mean GP with an RBF kernel, conditioned on training data."""
    k11 = rbf(x_train, x_train, ell)
    k21 = rbf(x_test, x_train, ell)
    k22 = rbf(x_test, x_test, ell)
    mean = k21 @ np.linalg.solve(k11, np.asarray(y_train, dtype=float))
    cov = k22 - k21 @ np.linalg.solve(k11, k21.T)
    return mean, (cov + cov.T) / 2


def _round(values, decimals=3):
    return np.round(np.asarray(values, dtype=float), decimals).tolist()


def regression_data(seed=SEED):
    rng = np.random.default_rng(seed)
    x = np.linspace(-3, 3, 10)
    noisy = x + rng.normal(0, 1.0, 10)
    less_noisy = x + rng.normal(0, 0.1, 10)
    slope_a = np.corrcoef(x, noisy)[0, 1] * np.std(noisy) / np.std(x)

    def panel(points, slope, spread, seed_offset):
        draws = np.random.default_rng(seed + seed_offset)
        b0 = draws.normal(0.0, spread, POOL)
        b1 = draws.normal(slope, spread, POOL)
        return {
            "points": _round(points),
            "ols": _round(np.polyval(np.polyfit(x, points, 1), x)),
            "truth": _round(slope * x),
            "lines": _round(b0[:, None] + b1[:, None] * x[None, :]),
            "betas": _round(np.column_stack([b0, b1]), 2),
        }

    return {"x": _round(x), "a": panel(noisy, slope_a, 1.0, 1), "b": panel(less_noisy, 1.0, 0.1, 2)}


def histogram_data(n=5000, seed=SEED):
    return {"z": _round(np.random.default_rng(seed).standard_normal(n))}


def mvn2_data(n=2500, seed=SEED):
    rng = np.random.default_rng(seed)
    return {"z": _round(rng.standard_normal((n, 2))), "reference": _round(rng.standard_normal((n, 2)))}


def iid_data(seed=SEED):
    rng = np.random.default_rng(seed)
    return {f"d{d}": _round(rng.standard_normal((POOL, d))) for d in (1, 2, 3, 50)}


def fuzzy_data():
    x = np.linspace(0, 50, 50)
    ells = list(range(1, 31))
    pools = {str(ell): _round(sample_pool(np.zeros(50), rbf(x, x, ell))) for ell in ells}
    return {"x": _round(x), "ells": ells, "pools": pools}


def pi_data():
    x = np.array([-np.pi, np.pi, 2 * np.pi])
    cov = np.diag(x**2)
    return {
        "x": _round(x, 4),
        "labels": [f"{value:.4f}" for value in x],
        "cov": _round(cov, 4),
        "pool": _round(sample_pool(x, cov)),
    }


def real50_data():
    x = np.linspace(-1, 1, 50)
    cov = np.diag(x**2)
    return {
        "x": _round(x),
        "labels": [f"{value:.2f}" for value in x],
        "cov": _round(cov, 4),
        "pool": _round(sample_pool(x, cov)),
    }


def double_data():
    x = np.linspace(-1, 1, 50)
    ells = np.round(np.arange(1, 41) * 0.05, 2)
    pools = [_round(sample_pool(np.zeros(50), rbf(x, x, ell))) for ell in ells]
    return {"x": _round(x), "ells": ells.tolist(), "pools": pools}


def posterior_data(seed=SEED):
    x_known = np.array(HOUSING_X)
    y_known = np.array(HOUSING_Y)
    x_test = np.linspace(0, 4 * np.pi, 50)
    y_mean, y_std = y_known.mean(), y_known.std()
    mean, cov = gp_posterior((y_known - y_mean) / y_std, x_known, x_test, ell=1.0)
    pool = sample_pool(mean, cov, n=POOL, seed=seed) * y_std + y_mean
    many = sample_pool(mean, cov, n=500, seed=seed + 1) * y_std + y_mean
    truth = (0.1 * np.sin(x_test) + 1) * 200000 + x_test * 10000
    return {
        "x": _round(x_test),
        "labels": [f"{value:.2f}" for value in x_test],
        "known": {"x": _round(x_known), "y": _round(y_known, 0)},
        "truth": {"x": _round(x_test), "y": _round(truth, 0)},
        "mean": _round(mean * y_std + y_mean, 0),
        "cov": _round(cov),
        "pool": _round(pool, 0),
        "many": _round(many, 0),
    }


def page_data():
    """All data for the post, as lists that json.dumps can write."""
    return {
        "regression": regression_data(),
        "hist": histogram_data(),
        "mvn2": mvn2_data(),
        "iid": iid_data(),
        "fuzzy": fuzzy_data(),
        "pi": pi_data(),
        "real50": real50_data(),
        "double": double_data(),
        "post": posterior_data(),
    }
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `uv run pytest tests/test_gp_data.py -v`
Expected: `9 passed`. (If `np.linalg.cholesky` fails with `LinAlgError` for an extreme ℓ, do not change the test. Report the ℓ value to the owner, because the jitter value is part of the design.)

- [ ] **Step 5: Commit**

```bash
git add blog/gaussian-processes/gp_data.py tests/test_gp_data.py
git commit -m "gp post: add the precomputed data module

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: GP widget helpers in JavaScript

> **Replaced 2026-10-01** (owner direction): the marimo → blog converter does this work. See `docs/superpowers/specs/2026-10-01-marimo-to-blog-design.md`. Do not implement this task.

**Files:**
- Create: `blog/gaussian-processes/wiring.js`
- Create: `blog/gaussian-processes/wiring.test.mjs`

**Interfaces:**
- Consumes: nothing.
- Produces: ES module `blog/gaussian-processes/wiring.js` with these exports:
  - `POOL_SIZE = 50`
  - `addSample(n: number) -> number`
  - `rows(xs: number[], ys: number[]) -> {x, y}[]`
  - `matrixCells(matrix: number[][]) -> {i, j, value}[]`
  - `parsePoints(text: string, maxPoints = 30) -> {points: number[], error: string | null}`
  - `rbfCells(xs: number[], ell: number) -> {i, j, value}[]` (throws `RangeError` if `ell` is not greater than 0)
  - `mvn2(z: number[][], mean: number[], cov: number[][]) -> {ok: boolean, error: string | null, points: number[][]}`
  - `scaleNormals(z: number[], mean: number, variance: number) -> number[]` (throws `RangeError` if `variance` is not greater than 0)
  - `ellIndex(ell: number, step = 0.05) -> number`
  - `picksToSamples(picks: number[]) -> {idx, k}[]`

- [ ] **Step 1: Write the failing tests**

`blog/gaussian-processes/wiring.test.mjs`:

```js
import assert from "node:assert/strict";
import {test} from "node:test";

import {
  POOL_SIZE,
  addSample,
  ellIndex,
  matrixCells,
  mvn2,
  parsePoints,
  picksToSamples,
  rbfCells,
  rows,
  scaleNormals,
} from "./wiring.js";

test("addSample counts up and stops at the pool size", () => {
  assert.equal(addSample(0), 1);
  assert.equal(addSample(POOL_SIZE - 1), POOL_SIZE);
  assert.equal(addSample(POOL_SIZE), POOL_SIZE);
});

test("rows pairs x and y values", () => {
  assert.deepEqual(rows([1, 2], [3, 4]), [{x: 1, y: 3}, {x: 2, y: 4}]);
});

test("matrixCells lists each cell with its row and column", () => {
  assert.deepEqual(matrixCells([[1, 2], [3, 4]]), [
    {i: 0, j: 0, value: 1},
    {i: 0, j: 1, value: 2},
    {i: 1, j: 0, value: 3},
    {i: 1, j: 1, value: 4},
  ]);
});

test("parsePoints reads the default text", () => {
  assert.deepEqual(parsePoints("1.549, 2, 3, 4, 5, 6, 10"), {points: [1.549, 2, 3, 4, 5, 6, 10], error: null});
});

test("parsePoints accepts spaces, semicolons, negative numbers and exponents", () => {
  assert.deepEqual(parsePoints("  -1;2  3e-1,,4 ").points, [-1, 2, 0.3, 4]);
});

test("parsePoints rejects text that is not a number", () => {
  assert.deepEqual(parsePoints("1, two, 3"), {points: [], error: '"two" is not a number.'});
});

test("parsePoints rejects empty text and too many points", () => {
  assert.equal(parsePoints("   ").error, "Type at least one number.");
  const many = Array.from({length: 31}, (_, i) => i).join(",");
  assert.equal(parsePoints(many).error, "Type 30 numbers or fewer.");
});

test("rbfCells has ones on the diagonal and the RBF value elsewhere", () => {
  const cells = rbfCells([0, 1], 1);
  assert.equal(cells.length, 4);
  assert.equal(cells[0].value, 1);
  assert.ok(Math.abs(cells[1].value - Math.exp(-0.5)) < 1e-12);
  assert.equal(cells[1].value, cells[2].value);
});

test("rbfCells rejects a length scale that is not positive", () => {
  assert.throws(() => rbfCells([0, 1], 0), RangeError);
  assert.throws(() => rbfCells([0, 1], Number.NaN), RangeError);
});

test("mvn2 with the identity matrix only moves the points by the mean", () => {
  assert.deepEqual(mvn2([[1, 2]], [0.5, -1], [[1, 0], [0, 1]]), {ok: true, error: null, points: [[1.5, 1]]});
});

test("mvn2 applies the 2x2 Cholesky factor", () => {
  const {points} = mvn2([[1, 0], [0, 1]], [0, 0], [[1, 0.5], [0.5, 1]]);
  assert.deepEqual(points[0], [1, 0.5]);
  assert.ok(Math.abs(points[1][1] - Math.sqrt(0.75)) < 1e-12);
});

test("mvn2 rejects a matrix that is not positive semi-definite", () => {
  assert.deepEqual(mvn2([[1, 1]], [0, 0], [[1, 2], [2, 1]]), {
    ok: false,
    error: "covariance is not symmetric positive-semidefinite.",
    points: [],
  });
});

test("mvn2 accepts a zero variance", () => {
  assert.deepEqual(mvn2([[1, 2]], [0, 0], [[0, 0], [0, 4]]).points, [[0, 4]]);
});

test("mvn2 rejects an empty input box", () => {
  assert.deepEqual(mvn2([[1, 2]], [0, 0], [[Number.NaN, 0], [0, 1]]), {
    ok: false,
    error: "Type a number in each box.",
    points: [],
  });
});

test("scaleNormals uses the square root of the variance", () => {
  assert.deepEqual(scaleNormals([1, -1], 2, 4), [4, 0]);
  assert.throws(() => scaleNormals([1], 0, 0), RangeError);
});

test("ellIndex maps slider values to list positions", () => {
  assert.equal(ellIndex(0.05), 0);
  assert.equal(ellIndex(0.15000000000000002), 2);
  assert.equal(ellIndex(2.0), 39);
});

test("picksToSamples counts samples for each length scale and stops at the pool size", () => {
  assert.deepEqual(picksToSamples([3, 3, 5, 3]), [
    {idx: 3, k: 0},
    {idx: 3, k: 1},
    {idx: 5, k: 0},
    {idx: 3, k: 2},
  ]);
  assert.equal(picksToSamples(Array(POOL_SIZE + 5).fill(1)).length, POOL_SIZE);
});
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `node --test blog/gaussian-processes/wiring.test.mjs`
Expected: FAIL with `Cannot find module` for `wiring.js`.

- [ ] **Step 3: Write the implementation**

`blog/gaussian-processes/wiring.js`:

```js
// Small helpers for the widgets in the Gaussian process post.
// They connect precomputed data to charts. All other math is in gp_data.py.

export const POOL_SIZE = 50;

/** The next count for a "New Sample" button. It stops at POOL_SIZE. */
export function addSample(n) {
  return Math.min(n + 1, POOL_SIZE);
}

/** Rows for Observable Plot, from two arrays of the same length. */
export function rows(xs, ys) {
  return ys.map((y, i) => ({x: xs[i], y}));
}

/** Heatmap cells for a matrix (an array of rows). */
export function matrixCells(matrix) {
  return matrix.flatMap((row, i) => row.map((value, j) => ({i, j, value})));
}

/** Read text such as "1.549, 2, 3" into numbers. */
export function parsePoints(text, maxPoints = 30) {
  const parts = String(text)
    .split(/[\s,;]+/)
    .filter((part) => part.length > 0);
  if (parts.length === 0) return {points: [], error: "Type at least one number."};
  if (parts.length > maxPoints) return {points: [], error: `Type ${maxPoints} numbers or fewer.`};
  const points = [];
  for (const part of parts) {
    const value = Number(part);
    if (!Number.isFinite(value)) return {points: [], error: `"${part}" is not a number.`};
    points.push(value);
  }
  return {points, error: null};
}

/** RBF kernel cells for the points xs: exp(-(xi - xj)^2 / (2 ell^2)). */
export function rbfCells(xs, ell) {
  if (!(ell > 0)) throw new RangeError("ell must be greater than 0");
  return xs.flatMap((xi, i) =>
    xs.map((xj, j) => ({i, j, value: Math.exp(-((xi - xj) ** 2) / (2 * ell * ell))})),
  );
}

/** Samples of a 2-D Gaussian: the 2x2 Cholesky formula applied to fixed standard-normal pairs z. */
export function mvn2(z, mean, cov) {
  const a = cov[0][0];
  const b = cov[0][1];
  const c = cov[1][1];
  if (![a, b, c, mean[0], mean[1]].every(Number.isFinite)) {
    return {ok: false, error: "Type a number in each box.", points: []};
  }
  if (a < 0 || c < 0 || a * c - b * b < -1e-12) {
    return {ok: false, error: "covariance is not symmetric positive-semidefinite.", points: []};
  }
  const l11 = Math.sqrt(a);
  const l21 = a > 0 ? b / l11 : 0;
  const l22 = Math.sqrt(Math.max(0, c - l21 * l21));
  const points = z.map(([z1, z2]) => [mean[0] + l11 * z1, mean[1] + l21 * z1 + l22 * z2]);
  return {ok: true, error: null, points};
}

/** mean + sqrt(variance) * z for each z. */
export function scaleNormals(z, mean, variance) {
  if (!(variance > 0)) throw new RangeError("variance must be greater than 0");
  const sd = Math.sqrt(variance);
  return z.map((value) => mean + sd * value);
}

/** The position of ell in [0.05, 0.10, ..., 2.00]. */
export function ellIndex(ell, step = 0.05) {
  return Math.round(ell / step) - 1;
}

/** Clicked ell positions, in order, to samples {idx, k}. At most POOL_SIZE samples for each idx. */
export function picksToSamples(picks) {
  const counts = new Map();
  const samples = [];
  for (const idx of picks) {
    const k = counts.get(idx) ?? 0;
    if (k >= POOL_SIZE) continue;
    counts.set(idx, k + 1);
    samples.push({idx, k});
  }
  return samples;
}
```

- [ ] **Step 4: Run the tests to see them pass**

Run: `node --test blog/gaussian-processes/wiring.test.mjs`
Expected: `# pass 17` and `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add blog/gaussian-processes/wiring.js blog/gaussian-processes/wiring.test.mjs
git commit -m "gp post: add the JavaScript helpers for the widgets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: The GP post page

> **Replaced 2026-10-01** (owner direction): the marimo → blog converter does this work. See `docs/superpowers/specs/2026-10-01-marimo-to-blog-design.md`. Do not implement this task.

**Files:**
- Create: `blog/gaussian-processes/index.qmd` (made by a one-time script that you do not commit)
- Create: `blog/gaussian-processes/gp-posterior.jpg`
- Create (made by Quarto): `blog/_freeze/gaussian-processes/`

**Interfaces:**
- Consumes: `gp_data.page_data()` (Task 9). The exports of `wiring.js` (Task 10).
- Produces: the post at `/blog/gaussian-processes/`. The post links to `live/` (Task 12 makes that page).

The one-time script takes the prose from marimo's Markdown export. It drops all 48 code cells and puts a widget block in place of 27 of them. The cell numbers come from the export of `apps/Intro_to_Gaussian_Process_Regression.py` in `~/self/marimo-blog`, with marimo 0.25.0:

| Cells | New content |
|---|---|
| 1–3, 6, 8, 9, 11–13, 16, 18, 20, 26, 29, 32, 36, 38, 42, 44, 47, 48 | removed (imports, helpers, setup code, empty cells) |
| 4 | static regression chart |
| 5 | widget 1: regression lines A and B, with "New Sample" and "Reset" |
| 7 | widget 2: histogram, with the mean and variance sliders |
| 10 | widget 3: 2×2 covariance and mean inputs, with the scatter chart |
| 14, 15, 17 | widget 4: 1-D, 2-D and 3-D samples |
| 19 | widget 5: 50-D samples, with "Connect Points" |
| 21 | static identity heatmap |
| 22 | the answer "INDEPENDENT!" in a `<details>` element |
| 23, 24 | widget 6: the RBF heatmap, and the ℓ slider (1–30) |
| 25 | widget 7: "fuzzy" samples |
| 27, 30 | static covariance heatmaps (multiples of π; 50 real values) |
| 28, 31 | widget 8: samples at multiples of π; samples at 50 real values |
| 33 | widget 6 again: the RBF heatmap for the same slider |
| 34 | Python code block that shows `rbf` (shown, not run) |
| 35 | widget 9: the points text box, the ℓ input and the annotated heatmap |
| 37 | widget 10: the ℓ slider (0.05–2.0) with samples and heatmap |
| 39 | static housing data chart |
| 40 | Python code block that shows `gp_posterior` (shown, not run) |
| 41 | widget 11: posterior samples |
| 43 | widget 12: 500 posterior samples |
| 45, 46 | static heatmaps of the conditional covariance and the conditional mean |

- [ ] **Step 1: Export the notebook prose**

```bash
uvx --from marimo@0.25.0 marimo export md ~/self/marimo-blog/apps/Intro_to_Gaussian_Process_Regression.py \
  -o "${TMPDIR:-/tmp}/gp_export.md" -f
grep -c '^```python {.marimo' "${TMPDIR:-/tmp}/gp_export.md"
```

Expected: `48`.

- [ ] **Step 2: Write the one-time script**

Write this file to `${TMPDIR:-/tmp}/make_gp_qmd.py` (do not add it to the repo):

````python
"""One-time script: build blog/gaussian-processes/index.qmd from marimo's Markdown export."""

import re
import sys
from pathlib import Path

export_md, out_qmd = Path(sys.argv[1]), Path(sys.argv[2])


def ojs(code: str) -> str:
    return "```{ojs}\n" + code.strip() + "\n```\n"


def button(name: str, clear: str = "Clear") -> str:
    return ojs(f'viewof {name} = Inputs.button([["New Sample", addSample], ["{clear}", () => 0]], {{value: 0}})')


FRONT = """---
title: "The First Blog Post You Should Read about Gaussian Processes (With Interactive Plots)"
description: "Build the core idea of Gaussian process regression step by step, with interactive plots."
date: 2025-02-12
categories: [statistics, machine learning, interactive]
image: gp-posterior.jpg
jupyter: python3
execute:
  echo: false
resources:
  - wiring.js
---
"""

STATIC_REGRESSION = ojs(r"""
{
  const r = gp.regression;
  const panel = (key, color, name) => html`<div><strong>${name}</strong>${Plot.plot({
    width: Math.min(320, width), height: 260, grid: true,
    x: {domain: [-3, 3]}, y: {label: "y"},
    marks: [
      Plot.dot(rows(r.x, r[key].points), {x: "x", y: "y", fill: color}),
      Plot.line(rows(r.x, r[key].ols), {x: "x", y: "y", stroke: color})
    ]
  })}</div>`;
  return html`<div style="display: flex; flex-wrap: wrap; gap: 1rem">${panel("a", "#c33f3f", "A")}${panel("b", "#1b7f86", "B")}</div>`;
}
""")

W1_REGRESSION = ojs(r"""
{
  const r = gp.regression;
  const panel = (key, color, name, yDomain) => html`<div><strong>${name}</strong>${Plot.plot({
    width: Math.min(320, width), height: 300, grid: true,
    x: {domain: [-3, 3]}, y: {domain: yDomain, label: "y"},
    marks: [
      Plot.dot(rows(r.x, r[key].points), {x: "x", y: "y", fill: color}),
      Plot.line(rows(r.x, r[key].truth), {x: "x", y: "y", stroke: color, strokeWidth: 3}),
      ...r[key].lines.slice(0, nReg).map((ys, k) =>
        Plot.line(rows(r.x, ys), {x: "x", y: "y", stroke: d3.schemeTableau10[k % 10], clip: true}))
    ]
  })}<small>${r[key].betas.slice(0, nReg).map(([b0, b1]) => `(β₀ ${b0.toFixed(1)}, β₁ ${b1.toFixed(1)})`).join(" ")}</small></div>`;
  return html`<div style="display: flex; flex-wrap: wrap; gap: 1rem">${panel("a", "#c33f3f", "A: more noise", [-8, 8])}${panel("b", "#1b7f86", "B: less noise", [-5, 5])}</div>`;
}
""") + button("nReg", clear="Reset")

W2_HISTOGRAM = ojs(r"""
Plot.plot({
  width: Math.min(640, width), height: 300,
  caption: `Normal distribution histogram (μ = ${mu.toFixed(2)}, σ² = ${variance.toFixed(2)})`,
  x: {domain: [-10, 10], label: "Value"},
  y: {domain: [0, 500], label: "Count"},
  marks: [
    Plot.rectY(scaleNormals(gp.hist.z, mu, variance), Plot.binX({y: "count"}, {x: (d) => d, thresholds: d3.range(-10, 10.05, 0.1), clip: true})),
    Plot.ruleY([0])
  ]
})
""") + ojs('viewof mu = Inputs.range([-5, 5], {step: 0.1, value: 0, label: "Mean (μ)"})') + ojs(
    'viewof variance = Inputs.range([0.1, 5], {step: 0.1, value: 1, label: "Variance (σ²)"})'
)

W3_MVN2 = ojs(r"""
viewof cov2 = Inputs.form({
  mu1: Inputs.number([0, 10], {step: 0.1, value: 0, label: "μ₁"}),
  mu2: Inputs.number([0, 10], {step: 0.1, value: 0, label: "μ₂"}),
  s11: Inputs.number([0, 10], {step: 0.1, value: 1, label: "Σ₁₁"}),
  s12: Inputs.number([0, 10], {step: 0.1, value: 0, label: "Σ₁₂ = Σ₂₁"}),
  s22: Inputs.number([0, 10], {step: 0.1, value: 1, label: "Σ₂₂"})
})
""") + ojs(r"""
{
  const result = mvn2(gp.mvn2.z, [cov2.mu1, cov2.mu2], [[cov2.s11, cov2.s12], [cov2.s12, cov2.s22]]);
  const size = Math.min(420, width);
  const chart = Plot.plot({
    width: size, height: size, grid: true,
    x: {domain: [-10, 10], label: "x"}, y: {domain: [-10, 10], label: "y"},
    marks: [
      Plot.dot(gp.mvn2.reference, {x: (d) => d[0], y: (d) => d[1], r: 1.2, fill: "gray", fillOpacity: 0.4}),
      result.ok ? Plot.dot(result.points, {x: (d) => d[0], y: (d) => d[1], r: 1.2, fill: "#52c2c7", clip: true}) : null
    ]
  });
  return result.ok ? chart : html`<div><p style="color: #c33f3f; font-weight: bold">Error: ${result.error}</p>${chart}</div>`;
}
""")

W4_1D = ojs('sampleChart(gp.iid.d1, n1, {xLabels: ["1"]})') + button("n1")
W4_2D = ojs('sampleChart(gp.iid.d2, n2, {xLabels: ["1", "2"]})') + button("n2")
W4_3D = ojs('sampleChart(gp.iid.d3, n3, {xLabels: ["1", "2", "3"]})') + button("n3")

W5_50D = ojs("sampleChart(gp.iid.d50, n50, {xs: d3.range(50), connect: connect50})") + button("n50") + ojs(
    'viewof connect50 = Inputs.toggle({label: "Connect Points", value: false})'
)

STATIC_IDENTITY = ojs("heatmap(matrixCells(d3.range(50).map((i) => d3.range(50).map((j) => (i === j ? 1 : 0)))))")

ANSWER = "<details><summary>Tap for the answer</summary>\n\n**INDEPENDENT!**\n\n</details>\n"

W6_HEATMAP = ojs("heatmap(rbfCells(d3.range(50), ell1))")
W6_SLIDER = ojs('viewof ell1 = Inputs.range([1, 30], {step: 1, value: 5, label: "Value of ℓ"})')

W7_FUZZY = ojs("md`*These samples use the ℓ slider above: ℓ = ${ell1}.*`") + ojs(
    "sampleChart(gp.fuzzy.pools[ell1], nFuzzy, {xs: gp.fuzzy.x, connect: true, height: 400})"
) + button("nFuzzy")

STATIC_PI_COV = ojs(
    "heatmap(matrixCells(gp.pi.cov), {xLabels: gp.pi.labels, yLabels: gp.pi.labels, annotate: true, maxSize: 300})"
)
W8_PI = ojs("sampleChart(gp.pi.pool, nPi, {xs: gp.pi.x, connect: true, height: 400})") + button("nPi")
STATIC_REAL50_COV = ojs("heatmap(matrixCells(gp.real50.cov), {xLabels: gp.real50.labels, yLabels: gp.real50.labels})")
W8_REAL50 = ojs("sampleChart(gp.real50.pool, nReal, {xs: gp.real50.x, connect: true, height: 400})") + button("nReal")

W6_AGAIN = ojs("heatmap(rbfCells(d3.range(50), ell1))") + ojs(
    "md`*This heatmap uses the ℓ slider from earlier: ℓ = ${ell1}.*`"
)

CODE_RBF = '''```python
import numpy as np


def rbf(xa, xb, ell):
    # RBF kernel: the covariance between each point in xa and each point in xb.
    xa = np.asarray(xa, dtype=float).reshape(-1)
    xb = np.asarray(xb, dtype=float).reshape(-1)
    return np.exp(-0.5 / ell**2 * (xa[:, None] - xb[None, :]) ** 2)
```
'''

W9_POINTS = (
    "Try your own points and ℓ:\n\n"
    + ojs('viewof pointsText = Inputs.text({label: "Points", value: "1.549, 2, 3, 4, 5, 6, 10", width: 320})')
    + ojs('viewof ellPts = Inputs.number([0.01, 100], {step: 0.01, value: 1, label: "ℓ"})')
    + ojs(r"""
{
  const {points, error} = parsePoints(pointsText);
  if (error) return html`<p style="color: #c33f3f; font-weight: bold">${error}</p>`;
  if (!(ellPts > 0)) return html`<p style="color: #c33f3f; font-weight: bold">ℓ must be greater than 0.</p>`;
  return heatmap(rbfCells(points, ellPts), {xLabels: points, yLabels: points, annotate: true, maxSize: 480});
}
""")
    + "\nWant to edit the Python code itself? [Open the live notebook](live/). It downloads Python, so it takes 20–70 s to load on a phone.\n"
)

W10_DOUBLE = ojs(r"""
{
  const samples = picksToSamples(picks);
  return Plot.plot({
    width: Math.min(640, width), height: 350, grid: true,
    x: {domain: [-1, 1]}, y: {domain: [-5, 5]},
    color: {type: "ordinal", legend: samples.length > 0},
    marks: samples.map(({idx, k}) =>
      Plot.line(rows(gp.double.x, gp.double.pools[idx][k]), {x: "x", y: "y", stroke: () => `ℓ = ${gp.double.ells[idx].toFixed(2)}`, clip: true}))
  });
}
""") + ojs(
    'viewof picks = Inputs.button([["New Sample", (list) => [...list, ellIndex(viewof ell2.value)]], ["Clear", () => []]], {value: []})'
) + ojs(
    'viewof ell2 = Inputs.range([0.05, 2], {step: 0.05, value: 0.5, label: "RBF kernel parameter (ℓ)"})'
) + ojs("heatmap(rbfCells(gp.double.x, ell2), {maxSize: 350})")

STATIC_HOUSING = ojs(r"""
Plot.plot({
  width: Math.min(640, width), height: 320, grid: true,
  x: {label: "Distance from the nuclear power plant (miles)"},
  y: {label: "Cost of a house ($)"},
  marks: [Plot.dot(rows(gp.post.known.x, gp.post.known.y), {x: "x", y: "y", fill: "#c33f3f", r: 5})]
})
""")

CODE_POSTERIOR = '''```python
def gp_posterior(y_train, x_train, x_test, ell=1.0):
    # Mean and covariance of a zero-mean GP with an RBF kernel, conditioned on training data.
    k11 = rbf(x_train, x_train, ell)
    k21 = rbf(x_test, x_train, ell)
    k22 = rbf(x_test, x_test, ell)
    mean = k21 @ np.linalg.solve(k11, y_train)
    cov = k22 - k21 @ np.linalg.solve(k11, k21.T)
    return mean, cov
```
'''

W11_POSTERIOR = ojs(r"""
Plot.plot({
  width: Math.min(640, width), height: 400, grid: true,
  x: {label: "Distance from the nuclear power plant (miles)"},
  y: {label: "Cost of a house ($)", domain: d3.extent([...gp.post.pool.flat(), ...gp.post.known.y])},
  marks: [
    ...gp.post.pool.slice(0, nPost).map((ys, k) =>
      Plot.line(rows(gp.post.x, ys), {x: "x", y: "y", stroke: d3.schemeTableau10[k % 10], marker: "circle"})),
    Plot.dot(rows(gp.post.known.x, gp.post.known.y), {x: "x", y: "y", fill: "#c33f3f", r: 7})
  ]
})
""") + button("nPost")

W12_MANY = ojs(r"""
Plot.plot({
  width: Math.min(640, width), height: 400, grid: true,
  x: {label: "Distance from the nuclear power plant (miles)"},
  y: {label: "Price ($)"},
  marks: [
    nMany > 0 ? Plot.line(gp.post.many.flatMap((ys, k) => rows(gp.post.x, ys).map((d) => ({...d, k}))), {x: "x", y: "y", z: "k", stroke: "#2f6db5", strokeOpacity: 0.02}) : null,
    Plot.line(rows(gp.post.truth.x, gp.post.truth.y), {x: "x", y: "y", stroke: "#ff54e0", strokeWidth: 2}),
    Plot.dot(rows(gp.post.known.x, gp.post.known.y), {x: "x", y: "y", fill: "#c33f3f", r: 4})
  ]
})
""") + ojs('viewof nMany = Inputs.button("Sample 500 Functions from Posterior")')

STATIC_COND_COV = ojs("heatmap(matrixCells(gp.post.cov), {xLabels: gp.post.labels, yLabels: gp.post.labels})")
STATIC_COND_MEAN = ojs(
    'heatmap(gp.post.mean.map((value, i) => ({i, j: 0, value})), {xLabels: ["mean"], yLabels: gp.post.labels})'
)

TAIL = """
```{python}
import gp_data

ojs_define(gp=gp_data.page_data())
```

```{ojs}
//| output: false
import {addSample, rows, matrixCells, parsePoints, rbfCells, mvn2, scaleNormals, ellIndex, picksToSamples} from "./wiring.js"
```

```{ojs}
//| output: false
function heatmap(cells, {xLabels = null, yLabels = null, annotate = false, maxSize = 420} = {}) {
  const ncols = d3.max(cells, (d) => d.j) + 1;
  const nrows = d3.max(cells, (d) => d.i) + 1;
  const cell = Math.min(width, maxSize) / Math.max(ncols, nrows);
  const ticks = (n) => d3.range(0, n, Math.max(1, Math.ceil(n / 10)));
  const label = (labels) => (i) => (labels ? labels[i] : i);
  const text = (keep, fill) => Plot.text(cells, {filter: keep, x: "j", y: "i", text: (d) => d.value.toFixed(2), fill});
  return Plot.plot({
    width: Math.max(ncols * cell + 110, 200), height: nrows * cell + 60,
    marginLeft: 60, marginTop: 30,
    x: {type: "band", domain: d3.range(ncols), ticks: ticks(ncols), tickFormat: label(xLabels), label: null, axis: "top"},
    y: {type: "band", domain: d3.range(nrows), ticks: ticks(nrows), tickFormat: label(yLabels), label: null},
    color: {scheme: "viridis", legend: true},
    marks: [
      Plot.cell(cells, {x: "j", y: "i", fill: "value", inset: 0}),
      annotate ? text((d) => d.value > 0.5, "black") : null,
      annotate ? text((d) => d.value <= 0.5, "white") : null
    ]
  });
}
```

```{ojs}
//| output: false
function sampleChart(pool, n, {xs = null, xLabels = null, connect = false, height = 300} = {}) {
  const marks = pool.slice(0, n).map((ys, k) => {
    const data = ys.map((y, i) => ({x: xLabels ? xLabels[i] : xs[i], y}));
    const color = d3.schemeTableau10[k % 10];
    return connect
      ? Plot.line(data, {x: "x", y: "y", stroke: color, marker: "circle"})
      : Plot.dot(data, {x: "x", y: "y", fill: color, r: 5});
  });
  return Plot.plot({
    width: Math.min(640, width), height, grid: true,
    x: xLabels ? {type: "point", domain: xLabels, label: null} : {label: null},
    y: {domain: d3.extent(pool.flat()), label: null},
    marks: [Plot.ruleY([0], {strokeOpacity: 0.3}), ...marks]
  });
}
```
"""

BLOCKS = {
    4: STATIC_REGRESSION, 5: W1_REGRESSION, 7: W2_HISTOGRAM, 10: W3_MVN2,
    14: W4_1D, 15: W4_2D, 17: W4_3D, 19: W5_50D, 21: STATIC_IDENTITY, 22: ANSWER,
    23: W6_HEATMAP, 24: W6_SLIDER, 25: W7_FUZZY, 27: STATIC_PI_COV, 28: W8_PI,
    30: STATIC_REAL50_COV, 31: W8_REAL50, 33: W6_AGAIN, 34: CODE_RBF, 35: W9_POINTS,
    37: W10_DOUBLE, 39: STATIC_HOUSING, 40: CODE_POSTERIOR, 41: W11_POSTERIOR,
    43: W12_MANY, 45: STATIC_COND_COV, 46: STATIC_COND_MEAN,
}

TEXT_EDITS = [
    ("# The First Blog Post You Should Read about Gaussian Processes (With Interactive Plots)\n", ""),
    (
        "> If you know python/numpy you might find it helpful to look at the code under the hood. "
        "Just click the ellipses in the upper right corner.",
        "> If you know Python and numpy, you can look at the code under the hood: open the "
        "[live notebook](live/), or read "
        "[gp_data.py](https://github.com/cyniphile/cyniphile.github.io/blob/master/blog/gaussian-processes/gp_data.py).",
    ),
    ("\n# Gaussians...and Multivariate Gaussians\n", "\n## Gaussians...and Multivariate Gaussians\n"),
    ("\n# Actually Fitting a Regression Model\n", "\n## Actually Fitting a Regression Model\n"),
    ("10,000 samples", "5,000 samples"),
    (r"\frac{1}{2ℓ^2}", r"\frac{1}{2\ell^2}"),
    ("and $ℓ$ is", r"and $\ell$ is"),
    ("parameter $ℓ$ set to 1.0", r"parameter $\ell$ set to 1.0"),
]

text = export_md.read_text(encoding="utf-8")
body = text.split("\n---\n", 1)[1]
parts = re.split(r"(```python \{\.marimo[^}]*\}\n.*?\n```)", body, flags=re.DOTALL)
out, cell = [], 0
for part in parts:
    if part.startswith("```python {.marimo"):
        cell += 1
        if cell in BLOCKS:
            out.append("\n" + BLOCKS[cell] + "\n")
    else:
        out.append(part)
assert cell == 48, f"expected 48 cells, found {cell}"
page = "\n" + "".join(out)
for old, new in TEXT_EDITS:
    assert page.count(old) == 1, f"text edit must match exactly once: {old!r}"
    page = page.replace(old, new)
page = re.sub(r"\n{3,}", "\n\n", FRONT + page + TAIL).rstrip() + "\n"
out_qmd.write_text(page, encoding="utf-8")
print(f"wrote {out_qmd} ({len(BLOCKS)} blocks, {len(TEXT_EDITS)} text edits)")
````

- [ ] **Step 3: Run the script**

Run: `uv run python "${TMPDIR:-/tmp}/make_gp_qmd.py" "${TMPDIR:-/tmp}/gp_export.md" blog/gaussian-processes/index.qmd`
Expected: `wrote blog/gaussian-processes/index.qmd (27 blocks, 8 text edits)`.

- [ ] **Step 4: Make the post image**

```bash
uv run python - <<'EOF'
import sys

sys.path.insert(0, "blog/gaussian-processes")
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import gp_data

data = gp_data.posterior_data()
fig, ax = plt.subplots(figsize=(12, 6.3), dpi=100)
for ys in data["many"]:
    ax.plot(data["x"], ys, color="#2f6db5", alpha=0.03, linewidth=1)
ax.plot(data["truth"]["x"], data["truth"]["y"], color="#ff54e0", linewidth=3)
ax.scatter(data["known"]["x"], data["known"]["y"], color="#c33f3f", s=60, zorder=3)
ax.set_axis_off()
fig.savefig("blog/gaussian-processes/gp-posterior.jpg", bbox_inches="tight", facecolor="white", pil_kwargs={"quality": 85})
EOF
ls -l blog/gaussian-processes/gp-posterior.jpg
```

Expected: a JPEG smaller than 300 KB. It shows blue sample curves, a pink curve and red points.

- [ ] **Step 5: Build the site**

Run: `uv run scripts/build.py`
Expected: only errors of this form, because the live notebook comes in Task 12:

```text
ERROR: blog/gaussian-processes/index.html: broken href live/
```

- [ ] **Step 6: Check each widget in a browser**

Run: `python3 -m http.server 8765 -d _site`, then open `http://127.0.0.1:8765/blog/gaussian-processes/`.

| # | Do this | Expected result |
|---|---|---|
| 1 | Click "New Sample" 3 times in the regression widget, then "Reset" | 3 lines show in A and in B with their β values, then they go away |
| 2 | Move the mean and variance sliders | The histogram moves and gets wider or narrower immediately |
| 3 | Set Σ₁₂ = 0.8, then Σ₁₂ = 2 | A tilted cloud, then the red error text and only the gray cloud |
| 4 | Click "New Sample" in the 1-D, 2-D and 3-D charts | A new set of dots for each click |
| 5 | Click "New Sample" 5 times in the 50-D chart, then turn on "Connect Points" | 5 dot rows, then 5 lines with dots |
| 6 | Move the ℓ slider (1–30) | Both RBF heatmaps change; the band around the diagonal gets wider for a larger ℓ |
| 7 | Click "New Sample" 3 times in the "fuzzy" chart, then move the ℓ slider | 3 smooth curves that change smoothly with ℓ |
| 8 | Click "New Sample" in the π and the 50-real-values charts | Curves with dots, with a wider spread for a larger \|x\| |
| 9 | Type `1, 2, x` in the Points box, then `0, 0.5, 1` | The text `"x" is not a number.`, then a 3×3 annotated heatmap |
| 10 | Click "New Sample" at ℓ = 0.5, set ℓ = 1.5, click "New Sample" | Two curves with a legend `ℓ = 0.50` and `ℓ = 1.50`; the heatmap changes with the slider |
| 11 | Click "New Sample" 3 times in the housing chart | 3 curves that go through the red points |
| 12 | Click "Sample 500 Functions from Posterior" | A blue band around the pink curve |
| 13 | Scroll through the page | All static charts and heatmaps show; the "Tap for the answer" box opens |

Also run this in the browser console: `document.querySelectorAll(".katex-error").length`
Expected: `0`. If it is not 0, add `html-math-method: mathjax` to the front matter of this post, render it again and check again.

- [ ] **Step 7: Commit**

```bash
git add blog/gaussian-processes/index.qmd blog/gaussian-processes/gp-posterior.jpg blog/_freeze
git commit -m "gp post: add the Quarto version with precomputed widgets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: The live notebook

> **Done 2026-10-01** with the converter work: the build exports `blog/<slug>/notebook.py` (not `live.py`) to `live/` in marimo's run mode with `--show-code`: the cells run when the page loads and the code is visible (edit mode waits for "Run all").

**Files:**
- Create: `blog/gaussian-processes/live.py` (a copy of the marimo notebook, without changes)

**Interfaces:**
- Consumes: `build.live_notebooks` (Task 3). The `live/` links in the GP post (Task 11).
- Produces: `/blog/gaussian-processes/live/`.

- [ ] **Step 1: Copy the notebook**

Run: `cp ~/self/marimo-blog/apps/Intro_to_Gaussian_Process_Regression.py blog/gaussian-processes/live.py`

- [ ] **Step 2: Build the site**

Run: `uv run scripts/build.py`
Expected: the last line is `All site checks passed`. The marimo export takes a few minutes, because it runs the notebook.

- [ ] **Step 3: Check the live notebook**

Run: `python3 -m http.server 8765 -d _site`, then open `http://127.0.0.1:8765/blog/gaussian-processes/`. Click "Open the live notebook".
Expected: the notebook text shows immediately. After Python loads, "New Sample" in the notebook adds a line.

- [ ] **Step 4: Commit**

```bash
git add blog/gaussian-processes/live.py
git commit -m "gp post: publish the original marimo notebook as a live notebook

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 13: Comments with giscus

**Files:**
- Modify: `scripts/check_site.py`, `tests/test_check_site.py`
- Modify: `blog/_quarto.yml`, `blog/index.qmd`, `blog/about/index.qmd`, `blog/subscribe/index.qmd`

**Interfaces:**
- Consumes: `post_slugs` and `main` (Task 2).
- Produces: `check_comments(site_dir: Path, slugs: set[str]) -> list[str]` in `scripts/check_site.py`, which `main` runs.

- [ ] **Step 1: Ask the owner to prepare the repo**

Stop, and ask the owner to do these 2 steps on GitHub. Wait until the owner confirms both:
1. In `cyniphile/cyniphile.github.io`, open Settings → General → Features, and turn on **Discussions**.
2. Open https://github.com/apps/giscus, click Configure, and give it access only to `cyniphile.github.io`.

- [ ] **Step 2: Check that GitHub gives the repo and category IDs**

```bash
gh api graphql -f query='query { repository(owner: "cyniphile", name: "cyniphile.github.io") { id discussionCategories(first: 20) { nodes { id name } } } }'
```

Expected: JSON with the repository `id` (it starts with `R_`) and a category named `Announcements` with an `id` (it starts with `DIC_`). Step 7 reads these IDs again.

- [ ] **Step 3: Write the failing test**

In `tests/test_check_site.py`, add `check_comments` to the import list from `check_site`, then add this test:

```python
def test_comments_show_only_on_posts(tmp_path):
    giscus = '<script src="https://giscus.app/client.js"></script>'
    write(tmp_path / "blog/index.html", "post list")
    write(tmp_path / "blog/abortion/index.html", giscus)
    write(tmp_path / "blog/voter-fraud/index.html", "no comments here")
    write(tmp_path / "blog/about/index.html", giscus)
    assert check_comments(tmp_path, {"abortion", "voter-fraud"}) == [
        "blog/about/index.html: comments must be off",
        "blog/voter-fraud/index.html: comments are missing",
    ]
```

- [ ] **Step 4: Run the test to see it fail**

Run: `uv run pytest tests/test_check_site.py -v`
Expected: FAIL with `ImportError: cannot import name 'check_comments'`.

- [ ] **Step 5: Write the implementation**

In `scripts/check_site.py`, add this function after `check_listing`:

```python
def check_comments(site_dir: Path, slugs: set[str]) -> list[str]:
    blog = site_dir / "blog"
    errors = []
    for page in [blog / "index.html", *sorted(blog.glob("*/index.html"))]:
        if not page.is_file():
            continue
        is_post = page.parent != blog and page.parent.name in slugs
        has_comments = "giscus" in page.read_text(encoding="utf-8", errors="replace")
        if is_post and not has_comments:
            errors.append(f"{rel(page, site_dir)}: comments are missing")
        if not is_post and has_comments:
            errors.append(f"{rel(page, site_dir)}: comments must be off")
    return errors
```

In `main`, change the list of checks to:

```python
    slugs = post_slugs(args.blog)
    errors = [
        *check_redirects(args.site),
        *check_internal_links(args.site),
        *check_page_budgets(args.site),
        *check_image_sizes(args.blog),
        *check_listing(args.site, slugs),
        *check_comments(args.site, slugs),
    ]
```

- [ ] **Step 6: Run the tests to see them pass**

Run: `uv run pytest -v`
Expected: all tests pass.

- [ ] **Step 7: Configure giscus**

Run this in one shell command, so the two IDs go directly into `blog/_quarto.yml`:

```bash
QUERY='query { repository(owner: "cyniphile", name: "cyniphile.github.io") { id discussionCategories(first: 20) { nodes { id name } } } }'
REPO_ID=$(gh api graphql -f query="$QUERY" --jq '.data.repository.id')
CATEGORY_ID=$(gh api graphql -f query="$QUERY" --jq '.data.repository.discussionCategories.nodes[] | select(.name == "Announcements") | .id')
test -n "$REPO_ID" && test -n "$CATEGORY_ID" && cat >> blog/_quarto.yml <<EOF

comments:
  giscus:
    repo: cyniphile/cyniphile.github.io
    repo-id: "$REPO_ID"
    category: "Announcements"
    category-id: "$CATEGORY_ID"
    mapping: pathname
    reactions-enabled: true
    loading: lazy
EOF
tail -10 blog/_quarto.yml
```

Expected: the end of `blog/_quarto.yml` shows the `comments` block with a `repo-id` that starts with `R_` and a `category-id` that starts with `DIC_`.

Add the line `comments: false` to the front matter of `blog/index.qmd`, `blog/about/index.qmd` and `blog/subscribe/index.qmd`.

- [ ] **Step 8: Build and check**

Run: `uv run scripts/build.py`
Expected: `All site checks passed`. Open `http://127.0.0.1:8765/blog/abortion/` (after `python3 -m http.server 8765 -d _site`). Expected: the giscus comment box shows at the end of the post. The About page has no comment box.

- [ ] **Step 9: Commit**

```bash
git add scripts/check_site.py tests/test_check_site.py blog/_quarto.yml blog/index.qmd blog/about/index.qmd blog/subscribe/index.qmd blog/_freeze
git commit -m "blog: add giscus comments on posts

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 14: CI workflow and README

**Files:**
- Create: `.github/workflows/publish.yml`
- Replace: `README.md`

**Interfaces:**
- Consumes: `uv run pytest`, `node --test ...`, `uv run scripts/build.py`.
- Produces: a `build` job for each push and pull request, and a `deploy` job for pushes to `master`.

- [ ] **Step 1: Write the workflow**

`.github/workflows/publish.yml`:

```yaml
name: Publish site

on:
  push:
    branches: [master]
  pull_request:
  workflow_dispatch:

permissions:
  contents: read

concurrency:
  group: pages-${{ github.ref }}
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
      - uses: quarto-dev/quarto-actions/setup@v2
        with:
          version: 1.10.18
      - uses: astral-sh/setup-uv@v10
      - uses: actions/setup-node@v7
        with:
          node-version: 22
      - name: Install Python packages
        run: uv sync --frozen
      - name: Test the Python scripts
        run: uv run pytest
      - name: Test the JavaScript helpers
        run: node --test blog/gaussian-processes/wiring.test.mjs
      - name: Build and check the site
        run: uv run scripts/build.py
      - uses: actions/upload-pages-artifact@v5
        with:
          path: _site

  deploy:
    if: github.event_name != 'pull_request' && github.ref == 'refs/heads/master'
    needs: build
    runs-on: ubuntu-latest
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v5
```

- [ ] **Step 2: Write the README**

`README.md`:

````markdown
# www.lukeschiefelbein.com

This repo builds the full site:

- `/` is the landing page. Its static files are in `site-root/`.
- `/blog/` is the blog. It is a Quarto project in `blog/`.

## Setup (one time)

1. Install uv and Quarto 1.10.18.
2. Run `uv sync`.

## Write a post

1. Make the folder `blog/<slug>/` with an `index.qmd` file. Put `title`, `date`, `description` and `categories` in its front matter.
2. Run `uv run quarto preview blog`. The page updates each time you save.
3. Commit the post and the files in `blog/_freeze/`. Push to `master`.

For an interactive post, look at `blog/gaussian-processes/`:

- Python calculates all data at build time (`gp_data.py`) and sends it to the page with `ojs_define`.
- Observable JS cells connect the controls to the precomputed data (`wiring.js`). JavaScript does no vector or matrix math.
- A marimo notebook with the name `live.py` in a post folder becomes a live notebook at `<post URL>/live/`.

## Build and test the full site

- `uv run pytest` tests the Python scripts.
- `node --test blog/gaussian-processes/wiring.test.mjs` tests the JavaScript helpers.
- `uv run scripts/build.py` builds `_site/` and runs the site checks.
- `python3 -m http.server -d _site` serves the site at http://localhost:8000.

## Deploy

GitHub Actions (`.github/workflows/publish.yml`) builds and deploys each push to `master`. A pull request runs the same build and checks, but it does not deploy.
````

- [ ] **Step 3: Check the workflow syntax**

Run: `uv run python -c "import yaml; yaml.safe_load(open('.github/workflows/publish.yml')); print('ok')"`
Expected: `ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/publish.yml README.md
git commit -m "ci: build, check and deploy the site with GitHub Actions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

- [ ] **Step 5: Push the branch and open a pull request (ask the owner first)**

Ask the owner for approval to push `blog-consolidation` and to open a pull request. After the approval:

```bash
git push -u origin blog-consolidation
gh pr create --draft --base master --head blog-consolidation \
  --title "Consolidate the blog into one Quarto site" \
  --body "This PR merges the fastpages blog and the marimo blog into this repo. See docs/superpowers/specs/2026-09-28-blog-consolidation-design.md.

🤖 Generated with [Claude Code](https://claude.com/claude-code)"
gh pr checks --watch
```

Expected: the `build` job passes. The `deploy` job is skipped for the pull request.

---

### Task 15: Checks before the cutover

**Files:** none. The results go into the pull request description.

**Interfaces:**
- Consumes: the full build (Tasks 1–14).
- Produces: a table of measured times, and the completed widget and look checklists.

- [ ] **Step 1: Build and serve the site**

Run: `uv run scripts/build.py && python3 -m http.server 8765 -d _site`
Expected: `All site checks passed`, then the server starts.

The local server does not compress files, so the times are slower than on GitHub Pages. If a page passes here, it also passes on GitHub Pages.

- [ ] **Step 2: Measure each post with the phone settings**

For each URL below, open a new Chrome DevTools page in a new isolated context, so the cache is empty. Set the network to "Fast 4G", the CPU slowdown to 4× and the viewport to 390 × 844 (mobile). Load the page with this script before navigation:

```js
window.__t = {};
new PerformanceObserver((list) => {
  for (const entry of list.getEntries()) {
    if (entry.name === "first-contentful-paint") window.__t.fcp = Math.round(entry.startTime);
  }
}).observe({type: "paint", buffered: true});
```

After the load, run:

```js
async () => {
  const until = async (ok) => {
    while (!ok()) await new Promise((resolve) => setTimeout(resolve, 50));
    return Math.round(performance.now());
  };
  const hasButton = () => [...document.querySelectorAll("button")].some((b) => b.textContent.trim() === "New Sample");
  const widgetsReady = document.querySelector("#quarto-document-content .cell") && hasButton()
    ? await until(() => hasButton() && document.querySelector(".cell-output-display svg"))
    : null;
  return {fcp: window.__t.fcp, widgetsReady};
}
```

URLs: `/blog/`, `/blog/abortion/`, `/blog/voter-fraud/`, `/blog/biology-rust/`, `/blog/gaussian-processes/`, all at `http://127.0.0.1:8765`.
Expected: `fcp` is less than 2000 for each URL. For the GP post, `widgetsReady` is less than 3000.
If the GP post fails only because of its size, stop and tell the owner. The fallback in the spec (section 11) is to move the large data from `ojs_define` to JSON files that load with `FileAttachment`.

- [ ] **Step 3: Check the widgets again**

Do the 13 checks of Task 11, Step 6 on the phone-size page.
Expected: the same results. No chart is wider than the screen.
Also open `/blog/gaussian-processes/live/`. Expected: the notebook text shows first, and "New Sample" works after Python loads.

- [ ] **Step 4: Check the look**

For each page, check the phone width (390 px) and the desktop width (1280 px). (The site has no dark mode; see spec section 8.6.)
Expected: the text is easy to read, the charts are readable, and no page scrolls sideways.

- [ ] **Step 5: Add the results to the pull request**

Write the current pull request text plus a results section to a file, then update the pull request:

```bash
gh pr view --json body --jq .body > "${TMPDIR:-/tmp}/pr-body.md"
cat >> "${TMPDIR:-/tmp}/pr-body.md" <<'EOF'

## Checks before the cutover

| Page | First text (ms) | Widgets work (ms) |
|---|---|---|
EOF
```

Add one table row for each URL of Step 2, with the measured `fcp` and `widgetsReady` values. Add one line for the widget checks (Step 3) and one line for the look checks (Step 4). Then run `gh pr edit --body-file "${TMPDIR:-/tmp}/pr-body.md"`.

---

### Task 16: Cutover

**Files:** none (settings on GitHub and GoatCounter).

**Interfaces:**
- Consumes: the pull request from Task 14, with the results from Task 15.
- Produces: the live site at `www.lukeschiefelbein.com`, from `cyniphile.github.io` only.

Ask the owner for approval before each step that changes GitHub or an external site. Stop if a check fails.

- [ ] **Step 1: The owner makes the GoatCounter account**

Ask the owner to sign up at https://www.goatcounter.com with the code `lukeschiefelbein`. If this code is not available, change `lukeschiefelbein.goatcounter.com` to the new code in `site-root/index.html`, `site-root/404.html`, `blog/_includes/goatcounter.html` and `tests/test_site_root.py`, then commit and push.

- [ ] **Step 2: Set the Pages source of `cyniphile.github.io` to GitHub Actions (approval)**

```bash
gh api repos/cyniphile/cyniphile.github.io/pages --jq '{build_type, cname, status}'
gh api -X PUT repos/cyniphile/cyniphile.github.io/pages -f build_type=workflow
gh api repos/cyniphile/cyniphile.github.io/pages --jq '{build_type, cname}'
curl -s -o /dev/null -w '%{http_code}\n' https://www.lukeschiefelbein.com/
```

Expected: `build_type` changes from `legacy` to `workflow`, `cname` stays `www.lukeschiefelbein.com`, and the landing page still returns `200`.

- [ ] **Step 3: Merge the pull request (approval)**

```bash
gh pr ready
gh pr merge --merge
gh run watch "$(gh run list --branch master --workflow publish.yml --limit 1 --json databaseId --jq '.[0].databaseId')"
```

Expected: the `build` and `deploy` jobs pass. Then `curl -s https://www.lukeschiefelbein.com/ | grep -c frontpage-wobble.png` prints `1`.

- [ ] **Step 4: Turn off Pages in the old repos (approval)**

```bash
gh api -X DELETE repos/cyniphile/blog/pages
gh api -X DELETE repos/cyniphile/marimo-blog/pages
```

Expected: both commands succeed with no output.

- [ ] **Step 5: Check all URLs on the live site**

Wait approximately 5 minutes, then run:

```bash
for path in / /blog/ /blog/about/ /blog/subscribe/ /blog/abortion/ /blog/voter-fraud/ /blog/biology-rust/ \
  /blog/gaussian-processes/ /blog/gaussian-processes/live/ /blog/index.xml /blog/feed.xml /robots.txt /no-such-page; do
  printf "%s %s\n" "$(curl -s -o /dev/null -w '%{http_code}' "https://www.lukeschiefelbein.com$path")" "$path"
done
uv run python - <<'EOF'
import sys
import urllib.request

sys.path.insert(0, "scripts")
from redirects import REDIRECTS, SITE_URL

for old, new in REDIRECTS.items():
    page = urllib.request.urlopen(SITE_URL + old).read().decode()
    print("OK " if f"url={new}" in page else "BAD", old, "->", new)
EOF
```

Expected: `200` for each path, except `404` for `/no-such-page`. `OK` for each redirect.

- [ ] **Step 6: Measure the live site with the phone settings**

Repeat Task 15, Step 2 with `https://www.lukeschiefelbein.com` URLs.
Expected: `fcp` is less than 2000 for each post, and `widgetsReady` is less than 3000 for the GP post. Tell the owner the numbers.

- [ ] **Step 7: Move the 3 old comments (approval)**

```bash
gh issue transfer 17 cyniphile/cyniphile.github.io -R cyniphile/blog
```

Then ask the owner to open the moved issue on GitHub, click **Convert to discussion**, and select the category **Announcements**. Next, the owner changes the discussion title to `blog/voter-fraud/`.
Open `https://www.lukeschiefelbein.com/blog/voter-fraud/`. Expected: the 3 old comments show under the post. If they do not show, change the title to `/blog/voter-fraud/` and load the page again.

- [ ] **Step 8: Check the analytics**

Open the GoatCounter dashboard. Expected: visits from Steps 5–7 show for `/` and for posts.

- [ ] **Step 9: Archive the old repos (approval)**

```bash
gh repo archive cyniphile/blog --yes
gh repo archive cyniphile/marimo-blog --yes
```

Expected: both repos show as archived (read-only) on GitHub.

- [ ] **Step 10: Mark the spec as done**

```bash
sed -i '' "s/^- Status: draft, for review$/- Status: implemented (cutover on $(date +%F))/" docs/superpowers/specs/2026-09-28-blog-consolidation-design.md
grep -n '^- Status' docs/superpowers/specs/2026-09-28-blog-consolidation-design.md
```

Expected: `- Status: implemented (cutover on YYYY-MM-DD)` with today's date. Commit this change and push it to `master` (approval).
