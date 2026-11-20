"""Scrape judul perikop TB dari alkitab.sabda.org -> data/perikop.json.

Bukan tahap build; hasilnya artefak sumber yang dipakai build_content.py.
HTML mentah disimpan di data/sabda/{abbr}_{pasal}.html supaya rerun tidak
memukul server lagi (hapus file kalau memang mau scrape ulang).

Aturan hasil audit 180 pasal (lihat data/reports/perikop_report.json):
  - judul menempel ke anchor ayat sesudahnya di pasal yang sama
  - judul setelah ayat terakhir = milik pasal berikutnya, ayat 1
  - pasal tanpa judul = lanjutan perikop pasal sebelumnya
  - pasal pertama boleh tanpa judul (mis. Kid 1:1) -> ayat 1 tanpa perikop

Output:
  {"translation":"tb","source":"...","books":{"Kejadian":{"1":[[1,"..."],...]}}}
  nilai = daftar [ayat_mulai, judul]; sisa aturan diselesaikan saat build.

    python scrape_perikop.py
"""
from __future__ import annotations

import datetime
import html
import json
import os
import re
import subprocess
import sys
import time

import books

ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(ROOT, "data", "sabda")
OUT = os.path.join(ROOT, "data", "perikop.json")
REPORT = os.path.join(ROOT, "data", "reports", "perikop_report.json")
SRC = os.path.join(ROOT, "data", "json")

URL = "https://alkitab.sabda.org/passage.php?passage={abbr}+{chapter}&ver=tb"
SOURCE = "https://alkitab.sabda.org (Terjemahan Baru)"
UA = "Mozilla/5.0 (alkitab-pwa perikop scrape)"
DELAY = 0.3
RETRIES = 4

# singkatan SABDA, sejajar dengan books.BOOKS
ABBR = [
    "Kej", "Kel", "Im", "Bil", "Ul", "Yos", "Hak", "Rut", "1Sam", "2Sam",
    "1Raj", "2Raj", "1Taw", "2Taw", "Ezr", "Neh", "Est", "Ayb", "Mzm", "Ams",
    "Pkh", "Kid", "Yes", "Yer", "Rat", "Yeh", "Dan", "Hos", "Yl", "Am",
    "Ob", "Yun", "Mi", "Nah", "Hab", "Zef", "Hag", "Za", "Mal", "Mat",
    "Mrk", "Luk", "Yoh", "Kis", "Rom", "1Kor", "2Kor", "Gal", "Ef", "Flp",
    "Kol", "1Tes", "2Tes", "1Tim", "2Tim", "Tit", "Flm", "Ibr", "Yak", "1Ptr",
    "2Ptr", "1Yoh", "2Yoh", "3Yoh", "Yud", "Why",
]
assert len(ABBR) == len(books.BOOKS)

TOK = re.compile(
    r'<div class="paragraphtitle">(?P<title>.*?)</div>'
    r'|<a name="(?P<verse>\d+)"[^>]*>\s*<span class="vref">',
    re.S,
)
ANCHOR = re.compile(r'<a name="(\d+)"[^>]*>\s*<span class="vref">')

# Title case judul perikop: tiap kata kapital, kecuali kata depan (preposisi),
# kata hubung (konjungsi), partikel, dan kata sandang. Kata pertama judul dan
# kata pertama setelah "—" / ":" tetap kapital.
LOWER_WORDS = frozenset(
    """
    di ke dari pada dalam yaitu kepada daripada untuk bagi ala bak tentang
    mengenai terhadap atas oleh dengan
    dan atau serta bahwa tetapi melainkan padahal sedangkan karena sebab lalu
    kemudian jika jikalau kalau asalkan bila manakala sejak semenjak sedari
    sewaktu tatkala ketika sementara begitu sambil selagi selama sehingga
    sampai hingga agar supaya biar pun
    per demi
    si para kaum yang
    """.split()
)
# "sang" boleh kapital kalau merujuk Tuhan/hal sakral (mis. "Sang Tunas"),
# jadi tidak pernah diturunkan.
KEEP_CASE = frozenset({"sang"})

WORD_SEP = re.compile(r"([—:;,.!?]|\s+)")


def eyd_case(text):
    """Kapitalkan tiap kata; sisakan kata tugas tetap huruf kecil."""
    out = []
    start = True  # awal judul atau setelah "—" / ":"
    for piece in WORD_SEP.split(text):
        if not piece or piece.isspace() or piece in "—:;,.!?":
            out.append(piece)
            if piece in ("—", ":"):
                start = True
            continue
        key = piece.lower()
        if key in KEEP_CASE:
            piece = piece[:1].upper() + piece[1:]
        elif start or key not in LOWER_WORDS:
            piece = piece[:1].upper() + piece[1:]
        else:
            piece = piece[:1].lower() + piece[1:]
        out.append(piece)
        start = False
    return "".join(out)


def clean_title(raw):
    """HTML -> teks judul; rapikan spasi/tanda pisah, lalu terapkan title case."""
    title = html.unescape(re.sub(r"<[^>]+>", "", raw)).strip()
    title = re.sub(r"\s*--\s*", "—", title)
    title = re.sub(r"\s+", " ", title)
    title = eyd_case(title)
    if not title or not title[0].isupper():
        raise ValueError(f"judul tidak sesuai EYD: {title!r}")
    return title


