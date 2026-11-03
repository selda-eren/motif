"""Prepare The Time Machine (Project Gutenberg #35) for MOTIF without tuning anything to the book.

Inputs : source/pg35.original.txt  (byte-exact download, never modified)
Outputs: data/texts/the_time_machine.txt / .json   processing text + book metadata
         source/chapters.json, source/SOURCE.json, source/passages.json

What is removed from the processing text (and nothing else): the Project Gutenberg header and footer,
the title block and table of contents, and the chapter heading lines (numeral + title). Line endings are
normalised CRLF -> LF because the existing segmenter splits paragraphs on '\\n\\s*\\n'. Chapter headings are
kept as metadata (title, original line numbers, offsets in the processing text) so that every passage can be
mapped to its chapter(s). Passage boundaries come from motif.text.segment with its default settings.
"""
import hashlib, json, re, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[2]
sys.path.insert(0, str(REPO / "backend"))
from motif.text import segment  # noqa: E402

raw_bytes = (ROOT / "source" / "pg35.original.txt").read_bytes()
sha_original = hashlib.sha256(raw_bytes).hexdigest()
lines = raw_bytes.decode("utf-8").replace("\r\n", "\n").split("\n")
start = next(i for i, l in enumerate(lines) if l.startswith("*** START OF THE PROJECT GUTENBERG EBOOK"))
end = next(i for i, l in enumerate(lines) if l.startswith("*** END OF THE PROJECT GUTENBERG EBOOK"))
ROMAN = re.compile(r"^\s*(I|II|III|IV|V|VI|VII|VIII|IX|X|XI|XII|XIII|XIV|XV|XVI)\.\s*$")
heads = []  # (line_index, numeral, title)
for i in range(start + 1, end):
    m = ROMAN.match(lines[i])
    if m:
        j = i + 1
        while not lines[j].strip(): j += 1
        heads.append((i, m.group(1), lines[j].strip(), j))
epi = next(i for i in range(heads[-1][0] + 1, end) if lines[i].strip() == "Epilogue")
heads.append((epi, "Epilogue", "Epilogue", epi))
assert len(heads) == 17, len(heads)

chapters, parts, pos = [], [], 0
for n, (hl, numeral, title, tl) in enumerate(heads):
    stop = heads[n + 1][0] if n + 1 < len(heads) else end
    body = "\n".join(lines[tl + 1: stop]).strip("\n")
    body = body.strip()
    if parts: pos += 2  # the "\n\n" separator
    chapters.append({"number": n + 1, "numeral": numeral, "title": title, "heading_line": hl + 1,
                     "body_first_line": tl + 2, "body_last_line": stop, "start": pos, "end": pos + len(body),
                     "words": len(body.split())})
    parts.append(body); pos += len(body)
text = "\n\n".join(parts) + "\n"
(REPO / "data" / "texts" / "the_time_machine.txt").write_text(text)
sha_text = hashlib.sha256(text.encode()).hexdigest()

meta = {"id": "the_time_machine", "title": "The Time Machine", "author": "H. G. Wells", "genre": "fiction",
        "source": "Project Gutenberg eBook #35 (first published 1895)", "source_url": "https://www.gutenberg.org/ebooks/35",
        "license": "Public domain", "text_file": "the_time_machine.txt"}
(REPO / "data" / "texts" / "the_time_machine.json").write_text(json.dumps(meta, indent=1, ensure_ascii=False) + "\n")

passages = segment(text)
def chapters_of(p):
    out = []
    for c in chapters:
        lo, hi = max(p.start, c["start"]), min(p.end, c["end"])
        if hi > lo: out.append({"chapter": c["number"], "numeral": c["numeral"], "title": c["title"], "chars": hi - lo})
    return out
plist = [{"index": p.index, "start": p.start, "end": p.end, "words": len(p.text.split()), "chapters": chapters_of(p),
          "sha256": hashlib.sha256(p.text.encode()).hexdigest()} for p in passages]
(ROOT / "source" / "chapters.json").write_text(json.dumps(chapters, indent=1, ensure_ascii=False))
(ROOT / "source" / "passages.json").write_text(json.dumps(plist, indent=1, ensure_ascii=False))
(ROOT / "source" / "SOURCE.json").write_text(json.dumps({
    "title": "The Time Machine", "author": "H. G. Wells", "url": "https://www.gutenberg.org/ebooks/35",
    "downloaded_from": "https://www.gutenberg.org/cache/epub/35/pg35.txt", "download_date": "2026-11-01",
    "edition_note": "Project Gutenberg eBook #35, released 2004-10-02, most recently updated 2026-06-16 (per the file header)",
    "original_file": "source/pg35.original.txt", "original_sha256": sha_original, "original_bytes": len(raw_bytes),
    "processing_text": "data/texts/the_time_machine.txt", "processing_sha256": sha_text,
    "removed": ["Project Gutenberg header (lines 1-%d)" % (start + 1), "Project Gutenberg footer (lines %d-end)" % (end + 1),
                "title block and table of contents", "17 chapter heading blocks (numeral and title), kept in chapters.json",
                "CRLF line endings normalised to LF"],
    "words": len(text.split()), "chapters": len(chapters), "passages": len(passages)}, indent=1))
print(json.dumps({"words": len(text.split()), "chapters": len(chapters), "passages": len(passages), "sha256": sha_text}))
for c in chapters: print(c["numeral"], c["title"], c["words"])
print("passage words: min", min(p["words"] for p in plist), "max", max(p["words"] for p in plist))
print("passages spanning >1 chapter:", sum(len(p["chapters"]) > 1 for p in plist))
