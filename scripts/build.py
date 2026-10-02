"""Build the full site into _site/: the Quarto blog, marimo live notebooks, static files and redirects."""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

import check_site
import marimo_to_blog
from redirects import write_redirects

ROOT = Path(__file__).resolve().parents[1]
KATEX_VERSION = "0.18.9"
# marimo of this environment (uv.lock), also when another marimo comes first on PATH
MARIMO = [sys.executable, "-m", "marimo"]


def run(cmd: list[str], cwd: Path) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, check=True)


def live_notebooks(blog_dir: Path, site_dir: Path) -> list[tuple[Path, Path]]:
    """Each blog/<slug>/notebook.py is also a live notebook: _site/blog/<slug>/live/index.html."""
    return [
        (src, site_dir / "blog" / src.parent.name / "live" / "index.html")
        for src in sorted(blog_dir.glob("*/notebook.py"))
    ]


def convert_notebook_posts(blog_dir: Path) -> list[Path]:
    """Write index.qmd (and widgets/) for each blog/<slug>/notebook.py that is out of date.

    A conversion runs the notebook and simulates its widgets (minutes), so an up-to-date post
    (same notebook, post.yml and converter) is not converted again. Return the converted posts.
    """
    converted = []
    for notebook in sorted(blog_dir.glob("*/notebook.py")):
        post = notebook.parent
        if not marimo_to_blog.up_to_date(post):
            print(f"+ convert {post}", flush=True)
            marimo_to_blog.convert(post)
            converted.append(post)
    return converted


def copy_tree(src: Path, dst: Path) -> None:
    shutil.copytree(src, dst, dirs_exist_ok=True)


def pin_katex(site_dir: Path) -> int:
    """Quarto loads KaTeX from katex@latest. Pin it to KATEX_VERSION in every page under blog/.

    Return the number of pages that changed. Only the version text changes: the encoding
    is UTF-8 and line endings stay as they are.
    """
    changed = 0
    for page in sorted((site_dir / "blog").rglob("*.html")):
        text = page.read_text(encoding="utf-8", newline="")
        pinned = text.replace("katex@latest", f"katex@{KATEX_VERSION}")
        if pinned != text:
            page.write_text(pinned, encoding="utf-8", newline="")
            changed += 1
    return changed


# The last data line of Quarto's giscus loader (Quarto 1.10.18, formats/html/giscus/giscus.ejs)
GISCUS_LANG_LINE = re.compile(r'^([ \t]*)script\.dataset\.lang = "[^"]*";$', re.MULTILINE)


def lazy_giscus(site_dir: Path) -> int:
    """Quarto 1.10.18 ignores the giscus option "loading: lazy". Add it to Quarto's giscus loader
    in every page under blog/, so the comment frame loads when the reader comes near it.

    Return the number of pages that changed."""
    changed = 0
    for page in sorted((site_dir / "blog").rglob("*.html")):
        text = page.read_text(encoding="utf-8", newline="")
        if "giscus.app/client.js" not in text or "script.dataset.loading" in text:
            continue
        lazy, count = GISCUS_LANG_LINE.subn(r'\g<0>\n\1script.dataset.loading = "lazy";', text)
        if count != 1:
            raise ValueError(f"{page}: Quarto's giscus loader changed; cannot add lazy loading")
        page.write_text(lazy, encoding="utf-8", newline="")
        changed += 1
    return changed


FEED_ITEM = re.compile(r"<item>.*?</item>", re.DOTALL)
FEED_DESCRIPTION = re.compile(r"<description><!\[CDATA\[(.*?)\]\]></description>", re.DOTALL)
FEED_NOTE = '<p class="mb-feed-note"><em><a href="{url}">Interactive figure: open the post to see it.</a></em></p>'


