#!/usr/bin/env python3
"""LEGI as a queryable store: the global dump overlaid by the increments.

One streaming pass per archive; archives are ingested in name order (the
global dump first). A file is keyed by its path below the text directory
(`LEGITEXT…/article/LEGI/ARTI/…/LEGIARTI….xml`): a later archive replaces
it, a `liste_suppression_legi.dat` line removes it. The tool carries no
semantics; it keeps bytes (zlib) and the metadata needed to find versions:

  files(key, text, kind, id, src, sha256, xml)
  articles(id, text, num, etat, debut, fin)          -- LEGIARTI only
  links(id, typelien, sens, cid, lid, num, numtexte, date, nature, label)
                                                      -- LIEN except CITATION
  archives(name, sha256, bytes, members, kept, suppressed)

  legi_index.py --db legi.sqlite ingest <archive.tar.gz>...
"""
from __future__ import annotations

import argparse
import hashlib
import os
import html
import re
import sqlite3
import sys
import tarfile
import zlib
from pathlib import Path

TEXT_DIR = re.compile(r"/((?:LEGI|JORF)TEXT\d{12})/(.*)$")
ATTR = re.compile(r'(\w+)="([^"]*)"')
SCHEMA = """
create table if not exists files(key text primary key, text text, kind text, id text,
  src text, sha256 text, xml blob);
create table if not exists articles(id text primary key, text text, num text, etat text,
  debut text, fin text);
create table if not exists links(id text, typelien text, sens text, cid text, lid text,
  num text, numtexte text, date text, nature text, label text);
create table if not exists archives(name text primary key, sha256 text, bytes integer,
  members integer, kept integer, suppressed integer);
"""


def key_of(name: str) -> tuple[str, str] | None:
    m = TEXT_DIR.search(name)
    if not m:
        return None
    return m.group(1), f"{m.group(1)}/{m.group(2)}"


def tag(xml: str, name: str) -> str:
    m = re.search(rf"<{name}>(.*?)</{name}>", xml, re.S)
    return m.group(1).strip() if m else ""


def drop(db: sqlite3.Connection, key: str) -> None:
    row = db.execute("select id, kind from files where key=?", (key,)).fetchone()
    if row is None:
        return
    db.execute("delete from files where key=?", (key,))
    if row[1] == "article":
        db.execute("delete from articles where id=?", (row[0],))
        db.execute("delete from links where id=?", (row[0],))


INDEXES = """
create index if not exists links_id on links(id);
create index if not exists links_cid on links(cid);
create index if not exists articles_text_num on articles(text, num);
create index if not exists files_id on files(id);
"""


def put(db: sqlite3.Connection, text: str, key: str, raw: bytes, src: str, fresh: bool = False) -> None:
    parts = key.split("/")
    kind = {"article": "article", "section_ta": "section", "texte": parts[2] if len(parts) > 2 else "texte"}.get(parts[1], parts[1])
    ident = parts[-1][:-4]
    if not fresh:
        drop(db, key)
    row = (key, text, kind, ident, src, hashlib.sha256(raw).hexdigest(), zlib.compress(raw, 6))
    try:
        db.execute("insert into files values(?,?,?,?,?,?,?)", row)
    except sqlite3.IntegrityError:
        # the same path under code_en_vigueur and code_non_vigueur: last one wins
        drop(db, key)
        db.execute("insert into files values(?,?,?,?,?,?,?)", row)
    if kind != "article":
        return
    xml = raw.decode("utf-8", "replace")
    db.execute("insert or replace into articles values(?,?,?,?,?,?)",
               (ident, text, html.unescape(tag(xml, "NUM")), tag(xml, "ETAT"),
                tag(xml, "DATE_DEBUT"), tag(xml, "DATE_FIN")))
    liens = xml.split("<LIENS>", 1)[-1] if "<LIENS>" in xml else ""
    for t, label in re.findall(r"(<LIEN\b[^>]*>)(.*?)</LIEN>", liens, re.S):
        a = {k: html.unescape(v) for k, v in ATTR.findall(t)}
        if a.get("typelien") == "CITATION":
            continue
        db.execute("insert into links values(?,?,?,?,?,?,?,?,?,?)",
                   (ident, a.get("typelien", ""), a.get("sens", ""), a.get("cidtexte", ""),
                    a.get("id", ""), a.get("num", ""), a.get("numtexte", ""),
                    a.get("datesignatexte", ""), a.get("naturetexte", ""),
                    " ".join(html.unescape(label).split())))


