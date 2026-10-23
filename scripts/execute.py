#!/usr/bin/env python3
"""Execute parsed amending operations over LEGI versions; compare with DILA.

For every (text, article) touched by the amending law:

  1. the versions DILA attributes to the law (LIEN typelien MODIFIE/CREE,
     sens cible, cidtexte = the law) are listed with their start dates;
  2. for each such version V_k, its predecessor V_{k-1} is the version of the
     same article that ends on V_k's start date;
  3. the law's operations on that article are applied, in document order, to
     V_{k-1}; every operation first resolves its locator inside the article
     and counts the occurrences of the quoted words in the resolved scope;
  4. the result is compared with V_k by a projection that ignores only
     whitespace, apostrophe/quote/dash variants and the space before
     punctuation.

The counting rule is the drafting convention: without « à chaque
occurrence », « deux fois », « la première occurrence », … the quoted words
must occur exactly once in the designated scope. A statute that leaves the
count open is not repaired: the operation is reported as ambiguous and the
text is left unchanged, and the explicit readings can be compared with DILA.
"""
from __future__ import annotations

import difflib
import html
import json
import re
import sqlite3
import sys
import zlib
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from xmltext import body as xml_body, first as xml_first  # noqa: E402
import fr_legistics as FL  # noqa: E402

# --- normalisation -----------------------------------------------------------------------
def norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace(" ", " ").replace(" ", " ")
    s = s.replace("–", "-").replace("—", "-").replace("‑", "-").replace("―", "-")
    s = re.sub(r"\b(\d+|I) er\b", r"\1er", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+([,.;:)])", r"\1", s)
    s = re.sub(r"\(\s+", "(", s)
    # dash spacing after enumerators and before numbers: "I. - A. - " = "I.-A.-"; "- 0,3 %" = "-0,3 %"
    s = re.sub(r"(?<=[.)°])\s*-\s*", "-", s)
    s = re.sub(r"^-\s+", "-", s)
    return s


ABROGE_LINE = re.compile(r"^\S+(?:\s+(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies))?\s*[-.)°]*\s*\(?(?:Abrogée?s?|Supprimée?s?)\)?\s*[.;]?$", re.I)


def cmp_form(l: str) -> str:
    """Comparison form of one alinéa: quotation marks of any style and the end
    punctuation are not compared (DILA turns a final « . » into « ; » when a new
    item follows, and consolidated non-codified texts use “ ” or " ")."""
    if "\x00" in l:
        return l
    l = re.sub(r"[«»“”„\"]", " ", l)
    l = re.sub(r"'\s+", "'", l)
    l = re.sub(r"\s+", " ", l).strip()
    l = re.sub(r"\s+([,.;:)])", r"\1", l)
    return re.sub(r"[\s.;,:]+$", "", l)


def proj_cmp(lines: list[str]) -> list[str]:
    return [cmp_form(l) for l in lines if not ABROGE_LINE.match(norm(l))]


def proj(lines: list[str]) -> list[str]:
    out = []
    for l in lines:
        if "\x00" in l:
            a, b = l.split("\x00", 1)
            out.append(norm(a) + "\x00" + norm(b))
            continue
        n = norm(l)
        if not n:
            continue
        out.append(n)
    return out


# --- enumerators inside a code article -------------------------------------------------------
SUF = FL.SUF
LINE_ENUM = [
    ("R", re.compile(r"^([IVXLC]+" + SUF + r"?)\s*(?:\.\s*)?[-–—]\s*")),
    ("A", re.compile(r"^([A-Z]" + SUF + r"?)\s*\.\s*(?:[-–—]\s*)?(?=\S)")),
    ("P", re.compile(r"^(\d+(?:\.\d+)*" + SUF + r"?)\s*\.\s*(?:[-–—]\s*)?(?=\S)")),
    ("N", re.compile(r"^(\d+°(?:\s*-\s*\d+)?" + SUF + r"?)\s*")),
    ("a", re.compile(r"^([a-z]" + SUF + r"?)\s*[).]\s*")),
    ("aa", re.compile(r"^([a-z]{2}" + SUF + r"?)\s*\)\s*")),
]
LRANK = {"R": 1, "A": 2, "P": 3, "N": 4, "a": 5, "aa": 6}