def clean_feed_html(content: str, link: str) -> str:
    """One feed item's HTML, for a feed reader (no JavaScript, no site styles): without the site
    header (include-before-body puts it inside <main>, which Quarto copies), scripts, stylesheets
    and comments; each interactive island (div.mb-cell, drawn by JavaScript) becomes a link to the
    post (one link for islands in a row); relative links become absolute (from the item link)."""
    soup = BeautifulSoup(content, "html.parser")
    for element in soup.select("header.site-header, script, link[rel=stylesheet]"):
        element.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for cell in soup.select("div.mb-cell"):
        cell.replace_with(BeautifulSoup(FEED_NOTE.format(url=html.escape(link, quote=True)), "html.parser"))
    for note in soup.select("p.mb-feed-note"):
        node = note.previous_sibling
        while isinstance(node, NavigableString) and not node.strip():
            node = node.previous_sibling
        if isinstance(node, Tag) and "mb-feed-note" in (node.get("class") or []):
            note.decompose()
    for tag, attribute in (("a", "href"), ("img", "src")):
        for element in soup.find_all(tag, attrs={attribute: True}):
            if not element[attribute].startswith("#"):
                element[attribute] = urljoin(link, element[attribute])
    return str(soup).strip()


def clean_feed(site_dir: Path) -> int:
    """Clean each item of the blog feed (clean_feed_html). Return the number of items."""
    feed = site_dir / "blog" / "index.xml"
    text = feed.read_text(encoding="utf-8")
    count = 0

    def item(match: re.Match) -> str:
        nonlocal count
        count += 1
        link = re.search(r"<link>(.*?)</link>", match.group(0)).group(1).strip()
        return FEED_DESCRIPTION.sub(
            lambda m: "<description><![CDATA["
            + clean_feed_html(m.group(1), link).replace("]]>", "]]]]><![CDATA[>") + "]]></description>",
            match.group(0))

    feed.write_text(FEED_ITEM.sub(item, text), encoding="utf-8")
    return count


def slash_sitemap(site_dir: Path) -> None:
    """Quarto's sitemap lists ".../index.html"; the canonical links, the feed and the redirects use
    ".../". List each page with one URL."""
    sitemap = site_dir / "blog" / "sitemap.xml"
    if not sitemap.is_file():
        raise FileNotFoundError(f"Quarto did not write the sitemap {sitemap}")
    text = sitemap.read_text(encoding="utf-8")
    sitemap.write_text(re.sub(r"/index\.html</loc>", "/</loc>", text), encoding="utf-8")


def tag_live_page(page: Path, includes: Path) -> None:
    """Add the one-path script and the GoatCounter tag (blog/_includes) to a live notebook page."""
    head = (includes / "one-url.html").read_text(encoding="utf-8") + (includes / "goatcounter.html").read_text(encoding="utf-8")
    text = page.read_text(encoding="utf-8")
    if "</head>" not in text:
        raise ValueError(f"{page}: no </head>")
    page.write_text(text.replace("</head>", head + "</head>", 1), encoding="utf-8")


def copy_feed(site_dir: Path) -> None:
    """Keep the old feed URL /blog/feed.xml for current RSS subscribers."""
    feed = site_dir / "blog" / "index.xml"
    if not feed.is_file():
        raise FileNotFoundError(f"Quarto did not write the feed {feed}")
    shutil.copyfile(feed, site_dir / "blog" / "feed.xml")


def build(root: Path = ROOT) -> int:
    site = root / "_site"
    blog = root / "blog"
    if site.exists():
        shutil.rmtree(site)
    convert_notebook_posts(blog)
    run(["quarto", "render", "blog"], cwd=root)
    copy_tree(blog / "_site", site / "blog")
    pin_katex(site)
    lazy_giscus(site)
    slash_sitemap(site)
    for src, out in live_notebooks(blog, site):
        run(
            # run mode with the code shown: the cells run when the page loads (edit mode waits for
            # "Run all", so a button does nothing), and the reader sees the code. --no-sandbox: the
            # preview runs in this environment (uv.lock), and marimo does not edit notebook.py.
            [*MARIMO, "export", "html-wasm", str(src), "--mode", "run", "--show-code", "--execute",
             "--no-sandbox", "-o", str(out), "-f"],
            cwd=root,
        )
        # marimo also writes CLAUDE.md (a prompt for AI assistants) next to the page: not for the site
        (out.parent / "CLAUDE.md").unlink(missing_ok=True)
        tag_live_page(out, blog / "_includes")
    copy_tree(root / "site-root", site)
    write_redirects(site)
    clean_feed(site)
    copy_feed(site)
    return check_site.main(["--site", str(site), "--blog", str(blog)])


if __name__ == "__main__":
    sys.exit(build())
