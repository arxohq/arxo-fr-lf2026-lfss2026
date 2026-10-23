"""Scan daily JORF archives (DILA) for rectificatifs.

Usage: python3 -I scan_rectificatifs.py <archives-dir> <out.jsonl>

For every archive (sorted by name) streams members and records:
- texte/version/*.xml whose TITREFULL contains "rectificatif" (any text);
- article/*.xml whose CONTEXTE/TEXTE/TITRE_TXT contains "rectificatif" (full text).
Also records every text/article whose title cites loi 2025-1403 or 2026-103.
Writes one JSON object per line, plus a per-archive summary line (sha256, members).
"""
import hashlib
import html
import json
import os
import re
import sys
import tarfile

TARGET = re.compile(r"2025-1403|2026-103\b")
RECT = re.compile(r"rectificatif", re.I)


def tag(xml, name):
    m = re.search(r"<%s>(.*?)</%s>" % (name, name), xml, re.S)
    return html.unescape(m.group(1)).strip() if m else ""


def body_text(xml):
    m = re.search(r"<BLOC_TEXTUEL>\s*<CONTENU>(.*?)</CONTENU>", xml, re.S)
    if not m:
        return ""
    s = re.sub(r"<br\s*/?>", "\n", m.group(1))
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


def main(src, out):
    names = sorted(n for n in os.listdir(src) if n.endswith(".tar.gz"))
    with open(out, "w", encoding="utf-8") as fo:
        for n in names:
            path = os.path.join(src, n)
            h = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            members = 0
            texts = 0
            with tarfile.open(path, "r|gz") as tf:
                for m in tf:
                    if not m.isfile():
                        continue
                    members += 1
                    p = m.name
                    is_tv = "/texte/version/" in p
                    is_art = "/article/" in p
                    if not (is_tv or is_art):
                        continue
                    raw = tf.extractfile(m).read().decode("utf-8", "replace")
                    if is_tv:
                        texts += 1
                        title = tag(raw, "TITREFULL")
                        if RECT.search(title) or TARGET.search(title):
                            fo.write(json.dumps({
                                "kind": "text", "archive": n, "member": p,
                                "id": tag(raw, "ID"), "num": tag(raw, "NUM"),
                                "nor": tag(raw, "NOR"),
                                "num_parution": tag(raw, "NUM_PARUTION"),
                                "date_publi": tag(raw, "DATE_PUBLI"),
                                "origine_publi": tag(raw, "ORIGINE_PUBLI"),
                                "titrefull": title,
                                "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                            }, ensure_ascii=False) + "\n")
                    else:
                        mt = re.search(r'<TEXTE cid="([^"]+)"[^>]*>\s*<TITRE_TXT[^>]*>(.*?)</TITRE_TXT>', raw, re.S)
                        if not mt:
                            continue
                        title = html.unescape(mt.group(2)).strip()
                        if RECT.search(title) and TARGET.search(title):
                            fo.write(json.dumps({
                                "kind": "article", "archive": n, "member": p,
                                "id": tag(raw, "ID"), "text_cid": mt.group(1),
                                "title": title, "body": body_text(raw),
                                "sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
                            }, ensure_ascii=False) + "\n")
            fo.write(json.dumps({"kind": "archive", "archive": n,
                                 "sha256": h.hexdigest(), "bytes": os.path.getsize(path),
                                 "members": members, "texte_version": texts}) + "\n")
            fo.flush()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