def line_enums(line: str) -> list[tuple[str, str]]:
    """'I.-A.-1. La …' -> [(R,I), (A,A), (P,1)]: a line can open several levels."""
    out = []
    s = norm(line)
    while True:
        e = line_enum(s)
        if not e:
            return out
        out.append(e)
        for kind, rx in LINE_ENUM:
            m = rx.match(s)
            if m:
                s = s[m.end():]
                break
        if len(out) > 4:
            return out


def line_enum(line: str) -> tuple[str, str] | None:
    s = norm(line)
    for kind, rx in LINE_ENUM:
        m = rx.match(s)
        if m:
            lab = re.sub(r"\s+", " ", m.group(1))
            if kind == "A" and lab in ("I", "V", "X", "L", "C") and re.match(r"^[IVXLC]\s*\.\s*[-–—]", s):
                return "R", lab
            return kind, lab
    return None


def label_kind(label: str) -> list[str]:
    lab = label.strip()
    base = lab.split(" ")[0]
    if re.fullmatch(r"\d+°", base):
        return ["N"]
    if re.fullmatch(r"\d+(?:\.\d+)*", base):
        return ["P", "N"]
    if re.fullmatch(r"[IVXLC]+", base):
        return ["R", "A"] if len(base) == 1 else ["R"]
    if re.fullmatch(r"[A-Z]", base):
        return ["A"]
    if re.fullmatch(r"[a-z]", base):
        return ["a"]
    if re.fullmatch(r"[a-z]{2}", base):
        return ["aa"]
    return []


def same_label(a: str, b: str) -> bool:
    a = re.sub(r"\s+", " ", a.strip()).rstrip(".")
    b = re.sub(r"\s+", " ", b.strip()).rstrip(".")
    return a == b


# --- regions -------------------------------------------------------------------------------
class Doc:
    """An article body as alinéas; regions are (line, start, end) triples."""

    def __init__(self, lines: list[str]):
        self.lines = [norm(l) for l in lines]

    def whole(self) -> list[tuple[int, int, int]]:
        return [(i, 0, len(l)) for i, l in enumerate(self.lines)]


def line_set(region) -> list[int]:
    return sorted({r[0] for r in region})


def sub_scope(doc: Doc, lines_idx: list[int], label: str) -> list[list[int]]:
    """Ranges of lines (within lines_idx) of subdivision `label`."""
    kinds = label_kind(label)
    out = []
    for pos, li in enumerate(lines_idx):
        es = line_enums(doc.lines[li])
        hit = [e for e in es if e[0] in kinds and same_label(e[1], label)]
        if not hit:
            continue
        rank = LRANK[hit[0][0]]
        span = [li]
        for lj in lines_idx[pos + 1:]:
            f = line_enums(doc.lines[lj])
            if f and min(LRANK[x[0]] for x in f) <= rank:
                break
            if not f and hit[0][0] in ("N", "a", "aa"):
                # an unnumbered alinéa after a list item belongs to the item while
                # the list goes on (a later sibling item follows, the item ends
                # with « : », or the alinéa ends with « ; »); after the last item
                # it is a closing alinéa of the parent
                prev_line = doc.lines[span[-1]].rstrip()
                later = lines_idx[lines_idx.index(lj) + 1:]
                sibling_after = any(any(x[0] == hit[0][0] for x in line_enums(doc.lines[k])) for k in later)
                if not (sibling_after or prev_line.endswith(":") or re.search(r"[;,]\s*(?:et|ou)?$", doc.lines[lj].rstrip())):
                    break
            span.append(lj)
        out.append(span)
    return out


SENT_ABBR = re.compile(r"(?:\b(?:[A-Z]|art|MM|M|Mme|cf|al|n|p|etc|ann|av|bd|ch|sect|liv|tit|déc|ord|loi)|\d)\.$")


