#!/usr/bin/env python3
"""A bill or adopted text of the Assemblée nationale as alinéas per article.

Input: the « .raw » HTML of an AN document (https://www.assemblee-nationale.fr/
dyn/docs/<ID>.raw), e.g. PRJLANR5L17B3210 (PLF 2027) or a « texte adopté ».
Output: the same JSON shape as jorf_text.py (articles: num, lines, sha256),
so that fr_legistics.py and execute.py run on a bill exactly as on a
published law. Article numbers are the bill's (« 3 », « 8 quinquies »).

  an_text.py --out plf2027.json PRJLANR5L17B3210.raw
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
import unicodedata
from pathlib import Path

HEAD = re.compile(r"^Article\s+(liminaire|1er|\d+(?:\s+(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|[A-Z]))*)\s*(?:\((?:nouveau|Supprimé|Non modifié|Conforme)\))?$", re.I)


def clean(s: str) -> str:
    s = html.unescape(s).replace(" ", " ").replace(" ", " ").replace("’", "'").replace("‑", "-")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"(?<=\w)\s+-\s+(?=\d)", "-", s)        # « L. 722 ‑ 1 » -> « L. 722-1 »
    s = re.sub(r"\b(\d+|I) (er|re)\b", r"\1\2", s)      # « 1 er » -> « 1er »
    return s


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("raw", type=Path)
    a = ap.parse_args()
    raw = a.raw.read_bytes()
    s = raw.decode("utf-8", "replace")
    s = re.sub(r"(?is)<(style|script|head)\b.*?</\1>", " ", s)
    s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</h\d>|</li>", "\n", s)
    s = re.sub(r"(?i)</td>", " | ", s)
    s = re.sub(r"(?i)</tr>", "\n", s)
    text = re.sub(r"<[^>]+>", " ", s)
    lines = [clean(x) for x in text.split("\n")]
    lines = [x for x in lines if x]
    arts: list[dict] = []
    cur = None
    for line in lines:
        m = HEAD.match(line)
        if m:
            cur = {"num": m.group(1), "lines": []}
            arts.append(cur)
            continue
        if cur is None:
            continue
        if re.match(r"^(?:Délibéré en séance publique|Vu pour être annexé|La Présidente|Le Président)", line):
            cur = None
            continue
        cur["lines"].append(line)
    for art in arts:
        art["sha256"] = hashlib.sha256("\n".join(art["lines"]).encode("utf-8")).hexdigest()
        art["id"] = f"{a.raw.stem}#{art['num']}"
    doc = {"text": a.raw.stem, "source_sha256": hashlib.sha256(raw).hexdigest(), "articles": arts}
    a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{a.raw.name}: {len(arts)} articles, {sum(len(x['lines']) for x in arts)} alinéas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
