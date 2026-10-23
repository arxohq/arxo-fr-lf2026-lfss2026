#!/usr/bin/env python3
"""Versions « à venir » after the law: do they carry the law's change?

For every operation executed OK into DILA version V (start d), every later
version W of the same article (start > d, not MODIFIE_MORT_NE) is checked for
the words the operation inserted. A version that lacks them, while V has them,
is reported; GAP when a still later version has them again (the change was
lost in one future version only), LOST when no later version has them (the
change disappears from the consolidation on that date: either a later
instruction removed it, which is checked against the law's own operations, or
the future version was built before the law and not rebuilt).

  future_check.py --db legi.sqlite --results run.json --out future.json
"""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import execute as X

ap = argparse.ArgumentParser()
ap.add_argument("--db", required=True); ap.add_argument("--results", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
legi = X.Legi(Path(a.db)); res = json.load(open(a.results, encoding="utf-8"))
out = []
cache = {}
def text(vid):
    if vid not in cache:
        cache[vid] = X.cmp_form(" ".join(X.proj(legi.lines(vid))))
    return cache[vid]
for o in res["ops"]:
    if not o["status"].startswith("OK") or not o.get("version") or o["kind"] not in ("insert_after", "insert_before", "replace", "complete", "complete_phrase", "rewrite", "prepend"):
        continue
    y = X.cmp_form(X.norm(o.get("y") or ""))
    if len(y) < 12:
        continue
    row = legi.db.execute("select text, num, debut from articles where id=?", (o["version"],)).fetchone()
    if not row:
        continue
    tid, num, d = row
    if y not in text(o["version"]):
        continue
    later = [v for v in legi.versions(tid, num) if v["debut"] > d and "MORT_NE" not in v["etat"]]
    flags = [(v["id"], v["debut"], v["fin"], v["etat"], y in text(v["id"])) for v in later]
    for i, (vid, deb, fin, etat, has) in enumerate(flags):
        if not has:
            again = any(f[4] for f in flags[i + 1:])
            out.append({"law_article": o["article"], "path": o["path"], "text": tid, "article": num, "inserted": o["y"],
                        "version_with": o["version"], "since": d, "version_without": vid, "from": deb, "to": fin, "etat": etat,
                        "class": "GAP" if again else "LOST", "source": o["source"]})
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
for r in out:
    print(r["class"], r["law_article"], r["path"], r["article"], r["version_without"], r["from"], "->", r["to"], r["etat"], "|", r["inserted"][:70])
print(len(out))