def sentences(text: str) -> list[tuple[int, int]]:
    """(start, end) of each sentence of one alinéa, skipping the leading enumerator."""
    e = None
    for kind, rx in LINE_ENUM:
        m = rx.match(text)
        if m:
            e = m.end()
            break
    start = 0
    out = []
    i = e or 0
    for m in re.finditer(r"[.!?](?=\s+[A-ZÀ-ÖØ-Þ«\"(])", text):
        if m.start() < i:
            continue
        before = text[max(0, m.start() - 6):m.start() + 1]
        if SENT_ABBR.search(before):
            continue
        out.append((start, m.end()))
        start = m.end()
        while start < len(text) and text[start] == " ":
            start += 1
    out.append((start, len(text)))
    return [x for x in out if x[1] > x[0]]


def pick(items: list, spec) -> list:
    if not items:
        return []
    if isinstance(spec, list) and spec and spec[0] == "range":
        a, b = spec[1], spec[2]
        n = len(items)
        ia = a - 1 if a > 0 else n + a
        ib = b - 1 if b > 0 else n + b
        if ia < 0 or ib >= n or ia > ib:
            return []
        return items[ia:ib + 1]
    out = []
    for k in spec:
        idx = k - 1 if k > 0 else len(items) + k
        if 0 <= idx < len(items):
            out.append(items[idx])
        else:
            return []
    return out


def resolve_groups(doc: Doc, inner: list) -> list | None:
    """Like resolve(), but one region per designated subdivision when the
    locator names several (« aux 1° et 3° du III »): the occurrence rule then
    applies to each of them."""
    for i, comp in enumerate(inner):
        if comp[0] == "alinea" and (len(comp[1]) > 1 or comp[1][:1] == ["range"]) and not any(c[0] == "phrase" for c in inner[i + 1:]):
            reg, why = resolve(doc, inner)
            if reg is None:
                return None
            return [[r] for r in reg]
        if comp[0] == "phrase" and (len(comp[1]) > 1 or comp[1][:1] == ["range"]):
            reg, why = resolve(doc, inner)
            if reg is None:
                return None
            return [[r] for r in reg]
        if comp[0] == "subs":
            out = []
            for lab in comp[1]:
                reg, why = resolve(doc, inner[:i] + [["sub", lab]] + inner[i + 1:])
                if reg is None:
                    return None
                out.append(reg)
            return out
    return None


def resolve(doc: Doc, inner: list) -> tuple[list[tuple[int, int, int]] | None, str]:
    """Locator path inside the article -> region; (None, reason) when unresolvable."""
    groups = [list(range(len(doc.lines)))]
    phrase_spec = None
    for comp in inner:
        kind = comp[0]
        if kind in ("sub", "subs", "subrange"):
            labels = comp[1] if kind == "subs" else ([comp[1]] if kind == "sub" else None)
            new = []
            for g in groups:
                if kind == "subrange":
                    a = sub_scope(doc, g, comp[1])
                    b = sub_scope(doc, g, comp[2])
                    if len(a) == 1 and len(b) == 1 and a[0][0] <= b[0][-1]:
                        new.append(list(range(a[0][0], b[0][-1] + 1)))
                    continue
                for lab in labels:
                    found = sub_scope(doc, g, lab)
                    if len(found) > 1:
                        return None, f"subdivision {lab} appears {len(found)} times in scope"
                    new.extend(found)
            if not new:
                return None, f"subdivision {comp[1] if kind != 'subrange' else comp[1] + ' à ' + comp[2]} not found"
            groups = new if kind != "subs" else [sorted({x for g in new for x in g})]
        elif kind == "alinea":
            new = []
            for g in groups:
                got = pick(g, comp[1])
                if not got:
                    return None, f"alinéa {comp[1]} not found (scope has {len(g)})"
                new.append(got)
            groups = new
        elif kind == "phrase":
            phrase_spec = comp[1]
    region = []
    for g in groups:
        for li in g:
            if phrase_spec is None:
                region.append((li, 0, len(doc.lines[li])))
    if phrase_spec is not None:
        for g in groups:
            sents = [(li, s, e) for li in g for (s, e) in sentences(doc.lines[li])]
            # phrases are counted per alinéa when the scope is one alinéa
            got = pick(sents, phrase_spec)
            if not got:
                return None, f"phrase {phrase_spec} not found ({len(sents)} phrases)"
            region.extend(got)
    return region, ""


