"""Read marimo's output HTML and write the blog version of it.

marimo writes each UI element as <marimo-ui-element object-id=...><marimo-KIND data-*='json'>.
The blog version keeps marimo's layout HTML (flex divs, markdown) and replaces each element:

- marimo-plotly → <div class="mb-plot" data-fig="N">; the figure goes in Rendered.figures
- marimo-mime-renderer (Vega-Lite) → <div class="mb-chart" data-chart="N">; the spec goes in
  Rendered.charts
- buttons, sliders, matrices and editable code editors → <div class="mb-KIND" data-control="NAME">;
  the runtime draws the control from its spec (Rendered.controls has the specs)
- a read-only code editor (mo.show_code) → <pre class="mb-code">; a cell whose whole output is one
  read-only code editor is written as a Markdown code block instead (Rendered.code)
- marimo-tex → <span class="math inline|display">TeX</span>, the form that Quarto's KaTeX script
  renders
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable

from bs4 import BeautifulSoup, Tag

CONTROL_KINDS = {"marimo-button": "button", "marimo-slider": "slider", "marimo-matrix": "matrix",
                 "marimo-code-editor": "editor"}
VEGA_MIME = re.compile(r"application/vnd\.vegalite\.v\d+\+json")


@dataclass
class Rendered:
    html: str
    figures: list[dict] = field(default_factory=list)  # {"figure": {...}, "config": {...}}
    charts: list[dict] = field(default_factory=list)  # Vega-Lite specs
    controls: list[dict] = field(default_factory=list)  # control specs, in page order
    code: str | None = None  # set when the whole output is one read-only code display
    warnings: list[str] = field(default_factory=list)


def data_attrs(tag: Tag) -> dict:
    """The data-* attributes of a marimo element, with their JSON values decoded."""
    attrs = {}
    for key, value in tag.attrs.items():
        if not key.startswith("data-"):
            continue
        try:
            attrs[key[5:]] = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            attrs[key[5:]] = value
    return attrs


def label_html(label) -> str:
    """A marimo label (rendered markdown HTML) as blog HTML: math as Quarto's KaTeX spans
    (the runtime renders them), without marimo's markdown wrappers."""
    if not label:
        return ""
    soup = BeautifulSoup(str(label), "html.parser")
    for tex in soup.find_all("marimo-tex"):
        tex.replace_with(_tex(tex, soup))
    for span in soup.find_all("span", class_=["markdown", "paragraph"]):
        span.unwrap()
    return str(soup).strip()


def label_text(label) -> str:
    """The plain text of a marimo label (math as its TeX), for accessible names."""
    if not label:
        return ""
    return BeautifulSoup(label_html(label), "html.parser").get_text(" ", strip=True)


def slider_values(attrs: dict) -> list:
    """Every value that a marimo slider can take, in order."""
    if attrs.get("steps"):
        return list(attrs["steps"])
    start, stop = attrs["start"], attrs["stop"]
    step = attrs.get("step") or 1
    count = int(round((stop - start) / step)) + 1
    decimals = max(0, -int(f"{step:e}".split("e")[1])) + 2
    values = [round(start + i * step, decimals) for i in range(count)]
    if all(float(v).is_integer() for v in values) and all(isinstance(x, int) for x in (start, stop, step)):
        values = [int(v) for v in values]
    return values


def _tex(tag: Tag, soup: BeautifulSoup) -> Tag:
    text = tag.get_text()
    display = text.startswith("||[") or text.startswith("||$$")
    inner = re.sub(r"^\|\|[\(\[]|\|\|[\)\]]$", "", text.strip())
    span = soup.new_tag("span", attrs={"class": f"math {'display' if display else 'inline'}"})
    span.string = inner
    return span


def control_spec(kind: str, name: str | None, attrs: dict) -> dict:
    spec = {"kind": kind, "name": name, "label": label_text(attrs.get("label")),
            "label_html": label_html(attrs.get("label"))}
    if kind == "button":
        spec["kind_style"] = attrs.get("kind") or "neutral"
        spec["disabled"] = bool(attrs.get("disabled"))
    elif kind == "slider":
        values = slider_values(attrs)
        initial = attrs.get("initial-value")
        # With steps=[...], marimo's frontend value is the index into the steps, not the value.
        by_index = bool(attrs.get("steps"))
        index = (int(initial) if initial is not None else 0) if by_index else _closest(values, initial)
        spec.update(values=values, index=index, by_index=by_index, debounce=bool(attrs.get("debounce")),
                    show_value=bool(attrs.get("show-value")), full_width=bool(attrs.get("full-width")))
    elif kind == "matrix":
        spec.update(value=attrs.get("initial-value"), min=attrs.get("min-value"), max=attrs.get("max-value"),
                    step=attrs.get("step"), precision=attrs.get("precision", 1),
                    symmetric=bool(attrs.get("symmetric")), disabled=attrs.get("disabled"))
    elif kind == "editor":
        spec.update(value=attrs.get("initial-value") or "", language=attrs.get("language") or "python",
                    min_height=attrs.get("min-height"))
    return spec


