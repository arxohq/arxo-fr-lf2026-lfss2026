#!/usr/bin/env python3
"""Provisions struck down by the Conseil constitutionnel vs. the consolidation.

Input: the decision as published (dispositif « Sont contraires à la
Constitution les dispositions suivantes … »), the law as published in JORF
and the LEGI store. For each censured provision:

  * JORF: the published law must carry the bracket « [Dispositions déclarées
    non conformes …] » in its place (whole article) or omit it;
  * LEGI: list the code versions DILA attributes to that law article
    (LIEN cible), with the subdivision of the law article named in the link
    label when DILA states it (« art. 60 (V) », « art. 60 (VT) »). A whole
    censured article must have none; for a partly censured article each
    linked version is shown for a check by hand against the surviving text.

  cc_check.py --db legi.sqlite --decision cc.json --law law.json --law-cid … --out cc.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execute as X  # noqa: E402


def dispositif(dec: dict) -> list[str]:
    lines = [l for a in dec["articles"] for l in a["lines"]]
    out, on = [], False
    for l in lines:
        if l.startswith("Sont contraires à la Constitution"):
            on = True
            continue
        if on:
            if not l.startswith("-"):
                break
            out.append(l.lstrip("- ").rstrip(" ;."))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--decision", type=Path, required=True)
    ap.add_argument("--law", type=Path, required=True)
    ap.add_argument("--law-cid", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    legi = X.Legi(a.db)
    dec = json.load(open(a.decision, encoding="utf-8"))
    law = json.load(open(a.law, encoding="utf-8"))
    arts = {x["num"]: x for x in law["articles"] if x["num"]}
    rows = []
    for item in dispositif(dec):
        m = re.search(r"(?:de\s+)?l'article\s+(\d+)\s*$", item)
        if not m:
            rows.append({"item": item, "status": "UNPARSED"})
            continue
        num = m.group(1)
        whole = bool(re.fullmatch(r"l'article\s+\d+", item))
        jorf = arts.get(num, {}).get("lines", [])
        brackets = [l for l in jorf if "non conformes à la Constitution" in l]
        linked = legi.db.execute(
            "select a.id, a.text, a.num, a.debut, a.fin, a.etat, l.typelien, l.label from links l join articles a on a.id=l.id "
            "where l.cid=? and l.sens='cible' and l.num=?", (a.law_cid, num)).fetchall()
        rows.append({
            "item": item, "law_article": num, "whole": whole,
            "jorf_brackets": brackets, "jorf_lines": len(jorf),
            "legi_linked": [dict(zip(("id", "text", "num", "debut", "fin", "etat", "type", "label"), r)) for r in linked],
            "status": ("CONSOLIDATED_DESPITE_CENSURE" if whole and linked else
                       "OK_NOT_CONSOLIDATED" if whole else "CHECK_BY_HAND" if linked else "OK_NO_LINK"),
        })
    json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for r in rows:
        print(r["status"], "|", r["item"], "|", len(r.get("legi_linked", [])), "linked;", len(r.get("jorf_brackets", [])), "brackets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