# --- occurrence matching ---------------------------------------------------------------------
def word_rx(x: str) -> re.Pattern:
    x = norm(x)
    pre = r"(?<![\w])" if re.match(r"\w", x) else ""
    post = r"(?![\w])" if re.search(r"\w$", x) else ""
    body = re.escape(x).replace(r"\ ", r"\s*")
    return re.compile(pre + body + post)


def enum_prefix_len(line: str) -> int:
    n = 0
    s = line
    while True:
        for kind, rx in LINE_ENUM:
            m = rx.match(s)
            if m:
                n += m.end()
                s = s[m.end():]
                break
        else:
            return n


def find_all(doc: Doc, region, x: str) -> list[tuple[int, int, int]]:
    rx = word_rx(x)
    out = []
    quoted_label = any(rx.match(norm(x)) for _, rx in LINE_ENUM)
    for li, s, e in region:
        skip = 0 if quoted_label else enum_prefix_len(doc.lines[li])
        for m in rx.finditer(doc.lines[li], s, e):
            if m.start() >= s and m.end() <= e and m.start() >= skip:
                out.append((li, m.start(), m.end()))
    return out


def choose(hits, occ, position, region, doc) -> tuple[list, str]:
    n = len(hits)
    if occ is None:
        if n == 1:
            return hits, "OK"
        if n == 0:
            return [], "NOT_FOUND"
        if position == "fin":
            last = hits[-1]
            li, s, e = region[-1]
            tail = doc.lines[li][last[2]:e]
            if last[0] == li and re.fullmatch(r"[\s.;:,»)]*", tail):
                return [last], "OK_POSITION"
        if position == "debut":
            firsth = hits[0]
            li, s, e = region[0]
            if firsth[0] == li and not doc.lines[li][s:firsth[1]].strip():
                return [firsth], "OK_POSITION"
        return [], f"COUNT_MISMATCH:{n}"
    if occ == "each":
        return (hits, "OK") if n >= 1 else ([], "NOT_FOUND")
    if occ[0] == "count":
        if n == occ[1]:
            return hits, "OK"
        return [], f"COUNT_MISMATCH:{n}/{occ[1]}"
    if occ[0] == "nth":
        k = occ[1]
        idx = k - 1 if k > 0 else n + k
        if 0 <= idx < n:
            return [hits[idx]], "OK"
        return [], f"COUNT_MISMATCH:{n}/nth{k}"
    return [], "BAD_OCC"


def splice(doc: Doc, edits: list[tuple[int, int, int, str]]) -> None:
    for li, s, e, rep in sorted(edits, key=lambda t: (t[0], t[1]), reverse=True):
        line = doc.lines[li]
        if rep and s > 0 and line[s - 1].isalnum() and rep[0].isalnum():
            rep = " " + rep
        if rep and e < len(line) and line[e].isalnum() and rep[-1].isalnum():
            rep = rep + " "
        doc.lines[li] = re.sub(r"\s{2,}", " ", (line[:s] + rep + line[e:])).strip()


def strip_art_prefix(lines: list[str]) -> list[str]:
    if lines and re.match(r"^«?\s*Art\.\s", lines[0]):
        lines = [re.sub(r"^«?\s*Art\.\s+" + FL.ART_NUM + r"\s*\.?\s*[-–—]\s*", "", lines[0], count=1)] + lines[1:]
    return lines


def tail_punct(text: str) -> int:
    m = re.search(r"\s*[.;:,]\s*$", text)
    return m.start() if m else len(text)