def _closest(values: list, value) -> int:
    if value is None or not values:
        return 0
    return min(range(len(values)), key=lambda i: abs(float(values[i]) - float(value)))


def render(html: str, name_for_id: Callable[[str], str | None]) -> Rendered:
    """Write the blog version of one cell's output HTML."""
    soup = BeautifulSoup(html, "html.parser")
    out = Rendered(html="")

    wrappers = soup.find_all("marimo-ui-element")
    elements = [w.find(True) for w in wrappers]
    if (len(wrappers) == 1 and elements[0] is not None and elements[0].name == "marimo-code-editor"
            and data_attrs(elements[0]).get("disabled") and not soup.get_text(strip=True)):
        out.code = data_attrs(elements[0]).get("initial-value") or ""
        return out

    for wrapper, element in zip(wrappers, elements):
        if element is None:
            wrapper.decompose()
            continue
        attrs = data_attrs(element)
        name = name_for_id(wrapper.get("object-id", ""))
        if element.name == "marimo-plotly":
            placeholder = soup.new_tag("div", attrs={"class": "mb-plot", "data-fig": str(len(out.figures))})
            out.figures.append({"figure": attrs.get("figure") or {}, "config": attrs.get("config") or {}})
        elif element.name == "marimo-code-editor" and attrs.get("disabled"):
            placeholder = soup.new_tag("pre", attrs={"class": "mb-code"})
            placeholder.string = attrs.get("initial-value") or ""
        elif element.name in CONTROL_KINDS:
            kind = CONTROL_KINDS[element.name]
            if name is None:
                out.warnings.append(f"a {kind} that no notebook variable holds is shown as static")
            placeholder = soup.new_tag("div", attrs={"class": f"mb-{kind}", "data-control": name or ""})
            out.controls.append(control_spec(kind, name, attrs))
        elif element.name == "marimo-vega" and attrs.get("spec"):
            # mo.ui.altair_chart: drawn like a chart; its selection does not drive other cells
            data = attrs["spec"]
            placeholder = soup.new_tag("div", attrs={"class": "mb-chart", "data-chart": str(len(out.charts))})
            out.charts.append(json.loads(data) if isinstance(data, str) else dict(data))
            out.warnings.append("an altair_chart is shown as a chart; its selection is not interactive")
        else:
            out.warnings.append(f"no blog version of <{element.name}>; its content is shown without interaction")
            element.unwrap()
            wrapper.unwrap()
            continue
        wrapper.replace_with(placeholder)

    for renderer in soup.find_all("marimo-mime-renderer"):
        attrs = data_attrs(renderer)
        mime = attrs.get("mime") or ""
        if VEGA_MIME.fullmatch(mime):
            data = attrs.get("data")
            spec: dict = json.loads(data) if isinstance(data, str) else dict(data or {})
            placeholder = soup.new_tag("div", attrs={"class": "mb-chart", "data-chart": str(len(out.charts))})
            out.charts.append(spec)
        elif mime == "text/html":
            placeholder = BeautifulSoup(str(attrs.get("data") or ""), "html.parser")
        elif mime.startswith("image/"):
            placeholder = soup.new_tag("img", attrs={"src": str(attrs.get("data") or ""), "alt": ""})
        else:
            placeholder = soup.new_tag("span")
            out.warnings.append(f"no blog version of the {mime} output; it is left out")
        renderer.replace_with(placeholder)

    for tex in soup.find_all("marimo-tex"):
        tex.replace_with(_tex(tex, soup))
    for paragraph in soup.find_all("span", class_="paragraph"):
        paragraph.name = "p"
        del paragraph["class"]
    for unknown in soup.find_all(re.compile(r"^marimo-")):
        out.warnings.append(f"no blog version of <{unknown.name}>; its content is shown without interaction")
        unknown.unwrap()

    out.html = str(soup)
    return out


def text_of(html: str) -> str:
    """Visible text of an HTML fragment (for comparisons)."""
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
