#!/usr/bin/env python3
"""Published law (JORF) vs. the text adopted by Parliament (AN « texte adopté »).

Both texts are reduced to a stream of words (quotes, dashes, apostrophes,
non-breaking spaces and the AN's spaced hyphens normalised; article headings
dropped) and aligned with difflib. Every differing segment is reported with
context. Expected differences: brackets of the Conseil constitutionnel,
article renumbering, blanks « loi n° du » filled at promulgation.

  ta_diff.py --jorf law.json --ta TA.raw.html --out diff.json
"""
import argparse, difflib, html, json, re, unicodedata

def words(text):
    t = text.replace("’", "'").replace(" ", " ").replace(" ", " ").replace("‑", "-")
    t = t.replace("–", "-").replace("—", "-").replace("“", "\"").replace("”", "\"")
    t = re.sub(r"\s*-\s*(?=\d)", "-", t)          # L. 722 ‑ 1 -> L. 722-1
    t = re.sub(r"(?<=\d)\s*-\s*", "-", t)
    t = unicodedata.normalize("NFC", t)
    t = t.replace("À", "A").replace("É", "E").replace("|", " ")
    t = re.sub(r"\b(\d+|I)\s+(er|re)\b", r"\1\2", t)
    t = re.sub(r"(?<=\w)\s+-\s+(?=\w)", "-", t)
    t = re.sub(r"\s*/\s*", " / ", t)
    t = re.sub(r"\+\s+(?=\d)", "+", t)
    t = re.sub(r"([«»;:,.()\"])", r" \1 ", t)
    return t.split()

ap = argparse.ArgumentParser()
ap.add_argument("--jorf", required=True); ap.add_argument("--ta", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
law = json.load(open(a.jorf, encoding="utf-8"))
jw, jsrc = [], []
for art in law["articles"]:
    for l in art["lines"]:
        ws = words(l); jw += ws; jsrc += [art["num"]] * len(ws)
s = open(a.ta, encoding="utf-8", errors="replace").read()
s = re.sub(r"(?is)<(style|script|head)\b.*?</\1>", " ", s)
s = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</td>|</tr>", "\n", s)
t = html.unescape(re.sub(r"<[^>]+>", " ", s))
start = t.find("dont la teneur suit")
if start < 0: start = t.find("teneur suit")
t = t[start:]
lines = [x.strip() for x in t.split("\n") if x.strip()]
lines = [x for x in lines if not re.fullmatch(r"(?:Article\s+\S+(?:\s+(?:bis|ter|quater|quinquies|sexies|septies|octies|nonies|decies|[A-Z]))*|\(nouveau\)|\(Supprimé\)|\(Non modifié\)|\(Conforme\))", x, re.I)]
tw = []
for x in lines:
    tw += words(x)
sm = difflib.SequenceMatcher(None, jw, tw, autojunk=False)
out = []
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag == "equal": continue
    J = " ".join(jw[i1:i2]); T = " ".join(tw[j1:j2])
    if len(J) > 600 or len(T) > 600:
        kind = "LARGE"
    else:
        kind = "SMALL"
    out.append({"tag": tag, "kind": kind, "jorf_article": jsrc[i1] if i1 < len(jsrc) else "", "jorf": J[:1200], "ta": T[:1200],
                "context": " ".join(jw[max(0, i1 - 25):i1]) + " ⟦…⟧ " + " ".join(jw[i2:i2 + 10])})
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(len(jw), len(tw), "segments", len(out))
