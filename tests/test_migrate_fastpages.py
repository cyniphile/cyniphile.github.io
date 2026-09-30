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
        '{{ "Even the term "pro-life" is loaded." | fndetail: 2 }}\n'
        "{{ 'There is <a href=\"https://x.org\">little evidence</a>.' |  fndetail: 4 }}\n"
    )
    assert m.convert_footnotes(body) == (
        "certainly simple[^2], it works.\n\n"
        '[^2]: Even the term "pro-life" is loaded.\n'
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


def test_convert_captions_turns_the_title_into_the_caption_and_keeps_the_alt_text():
    body = (
        '![abortion](sign.jpg "Which sign makes you angry?")\n'
        '![](plot.png "Data: https://example.org/data.")\n'
    )
    assert m.convert_captions(body) == (
        '![Which sign makes you angry?](sign.jpg){fig-alt="abortion"}\n'
        "![Data: https://example.org/data.](plot.png)\n"
    )


def test_convert_captions_keeps_the_alt_text_of_an_image_without_a_title():
    body = "![fraud](https://example.com/external.jpg)\n"
    assert m.convert_captions(body) == '![](https://example.com/external.jpg){fig-alt="fraud"}\n'


def test_convert_captions_leaves_images_with_neither_alt_text_nor_title_alone():
    body = "![](randolph.png)\ntext ![](jackson.png) more\n![](meme.jpg) \n"
    assert m.convert_captions(body) == body


def test_convert_captions_escapes_quotes_in_the_alt_text():
    assert m.convert_captions('![the "big" one](a.png)') == '![](a.png){fig-alt="the \\"big\\" one"}'


def test_convert_captions_escapes_brackets_in_the_title():
    assert m.convert_captions('![](a.png "See [1] and [2]")') == "![See \\[1\\] and \\[2\\]](a.png)"


def test_convert_captions_escapes_underscores_in_the_real_ballot_title():
    # Real title of the voter-fraud post. Not escaped, Pandoc reads "_-_US_election_08_(" as
    # emphasis and the caption shows "Larsz_-<em>US_election_08</em>(by-sa).jpg".
    body = (
        '![](stright-ticket-ballot.jpg "A ballot with a \'straight-party\' option. '
        'https://commons.wikimedia.org/wiki/File:Larsz_-_US_election_08_(by-sa).jpg")\n'
    )
    assert m.convert_captions(body) == (
        "![A ballot with a 'straight-party' option. "
        "https://commons.wikimedia.org/wiki/File:Larsz\\_-\\_US\\_election\\_08\\_(by-sa).jpg]"
        "(stright-ticket-ballot.jpg)\n"
    )


def test_convert_captions_escapes_every_character_that_markdown_could_read_as_markup():
    # Escaped: backslash, [ ] _ * ` < $
    assert m.convert_captions('![](a.png "a_b *c* `d` <e> $f$ \\g [h]")') == (
        "![a\\_b \\*c\\* \\`d\\` \\<e> \\$f\\$ \\\\g \\[h\\]](a.png)"
    )


def test_convert_captions_handles_real_titles_with_parentheses_and_line_breaks():
    body = (
        '![abortion](https://upload.wikimedia.org/x_%2832676869635%29.jpg "Which sign? '
        'https://commons.wikimedia.org/wiki/File:Abortion_(32676869635).jpg)")\n'
        '![](fayette.png "Data: https://www.sos.alabama.gov/alabama-votes/voter/election-data\n")\n'
    )
    assert m.convert_captions(body) == (
        "![Which sign? https://commons.wikimedia.org/wiki/File:Abortion\\_(32676869635).jpg)]"
        '(https://upload.wikimedia.org/x_%2832676869635%29.jpg){fig-alt="abortion"}\n'
        "![Data: https://www.sos.alabama.gov/alabama-votes/voter/election-data](fayette.png)\n"
    )


def test_convert_captions_does_not_convert_an_image_twice():
    body = '![A caption](a.png){fig-alt="alt text"}\n'
    assert m.convert_captions(body) == body
    assert m.convert_captions(m.convert_captions('![alt text](a.png "A caption")\n')) == body


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


def test_convert_post_shows_image_titles_as_captions(tmp_path):
    post = tmp_path / "2020-11-12-voter-fraud.md"
    post.write_text(
        "---\ntitle: X\n---\n"
        '![fraud]({{ site.baseurl }}/images/chart.png "Photo: NHPR")\n',
        encoding="utf-8",
    )
    images = tmp_path / "images"
    images.mkdir()
    Image.new("RGB", (20, 20), "blue").save(images / "chart.png")
    text = m.convert_post(post, images, tmp_path / "out").read_text(encoding="utf-8")
    assert '![Photo: NHPR](chart.png){fig-alt="fraud"}' in text


def test_convert_post_stops_on_unknown_liquid_tags(tmp_path):
    post = tmp_path / "2020-01-02-x.md"
    post.write_text("---\ntitle: X\n---\n{% include warning.html %}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Liquid"):
        m.convert_post(post, tmp_path, tmp_path / "out")
