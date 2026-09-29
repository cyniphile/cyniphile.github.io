import re
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
