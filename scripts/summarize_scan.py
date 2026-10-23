"""Summarize scan_rectificatifs.py output.

Usage: python3 -I summarize_scan.py <out.json> <scan.jsonl>...
Prints: archives scanned (date span, count), all rectificatif texts (count),
rectificatifs of loi 2025-1403 / 2026-103 with their article bodies.
"""
import json
import re
import sys

TARGET = re.compile(r"2025-1403|2026-103\b")


def main(out, files):
    archives = {}
    texts = {}
    arts = {}
    for fn in files:
        for line in open(fn, encoding="utf-8"):
            d = json.loads(line)
            if d["kind"] == "archive":
                archives[d["archive"]] = d
            elif d["kind"] == "text":
                if re.search(r"rectificatif", d["titrefull"], re.I):
                    texts.setdefault(d["id"], d)
            else:
                arts.setdefault(d["id"], d)
    names = sorted(archives)
    target = {k: v for k, v in texts.items() if TARGET.search(v["titrefull"])}
    res = {
        "archives": {"count": len(names), "first": names[0], "last": names[-1],
                     "bytes": sum(a["bytes"] for a in archives.values()),
                     "list": [{"name": n, "sha256": archives[n]["sha256"], "bytes": archives[n]["bytes"],
                               "members": archives[n]["members"]} for n in names]},
        "rectificatifs_all": len(texts),
        "rectificatifs_target": [
            {k: v[k] for k in ("id", "num", "nor", "num_parution", "date_publi", "origine_publi", "titrefull", "archive", "sha256")}
            for v in sorted(target.values(), key=lambda v: v["date_publi"])],
        "articles": [
            {k: v[k] for k in ("id", "text_cid", "title", "archive", "sha256", "body")}
            for v in sorted(arts.values(), key=lambda v: v["archive"])],
    }
    json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("archives", len(names), names[0], names[-1], round(res["archives"]["bytes"] / 1e9, 3), "GB")
    print("rectificatifs (all texts):", len(texts))
    for v in res["rectificatifs_target"]:
        print("TARGET", v["date_publi"], v["num_parution"], v["id"], v["titrefull"])
    for a in res["articles"]:
        print("---", a["id"], a["text_cid"], a["archive"])
        print(a["body"])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
