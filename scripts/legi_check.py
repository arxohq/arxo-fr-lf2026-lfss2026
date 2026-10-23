"""Check current LEGI versions for findings A2, B1-B3 (read-only on a legi.sqlite).

Usage: python3 -I legi_check.py <legi.sqlite> <out.json>
"""
import hashlib
import html
import json
import re
import sqlite3
import sys
import zlib

CGI = "LEGITEXT000006069577"
CSS = "LEGITEXT000006073189"

CHECKS = [
    # (finding, text, num, LEGIARTI or None for all versions, defect present?, expected-text probe)
    ("A2", CGI, "199 sexdecies", None,
     "mentionnés au 16° du II du même II", "mentionnés au 16° du même II"),
    ("B1", CSS, "L136-4", None,
     "bénéfices déterminés articles 50-0", "bénéfices déterminés aux articles 50-0"),
    ("B1b", CSS, "L136-4", None, "définiaux", "défini aux"),
    ("B2", CGI, "1600", None,
     None, "et l'établissement public du commerce et de l'industrie de Corse"),
    ("B3", CSS, "L162-23-8", None,
     "La part prévue au 2° du I de l'article L. 162-23, affectée à la", None),
]


def body(xml):
    m = re.search(r"<BLOC_TEXTUEL>\s*<CONTENU>(.*?)</CONTENU>", xml, re.S)
    s = m.group(1) if m else ""
    s = re.sub(r"<br\s*/?>", "\n", s)
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", s)


def links(xml):
    out = []
    liens = xml.split("<LIENS>", 1)[-1] if "<LIENS>" in xml else ""
    for t, label in re.findall(r"(<LIEN\b[^>]*>)(.*?)</LIEN>", liens, re.S):
        a = dict(re.findall(r'(\w+)="([^"]*)"', t))
        if a.get("typelien") in ("MODIFIE", "CREE", "MODIFICATION", "CREATION") or a.get("sens") == "cible":
            out.append({k: html.unescape(a.get(k, "")) for k in ("typelien", "sens", "cidtexte", "numtexte", "datesignatexte", "num")})
    return out


def main(dbp, out):
    db = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    last = db.execute("select name, sha256 from archives order by name desc limit 1").fetchone()
    res = {"legi_last_archive_in_db": last, "checks": []}
    for code, text, num, _, bad, good in CHECKS:
        rows = db.execute(
            "select a.id, a.etat, a.debut, a.fin, f.xml, f.sha256 from articles a join files f on f.id=a.id "
            "where a.text=? and a.num=? and a.fin>='2026-01-01' order by a.debut", (text, num)).fetchall()
        for ident, etat, debut, fin, blob, sha in rows:
            xml = zlib.decompress(blob).decode("utf-8", "replace")
            b = body(xml)
            flat = " ".join(b.split())
            res["checks"].append({
                "finding": code, "num": num, "id": ident, "etat": etat, "debut": debut, "fin": fin,
                "xml_sha256": sha,
                "defect_present": (bad in flat) if bad else None,
                "expected_present": (good in flat) if good else None,
                "liens_modifie": [l for l in links(xml) if l["typelien"] in ("MODIFIE", "CREE")][:12],
            })
    json.dump(res, open(out, "w"), ensure_ascii=False, indent=1)
    for c in res["checks"]:
        print(c["finding"], c["num"], c["id"], c["etat"], c["debut"], c["fin"],
              "defect" if c["defect_present"] else ("no-defect" if c["defect_present"] is False else "-"),
              "expected" if c["expected_present"] else ("no-expected" if c["expected_present"] is False else "-"))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
