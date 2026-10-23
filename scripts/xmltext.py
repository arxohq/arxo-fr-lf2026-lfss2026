"""Rendering of DILA XML bodies (JORF and LEGI) into alinéas.

One alinéa per line. DILA puts a JORF article into one <p> with <br/>
separators, a LEGI article into one <p> per alinéa or into bare text with
<br/>; tables are rendered row by row, cells joined by " | ". The same
renderer is used for both sides, so that a comparison of an amended LEGI
version with the consolidation never depends on markup.
"""
from __future__ import annotations

import html
import re
import unicodedata

ATTR = re.compile(r'(\w+)="([^"]*)"')


def attrs(tag: str) -> dict[str, str]:
    return {k: html.unescape(v) for k, v in ATTR.findall(tag)}


def clean(fragment: str) -> str:
    text = re.sub(r"<[^>]+>", "", fragment)
    text = html.unescape(text).replace("\xa0", " ").replace(" ", " ")
    text = unicodedata.normalize("NFC", text)
    return " ".join(text.split())


def lines(block: str) -> list[str]:
    """Alinéas of a CONTENU block, in document order."""
    out: list[str] = []
    pos = 0
    for m in re.finditer(r"<table\b.*?</table>", block, re.S | re.I):
        out.extend(_flow(block[pos:m.start()]))
        for row in re.findall(r"<tr\b.*?</tr>", m.group(0), re.S | re.I):
            cells = [clean(c) for c in re.findall(r"<t[hd]\b.*?</t[hd]>", row, re.S | re.I)]
            if any(cells):
                out.append("| " + " | ".join(cells) + " |")
        pos = m.end()
    out.extend(_flow(block[pos:]))
    return out


def _flow(segment: str) -> list[str]:
    parts = re.split(r"<br\s*/?>|</?p\b[^>]*>|</?div\b[^>]*>", segment, flags=re.I)
    return [t for t in (clean(p) for p in parts) if t]


def body(xml: str, tag: str = "BLOC_TEXTUEL") -> list[str]:
    m = re.search(rf"<{tag}>\s*<CONTENU>(.*?)</CONTENU>", xml, re.S)
    return lines(m.group(1)) if m else []


def first(xml: str, tag: str) -> str:
    m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.S)
    return html.unescape(m.group(1)).strip() if m else ""