def label_value(label: str) -> tuple:
    base, *suf = label.split(" ")
    sv = FL.SUFFIXES.index(suf[0]) + 1 if suf and suf[0] in FL.SUFFIXES else 0
    b = base.rstrip("°").rstrip(".")
    if re.fullmatch(r"[IVXLC]+", b):
        vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
        tot = 0
        for i, ch in enumerate(b):
            v = vals[ch]
            tot += -v if i + 1 < len(b) and vals[b[i + 1]] > v else v
        return (tot, sv)
    if re.fullmatch(r"\d+", b):
        return (int(b), sv)
    if re.fullmatch(r"[A-Za-z]{1,2}", b):
        return (sum(ord(c) for c in b.lower()), sv)
    return (0, sv)


def apply(doc: Doc, op: dict) -> tuple[str, str]:
    """Apply one op in place. Returns (status, detail)."""
    kind = op["kind"]
    t = op["target"]
    inner = t["inner"]
    position = t.get("position")
    if kind in ("autonomous", "context", "unparsed", "move", "create_article"):
        return "SKIP", kind
    region, why = resolve(doc, inner)
    if region is None:
        return "SCOPE_UNRESOLVED", why
    if kind in ("replace", "suppress", "insert_after", "insert_before", "rewrite_end_after"):
        needle = op["x"] if kind in ("replace", "suppress") else op["anchor"]
        hits = find_all(doc, region, needle)
        groups = resolve_groups(doc, inner) if op["occurrence"] is None else None
        if groups and len(groups) > 1:
            sel, st = [], "OK"
            for g in groups:
                gs, gst = choose(find_all(doc, g, needle), None, position if kind in ("replace", "suppress") else None, g, doc)
                if not gs:
                    sel, st = [], gst + " (per subdivision)"
                    break
                sel += gs
        else:
            sel, st = choose(hits, op["occurrence"], position if kind in ("replace", "suppress") else None, region, doc)
        if not sel:
            whole = find_all(doc, doc.whole(), needle)
            return st, f"{len(hits)} in scope, {len(whole)} in article: {needle[:60]!r}"
        y = norm(op["y"] or "")
        edits = []
        for li, s, e in sel:
            if kind == "replace":
                edits.append((li, s, e, y))
            elif kind == "suppress":
                edits.append((li, s, e, ""))
            elif kind == "insert_after":
                sep = "" if re.match(r"^[,.;:)]", y) else " "
                edits.append((li, e, e, sep + y))
            elif kind == "insert_before":
                edits.append((li, s, s, y + " "))
            elif kind == "rewrite_end_after":
                rl = [r for r in region if r[0] == li][-1]
                edits.append((li, e, rl[2], " " + y))
        splice(doc, edits)
        return st, f"{len(hits)} in scope"
    if kind == "rewrite_start":
        y = norm(op["y"])
        m = re.match(r"^(.*?)\s*…\s*\(le reste sans changement\)\s*[.;]?\s*$", y)
        if not m:
            return "UNSUPPORTED", "rewrite_start without « (le reste sans changement) »"
        li = region[0][0]
        # the boundary of the old beginning is not stated: keep the whole old
        # alinéa after a marker; the comparison accepts DILA's text when it is
        # the new beginning followed by a suffix of the old alinéa
        doc.lines[li] = m.group(1) + "\x00" + doc.lines[li]
        return "OK", "new beginning; boundary of the old one checked against DILA"
    if kind == "complete":
        li, s, e = region[-1]
        cut = s + tail_punct(doc.lines[li][s:e])
        y = norm(op["y"])
        sep = "" if re.match(r"^[,.;:)]", y) else " "
        splice(doc, [(li, cut, cut, sep + y)])
        return "OK", ""
    if kind == "prepend":
        li, s, e = region[0]
        splice(doc, [(li, s, s, norm(op["y"]) + " ")])
        return "OK", ""
    if kind == "complete_phrase":
        li, s, e = region[-1]
        splice(doc, [(li, e, e, " " + norm(op["y"]))])
        return "OK", ""
    if kind == "rewrite":
        if any(c[0] == "phrase" for c in inner):
            li = region[0][0]
            s, e = region[0][1], region[-1][2]
            if any(r[0] != li for r in region):
                return "SCOPE_UNRESOLVED", "phrases span alinéas"
            splice(doc, [(li, s, e, norm(op["y"]))])
            return "OK", ""
        ls = line_set(region)
        doc.lines[ls[0]:ls[-1] + 1] = [norm(op["y"])]
        return "OK", ""
    if kind in ("rewrite_block", "replace_block"):
        blk = [norm(x) for x in strip_art_prefix(op["block"] or [])]
        if not inner:
            doc.lines[:] = blk
            return "OK", "whole article"
        if any(c[0] == "phrase" for c in inner):
            li = region[0][0]
            splice(doc, [(li, region[0][1], region[-1][2], " ".join(blk))])
            return "OK", ""
        ls = line_set(region)
        doc.lines[ls[0]:ls[-1] + 1] = blk
        return "OK", ""
    if kind in ("insert_block_after", "insert_block_before", "add_block_end", "prepend_block"):
        blk = [norm(x) for x in op["block"] or []]
        if not inner and kind in ("insert_block_after", "insert_block_before"):
            return "SCOPE_UNRESOLVED", "no anchor"
        ls = line_set(region) if inner else list(range(len(doc.lines)))
        if kind in ("insert_block_after", "add_block_end"):
            at = (ls[-1] + 1) if ls else len(doc.lines)
        else:
            at = ls[0] if ls else 0
        if kind == "add_block_end" and any(c[0] == "phrase" for c in inner):
            return "SCOPE_UNRESOLVED", "block after phrase"
        doc.lines[at:at] = blk
        return "OK", ""
    if kind == "retablir":
        blk = [norm(x) for x in op["block"] or []]
        if not inner or inner[-1][0] != "sub":
            return "SCOPE_UNRESOLVED", "no label"
        label = inner[-1][1]
        parent, why = resolve(doc, inner[:-1])
        if parent is None:
            return "SCOPE_UNRESOLVED", why
        pl = line_set(parent)
        kinds = label_kind(label)
        existing = sub_scope(doc, pl, label)
        if existing:
            span = existing[0]
            if len(span) == 1 and re.search(r"\(?abrogée?s?\)?", doc.lines[span[0]], re.I):
                doc.lines[span[0]:span[0] + 1] = blk
                return "OK", "replaced (Abrogé)"
            return "RETABLIR_EXISTS", f"{label} is present"
        want = label_value(label)
        at = None
        for li in pl:
            e = line_enum(doc.lines[li])
            if e and e[0] in kinds and label_value(e[1]) > want:
                at = li
                break
        if at is None:
            at = (pl[-1] + 1) if pl else len(doc.lines)
        doc.lines[at:at] = blk
        return "OK", ""
    if kind in ("delete", "abrogate"):
        if not inner:
            return "ARTICLE_ABROGATED", ""
        if any(c[0] == "phrase" for c in inner):
            li = region[0][0]
            splice(doc, [(li, region[0][1], region[-1][2], "")])
            return "OK", ""
        ls = line_set(region)
        for li in sorted(ls, reverse=True):
            del doc.lines[li]
        return "OK", ""
    if kind == "renumber":
        news = re.findall(r"(?:[IVXLC]+|[A-Z]|\d+°|\d+|[a-z]{1,2})" + SUF + "?", op["y"] or "")
        olds = []
        for c in inner:
            if c[0] == "sub":
                olds = [c[1]]
            elif c[0] == "subs":
                olds = c[1]
        if not olds or len(olds) != len(news):
            return "UNSUPPORTED", f"renumber {olds} -> {news}"
        parent, why = resolve(doc, [c for c in inner if c[0] not in ("sub", "subs")][:-0] or [])
        edits = []
        lines_all = list(range(len(doc.lines)))
        for o, n in zip(olds, news):
            sc = sub_scope(doc, lines_all if not parent else line_set(parent), o)
            if len(sc) != 1:
                return "SCOPE_UNRESOLVED", f"{o}: {len(sc)}"
            li = sc[0][0]
            doc.lines[li] = re.sub(r"^" + re.escape(o), n, doc.lines[li], count=1)
        return "OK", ""
    return "UNSUPPORTED", kind