def ingest(db: sqlite3.Connection, path: Path) -> None:
    name = path.name
    if db.execute("select 1 from archives where name=?", (name,)).fetchone():
        print(f"{name}: already ingested")
        return
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    members = kept = suppressed = 0
    fresh = db.execute("select count(*) from archives").fetchone()[0] == 0 and name.startswith("Freemium")
    deferred: list[str] = []
    with tarfile.open(path, "r|gz") as tar:
        for m in tar:
            members += 1
            if not m.isfile():
                continue
            if m.name.endswith("liste_suppression_legi.dat"):
                deferred.extend(tar.extractfile(m).read().decode("utf-8", "replace").splitlines())
                continue
            if not m.name.endswith(".xml"):
                continue
            k = key_of(m.name)
            if k is None:
                continue
            put(db, k[0], k[1], tar.extractfile(m).read(), name, fresh)
            kept += 1
            if kept % 200000 == 0:
                print(f"  {name}: {kept}", flush=True)
                db.commit()
    for line in deferred:
        k = key_of(line.strip() + ".xml")
        if k:
            drop(db, k[1])
            suppressed += 1
    if fresh:
        db.executescript(INDEXES)
    db.execute("insert into archives values(?,?,?,?,?,?)",
               (name, digest.hexdigest(), path.stat().st_size, members, kept, suppressed))
    db.commit()
    print(f"{name}: members {members}, kept {kept}, suppressed {suppressed}", flush=True)


def ingest_dir(db: sqlite3.Connection, root: Path, name: str, sha: str, size: int) -> None:
    """The global dump extracted by `tar --include` (codes and text cards only)."""
    if db.execute("select 1 from archives where name=?", (name,)).fetchone():
        print(f"{name}: already ingested")
        return
    fresh = db.execute("select count(*) from archives").fetchone()[0] == 0
    kept = 0
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if not f.endswith(".xml"):
                continue
            full = os.path.join(dirpath, f)
            k = key_of(full)
            if k is None:
                continue
            with open(full, "rb") as fh:
                put(db, k[0], k[1], fh.read(), name, fresh)
            kept += 1
            if kept % 100000 == 0:
                print(f"  {name}: {kept}", flush=True)
                db.commit()
    if fresh:
        db.executescript(INDEXES)
    db.execute("insert into archives values(?,?,?,?,?,?)", (name, sha, size, -1, kept, 0))
    db.commit()
    print(f"{name}: kept {kept} (extracted subset)", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("archives", nargs="+", type=Path)
    q = sub.add_parser("ingest-dir")
    q.add_argument("root", type=Path)
    q.add_argument("--name", required=True)
    q.add_argument("--sha", required=True)
    q.add_argument("--size", type=int, required=True)
    a = ap.parse_args()
    db = sqlite3.connect(a.db)
    db.executescript(SCHEMA)
    if db.execute("select count(*) from archives").fetchone()[0]:
        db.executescript(INDEXES)
    db.execute("pragma journal_mode=wal")
    db.execute("pragma synchronous=off")
    if a.cmd == "ingest-dir":
        ingest_dir(db, a.root, a.name, a.sha, a.size)
        return 0
    for path in sorted(a.archives, key=lambda p: (not p.name.startswith("Freemium"), p.name)):
        ingest(db, path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
