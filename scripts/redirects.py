"""Old URL paths of the site, and the redirect pages that send readers to the new paths."""

from __future__ import annotations

import html
import json
from pathlib import Path
from urllib.parse import unquote

SITE_URL = "https://www.lukeschiefelbein.com"

REDIRECTS: dict[str, str] = {
    "/blog/search/": "/blog/",
    "/blog/categories/": "/blog/topics/",
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


# A meta refresh drops the fragment of the old link ("#section"), so a script moves the reader
# first, with the fragment. The old Topics page filtered with "#<category>"; the new one with
# "#category=<category>".
FRAGMENT_PREFIX: dict[str, str] = {"/blog/categories/": "category="}


def redirect_page(new_path: str, fragment_prefix: str = "") -> str:
    """Return an HTML page that sends browsers and search engines to new_path. The meta refresh
    is for browsers without JavaScript."""
    target = html.escape(new_path, quote=True)
    canonical = html.escape(SITE_URL + new_path, quote=True)
    fragment = ("location.hash" if not fragment_prefix else
                f'(location.hash ? "#" + {json.dumps(fragment_prefix)} + location.hash.slice(1) : "")')
    script = f"<script>location.replace({json.dumps(new_path)} + {fragment});</script>"
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        "<title>Page moved</title>\n"
        f'<link rel="canonical" href="{canonical}">\n'
        f"{script}\n"
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
        page.write_text(redirect_page(new, FRAGMENT_PREFIX.get(old, "")), encoding="utf-8")
        written.append(page)
    return written
