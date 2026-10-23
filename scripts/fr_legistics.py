#!/usr/bin/env python3
"""French amending legistics: an amending article -> a list of operations.

Input is a list of alinéas (one string per alinéa), as rendered from JORF XML
or from a bill text (PLF/PLFSS on the Assemblée nationale site): the parser
never looks at markup. Output is a list of `Op` records, each with

  * the enumeration path inside the amending article ("I 2° b"),
  * the target, accumulated through the "… est ainsi modifié :" contexts:
    code or text, article, and the path inside the article
    (subdivisions, alinéas, phrases, position),
  * the kind of operation and its arguments (old words, new words, block),
  * the occurrence requirement of the instruction ("1", "each", "nth k").

Anything the grammar below does not recognise becomes an explicit
`unparsed` op with the source line; a provision that does not amend another
text (entry into force, report, compensation, table) becomes `autonomous`.
Nothing is dropped silently.

The grammar follows the drafting conventions of the Guide de légistique
(Légifrance, 2017, 3.3.2 « Rédaction des dispositions modificatives »):
« les mots : « … » sont remplacés par les mots : « … » », « est ainsi
modifié : », « est complété par », « est abrogé », « après le mot : « … »,
sont insérés les mots : « … » », « est ainsi rédigé », « est ainsi rétabli ».
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import asdict, dataclass, field

SUFFIXES = ("bis ter quater quinquies sexies septies octies nonies decies undecies duodecies "
            "terdecies quaterdecies quindecies sexdecies septdecies octodecies novodecies "
            "vicies unvicies duovicies tervicies quatervicies quinvicies sexvicies septvicies "
            "octovicies novovicies tricies untricies duotricies").split()
SUF = r"(?:\s+(?:" + "|".join(sorted(SUFFIXES, key=len, reverse=True)) + r"))"
ORDINALS = {
    "premier": 1, "première": 1, "1er": 1, "1re": 1, "deuxième": 2, "second": 2, "seconde": 2,
    "troisième": 3, "quatrième": 4, "cinquième": 5, "sixième": 6, "septième": 7,
    "huitième": 8, "neuvième": 9, "dixième": 10, "onzième": 11, "douzième": 12,
    "treizième": 13, "quatorzième": 14, "quinzième": 15, "seizième": 16,
    "dix-septième": 17, "dix-huitième": 18, "dix-neuvième": 19, "vingtième": 20,
    "vingt et unième": 21, "vingt-deuxième": 22, "vingt-troisième": 23,
    "vingt-quatrième": 24, "vingt-cinquième": 25, "vingt-sixième": 26,
    "vingt-septième": 27, "vingt-huitième": 28, "vingt-neuvième": 29, "trentième": 30,
    "dernier": -1, "dernière": -1, "avant-dernier": -2, "avant-dernière": -2,
}
ORD = r"(?:" + "|".join(re.escape(k) for k in sorted(ORDINALS, key=len, reverse=True)) + r")"
CARDINALS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6,
             "sept": 7, "huit": 8, "neuf": 9, "dix": 10, "onze": 11, "douze": 12,
             "treize": 13, "quatorze": 14, "quinze": 15, "seize": 16, "vingt": 20}
CARD = r"(?:" + "|".join(sorted(CARDINALS, key=len, reverse=True)) + r"|\d+)"

# --- enumerators of the amending article --------------------------------------------
ENUM = [
    ("R", re.compile(r"^([IVXLC]+" + SUF + r"?)\s*\.?\s*[-–—]\s*")),
    ("A", re.compile(r"^([A-Z]" + SUF + r"?)\s*\.\s*[-–—]\s*")),
    ("N", re.compile(r"^(\d+°" + SUF + r"?)\s+")),
    ("P", re.compile(r"^(\d+(?:\.\d+)*" + SUF + r"?)\s*\.\s*[-–—]\s*")),
    ("a", re.compile(r"^([a-z]" + SUF + r"?)\)\s*")),
    ("aa", re.compile(r"^([a-z]{2}" + SUF + r"?)\)\s*")),
    ("dash", re.compile(r"^[-–—]\s+")),
]
RANK = {"R": 1, "A": 2, "P": 3, "N": 4, "a": 5, "aa": 6, "dash": 7}


def enum_of(line: str) -> tuple[str, str, str] | None:
    for kind, rx in ENUM:
        m = rx.match(line)
        if m:
            label = m.group(1) if m.groups() else "-"
            return kind, label, line[m.end():]
    return None


@dataclass
class Node:
    rank: int
    kind: str
    label: str
    text: str
    line: int
    block: list[str] = field(default_factory=list)
    children: list["Node"] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)


def is_quote_start(line: str) -> bool:
    return line.startswith("«")


def closes_block(line: str) -> bool:
    """A quoted alinéa that ends the quoted block: » then optional punctuation."""
    stripped = re.sub(r"[\s;.,]*$", "", line)
    if not stripped.endswith("»"):
        return False
    return balance(stripped) <= 0


def balance(s: str) -> int:
    return s.count("«") - s.count("»")


ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII", "XIII", "XIV", "XV",
         "XVI", "XVII", "XVIII", "XIX", "XX", "XXI", "XXII", "XXIII", "XXIV", "XXV", "XXVI", "XXVII",
         "XXVIII", "XXIX", "XXX", "XXXI", "XXXII", "XXXIII", "XXXIV", "XXXV", "XXXVI", "XXXVII", "XXXVIII",
         "XXXIX", "XL", "XLI", "XLII", "XLIII", "XLIV", "XLV", "XLVI", "XLVII", "XLVIII", "XLIX", "L"]


def disambiguate(e: tuple, last: dict) -> tuple:
    """« C. - » after « B. - » is the letter C, not the Roman 100; « V. - » after
    « IV. - » is Roman. Decided by the previous labels of both kinds."""
    kind, label, rest = e
    base = label.split(" ")[0]
    if kind == "R" and len(base) == 1 and base in "IVXLC":
        prev_a = (last.get("A") or "").split(" ")[0]
        prev_r = (last.get("R") or "").split(" ")[0]
        roman_next = prev_r in ROMAN and ROMAN.index(prev_r) + 1 < len(ROMAN) and ROMAN[ROMAN.index(prev_r) + 1] == base
        letter_next = len(prev_a) == 1 and ord(base) == ord(prev_a) + 1
        if letter_next and not roman_next:
            return ("A", label, rest)
    return e


def build_tree(lines: list[str]) -> Node:
    root = Node(0, "root", "", "", -1)
    stack = [root]
    last: dict[str, str] = {}
    i = 0
    in_block = False
    while i < len(lines):
        line = lines[i]
        cur = stack[-1]
        if in_block:
            cur.block.append(line)
            if closes_block(line):
                in_block = False
            i += 1
            continue
        if is_quote_start(line) and (cur.text.rstrip().endswith(":") or cur.block):
            cur.block.append(line)
            in_block = not closes_block(line)
            i += 1
            continue
        e = enum_of(line)
        if e is None or line.startswith("|"):
            if cur is root and not root.text:
                root.text = line
            else:
                cur.extra.append(line)
            i += 1
            continue
        while e is not None:
            kind, label, rest = e
            e = disambiguate(e, last)
            kind, label, rest = e
            last[kind] = label
            rank = RANK[kind]
            while stack[-1].rank >= rank and stack[-1] is not root:
                stack.pop()
            inner = enum_of(rest)
            if inner is not None and RANK[inner[0]] > rank:
                node = Node(rank, kind, label, "", i)
                stack[-1].children.append(node)
                stack.append(node)
                e = inner
                continue
            node = Node(rank, kind, label, rest, i)
            stack[-1].children.append(node)
            stack.append(node)
            e = None
        i += 1
    return root


# --- quotes -------------------------------------------------------------------------------
def mask(text: str) -> tuple[str, list[str]]:
    """Replace every top-level « … » by Qn; nested guillemets stay inside."""
    out, quotes, depth, start, buf = [], [], 0, 0, []
    i = 0
    while i < len(text):
        ch = text[i]
        if ch == "«":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "»" and depth > 0:
            depth -= 1
            if depth == 0:
                quotes.append(text[start + 1:i].strip())
                out.append(f"Q{len(quotes) - 1}")
                i += 1
                continue
        if depth == 0:
            out.append(ch)
        i += 1
    if depth > 0:  # unbalanced: keep the tail as a quote
        quotes.append(text[start + 1:].strip())
        out.append(f"Q{len(quotes) - 1}")
    return "".join(out), quotes


def block_text(block: list[str]) -> list[str]:
    """Alinéas of a quoted block without the guillemets and the closing punctuation."""
    out = []
    for n, line in enumerate(block):
        s = line
        if s.startswith("«"):
            s = s[1:].lstrip()
        if n == len(block) - 1:
            s = re.sub(r"\s*»[\s;.,]*$", "", s)
        out.append(s.strip())
    return out


# --- locators -----------------------------------------------------------------------------
CODE_RX = re.compile(r"\b(?:du|le|au|dudit|même)\s+((?:livre\s+des\s+procédures\s+fiscales)|code\s+(?:général\s+|des\s+|de\s+(?:la\s+|l')?|du\s+|rural\s+)?[^,;:]*?)(?=\s*(?:,|;|:|\.|$|\s+est\b|\s+sont\b|\s+dans\b|\s+il\b|\s+après\b|\s+avant\b|\s+les?\s+mots\b|\s+la\s+référence\b|\s+le\s+taux\b|\s+le\s+montant\b))", re.I)
_TITLE = r"(?:\s+précitée|\s+\(n°[^)]*\))?(?:\s+(?:de\s+finances|de\s+financement|relative?s?|portant|pour|visant|instituant|modifiant|tendant|organique|d'|de|sur|en\s+faveur)\b[^,;:]*?)?(?=\s*(?:,|;|:|$|\s+(?:est|sont|il|dans|après|avant|les\s+mots|le\s+mot|la\s+référence|le\s+taux|la\s+date|le\s+montant|l'année)\b))"
TEXT_RX = re.compile(r"\b(?:de\s+la|la|à\s+la)\s+(loi(?:\s+organique)?(?:\s+de\s+finances(?:\s+rectificative)?\s+pour\s+\d{4}\s*\(?)?(?:\s+n°\s*[\d-]+)?(?:\s+du\s+\d+(?:er)?\s+\w+\s+\d{4})?)" + _TITLE + r"|\b(?:de\s+l'|l')\s*(ordonnance\s+n°\s*[\d-]+\s+du\s+\d+(?:er)?\s+\w+\s+\d{4})" + _TITLE + r"|\b(?:du|le)\s+(décret\s+n°\s*[\d-]+\s+du\s+\d+(?:er)?\s+\w+\s+\d{4})" + _TITLE, re.I)
ART_NUM = (r"(?:(?:LO|L|R|D|A)\s*\.?\s*\*?\s*)?\d+(?:er)?(?:-\d+)*" + SUF + r"?(?:-\d+)*(?:\s+[A-Z]{1,3}(?![a-zé])" + SUF + r"?(?:-\d+)*)*"
           r"(?:\s+[A-Z](?![a-zé]))?(?:\s+unique)?")
ART_RX = re.compile(r"\b(?:l'|les|aux|à l'|des|de l'|d')\s*articles?\s+(" + ART_NUM + r"|unique)", re.I)
SUB_TOKEN = r"(?:[IVXLC]+|[A-Z]|\d+°|\d+(?:\.\d+)*|[a-z]{1,2})" + SUF + r"?"


def norm_art(num: str) -> str:
    num = re.sub(r"\s+", " ", num.strip())
    num = re.sub(r"^(LO|L|R|D|A)\s*\.?\s*\*?\s*", lambda m: m.group(1), num)
    num = re.sub(r"^(LO|L|R|D|A)(\d)", r"\1\2", num)
    return num


def code_key(name: str) -> str:
    name = name.lower().replace("’", "'")
    name = re.sub(r"'\s+", "'", name)
    name = re.sub(r"\s+", " ", name).strip()
    name = re.sub(r"\s+(?:est|sont)\b.*$", "", name)
    return name


@dataclass
class Target:
    code: str | None = None       # "code de la sécurité sociale"
    text: str | None = None       # "loi n° 2017-1836 du 30 décembre 2017"
    article: str | None = None    # "L131-8", "200 quater", "23"
    inner: list = field(default_factory=list)   # [["sub","I"], ["alinea",[2]], ["phrase",[1]]]
    position: str | None = None   # "debut" | "fin"
    division: str | None = None   # "chapitre II du titre III du livre Ier"

    def copy(self) -> "Target":
        return Target(self.code, self.text, self.article, [list(x) for x in self.inner],
                      self.position, self.division)


def ordinal_list(s: str) -> list[int] | None:
    """'troisième à avant-dernier' -> range marker; 'sixième et avant-dernière' -> list."""
    s = s.strip()
    m = re.fullmatch(rf"({ORD})\s+à\s+({ORD})", s)
    if m:
        return ["range", ORDINALS[m.group(1)], ORDINALS[m.group(2)]]
    parts = re.split(r"\s*,\s*|\s+et\s+", s)
    out = []
    for p in parts:
        if p in ORDINALS:
            out.append(ORDINALS[p])
        else:
            return None
    return out


def parse_locator(phrase: str, base: Target) -> tuple[Target, list[str]]:
    """Locator phrase -> target, relative to the base (context) target.

    The phrase is read innermost-first, as French writes it ("la première phrase
    du deuxième alinéa du 2° du I de l'article L. 136-8 du code …"). Returns the
    target and the list of unrecognised fragments (empty when fully read)."""
    t = base.copy()
    p = " " + phrase.replace("’", "'").strip() + " "
    p = re.sub(r"\b([dlDL])'\s*", r"\1' ", p)
    leftovers: list[str] = []
    cm = None
    for m in CODE_RX.finditer(p):
        cm = m
    changed_text = False
    if cm and "présent code" not in cm.group(0) and not re.search(r"(?:même|présent)\s+code\s*$", cm.group(0)):
        new_code = code_key(cm.group(1))
        if new_code != t.code:
            t.code = new_code
            t.text = None
            changed_text = True
        p = p[:cm.start()] + " " + p[cm.end():]
    p = re.sub(r"\b(?:du|le|au)\s+(?:même|présent)\s+code\b", " ", p, flags=re.I)
    tm = TEXT_RX.search(p)
    if tm:
        t.text = " ".join(next(g for g in tm.groups() if g).split())
        t.code = None
        changed_text = True
        p = p[:tm.start()] + " " + p[tm.end():]
    am = ART_RX.search(p)
    inner_new: list = []
    if am:
        art = norm_art(am.group(1))
        t.inner = []
        t.position = None
        t.article = art
        p = p[:am.start()] + " " + p[am.end():]
    elif changed_text:
        t.article = None
        t.inner = []
    p = re.sub(r"\b(?:du|au|le)\s+(?:même|présent)\s+article\b", " ", p, flags=re.I)
    p = re.sub(r"\bdudit\s+", " du ", p, flags=re.I)
    p = re.sub(r"\b((?:le|la|les|au|aux|du|des|à\s+la))\s+mêmes?\s+", r" \1 ", p, flags=re.I)
    # divisions above the article
    dm = re.search(rf"\b((?:la |le |à la |au |à l'|de la |du )?(?:{ORD}\s+)?(?:sous-paragraphe|paragraphe|sous-section|section|chapitre|titre|livre|partie)\b[^,;:]*)", p, re.I)
    if dm and not am:
        t.division = dm.group(1).strip()
        p = p[:dm.start()] + " " + p[dm.end():]
    # position
    if re.search(r"\b(?:à|a)\s+la\s+fin\b", p, re.I):
        t.position = "fin"
        p = re.sub(r"\b(?:à|a)\s+la\s+fin\s+(?:du|de\s+la|de\s+l'|des)?", " le ", p, flags=re.I)
    elif re.search(r"\bau\s+début\b", p, re.I):
        t.position = "debut"
        p = re.sub(r"\bau\s+début\s+(?:du|de\s+la|de\s+l'|des)?", " le ", p, flags=re.I)
    DET = r"(?:le|la|les|l'|aux?|à\s+la|à\s+l'|du|des|de\s+la|de\s+l'|de)"
    # phrases
    pm = re.search(rf"\b{DET}\s*((?:{ORD})(?:\s*(?:,|et|à)\s*(?:{ORD}))*)\s+phrases?\b", p, re.I)
    pm2 = re.search(rf"\b{DET}\s*({CARD})\s+(premières|dernières)\s+phrases\b", p, re.I)
    if pm:
        ol = ordinal_list(pm.group(1).lower())
        if ol is None:
            leftovers.append(pm.group(0))
        else:
            inner_new.append(["phrase", ol])
        p = p[:pm.start()] + " " + p[pm.end():]
    elif pm2:
        n = CARDINALS.get(pm2.group(1).lower()) or int(pm2.group(1))
        inner_new.append(["phrase", ["range", 1, n] if pm2.group(2).lower() == "premières" else ["range", -n, -1]])
        p = p[:pm2.start()] + " " + p[pm2.end():]
    # alinéas
    am2 = re.search(rf"\b{DET}\s*((?:{ORD})(?:\s*(?:,|et|à)\s*(?:{ORD}))*)\s+alinéas?\b", p, re.I)
    am3 = re.search(rf"\b{DET}\s*({CARD})\s+(premiers|derniers)\s+alinéas\b", p, re.I)
    if am2:
        ol = ordinal_list(am2.group(1).lower())
        if ol is None:
            leftovers.append(am2.group(0))
        else:
            inner_new.append(["alinea", ol])
        p = p[:am2.start()] + " " + p[am2.end():]
    elif am3:
        n = CARDINALS.get(am3.group(1).lower()) or int(am3.group(1))
        inner_new.append(["alinea", ["range", 1, n] if am3.group(2).lower() == "premiers" else ["range", -n, -1]])
        p = p[:am3.start()] + " " + p[am3.end():]
    if re.search(r"\bintitulé\b", p, re.I):
        leftovers.append("heading")
        p = re.sub(r"\b(?:à\s+)?l'\s*intitulé\b", " ", p, flags=re.I)
    # tables ("la quatrième ligne du tableau") are flagged, not resolved
    if re.search(r"\b(?:tableau|lignes?|colonnes?)\b", p, re.I):
        leftovers.append("table")
    # subdivisions: what remains, innermost first: "le c du 3° bis du I"
    subs = []
    for m in re.finditer(rf"(?:^|\s)(?:le|la|les|l'|au|aux|du|des|de|à|en)\s+((?:{SUB_TOKEN})(?:\s*(?:,|et|à)\s*(?:{SUB_TOKEN}))*)(?=\s|,|$)", p, re.I):
        tok = m.group(1).strip()
        if tok.lower() in STOP_TOKENS or re.fullmatch(r"[a-z]{2,}", tok) and tok not in ("aa", "bb", "cc", "dd", "ee", "ff", "gg", "hh", "ii"):
            continue
        subs.append(tok)
    sub_items = []
    for s in subs:
        toks = re.split(r"\s*,\s*|\s+et\s+", s.strip())
        if " à " in s:
            a, b = [x.strip() for x in s.split(" à ", 1)]
            sub_items.append(["subrange", a, b])
        elif len(toks) > 1:
            sub_items.append(["subs", toks])
        else:
            sub_items.append(["sub", toks[0]])
    path = list(reversed(sub_items))
    alinea_phr = list(reversed(inner_new))  # alinéa before phrase
    if path and t.inner and any(x[0] in ("alinea", "phrase") for x in t.inner):
        leftovers.append("subdivision below an alinéa context")
    if path or alinea_phr:
        t.inner = t.inner + path + alinea_phr
    rest = p
    for s in subs:
        rest = re.sub(r"(?<![\w°])" + re.escape(s) + r"(?![\w°])", " ", rest, count=1)
    rest = re.sub(r"\b(?:le|la|les|l'|au|aux|du|des|de|à|a|dudit|même|présent|code|article|dans|sa|leur|rédaction|ainsi|et|en|ce|qui|concerne|y|est|sont|il|résultant|issue|cet|cette)\b", " ", rest, flags=re.I)
    rest = re.sub(r"[\s,;:.'’]+", " ", rest).strip()
    if rest and rest not in ("A", "À"):
        leftovers.append(rest)
    return t, leftovers


STOP_TOKENS = {"la", "le", "les", "de", "du", "des", "un", "une", "en", "et", "au", "aux", "ou", "il", "y", "à", "ce", "sa", "se", "si", "ne", "on", "ni"}


def fan_out(loc: str) -> list[str]:
    """'Au I et à la fin de la seconde phrase du II' -> two locators;
    'aux articles L. 1 et L. 2' -> one locator per article."""
    segs = [x for x in re.split(r"\s*,?\s+(?:et|ainsi\s+qu')\s*(?=(?:à|au|aux|a)\s)|,\s*(?=(?:à|au|aux)\s)", loc) if x.strip()]
    out = []
    for seg in segs or [loc]:
        m = re.search(r"\b(?:des|aux|les)\s+articles\s+((?:" + ART_NUM + r")(?:\s*(?:,|et)\s*(?:" + ART_NUM + r"))+)", seg)
        if m:
            arts = re.split(r"\s*,\s*|\s+et\s+", m.group(1))
            for a in arts:
                out.append(seg[:m.start()] + " de l'article " + a + seg[m.end():])
        else:
            out.append(seg)
    return out


# --- clauses ------------------------------------------------------------------------------
NOUN = r"(?:mots?|taux|montants?|références?|nombres?|chiffres?|dates?|années?|signes?|lettres?|mentions?|pourcentages?|sommes?|expressions?|termes?|millésimes?|seuils?|valeurs?|tarifs?|durées?|coefficients?|rangs?|numéros?|périodes?|abréviations?|proportions?|délais?|fractions?|âges?|limites?|plafonds?|majorations?|minorations?|unités?|quotités?|indices?|caractères?|sigles?|intitulés?|parts?|tranches?|pourcents?|points?|ratios?|niveaux?)"
OCC_PRE = re.compile(rf"^(?:la|les|l')\s*(?P<occ>{ORD}|{CARD})\s+occurrences?\s+(?:du|de la|des|de l')\s*{NOUN}\s*:\s*Q(?P<x>\d+)", re.I)
VERB = r"(?:remplacée?s?|supprimée?s?|insérée?s?|ajoutée?s?|complétée?s?|rédigée?s?|modifiée?s?|abrogée?s?|rétablie?s?|devien(?:nen)?t|renumérotée?s?|déplacée?s?)"


@dataclass
class Op:
    law: str
    article: str
    path: str
    kind: str
    target: dict
    x: str | None = None
    y: str | None = None
    block: list[str] | None = None
    anchor: str | None = None
    occurrence: object = None
    count_words: int | None = None
    what: str | None = None
    leftovers: list[str] = field(default_factory=list)
    source: str = ""
    when: str | None = None


def occurrence_after(rest: str) -> object:
    r = rest.lower()
    if re.search(r"partout où|à chaque occurrence|chaque fois qu|toutes? les occurrences", r):
        return "each"
    m = re.search(rf"\b({CARD})\s+fois\b", r)
    if m:
        return ["count", CARDINALS.get(m.group(1), None) or int(m.group(1))]
    m = re.search(rf"aux\s+({CARD})\s+occurrences", r)
    if m:
        return ["count", CARDINALS.get(m.group(1), None) or int(m.group(1))]
    m = re.search(rf"à\s+la\s+({ORD})\s+occurrence", r)
    if m:
        return ["nth", ORDINALS[m.group(1)]]
    return None


KEY_START = re.compile(r"^,?\s*(?:à|a|au|aux|après|avant|les?|la|l'|le|il|est|sont|sa|son|ses|leur|dans|en)\b", re.I)


def split_clauses(masked: str) -> list[str]:
    """Split on ' et ' / ';' between two clauses that each carry a verb."""
    parts = re.split(r"(\s+et\s*(?=,|\s)|\s*;\s+)", masked)
    out: list[str] = []
    buf = parts[0]
    i = 1
    while i < len(parts):
        sep, nxt = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        right_has_verb = re.search(VERB, nxt, re.I)
        if re.search(VERB, buf, re.I) and right_has_verb and KEY_START.match(nxt) and re.search(r"Q\d", buf):
            out.append(buf)
            buf = nxt.lstrip(", ")
        else:
            buf = buf + sep + nxt
        i += 2
    out.append(buf)
    return out


def interpret(text: str, block: list[str] | None, ctx: Target, law: str, art: str, path: str) -> tuple[list[Op], Target | None]:
    """One instruction line -> ops, and the new context if the line opens one."""
    masked, quotes = mask(text)
    m0 = masked.strip().rstrip(";.").strip()
    ops: list[Op] = []

    def Qv(i: str) -> str:
        return quotes[int(i)]

    def mk(kind: str, loc: str, **kw) -> Op:
        t, left = parse_locator(loc, ctx)
        return Op(law, art, path, kind, asdict(t), leftovers=left, source=text, **kw)

    # context: "… est ainsi modifié :" / "sont ainsi modifiés :" / "est modifié comme suit :"
    mc = re.match(r"^(?P<loc>.*?)\s+(?:est|sont)\s+(?:ainsi\s+)?modifiée?s?(?:\s+comme suit)?\s*:?\s*$", m0, re.I)
    if mc and "Q" not in mc.group("loc"):
        t, left = parse_locator(mc.group("loc"), ctx)
        if left:
            ops.append(Op(law, art, path, "context", asdict(t), leftovers=left, source=text))
        return ops, t
    if re.match(r"^(?:Au|A l'|À l'|A la|À la|Aux|Dans)\b.*:\s*$", m0 + ":" if text.rstrip().endswith(":") else m0) and text.rstrip().endswith(":") and not block and "Q" not in m0:
        # "Au I de l'article X :" opens a context without a verb
        loc = re.sub(r"\s*:\s*$", "", m0)
        t, left = parse_locator(loc, ctx)
        return ops, t

    base = asdict(ctx)
    prev: Op | None = None
    for clause in split_clauses(m0):
        c = clause.strip().strip(",").strip()
        if not c:
            continue
        c = re.sub(r"^[Ee]t\s+", "", c)
        got = clause_op(c, quotes, block, ctx, law, art, path, text)
        for op in got:
            # "Au premier alinéa de l'article X, A … et B …": a clause without a
            # locator of its own inherits the locator of the previous clause
            own = (op.target.get("article") != base.get("article") or op.target.get("inner") != base.get("inner")
                   or op.target.get("code") != base.get("code") or op.target.get("text") != base.get("text"))
            if prev is not None and not own and op.kind not in ("unparsed",):
                pos = op.target.get("position")
                op.target = json.loads(json.dumps(prev.target))
                if pos:
                    op.target["position"] = pos
                op.leftovers = op.leftovers + ["(locator inherited from the previous clause)"]
            prev = op
        ops.extend(got)
    return ops, None


def clause_op(c: str, quotes: list[str], block, ctx: Target, law: str, art: str, path: str, text: str) -> list[Op]:
    def Q(i):
        return quotes[int(i)]

    def mk(kind: str, loc: str, **kw) -> list[Op]:
        out = []
        for seg in fan_out(loc):
            t, left = parse_locator(seg, ctx)
            out.append(Op(law, art, path, kind, asdict(t), leftovers=left, source=text, when=when, **kw))
        if len(out) > 1:
            # segments without their own article share the article of the last one
            last = out[-1].target
            for o in out[:-1]:
                if o.target.get("article") == ctx.article and last.get("article") != ctx.article:
                    o.target["article"] = last["article"]
                    o.target["code"] = last["code"]
                    o.target["text"] = last["text"]
                    o.leftovers = o.leftovers + ["(article shared with the last locator)"]
        return out

    blk = block_text(block) if block else None
    when = None
    md = re.match(r"^(?:Au|À compter du|A compter du|à compter du|au)\s+(1er|\d+)\s+(\w+)\s+(\d{4}),\s*", c)
    if md:
        when = " ".join(md.groups())
        c = c[md.end():]
    m = re.match(rf"^(?P<rel>après|avant)\s+(?:la|le|les|l')\s*(?:(?P<occ>{ORD})\s+occurrence\s+(?:du|de la|des|de l')\s*)?{NOUN}\s*:\s*Q(?P<a>\d+)\s*,\s*la\s+fin\b(?P<loc>.*?)\s+est\s+(?:(?P<sup>supprimée)|ainsi\s+rédigée?\s*:\s*Q(?P<y>\d+))\s*$", c, re.I)
    if m:
        occ = ["nth", ORDINALS[m.group("occ").lower()]] if m.group("occ") else None
        return mk("rewrite_end_after", m.group("loc"), anchor=Q(m.group("a")), y="" if m.group("sup") else Q(m.group("y")), occurrence=occ)
    # leading locator "A la fin du c du 3° bis, " / "Au 2° du I, "
    loc_prefix = ""
    m = re.match(r"^((?:A|À|a|à|Au|Aux|au|aux|Dans|dans|Après|après|Avant|avant)\b[^Q]*?),\s+(?=(?:la|le|les|l'|il|sont|est|après|avant)\b)", c)
    if m and not re.match(r"^(?:Après|après|Avant|avant)\s+(?:la|le|les|l')\s*" + NOUN + r"\s*:", c):
        loc_prefix = m.group(1)
        c2 = c[m.end():]
    else:
        c2 = c

    def where(extra: str = "") -> str:
        return (loc_prefix + " " + extra).strip()

    # occurrence-first: "la première occurrence du mot : Q0 est remplacée par les mots : Q1"
    mo = OCC_PRE.match(c2)
    occ_pre = None
    if mo:
        o = mo.group("occ").lower()
        occ_pre = ["nth", ORDINALS[o]] if o in ORDINALS else ["count", CARDINALS.get(o) or int(o)]
        c2 = f"le mot : Q{mo.group('x')}" + c2[mo.end():]

    # REPLACE words
    m = re.match(rf"^(?P<pre>.*?)(?:la|le|les|l')\s*{NOUN}\s*:\s*Q(?P<x>\d+)(?P<mid>.*?)\s+(?:est|sont)\s+remplacée?s?\s+par\s+(?:la|le|les|l'|un|une|des)\s*{NOUN}\s*:\s*Q(?P<y>\d+)(?P<post>.*)$", c2, re.I)
    if m:
        occ = occ_pre or occurrence_after(m.group("mid") + " " + m.group("post"))
        return mk("replace", where(m.group("pre") + " " + m.group("post")), x=Q(m.group("x")), y=Q(m.group("y")), occurrence=occ)
    # REPLACE with inline phrase/alinea: "… sont remplacés par une phrase ainsi rédigée : Q1"
    m = re.match(rf"^(?:la|le|les|l')\s*{NOUN}\s*:\s*Q(?P<x>\d+)(?P<mid>.*?)\s+(?:est|sont)\s+remplacée?s?\s+par\s+(?:une|deux|trois|des)\s+(?:phrases?|alinéas?)\s+ainsi\s+rédigée?s?\s*:\s*Q(?P<y>\d+)(?P<post>.*)$", c2, re.I)
    if m:
        return mk("replace", where(m.group("post")), x=Q(m.group("x")), y=Q(m.group("y")), occurrence=occ_pre or occurrence_after(m.group("mid")))
    # SUPPRESS words
    m = re.match(rf"^(?P<pre>.*?)(?:la|le|les|l')\s*{NOUN}\s*:\s*Q(?P<x>\d+)(?P<mid>.*?)\s+(?:est|sont)\s+supprimée?s?(?P<post>.*)$", c2, re.I)
    if m:
        return mk("suppress", where(m.group("pre") + " " + m.group("post")), x=Q(m.group("x")), occurrence=occ_pre or occurrence_after(m.group("mid") + " " + m.group("post")))
    # INSERT words after/before anchor
    m = re.match(rf"^(?P<pre>.*?)(?P<rel>après|avant)\s+(?:la|le|les|l')\s*(?:(?P<occ>{ORD})\s+occurrence\s+(?:du|de la|des|de l')\s*)?{NOUN}\s*:\s*Q(?P<a>\d+)(?P<mid>.*?)\s*,?\s*(?:(?:il\s+)?(?:est|sont)\s+(?:insérée?s?|ajoutée?s?)|sont\s+insérés)\s+(?:la|le|les|l'|un|une|des|deux|trois)?\s*{NOUN}?\s*(?:ainsi\s+rédigée?s?)?\s*:\s*Q(?P<y>\d+)(?P<post>.*)$", c2, re.I)
    if m:
        occ = ["nth", ORDINALS[m.group("occ").lower()]] if m.group("occ") else occurrence_after(m.group("mid") + " " + m.group("post"))
        return mk("insert_" + ("after" if m.group("rel").lower() == "après" else "before"),
                   where(m.group("pre") + " " + m.group("mid") + " " + m.group("post")),
                   anchor=Q(m.group("a")), y=Q(m.group("y")), occurrence=occ)
    # "Après le mot : Q0, la fin du X est supprimée / est ainsi rédigée : Q1"
    m = re.match(rf"^(?P<rel>après|avant)\s+(?:la|le|les|l')\s*(?:(?P<occ>{ORD})\s+occurrence\s+(?:du|de la|des|de l')\s*)?{NOUN}\s*:\s*Q(?P<a>\d+)\s*,\s*la\s+fin\b(?P<loc>.*?)\s+est\s+(?:(?P<sup>supprimée)|ainsi\s+rédigée?\s*:\s*Q(?P<y>\d+))\s*$", c2, re.I)
    if m:
        occ = ["nth", ORDINALS[m.group("occ").lower()]] if m.group("occ") else None
        return mk("rewrite_end_after", where(m.group("loc")), anchor=Q(m.group("a")), y="" if m.group("sup") else Q(m.group("y")), occurrence=occ)
    m = re.match(r"^(?:le|la)\s+début\b(?P<loc>.*?)\s+est\s+ainsi\s+rédigée?\s*:\s*Q(?P<y>\d+)\s*$", c2, re.I)
    if m:
        return mk("rewrite_start", where(m.group("loc")), y=Q(m.group("y")))
    # "après la première occurrence du mot : Q0, la fin de la première phrase est ainsi rédigée : Q1"
    m = re.match(rf"^(?P<rel>après|avant)\s+(?:la|le|les|l')\s*(?:(?P<occ>{ORD})\s+occurrence\s+(?:du|de la|des|de l')\s*)?{NOUN}\s*:\s*Q(?P<a>\d+)\s*,\s*la\s+fin\s+(?P<loc>.*?)\s+est\s+ainsi\s+rédigée\s*:\s*Q(?P<y>\d+)\s*$", c2, re.I)
    if m:
        occ = ["nth", ORDINALS[m.group("occ").lower()]] if m.group("occ") else None
        return mk("rewrite_end_after", where(m.group("loc")), anchor=Q(m.group("a")), y=Q(m.group("y")), occurrence=occ)
    # COMPLETE with words / phrase inline: "<loc> est complété par les mots : Q0"
    m = re.match(rf"^(?P<loc>.*?)\s*(?:est|sont)\s+complétée?s?\s+par\s+(?:la|le|les|l'|un|une|des|deux|trois)\s*(?P<what>{NOUN}|phrases?|alinéas?)\s*(?:ainsi\s+rédigée?s?)?\s*:\s*Q(?P<y>\d+)(?P<post>.*)$", c2, re.I)
    if m:
        kind = "complete_phrase" if m.group("what").lower().startswith("phrase") else ("complete_alinea" if m.group("what").lower().startswith("alinéa") else "complete")
        return mk(kind, where(m.group("loc") + " " + m.group("post")), y=Q(m.group("y")))
    m = re.match(rf"^(?P<loc>.*?)\s*(?:il\s+)?(?:est|sont)\s+ajoutée?s?\s+(?:la|le|les|l'|un|une|des|deux|trois)\s*(?P<what>{NOUN}|phrases?)\s*(?:ainsi\s+rédigée?s?)?\s*:\s*Q(?P<y>\d+)(?P<post>.*)$", c2, re.I)
    if m:
        kind = "complete_phrase" if m.group("what").lower().startswith("phrase") else "complete"
        if kind == "complete" and (loc_prefix.lower().startswith("au début") or re.search(r"au début", m.group("loc"), re.I)):
            kind = "prepend"
        return mk(kind, where(m.group("loc") + " " + m.group("post")), y=Q(m.group("y")))
    # INLINE REWRITE: "<loc> est ainsi rédigé(e) : Q0"
    m = re.match(r"^(?P<loc>.*?)\s+(?:est|sont)\s+ainsi\s+rédigée?s?\s*:\s*Q(?P<y>\d+)(?P<post>.*)$", c2, re.I)
    if m:
        return mk("rewrite", where(m.group("loc")), y=Q(m.group("y")))
    # BLOCK ops (the quoted block follows the line)
    if blk is not None or c2.rstrip().endswith(":"):
        b = blk or []
        m = re.match(r"^(?P<loc>.*?)\s+(?:est|sont)\s+ainsi\s+rédigée?s?\s*:?\s*$", c2, re.I)
        if m:
            return mk("rewrite_block", where(m.group("loc")), block=b)
        m = re.match(r"^(?P<loc>.*?)\s+(?:est|sont)\s+(?:ainsi\s+)?rétablie?s?\s*:?\s*$", c2, re.I)
        if m:
            return mk("retablir", where(m.group("loc")), block=b)
        m = re.match(rf"^(?P<loc>.*?)\s+(?:est|sont)\s+remplacée?s?\s+par\s+(?P<n>{CARD}|des|un|une)\s+(?P<what>[^:]*?)\s+ainsi\s+rédigée?s?\s*:?\s*$", c2, re.I)
        if m:
            return mk("replace_block", where(m.group("loc")), block=b, what=m.group("what"))
        m = re.match(rf"^(?:(?P<rel>Après|Avant|après|avant)\s+(?P<loc>.*?),\s*)?(?:il\s+est|sont|est)\s+(?:insérée?s?|ajoutée?s?|créée?s?)\s+(?P<n>{CARD}|des|un|une|les)?\s*(?P<what>.*?)\s+ainsi\s+rédigée?s?\s*:?\s*$", c2, re.I)
        if m:
            rel = (m.group("rel") or "").lower()
            loc = m.group("loc") or ""
            kind = {"après": "insert_block_after", "avant": "insert_block_before"}.get(rel, "add_block_end")
            if not rel and loc_prefix and re.match(r"^(?:Après|après)\b", loc_prefix):
                kind, loc = "insert_block_after", re.sub(r"^(?:Après|après)\s+", "", loc_prefix)
            elif not rel and loc_prefix and re.match(r"^(?:Avant|avant)\b", loc_prefix):
                kind, loc = "insert_block_before", re.sub(r"^(?:Avant|avant)\s+", "", loc_prefix)
            elif not rel and loc_prefix and re.match(r"^(?:Au|au)\s+début\b", loc_prefix):
                kind = "prepend_block"
                loc = loc_prefix
            elif not rel:
                loc = loc_prefix
            t, left = parse_locator(loc, ctx)
            what = m.group("what")
            na = re.match(r"^(?:un\s+|des\s+)?articles?\s+(" + ART_NUM + r"(?:\s*(?:,|et|à)\s*" + ART_NUM + r")*)\s*$", what or "", re.I)
            if na:
                return [Op(law, art, path, "create_article", asdict(t), block=b, what=what, y=na.group(1), anchor=kind, leftovers=left, source=text)]
            op = Op(law, art, path, kind, asdict(t), block=b, what=what, leftovers=left, source=text)
            return [op]
        m = re.match(rf"^(?P<loc>.*?)\s+(?:est|sont)\s+complétée?s?\s+par\s+(?P<n>{CARD}|des|un|une)?\s*(?P<what>.*?)\s+ainsi\s+rédigée?s?\s*:?\s*$", c2, re.I)
        if m:
            what = m.group("what")
            na = re.match(r"^(?:un\s+|des\s+)?articles?\s+(" + ART_NUM + r"(?:\s*(?:,|et|à)\s*" + ART_NUM + r")*)\s*$", what or "", re.I)
            if na:
                t, left = parse_locator(where(m.group("loc")), ctx)
                return [Op(law, art, path, "create_article", asdict(t), block=b, what=what, y=na.group(1), anchor="add_block_end", leftovers=left, source=text)]
            return mk("add_block_end", where(m.group("loc")), block=b, what=what)
        m = re.match(rf"^(?P<loc>.*?)\s+(?:est|sont)\s+(?:remplacée?s?|complétée?s?)\s+par\s+(?:les\s+)?(?:dispositions|mots|alinéas)\s+suivant(?:e?s)?\s*:?\s*$", c2, re.I)
        if m:
            return mk("rewrite_block", where(m.group("loc")), block=b)
    # ABROGATE / structural suppression
    m = re.match(r"^(?P<loc>.*?)\s+(?:est|sont)\s+abrogée?s?(?P<post>.*)$", c2, re.I)
    if m and "Q" not in m.group("loc"):
        return mk("abrogate", where(m.group("loc")))
    m = re.match(r"^(?P<loc>.*?)\s+(?:est|sont)\s+supprimée?s?(?P<post>.*)$", c2, re.I)
    if m and "Q" not in m.group("loc"):
        return mk("delete", where(m.group("loc")))
    # RENUMBER
    m = re.match(r"^(?P<loc>.*?)\s+(?:devien(?:nen)?t|sont\s+renumérotée?s?|est\s+renumérotée?)\s+(?:respectivement\s+)?(?P<new>.*)$", c2, re.I)
    if m and "Q" not in m.group("loc"):
        return mk("renumber", where(m.group("loc")), y=m.group("new").strip())
    m = re.match(r"^(?P<loc>.*?)\s+(?:est|sont)\s+(?:transférée?s?|déplacée?s?|insérée?s?)\s+(?P<new>.*)$", c2, re.I)
    if m and "Q" not in m.group("loc"):
        return mk("move", where(m.group("loc")), y=m.group("new").strip())
    return [Op(law, art, path, "unparsed", asdict(ctx), source=text)]


AMEND_HINT = re.compile(rf"\b(?:est|sont)\s+(?:ainsi\s+)?{VERB}|\bil\s+est\s+(?:inséré|ajouté|créé|rétabli)|\bsont\s+(?:insérés|ajoutés)|\best\s+ajoutée\b|\bEst\s+ajoutée?\b|\bSont\s+ajoutée?s\b|\bdevien(?:nen)?t\b", re.I)


def is_amending(text: str) -> bool:
    masked, _ = mask(text)
    if re.search(r"\b(?:s'applique|sont applicables|est applicable|entrent? en vigueur|est compensée|remet au Parlement|à titre expérimental|demeure|sont rectifiés|est fixée?|sont fixés|est rectifié)\b", masked, re.I) and not re.search(r"(?:remplacée?s?|supprimée?s?|insérée?s?|abrogée?s?|ainsi\s+modifiée?s?|ainsi\s+rédigée?s?|complétée?s?)", masked, re.I):
        return False
    return bool(AMEND_HINT.search(masked))


def walk(node: Node, ctx: Target, law: str, art: str, trail: list[str], out: list[Op]) -> None:
    path = " ".join(trail)
    new_ctx = None
    if node.kind != "root" or node.text:
        text = node.text
        if node.kind == "root":
            text = node.text
        if text:
            if is_amending(text) or (text.rstrip().endswith(":") and node.children and re.search(r"modifi|suit", text)):
                ops, new_ctx = interpret(text, node.block or None, ctx, law, art, path)
                out.extend(ops)
            else:
                out.append(Op(law, art, path, "autonomous", asdict(ctx), source=text))
        for extra in node.extra:
            if extra.startswith("|"):
                continue
            if is_amending(extra):
                ops, _ = interpret(extra, None, new_ctx or ctx, law, art, path)
                out.extend(ops)
            else:
                out.append(Op(law, art, path, "autonomous", asdict(ctx), source=extra))
    child_ctx = new_ctx or ctx
    for ch in node.children:
        walk(ch, child_ctx, law, art, trail + [ch.label], out)


def parse_article(lines: list[str], law: str, art: str, base: Target | None = None) -> list[Op]:
    lines = [l.replace("İ", "I") for l in lines]
    root = build_tree(lines)
    out: list[Op] = []
    walk(root, base or Target(), law, art, [], out)
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("text_json")
    ap.add_argument("--law", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    doc = json.load(open(a.text_json, encoding="utf-8"))
    ops: list[dict] = []
    for art in doc["articles"]:
        if not art["num"]:
            continue
        for op in parse_article(art["lines"], a.law, art["num"]):
            ops.append(asdict(op))
    json.dump(ops, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    from collections import Counter
    print(a.law, len(ops), dict(Counter(o["kind"] for o in ops)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
