#!/usr/bin/env python3
"""Build data/operations.csv from the run results (one row per amending operation).

  python3 -I scripts/build_operations_csv.py data/raw/run-lfss2026.json.gz \
      data/raw/run-lf2026.json.gz --slice data/raw/slice.json --out data/operations.csv

A row is an elementary operation parsed from an amending instruction (provisions that
amend no other text, such as entry-into-force clauses, are not listed). The status is
the result of executing the instruction on the LEGI version preceding the version that
LEGI links to the law. "non analysé" means the row was not reviewed by hand: it is
not a finding and not an anomaly.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

LAW = {"LFSS2026": "LFSS 2026 (loi n° 2025-1403)", "LF2026": "LF 2026 (loi n° 2026-103)"}

STATUS = {
    "OK": "exécutée telle quelle",
    "OK_UNLINKED": "exécutée ; la version LEGI correspondante n'a pas de lien vers la loi",
    "DEFERRED": "rattachée à une version LEGI d'une autre date",
    "ARTICLE_ABROGATED": "abrogation confirmée par LEGI",
    "ARTICLE_NOT_IN_LEGI": "hors périmètre : article absent de l'extraction LEGI utilisée",
    "TARGET_UNRESOLVED": "cible non résolue par l'analyseur",
    "SCOPE_UNRESOLVED": "subdivision non résolue par l'analyseur",
    "UNPARSED": "instruction non reconnue par l'analyseur",
    "UNSUPPORTED": "construction non prise en charge par l'analyseur",
    "NOT_ASSIGNED": "aucune version LEGI rattachée à cet article de la loi",
    "NO_DILA_VERSION": "aucune version LEGI rattachée à la loi",
    "RETABLIR_EXISTS": "rétablissement : la subdivision existe déjà",
    "NOT_FOUND": "mots cités introuvables",
    "NOT_FOUND (per subdivision)": "mots cités introuvables dans une subdivision",
}

# (law, seq) -> finding code (see data/findings.csv)
FINDINGS = {
    ("LF2026", 226): "A2",
    ("LF2026", 864): "A7", ("LF2026", 976): "A7",
    ("LFSS2026", 520): "A8", ("LFSS2026", 523): "A8", ("LFSS2026", 530): "A8",
    ("LFSS2026", 521): "D1",
    ("LFSS2026", 103): "B1", ("LFSS2026", 104): "B1",
    ("LFSS2026", 351): "B3", ("LFSS2026", 352): "B3",
    ("LF2026", 1257): "B2, B4",
    ("LFSS2026", 230): "B4",
    ("LF2026", 563): "B4", ("LF2026", 564): "B4",
    ("LF2026", 1446): "A3", ("LF2026", 1447): "A3",
    ("LFSS2026", 568): "A5",
}
A6 = ("LF2026", "81", "V")  # code name misspelt in the law: the parser cannot resolve the target


def status_fr(raw: str) -> str:
    parts = raw.split("|")
    head = parts[0]
    if head.startswith("COUNT_MISMATCH:"):
        label = f"nombre d'occurrences différent de celui attendu ({head.split(':', 1)[1]})"
    else:
        label = STATUS.get(head, head)
    if "BASE_OK" in parts[1:]:
        label += " ; exécutable sur le texte d'avant les instructions précédentes du même article"
    return label


def load(path: Path):
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as fh:
        return json.load(fh)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("results", nargs="+", type=Path)
    ap.add_argument("--slice", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    sl = {(x["law"], x["seq"]) for x in load(a.slice)} if a.slice else set()
    rows = []
    for path in a.results:
        res = load(path)
        step_of = {}
        for st in res["steps"]:
            for s in st.get("ops", []):
                step_of[s] = st
        for o in res["ops"]:
            if o["status"] in ("AUTONOMOUS", "CONTEXT"):
                continue
            t = o["target"]
            st = step_of.get(o["seq"])
            key = (o["law"], o["seq"])
            finding = FINDINGS.get(key, "")
            if not finding and (o["law"], o["article"]) == A6[:2] and o["path"].startswith(A6[2] + " "):
                finding = "A6"
            if finding:
                review = "constat " + finding
            elif key in sl:
                review = "revue manuelle (échantillon)"
            elif o["status"] in ("OK", "ARTICLE_ABROGATED") and (not st or st["result"] in ("EQUAL", "CREATED", "EQUAL_UNLINKED")):
                review = "conforme à LEGI"
            else:
                review = "non analysé"
            rows.append({
                "loi": LAW.get(o["law"], o["law"]),
                "article_loi": o["article"],
                "subdivision": o["path"],
                "texte_cible": t.get("code") or t.get("text") or "",
                "article_cible": t.get("article") or "",
                "operation": o["kind"],
                "statut_code": o["status"],
                "statut": status_fr(o["status"]),
                "comparaison_legi": (st["result"] + " " + (st.get("debut") or "")).strip() if st else "",
                "version_legi": (st.get("version") or "") if st else "",
                "revue": review,
                "detail": (o.get("detail") or "").replace("\n", " "),
            })
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(len(rows), "rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
