#!/usr/bin/env python3
"""Run the amending operations of one law over LEGI and compare with DILA.

  run.py --db legi.sqlite --law-cid JORFTEXT… --ops ops.json --out results.json
         [--only-articles L136-8,200 quater] [--only-codes "code de la sécurité sociale"]

Output: one record per operation (status of the instruction over the
previous version) and one record per DILA version step (equal / differ with
a diff of the projection). See execute.py for the rules.
"""
from __future__ import annotations

import argparse
import copy
import difflib
import html
import json
import re
import sys
import zlib
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import execute as X  # noqa: E402
from xmltext import first as xml_first  # noqa: E402

AMEND = {"replace", "suppress", "insert_after", "insert_before", "rewrite_end_after", "complete",
         "prepend", "complete_phrase", "rewrite", "rewrite_block", "replace_block",
         "insert_block_after", "insert_block_before", "add_block_end", "prepend_block", "retablir",
         "delete", "abrogate", "renumber", "create_article", "move", "rewrite_start"}


def text_index(legi: X.Legi) -> dict[str, str]:
    """Number of a non-codified text ('2017-1836') -> its directory in LEGI."""
    cache = legi.db.execute("select name from sqlite_master where name='textnums'").fetchone()
    if not cache:
        legi.db.execute("create table textnums(num text, text text, nature text, titre text)")
        for text, blob in legi.db.execute("select text, xml from files where kind='version' and text like 'JORFTEXT%'").fetchall():
            x = zlib.decompress(blob).decode("utf-8")
            num = xml_first(x, "NUM")
            if num:
                legi.db.execute("insert into textnums values(?,?,?,?)",
                                (num, text, xml_first(x, "NATURE"), html.unescape(xml_first(x, "TITREFULL"))))
        legi.db.commit()
    return {}


def resolve_text(legi: X.Legi, target: dict) -> str | None:
    if target.get("code"):
        return legi.text_id(target)
    if target.get("text"):
        m = re.search(r"n°\s*([\d-]+)", target["text"])
        if not m:
            return None
        rows = legi.db.execute("select text, nature from textnums where num=?", (m.group(1),)).fetchall()
        nature = target["text"].split()[0].upper()
        rows = [r for r in rows if r[1].upper().startswith(nature[:3])] or rows
        return rows[0][0] if rows else None
    return None


def article_candidates(num: str) -> list[str]:
    out = [num]
    if num == "1":
        out.append("1er")
    m = re.match(r"^(LO|L|R|D|A)(\d.*)$", num)
    if m:
        out.append(f"{m.group(1)}. {m.group(2)}")
    return out


def sim(a: list[str], b: list[str]) -> float:
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    same = sum(bl.size for bl in sm.get_matching_blocks())
    # char-level on the differing lines
    extra = 0.0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "replace":
            sa, sb = " ".join(a[i1:i2]), " ".join(b[j1:j2])
            extra += difflib.SequenceMatcher(None, sa, sb, autojunk=False).ratio() * min(i2 - i1, j2 - j1)
    return (same + extra) / max(len(a), len(b), 1)


