#!/usr/bin/env python3
"""Reference integrity around an amending law, over LEGI.

(a) outgoing: every « article X » named in text the law inserts (quoted words,
    blocks, new articles) must exist on the date the inserted text applies:
    a version with debut <= D < fin, in the code the reference names (or the
    code being amended). A reference to an article that only has a version
    starting after D is a forward reference, not a dangling one.
(b) incoming: every article the law abrogates or renumbers must not still be
    named, on the abrogation date, by an article in force of the same code
    (or by an article of another code naming that code).

  refs.py --db legi.sqlite --results results.json --ops ops.json --out refs.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import zlib
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execute as X  # noqa: E402
import fr_legistics as FL  # noqa: E402
import run as R  # noqa: E402

REF = re.compile(r"\barticles?\s+((?:" + FL.ART_NUM + r")(?:\s*(?:,|et|à|ou)\s*(?:" + FL.ART_NUM + r"))*)"
                 r"(?P<tail>(?:\s+(?:du|de\s+la|de\s+l')\s+(?:présent|même)\s+code|\s+du\s+(?:code|livre\s+des\s+procédures\s+fiscales)[^,;.)]*|\s+de\s+la\s+loi\b|\s+de\s+l'ordonnance\b|\s+du\s+décret\b|\s+de\s+la\s+(?:présente\s+)?loi|\s+du\s+règlement|\s+de\s+la\s+directive|\s+du\s+traité|\s+de\s+la\s+Constitution|\s+de\s+l'annexe|\s+(?:de\s+l')?annexe)?)", re.I)


def split_nums(s: str) -> list[tuple[str, bool]]:
    """'L. 1, L. 2 et L. 3' -> [(L1,False)...]; 'à' ranges keep both ends."""
    toks = re.split(r"\s*(?:,|\bet\b|\bou\b)\s*", s)
    out = []
    for t in toks:
        if " à " in t:
            a, b = t.split(" à ", 1)
            out += [(FL.norm_art(a), True), (FL.norm_art(b), True)]
        elif t.strip():
            out.append((FL.norm_art(t), False))
    return out


def in_force(versions: list[dict], d: str) -> list[dict]:
    return [v for v in versions if v["debut"] <= d < v["fin"]]


def outgoing(legi: X.Legi, ops: list[dict], results: dict, law_date: str) -> list[dict]:
    dates = {}
    for r in results["ops"]:
        if r.get("version"):
            row = legi.db.execute("select debut from articles where id=?", (r["version"],)).fetchone()
            if row:
                dates[r["seq"]] = row[0]
    out = []
    for r in results["ops"]:
        texts = []
        if r.get("y") and r["kind"] not in ("renumber", "move"):
            texts.append(r["y"])
        if r.get("block"):
            texts.extend(r["block"])
        if not texts or r["kind"] in ("autonomous", "context", "unparsed"):
            continue
        tid = r.get("text_id")
        d = dates.get(r["seq"], law_date)
        for t in texts:
            for m in REF.finditer(t):
                tail = (m.group("tail") or "").strip()
                if tail and not re.search(r"(?:présent|même)\s+code", tail) and not tail.lower().startswith("du code") and not tail.lower().startswith("du livre"):
                    continue  # another kind of text: not checked
                code_tid = tid
                if tail.lower().startswith(("du code", "du livre")):
                    code_tid = legi.text_id({"code": FL.code_key(tail[3:])})
                if code_tid is None or not code_tid.startswith("LEGITEXT"):
                    continue
                for num, ranged in split_nums(m.group(1)):
                    vers = []
                    for cand in R.article_candidates(num):
                        vers = legi.versions(code_tid, cand)
                        if vers:
                            break
                    now = in_force(vers, d)
                    if now:
                        continue
                    later = [v for v in vers if v["debut"] > d]
                    status = "FORWARD" if later else ("ABROGATED_BEFORE" if vers else "NEVER_IN_LEGI")
                    # the law itself may create it in the same op (new article block)
                    if status == "NEVER_IN_LEGI" and r["kind"] == "create_article" and num in [FL.norm_art(x) for x in re.split(r"\s*,\s*|\s+et\s+|\s+à\s+", r.get("y") or "")]:
                        continue
                    out.append({"seq": r["seq"], "law_article": r["article"], "path": r["path"],
                                "target": r["target"].get("article"), "code": code_tid, "ref": num,
                                "date": d, "status": status,
                                "versions": [(v["id"], v["debut"], v["fin"], v["etat"]) for v in vers][-3:],
                                "context": t[max(0, m.start() - 80):m.end() + 60]})
    return out


def code_name_rx(legi: X.Legi, tid: str) -> str:
    names = [k for k, v in legi.codes().items() if v == tid]
    return names[0] if names else ""


def incoming(legi: X.Legi, results: dict) -> list[dict]:
    gone = []
    for r in results["ops"]:
        if r["status"] == "ARTICLE_ABROGATED" and r.get("text_id"):
            vid = r.get("version")
            row = legi.db.execute("select fin from articles where id=?", (vid,)).fetchone() if vid else None
            gone.append((r["text_id"], r["target"]["article"], row[0] if row else None, r["seq"], r["article"], "abrogated"))
    out = []
    cache: dict[tuple, list] = {}
    for tid, num, d, seq, lart, why in gone:
        if not d or d >= "2999":
            continue
        disp = num
        m = re.match(r"^(LO|L|R|D|A)(\d.*)$", num)
        pat = (re.escape(m.group(1)) + r"\.?\s*" + re.escape(m.group(2))) if m else re.escape(num).replace(r"\ ", r"\s+")
        rx = re.compile(r"(?<![\w-])" + pat + r"(?![\w-]|\s+(?:" + "|".join(FL.SUFFIXES) + r")\b|\s+[A-Z]\b)")
        name = code_name_rx(legi, tid)
        key = (tid, d)
        if key not in cache:
            rows = legi.db.execute("select a.id, a.num, f.xml from articles a join files f on f.id=a.id and f.kind='article' "
                                   "where a.text=? and a.debut<=? and a.fin>?", (tid, d, d)).fetchall()
            cache[key] = [(i, n, zlib.decompress(x).decode("utf-8")) for i, n, x in rows]
        for aid, anum, xml in cache[key]:
            if anum == num:
                continue
            body = " ".join(X.xml_body(xml))
            for mm in rx.finditer(body):
                before = body[max(0, mm.start() - 120):mm.start()]
                after = body[mm.end():mm.end() + 90]
                if not re.search(r"articles?\b", before, re.I):
                    continue
                other = re.match(r"^[^.;]{0,40}?\b(?:du|de\s+la|de\s+l')\s+(code|loi|ordonnance|décret|livre)\b(?!\s+des\s+procédures\s+fiscales)", after)
                if other and not re.match(r"^[^.;]{0,40}?\bdu\s+(?:présent|même)\s+code", after):
                    if name and name not in after.lower():
                        continue
                if re.search(r"dans\s+sa\s+rédaction\s+antérieure|en\s+vigueur\s+avant|dans\s+leur\s+rédaction\s+antérieure", after + before[-60:]):
                    status = "HISTORICAL_REFERENCE"
                else:
                    status = "DANGLING"
                out.append({"seq": seq, "law_article": lart, "gone": num, "code": tid, "date": d, "why": why,
                            "citing": anum, "citing_version": aid, "status": status,
                            "context": before[-90:] + "⟦" + mm.group(0) + "⟧" + after[:80]})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--results", type=Path, required=True)
    ap.add_argument("--law-date", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    legi = X.Legi(a.db)
    res = json.load(open(a.results, encoding="utf-8"))
    o = outgoing(legi, res["ops"], res, a.law_date)
    i = incoming(legi, res)
    json.dump({"outgoing": o, "incoming": i}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print("outgoing:", dict(Counter(x["status"] for x in o)), "incoming:", dict(Counter(x["status"] for x in i)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