def parse_page(page):
    """[[judul, ayat|None], ...] sesuai urutan dokumen. None = judul ekor pasal."""
    page = re.sub(r"<sup>.*?</sup>", "", page, flags=re.S)
    out, cur = [], None
    for m in TOK.finditer(page):
        if m.group("title") is not None:
            title = clean_title(m.group("title"))
            cur = [title, None]
            out.append(cur)
        elif cur is not None and cur[1] is None:
            cur[1] = int(m.group("verse"))
    return out


def resolve_book(name, pages, counts):
    """pages: hasil parse_page per pasal; counts: jumlah ayat per pasal.

    Mengembalikan {pasal: [[ayat, judul], ...]} + daftar peringatan.
    """
    starts, pending, warn = {}, None, []
    for chapter, marks in enumerate(pages, 1):
        n = counts[chapter - 1]
        rows, tail = [], None
        for title, verse in marks:
            if verse is None:
                tail = title
                continue
            if not 1 <= verse <= n:
                raise ValueError(f"{name} {chapter}: judul '{title}' di ayat {verse}, pasal cuma {n} ayat")
            rows.append([verse, title])
        if pending:
            if rows and rows[0][0] == 1:
                if rows[0][1] != pending:
                    warn.append(f"{name} {chapter}: judul ekor '{pending}' != judul ayat 1 '{rows[0][1]}'")
            else:
                rows.insert(0, [1, pending])
        pending = tail
        starts[str(chapter)] = rows
    if pending:
        warn.append(f"{name}: judul ekor '{pending}' setelah pasal terakhir dibuang")
    return starts, warn


def app_counts(book):
    order, name, testament, fname, chapters = book
    sub = "pl" if testament == "PL" else "pb"
    data = json.load(open(os.path.join(SRC, sub, fname + ".json"), encoding="utf-8"))
    got = [len(data["chapters"][str(c)]) for c in range(1, chapters + 1)]
    if len(data["chapters"]) != chapters:
        raise ValueError(f"{name}: {len(data['chapters'])} pasal di data/json, books.py bilang {chapters}")
    return got


def fetch(abbr, chapter):
    path = os.path.join(CACHE, f"{abbr}_{chapter}.html")
    if os.path.exists(path) and os.path.getsize(path) > 2000:
        return open(path, encoding="utf-8", errors="replace").read()
    os.makedirs(CACHE, exist_ok=True)
    url = URL.format(abbr=abbr, chapter=chapter)
    for attempt in range(RETRIES):
        r = subprocess.run(["curl", "-sf", "--max-time", "40", "-A", UA, url],
                           capture_output=True)
        if r.returncode == 0 and b'<span class="vref">' in r.stdout:
            with open(path, "wb") as f:
                f.write(r.stdout)
            time.sleep(DELAY)
            return r.stdout.decode("utf-8", "replace")
        time.sleep(2 ** attempt)
    return None


def main():
    result, warnings, failures = {}, [], []
    total_chapters = total_headings = no_head = starts_late = 0

    for abbr, book in zip(ABBR, books.BOOKS):
        _, name, _, _, chapters = book
        counts = app_counts(book)
        pages = []
        for chapter in range(1, chapters + 1):
            page = fetch(abbr, chapter)
            total_chapters += 1
            if page is None:
                failures.append(f"{name} {chapter}: gagal fetch")
                pages.append([])
                continue
            anchors = [int(x) for x in ANCHOR.findall(page)]
            if len(anchors) != counts[chapter - 1] or anchors != list(range(1, counts[chapter - 1] + 1)):
                failures.append(f"{name} {chapter}: {len(anchors)} anchor SABDA != "
                                f"{counts[chapter - 1]} ayat data/json")
            pages.append(parse_page(page))
        try:
            starts, warn = resolve_book(name, pages, counts)
        except ValueError as e:
            failures.append(str(e))
            continue
        warnings.extend(warn)

        for chapter in range(1, chapters + 1):
            rows = starts[str(chapter)]
            if not rows:
                no_head += 1
            total_headings += len(rows)
            starts_late += sum(1 for verse, _ in rows if verse > 1)
        result[name] = starts
        print(f"{name}: {chapters} pasal, {sum(len(v) for v in starts.values())} judul", flush=True)

    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    report = {
        "chapters": total_chapters,
        "headings": total_headings,
        "chapters_without_heading": no_head,
        "headings_starting_after_verse_1": starts_late,
        "warnings": warnings,
        "failures": failures,
        "fetched_at": datetime.datetime.now().isoformat(timespec="seconds"),
    }
    json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if failures:
        sys.exit(f"GAGAL: {len(failures)} pasal bermasalah, lihat {REPORT}")

    json.dump({"translation": "tb", "source": SOURCE, "scraped_at": report["fetched_at"],
               "books": result},
              open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    print(f"ok: {total_chapters} pasal, {total_headings} judul -> {OUT}")


if __name__ == "__main__":
    main()