def udiff(a: list[str], b: list[str]) -> list[str]:
    return list(difflib.unified_diff(a, b, "applied", "dila", n=0, lineterm=""))[2:60]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", type=Path, required=True)
    ap.add_argument("--law-cid", required=True)
    ap.add_argument("--ops", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--only-articles", default="")
    ap.add_argument("--only-codes", default="")
    a = ap.parse_args()
    legi = X.Legi(a.db)
    text_index(legi)
    ops = json.load(open(a.ops, encoding="utf-8"))
    for n, op in enumerate(ops):
        op["seq"] = n
    only_arts = {x.strip() for x in a.only_articles.split(",") if x.strip()}
    only_codes = {x.strip().lower() for x in a.only_codes.split("|") if x.strip()}

    lv = X.law_versions(legi, a.law_cid)
    linked: dict[str, list[dict]] = defaultdict(list)
    for v in lv:
        linked[v["id"]].append(v)

    groups: dict[tuple, list[dict]] = defaultdict(list)
    op_rows: list[dict] = []
    for op in ops:
        if op["kind"] not in AMEND:
            op_rows.append({**op, "status": op["kind"].upper(), "detail": ""})
            continue
        tgt = op["target"]
        if only_codes and (tgt.get("code") or "").lower() not in only_codes:
            continue
        if op["kind"] == "create_article":
            arts = [X.FL.norm_art(x) for x in re.split(r"\s*,\s*|\s+et\s+|\s+à\s+", op["y"] or "") if x.strip()]
        else:
            arts = [tgt.get("article")]
        if only_arts and not (set(arts) & only_arts):
            continue
        tid = resolve_text(legi, tgt)
        for art in arts:
            groups[(tid, art)].append(op)

    steps: list[dict] = []
    status: dict[int, tuple] = {}
    for (tid, art), gops in sorted(groups.items(), key=lambda kv: (str(kv[0][0]), str(kv[0][1]))):
        if tid is None or art is None:
            for op in gops:
                status[op["seq"]] = ("TARGET_UNRESOLVED", f"text={tid} article={art}", None)
            continue
        versions = []
        for cand in article_candidates(art):
            versions = legi.versions(tid, cand)
            if versions:
                art_num = cand
                break
        if not versions:
            for op in gops:
                status[op["seq"]] = ("ARTICLE_NOT_IN_LEGI", f"{tid} {art}", None)
            steps.append({"text": tid, "article": art, "versions": 0, "linked": [], "result": "ARTICLE_NOT_IN_LEGI",
                          "ops": [o["seq"] for o in gops]})
            continue
        law_arts = {o["article"] for o in gops}
        mine = [v for v in versions if v["id"] in linked and any(l["type"] in ("MODIFIE", "CREE", "TRANSFERE") for l in linked[v["id"]])]
        abrog = [v for v in versions if v["id"] in linked and any(l["type"].startswith("ABROG") for l in linked[v["id"]])]
        mine.sort(key=lambda v: (v["debut"], v["fin"]))
        if not mine:
            # whole-article abrogation shows as a closed last version
            for op in gops:
                if op["kind"] == "abrogate" and not op["target"]["inner"] and abrog:
                    v = abrog[-1]
                    status[op["seq"]] = ("ARTICLE_ABROGATED", f"DILA closes {v['id']} on {v['fin']} ({v['etat']})", v["id"])
                elif op["kind"] == "abrogate" and not op["target"]["inner"]:
                    last = versions[-1]
                    status[op["seq"]] = ("ARTICLE_ABROGATED" if last["etat"].startswith("ABROG") else "NO_DILA_VERSION",
                                         f"last version {last['id']} {last['debut']}..{last['fin']} {last['etat']}", None)
                else:
                    status[op["seq"]] = ("NO_DILA_VERSION", f"{len(versions)} versions, none linked to the law", None)
            steps.append({"text": tid, "article": art_num, "versions": len(versions), "linked": [],
                          "result": "NO_DILA_VERSION", "ops": [o["seq"] for o in gops]})
            continue
        pending = list(gops)
        for vk in mine:
            k_arts = {l["law_art"] for l in linked[vk["id"]]}
            k_types = sorted({l["type"] for l in linked[vk["id"]]})
            others = [l for l in legi.links(vk["id"]) if l["sens"] == "cible" and l["cid"] != a.law_cid and l["type"] in ("MODIFIE", "CREE", "ABROGE", "TRANSFERE")]
            # a version DILA marks MODIFIE_MORT_NE (abrogated before entering into force)
            # never was the law: the base is the version before it
            prev = [v for v in versions if v["fin"] == vk["debut"] and v["id"] != vk["id"] and "MORT_NE" not in v["etat"]]
            prev.sort(key=lambda v: v["debut"])
            target_lines = X.proj(legi.lines(vk["id"]))
            cands = [o for o in pending if o["article"] in k_arts or not k_arts]
            if not prev:
                # created by the law
                created = [o for o in cands if o["kind"] == "create_article" or (o["kind"] in ("rewrite_block", "retablir") and not o["target"]["inner"])]
                res = "CREATED"
                diff = []
                for o in created:
                    blk = X.proj(X.strip_art_prefix(o["block"] or []))
                    # an article block may carry several articles: keep the part of this one
                    seg = split_articles(o["block"] or []).get(art_num) or blk
                    seg = X.proj(seg)
                    if X.same(seg, target_lines):
                        status[o["seq"]] = ("OK", "created; text equal to DILA", vk["id"])
                    else:
                        status[o["seq"]] = ("OK", "created; text differs from DILA", vk["id"])
                        res = "CREATED_DIFFERS"
                        diff = udiff(seg, target_lines)
                    pending.remove(o)
                for o in [o for o in cands if o not in created]:
                    pass
                steps.append({"text": tid, "article": art_num, "version": vk["id"], "debut": vk["debut"],
                              "link_types": k_types, "law_articles": sorted(k_arts), "prev": None,
                              "others": [l["label"] for l in others], "result": res, "diff": diff,
                              "ops": [o["seq"] for o in created]})
                continue
            pv = prev[-1]
            base_lines = legi.lines(pv["id"])
            doc = X.Doc(base_lines)
            accepted = []
            # first: all candidate operations of this step, in order
            whole = X.Doc(base_lines)
            whole_st = []
            for o in cands:
                if o["kind"] == "create_article" or (o["kind"] == "abrogate" and not o["target"]["inner"]):
                    continue
                st, det = X.apply(whole, o)
                whole_st.append((o, st, det))
            if whole_st and all(st.startswith("OK") for _, st, _ in whole_st) and X.same(X.proj(whole.lines), target_lines):
                doc = whole
                for o, st, det in whole_st:
                    accepted.append(o)
                    status[o["seq"]] = (st, det, vk["id"])
                cands = []
            for o in cands:
                if o["kind"] == "create_article":
                    continue
                if o["kind"] == "abrogate" and not o["target"]["inner"]:
                    continue
                trial = X.Doc([])
                trial.lines = list(doc.lines)
                st, det = X.apply(trial, o)
                before = sim(X.proj(doc.lines), target_lines)
                after = sim(X.proj(trial.lines), target_lines)
                if st.startswith("OK") and after >= before:
                    doc = trial
                    accepted.append(o)
                    status[o["seq"]] = (st, det, vk["id"])
                elif not st.startswith("OK"):
                    base_trial = X.Doc(base_lines)
                    st0, det0 = X.apply(base_trial, o)
                    if st0.startswith("OK") and sim(X.proj(base_trial.lines), target_lines) > sim(X.proj(base_lines), target_lines):
                        det = det + f"; on the text BEFORE the preceding instructions of this step: {st0}"
                        st = st + "|BASE_OK"
                    if o["seq"] not in status:
                        status[o["seq"]] = (st, det, vk["id"])
                    if len(mine) == 1 or vk is mine[-1]:
                        accepted.append(o)
                else:
                    status.setdefault(o["seq"], ("DEFERRED", f"applying it moves away from DILA version {vk['id']}", vk["id"]))
            for o in accepted:
                if o in pending:
                    pending.remove(o)
            got = X.proj(doc.lines)
            equal = X.same(got, target_lines)
            steps.append({"text": tid, "article": art_num, "version": vk["id"], "debut": vk["debut"], "fin": vk["fin"],
                          "link_types": k_types, "law_articles": sorted(k_arts), "prev": pv["id"],
                          "prev_debut": pv["debut"], "others": [l["label"] for l in others],
                          "result": "EQUAL" if equal else "DIFFERS", "diff": [] if equal else udiff(X.proj_cmp(got), X.proj_cmp(target_lines)),
                          "punct_only": (not equal) and False,
                          "ops": [o["seq"] for o in accepted]})
        for o in pending:
            if o["kind"] == "abrogate" and not o["target"]["inner"] and abrog:
                v = abrog[-1]
                status[o["seq"]] = ("ARTICLE_ABROGATED", f"DILA closes {v['id']} on {v['fin']} ({v['etat']})", v["id"])
            elif o["kind"] == "abrogate" and not o["target"]["inner"]:
                last = versions[-1]
                status[o["seq"]] = ("ARTICLE_ABROGATED" if last["etat"].startswith("ABROG") or last["fin"] < "2999" else "NO_DILA_VERSION",
                                    f"last version {last['id']} {last['debut']}..{last['fin']} {last['etat']}", last["id"])
            elif o["seq"] not in status:
                status[o["seq"]] = ("NOT_ASSIGNED", "no DILA version of this article linked to this law article", None)
    # fallback: an operation with no DILA version linked to its law article may have
    # been consolidated in a version that carries no LIEN to the law
    by_group = defaultdict(list)
    for (tid, art), gops in groups.items():
        for o in gops:
            if status.get(o["seq"], ("",))[0] in ("NOT_ASSIGNED", "NO_DILA_VERSION") and tid and art:
                by_group[(tid, art)].append(o)
    for (tid, art), gops in by_group.items():
        versions = []
        for cand in article_candidates(art):
            versions = legi.versions(tid, cand)
            if versions:
                break
        found = None
        for vk in versions:
            if vk["debut"] < "2025-12-31" or "MORT_NE" in vk["etat"]:
                continue
            prev = [v for v in versions if v["fin"] == vk["debut"] and v["id"] != vk["id"] and "MORT_NE" not in v["etat"]]
            if not prev:
                continue
            d = X.Doc(legi.lines(prev[-1]["id"]))
            sts = [X.apply(d, o)[0] for o in gops]
            if all(x.startswith("OK") for x in sts) and X.same(X.proj(d.lines), X.proj(legi.lines(vk["id"]))):
                found = (vk, prev[-1])
                break
        for o in gops:
            if found:
                vk, pv = found
                status[o["seq"]] = ("OK_UNLINKED", f"equal to DILA version {vk['id']} ({vk['debut']}) which has no LIEN to this law", vk["id"])
        if found:
            vk, pv = found
            steps.append({"text": tid, "article": art, "version": vk["id"], "debut": vk["debut"], "fin": vk["fin"],
                          "link_types": [], "law_articles": sorted({o["article"] for o in gops}), "prev": pv["id"],
                          "prev_debut": pv["debut"], "others": [], "result": "EQUAL_UNLINKED", "diff": [],
                          "ops": [o["seq"] for o in gops]})
    for op in ops:
        if op["kind"] in AMEND and op["seq"] in status:
            st, det, ver = status[op["seq"]]
            op_rows.append({**op, "status": st, "detail": det, "version": ver,
                            "text_id": resolve_text(legi, op["target"])})
    op_rows.sort(key=lambda r: r["seq"])
    json.dump({"law": a.law_cid, "ops": op_rows, "steps": steps}, open(a.out, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    print("ops:", dict(Counter(r["status"] for r in op_rows)))
    print("steps:", dict(Counter(s["result"] for s in steps)))
    return 0


def split_articles(block: list[str]) -> dict[str, list[str]]:
    """A quoted block holding « Art. L. 1. - … » « Art. L. 2. - … » -> per article."""
    out: dict[str, list[str]] = {}
    cur = None
    for line in block:
        s = line.lstrip("« ").strip()
        m = re.match(r"^Art\.\s+(" + X.FL.ART_NUM + r")\s*\.?\s*[-–—]\s*(.*)$", s)
        if m:
            cur = X.FL.norm_art(m.group(1))
            out[cur] = [m.group(2)]
        elif cur:
            out[cur].append(s)
    return out


if __name__ == "__main__":
    sys.exit(main())
