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
