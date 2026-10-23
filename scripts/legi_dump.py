"""Print body text of LEGIARTI ids from a legi.sqlite (read-only). Usage: legi_dump.py db out_dir id..."""
import html, re, sqlite3, sys, zlib, os
db = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
os.makedirs(sys.argv[2], exist_ok=True)
for ident in sys.argv[3:]:
    blob, = db.execute("select xml from files where id=?", (ident,)).fetchone()
    xml = zlib.decompress(blob).decode("utf-8", "replace")
    m = re.search(r"<BLOC_TEXTUEL>\s*<CONTENU>(.*?)</CONTENU>", xml, re.S)
    s = m.group(1) if m else ""
    s = re.sub(r"<br\s*/?>", "\n", s); s = re.sub(r"</p>", "\n", s); s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = "\n".join(" ".join(l.split()) for l in s.splitlines() if l.strip())
    open(os.path.join(sys.argv[2], ident + ".txt"), "w").write(s + "\n")
    open(os.path.join(sys.argv[2], ident + ".xml"), "w").write(xml)