# --- LEGI access -----------------------------------------------------------------------------
class Legi:
    def __init__(self, path: Path):
        self.db = sqlite3.connect(path)
        self._codes = None
        self._texts = {}

    def xml(self, ident: str) -> str | None:
        row = self.db.execute("select xml from files where id=? and kind='article'", (ident,)).fetchone()
        return zlib.decompress(row[0]).decode("utf-8") if row else None

    def codes(self) -> dict[str, str]:
        if self._codes is None:
            self._codes = {}
            for text, blob in self.db.execute("select text, xml from files where kind='version' and text like 'LEGITEXT%'"):
                x = zlib.decompress(blob).decode("utf-8")
                if "<NATURE>CODE</NATURE>" not in x:
                    continue
                title = html.unescape(xml_first(x, "TITREFULL") or xml_first(x, "TITRE"))
                key = FL.code_key(title)
                key = re.sub(r"\s*\(.*$", "", key)
                self._codes.setdefault(key, text)
        return self._codes

    def text_id(self, target: dict) -> str | None:
        if target.get("code"):
            c = FL.code_key(target["code"])
            codes = self.codes()
            if c in codes:
                return codes[c]
            for k, v in codes.items():
                if k.startswith(c) or c.startswith(k):
                    return v
            return None
        if target.get("text"):
            m = re.search(r"n°\s*([\d-]+)", target["text"])
            if not m:
                return None
            num = m.group(1)
            if num in self._texts:
                return self._texts[num]
            ident = None
            for text, blob in self.db.execute("select text, xml from files where kind='version' and text like 'JORFTEXT%' and xml is not null"):
                pass
            self._texts[num] = ident
            return ident
        return None

    def versions(self, text: str, num: str) -> list[dict]:
        rows = self.db.execute("select id, debut, fin, etat from articles where text=? and num=? order by debut, fin", (text, num)).fetchall()
        return [{"id": r[0], "debut": r[1], "fin": r[2], "etat": r[3]} for r in rows]

    def lines(self, ident: str) -> list[str]:
        x = self.xml(ident)
        return xml_body(x) if x else []

    def links(self, ident: str) -> list[dict]:
        rows = self.db.execute("select typelien, sens, cid, lid, num, label from links where id=?", (ident,)).fetchall()
        return [{"type": r[0], "sens": r[1], "cid": r[2], "lid": r[3], "num": r[4], "label": r[5]} for r in rows]


def law_versions(legi: Legi, law_cid: str) -> list[dict]:
    rows = legi.db.execute(
        "select a.id, a.text, a.num, a.debut, a.fin, a.etat, l.typelien, l.num from links l join articles a on a.id=l.id "
        "where l.cid=? and l.sens='cible'", (law_cid,)).fetchall()
    return [{"id": r[0], "text": r[1], "num": r[2], "debut": r[3], "fin": r[4], "etat": r[5], "type": r[6], "law_art": r[7]} for r in rows]


def same(got: list[str], want: list[str]) -> bool:
    got, want = proj_cmp(got), proj_cmp(want)
    if len(got) != len(want):
        if "\x00" not in " ".join(got) and cmp_form(" ".join(got)) == cmp_form(" ".join(want)):
            return True  # same words, different division into alinéas
        return False
    for g, w in zip(got, want):
        if "\x00" in g:
            new, old = g.split("\x00", 1)
            if not w.startswith(new):
                return False
            rest = w[len(new):].strip()
            if not old.endswith(rest):
                return False
        elif g != w:
            return False
    return True
