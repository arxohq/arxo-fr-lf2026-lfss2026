#!/usr/bin/env python3
"""A JORF text (loi, décision) as published: articles in structure order.

Input: one or more extracted JORF increments (directories holding
jorf/global/...). The latest file for a path wins (increments are passed in
name order). Output JSON: text metadata, and for every article its number,
JORFARTI id, section trail, alinéas and sha256 of the XML bytes.

  jorf_text.py --text JORFTEXT000053508155 --out lf2026.json <inc-dir>...
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xmltext import attrs, body, first  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("dirs", nargs="+", type=Path)
    a = ap.parse_args()
    struct: Path | None = None
    version: Path | None = None
    arts: dict[str, Path] = {}
    sects: dict[str, Path] = {}
    for d in a.dirs:
        for p in d.rglob("*.xml"):
            s = p.as_posix()
            stem = p.name[:-4]
            if stem == a.text and "/texte/struct/" in s:
                struct = p
            elif stem == a.text and "/texte/version/" in s:
                version = p
            elif "/article/" in s and stem.startswith("JORFARTI"):
                arts[stem] = p
            elif "/section_ta/" in s and stem.startswith("JORFSCTA"):
                sects[stem] = p
    if struct is None or version is None:
        raise SystemExit(f"{a.text}: struct or version missing")
    vx = version.read_text(encoding="utf-8")
    out_articles: list[dict] = []
    problems: list[str] = []

    def walk(xml: str, trail: list[str]) -> None:
        for tag, title in re.findall(r"(<LIEN_SECTION_TA\b[^>]*>|<LIEN_ART\b[^>]*/>)([^<]*)", xml):
            row = attrs(tag)
            if tag.startswith("<LIEN_SECTION_TA"):
                name = " ".join(title.split())
                p = sects.get(row["id"])
                if p is None:
                    problems.append(f"section without file: {row['id']} {name}")
                    continue
                inner = p.read_text(encoding="utf-8")
                inner = inner.split("<STRUCTURE_TA>", 1)[-1].split("</STRUCTURE_TA>", 1)[0]
                walk(inner, trail + [name])
            else:
                p = arts.get(row["id"])
                if p is None:
                    problems.append(f"article without file: {row['id']} {row.get('num')}")
                    continue
                raw = p.read_bytes()
                x = raw.decode("utf-8")
                out_articles.append({
                    "num": row.get("num", ""), "id": row["id"], "trail": trail,
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "lines": body(x),
                })

    sx = struct.read_text(encoding="utf-8")
    walk(sx.split("<STRUCT>", 1)[-1].split("</STRUCT>", 1)[0], [])
    doc = {
        "text": a.text,
        "titre": first(vx, "TITREFULL"),
        "nor": first(vx, "NOR"),
        "date_publi": first(vx, "DATE_PUBLI"),
        "date_texte": first(vx, "DATE_TEXTE"),
        "struct_sha256": hashlib.sha256(struct.read_bytes()).hexdigest(),
        "version_sha256": hashlib.sha256(version.read_bytes()).hexdigest(),
        "visas": body(vx, "VISAS"),
        "signataires": body(vx, "SIGNATAIRES"),
        "problems": problems,
        "articles": out_articles,
    }
    a.out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{a.text}: {len(out_articles)} articles, "
          f"{sum(len(x['lines']) for x in out_articles)} alinéas, problems {len(problems)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
