"""ODT -> Markdown converter for the RAG pipeline.

Only the Python standard library is used (zipfile + xml.etree.ElementTree),
so no extra runtime dependency is introduced.

Conversion rules:
- Headings: ``<text:h>`` with an outline-level become ``#``/``##``/``###``.
  Heuristic fallback: bold, short, single-line paragraphs without trailing
  punctuation are treated as headings.
- Lists: ``text:list`` whose style name contains ``Number`` -> ``1.`` else ``-``.
- Tables: rendered as Markdown tables.
- Monospace font runs -> fenced code blocks.
- Images, formulas, headers/footers and footnotes are ignored.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
NS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_FO = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"

NS = {
    "office": NS_OFFICE,
    "style": NS_STYLE,
    "text": NS_TEXT,
    "table": NS_TABLE,
    "fo": NS_FO,
}


def q(prefix: str, local: str = "") -> str:
    """Build a ``{namespace}localname`` qualified tag."""
    if not local:
        local = prefix.split(":", 1)[1]
        prefix = prefix.split(":", 1)[0]
    return f"{{{NS[prefix]}}}{local}"


# --- Styles ---
def _para_props(style: ET.Element) -> dict:
    """Extract (font-size, font-weight, font-name) from text-properties."""
    out: dict = {}
    ts = style.find(q("style:text-properties"))
    if ts is None:
        return out
    fs = ts.get(q("fo:font-size"))
    fw = ts.get(q("fo:font-weight"))
    fn = ts.get(q("style:font-name"))
    if fs:
        out["size"] = fs
    if fw:
        out["weight"] = fw
    if fn:
        out["font"] = fn
    return out


def load_all_styles(zf: zipfile.ZipFile) -> dict[str, dict]:
    """Resolve style properties from styles.xml + content.xml with inheritance."""
    raw: dict[str, dict] = {}
    for member in ("styles.xml", "content.xml"):
        try:
            xml_bytes = zf.read(member)
        except KeyError:
            continue
        root = ET.fromstring(xml_bytes)
        for container_tag in (q("office:styles"), q("office:automatic-styles")):
            for container in root.iter(container_tag):
                for s in container.findall(q("style:style")):
                    name = s.get(q("style:name"))
                    if not name:
                        continue
                    raw[name] = {
                        "props": _para_props(s),
                        "parent": s.get(q("style:parent-style-name")),
                        "family": s.get(q("style:family")),
                        "outline": s.get(q("style:default-outline-level")),
                    }

    resolved: dict[str, dict] = {}

    def resolve(name: str | None, seen: set[str]) -> dict:
        if not name or name not in raw:
            return {}
        if name in resolved:
            return resolved[name]
        if name in seen:
            return dict(raw[name]["props"])
        seen.add(name)
        node = raw[name]
        merged = dict(resolve(node["parent"], seen))
        merged.update(node["props"])
        merged["family"] = node["family"]
        if node["outline"]:
            merged["outline"] = node["outline"]
        resolved[name] = merged
        return merged

    for nm in raw:
        resolve(nm, set())
    return resolved


_MONO_FONTS = (
    "Courier",
    "Consolas",
    "Monaco",
    "Menlo",
    "Liberation Mono",
    "Hack",
    "Source Code Pro",
)


def is_mono(props: dict | None) -> bool:
    if not props:
        return False
    font = (props.get("font") or "").lower()
    return any(m.lower() in font for m in _MONO_FONTS)


def parse_pt(s: str | None) -> float:
    if not s:
        return 0.0
    m = re.match(r"([0-9.]+)\s*pt", s)
    return float(m.group(1)) if m else 0.0


# --- Text extraction ---
_INVISIBLE_RE = re.compile(r"[\u200b\ufeff]")


def _clean(text: str) -> str:
    return _INVISIBLE_RE.sub(" ", text).replace("\xa0", " ").strip()


def _node_text(el: ET.Element) -> str:
    """Recursively collect text: line-break->\\n, tab->\\t, text:s->spaces."""
    parts: list[str] = []
    if el.text:
        parts.append(el.text)
    for child in el:
        tag = child.tag
        if tag == q("text:line-break"):
            parts.append("\n")
        elif tag == q("text:tab"):
            parts.append("\t")
        elif tag == q("text:s"):
            c = child.get(q("text:c"))
            try:
                n = int(c) if c else 1
            except ValueError:
                n = 1
            parts.append(" " * n)
        elif tag in (
            q("text:soft-page-break"),
            q("text:bookmark"),
            q("text:bookmark-start"),
            q("text:bookmark-end"),
        ):
            pass
        else:
            parts.append(_node_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def paragraph_text(p: ET.Element) -> str:
    """Visible paragraph text preserving line breaks and tabs."""
    return _clean(_node_text(p))


def effective_props(p: ET.Element, styles: dict) -> dict:
    """Paragraph props: paragraph style + fallback to a lone span style."""
    sn = p.get(q("text:style-name"), "")
    props = dict(styles.get(sn, {}))
    if "weight" in props and "size" in props:
        return props
    spans = p.findall(q("text:span"))
    lead = (p.text or "").strip()
    if len(spans) == 1 and not lead:
        sp = styles.get(spans[0].get(q("text:style-name")) or "", {})
        for k in ("weight", "size", "font"):
            if k in sp and k not in props:
                props[k] = sp[k]
    return props


# --- Lists ---
def emit_list(lst: ET.Element, styles: dict, level: int = 0) -> list[str]:
    style_name = lst.get(q("text:style-name"), "")
    is_ordered = "Number" in style_name
    indent = "  " * level
    out: list[str] = []
    counter = 1
    for item in lst.findall(q("text:list-item")):
        emitted = False
        for child in list(item):
            tag = child.tag
            if tag in (q("text:p"), q("text:h")):
                txt = paragraph_text(child)
                if not txt:
                    continue
                marker = f"{counter}." if is_ordered else "-"
                lines = [ln.strip() for ln in txt.split("\n") if ln.strip()]
                for i, line in enumerate(lines):
                    if i == 0:
                        out.append(f"{indent}{marker} {line}")
                    else:
                        out.append(f"{indent}  {line}")
                emitted = True
            elif tag == q("text:list"):
                out.extend(emit_list(child, styles, level + 1))
        if emitted:
            counter += 1
    return out


# --- Tables ---
def _cell_text(cell: ET.Element) -> str:
    parts: list[str] = []
    for p in cell:
        if p.tag in (q("text:p"), q("text:h")):
            t = paragraph_text(p)
            if t:
                parts.append(t.replace("\n", " "))
    return _clean(" ".join(parts)).replace("|", "\\|")


def emit_table(tbl: ET.Element) -> list[str]:
    rows: list[list[str]] = []
    for tr in tbl.iter(q("table:table-row")):
        cells: list[str] = []
        for cell in tr:
            if cell.tag == q("table:table-cell"):
                cells.append(_cell_text(cell))
            elif cell.tag == q("table:covered-table-cell"):
                cells.append("")
        if cells:
            rows.append(cells)
    if not rows:
        return []
    width = max(len(r) for r in rows)
    rows = [r + [""] * (width - len(r)) for r in rows]
    header, *body = rows
    out = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(["---"] * width) + " |",
    ]
    out.extend("| " + " | ".join(r) + " |" for r in body)
    return out


# --- Bold + short paragraph -> heading ---
def _is_bold(weight: str | None) -> bool:
    if not weight:
        return False
    w = weight.strip().lower()
    if w in ("bold", "bolder"):
        return True
    try:
        return int(w) >= 600
    except ValueError:
        return False


def looks_like_heading(text: str, props: dict, base_size: float) -> tuple[bool, int]:
    """Bold, short, single-line, no trailing punctuation -> heading."""
    if not text:
        return False, 0
    if not _is_bold(props.get("weight")):
        return False, 0
    if "\n" in text or len(text) > 80:
        return False, 0
    if text[-1] in ".,;:!?":
        return False, 0
    size = parse_pt(props.get("size"))
    if size >= base_size * 1.5:
        return True, 1
    if size >= base_size * 1.25:
        return True, 2
    if size >= base_size or size == 0:
        return True, 3
    return False, 0


# --- Main conversion ---
def convert(odt_path: Path) -> str:
    with zipfile.ZipFile(odt_path) as zf:
        styles = load_all_styles(zf)
        content = zf.read("content.xml")
    root = ET.fromstring(content)
    body = root.find(q("office:body"))
    text_root = body.find(q("office:text")) if body is not None else None
    if text_root is None:
        return ""

    sizes = [
        parse_pt(p.get("size"))
        for p in styles.values()
        if p.get("size") and p.get("family") in (None, "paragraph")
    ]
    sizes = [s for s in sizes if s > 0]
    base_size = sorted(sizes)[len(sizes) // 2] if sizes else 12.0
    if base_size == 0:
        base_size = 12.0

    md: list[str] = []
    in_code = False
    code_buf: list[str] = []

    def flush_code() -> None:
        nonlocal in_code, code_buf
        if in_code and code_buf:
            md.append("```")
            md.extend(code_buf)
            md.append("```")
            md.append("")
        in_code = False
        code_buf = []

    def emit_heading(el: ET.Element) -> None:
        lvl_attr = el.get(q("text:outline-level"))
        if lvl_attr is None:
            sn = el.get(q("text:style-name"), "")
            lvl_attr = styles.get(sn, {}).get("outline")
        try:
            md_level = int(lvl_attr) if lvl_attr is not None else 1
        except (TypeError, ValueError):
            md_level = 1
        md_level = max(1, min(6, md_level))
        txt = paragraph_text(el)
        if txt:
            flush_code()
            md.append(f"{'#' * md_level} {txt}")
            md.append("")

    def emit_paragraph(el: ET.Element) -> None:
        nonlocal in_code, code_buf
        props = effective_props(el, styles)
        txt = paragraph_text(el)
        if not txt:
            return
        is_h, md_level = looks_like_heading(txt, props, base_size)
        if is_h:
            flush_code()
            md.append(f"{'#' * md_level} {txt}")
            md.append("")
            return
        if is_mono(props):
            if not in_code:
                in_code = True
                code_buf = []
            code_buf.append(txt)
            return
        flush_code()
        for line in txt.split("\n"):
            if line.strip():
                md.append(line)
        md.append("")

    def walk(elements) -> None:
        for el in elements:
            tag = el.tag
            if tag == q("text:h"):
                emit_heading(el)
            elif tag == q("text:p"):
                emit_paragraph(el)
            elif tag == q("text:list"):
                flush_code()
                items = emit_list(el, styles, level=0)
                if items:
                    md.extend(items)
                    md.append("")
            elif tag == q("table:table"):
                flush_code()
                md.extend(emit_table(el))
                md.append("")
            elif tag in (q("text:section"), q("office:text")):
                walk(list(el))

    walk(list(text_root))
    flush_code()
    while md and not md[-1].strip():
        md.pop()
    return "\n".join(md).rstrip() + "\n"
