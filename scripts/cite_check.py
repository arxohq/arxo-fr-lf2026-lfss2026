#!/usr/bin/env python3
"""Citations of other texts inside a law: number, date and title must agree.

Every « loi n° N du D <intitulé> », « ordonnance n° N du D … », « décret n° N
du D … » in the published law (including the quoted text it inserts) is
looked up by its number in the LEGI registry of texts (texte/version:
NUM, TITREFULL). Reported:

  DATE_MISMATCH   the cited date is not the date of the text with that number;
  TITLE_MISMATCH  the cited title words are not the beginning of its title;
  SELF            the citation names the citing law itself (number of the law);
  NOT_IN_LEGI     no text with that number in LEGI (not consolidated, or a typo).

  cite_check.py --db legi.sqlite --law law.json --self-num 2025-1403 --out cites.json
"""
from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

CITE = re.compile(r"\b(loi(?:\s+organique)?|ordonnance|décret)\s+n°\s*([\d-]+)\s+du\s+(\d{1,2}(?:er)?\s+\w+\s+\d{4})"
                  r"(?P<title>\s+(?:de\s+finances|de\s+financement|relative?s?|portant|pour|visant|instituant|modifiant|tendant|d'|de|sur|en\s+faveur|prise|ratifiant|habilitant|concernant|expérimentant|améliorant|d'urgence)\b[^,;:»()]*)?", re.I)


def fold(s: str) -> str:
    s = s.replace("’", "'").replace(" ", " ").replace("œ", "oe")
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--law", type=Path, required=True)
    ap.add_argument("--self-num", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    db = sqlite3.connect(a.db)
    law = json.load(open(a.law, encoding="utf-8"))
    rows = []
    for art in law["articles"]:
        for i, line in enumerate(art["lines"]):
            for m in CITE.finditer(line):
                nature, num, date = m.group(1), m.group(2), m.group(3)
                title = (m.group("title") or "").strip()
                reg = db.execute("select text, nature, titre from textnums where num=?", (num,)).fetchall()
                reg = [r for r in reg if fold(r[1])[:3] == fold(nature)[:3]] or reg
                st, detail = "OK", ""
                if num == a.self_num:
                    st = "SELF"
                if not reg:
                    st = "NOT_IN_LEGI" if st == "OK" else st
                else:
                    t = fold(reg[0][2])
                    if fold(date) not in t:
                        st, detail = "DATE_MISMATCH", reg[0][2]
                    elif title:
                        after = t.split(fold(date), 1)[-1].strip()
                        if not after.startswith(fold(title)[:max(12, min(len(fold(title)), 40))]):
                            st, detail = "TITLE_MISMATCH", reg[0][2]
                    if st == "OK" and num == a.self_num:
                        st = "SELF"
                rows.append({"article": art["num"], "line": i, "cite": m.group(0), "num": num, "date": date,
                             "title": title, "status": st, "registry": detail or (reg[0][2] if reg else ""),
                             "context": line[max(0, m.start() - 160):m.end() + 40]})
    json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(dict(Counter(r["status"] for r in rows)))
    for r in rows:
        if r["status"] not in ("OK", "NOT_IN_LEGI"):
            print(r["status"], "art", r["article"], "|", r["cite"], "| registry:", r["registry"][:120])
    return 0


if __name__ == "__main__":
    sys.exit(main())
