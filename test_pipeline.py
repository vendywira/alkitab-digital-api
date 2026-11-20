"""Cek cepat: aturan pembersihan + invariant DB hasil build. Tanpa framework.

    python test_pipeline.py
"""
import os
import sqlite3
import sys

import books
from build_content import LEFTOVER, verse_id
from clean_json import clean_text, structure
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))


def test_rules():
    c = Counter()
    assert clean_text("Yoab--memang Yoab", c) == "Yoab—memang Yoab"
    assert clean_text("kedua belas- -yakni", c) == "kedua belas—yakni"
    assert clean_text("anak- anak itu", c) == "anak-anak itu"
    assert clean_text("katanya: /\"Aku haus!\"*", c) == "katanya: \"Aku haus!\""
    assert clean_text("Adar--,pada hari", c) == "Adar—, pada hari"
    assert clean_text("...Musa: Bilangan 6.23–7.3 40", c) == "...Musa:"
    # nomor ayat Ibrani = isi asli, tidak boleh hilang
    assert clean_text("(22-44) Hanya bukit", c) == "(22-44) Hanya bukit"
    # digit hilang saat judul mazmur terpotong
    assert clean_text("Mazmur Daud. (5-) Berilah telinga", c) == "Mazmur Daud. (5-2) Berilah telinga"
    assert clean_text("murid-Ku* Yohanes ", c) == "murid-Ku"
    print("aturan pembersihan ok")


def test_structure():
    log = []
    # judul mazmur terpotong page break: record ke-2 menyambung record ke-1
    recs = [{"verse": 1, "text": "Mazmur Daud. (5-"},
            {"verse": 2, "text": ") Berilah telinga"}]
    out = structure(recs, log)
    assert [r["verse"] for r in out] == [1]
    assert clean_text(out[0]["text"], Counter()) == "Mazmur Daud. (5-2) Berilah telinga"

    # record heading kosong dibuang, record sambungan menempel ke ayat sebelumnya
    recs = [{"verse": 9, "text": "nama Yabes itu"},
            {"verse": 1, "text": "Tawarikh 4.10–15 15 diberi ibunya kepadanya"},
            {"verse": 1, "text": "Tawarikh 2.52–3.3 11"}]
    out = structure(recs, log)
    assert [r["verse"] for r in out] == [9]
    assert out[0]["text"] == "nama Yabes itu Tawarikh 4.10–15 15 diberi ibunya kepadanya"
    assert clean_text(out[0]["text"], Counter()) == "nama Yabes itu diberi ibunya kepadanya"
    print("perapian record ok")


def test_db():
    db = os.path.join(ROOT, "data", "output", "alkitab_content.db")
    if not os.path.exists(db):
        print("DB belum ada, lewati cek DB")
        return
    con = sqlite3.connect(db)
    assert con.execute("SELECT COUNT(*) FROM books").fetchone()[0] == 66
    assert con.execute("SELECT COUNT(*) FROM translations").fetchone()[0] == 1
    total = con.execute("SELECT COUNT(*) FROM verses").fetchone()[0]
    assert total > 30000, total
    assert con.execute("SELECT COUNT(*) FROM (SELECT book_id, chapter, verse FROM verses "
                       "GROUP BY 1,2,3 HAVING COUNT(*) > 1)").fetchone()[0] == 0
    for bid, ch, v, text in con.execute("SELECT book_id, chapter, verse, text FROM verses"):
        assert not LEFTOVER.search(text), (bid, ch, v, text[:80])
        assert text == text.strip() and text
    assert con.execute("SELECT text FROM verses WHERE id=?", (verse_id(1, 1, 1),)).fetchone()[0] \
        == "Pada mulanya Allah menciptakan langit dan bumi."
    assert con.execute("SELECT COUNT(*) FROM verses WHERE book_id=19 AND chapter=119").fetchone()[0] == 176

    def pericope(b, c, v):
        return con.execute("SELECT pericope FROM verses WHERE book_id=? AND chapter=? AND verse=?",
                           (b, c, v)).fetchone()[0]

    kej1 = pericope(1, 1, 1)
    assert kej1 == "Allah Menciptakan Langit dan Bumi serta Isinya"
    # pasal tanpa judul mewarisi judul pasal sebelumnya, termasuk pasal berikutnya
    assert pericope(1, 1, 31) == kej1
    assert pericope(1, 2, 1) == kej1
    assert pericope(1, 2, 8) == "Manusia dan Taman Eden"
    assert pericope(40, 5, 13) == "Garam Dunia dan Terang Dunia"
    assert pericope(37, 2, 1) == "Kemegahan Bait Suci yang Baru"
    # judul sudah dinormalkan ke EYD (bukan Title Case tiap kata)
    assert pericope(15, 3, 8) == "Perletakan Dasar Bait Suci"
    assert pericope(27, 7, 1) == "Keempat Binatang dan Anak Manusia"
    assert pericope(38, 3, 1) == "Penglihatan Keempat: Imam Besar Yosua"
    assert pericope(1, 35, 16) == "Kelahiran Benyamin—Rahel Mati"
    bad_title = con.execute(
        "SELECT book_id, chapter, verse, pericope FROM verses "
        "WHERE pericope LIKE '%--%' OR pericope LIKE '%  %' "
        "OR pericope LIKE ' %' OR pericope LIKE '% ' OR pericope GLOB '[a-z]*'"
    ).fetchall()
    assert not bad_title, bad_title
    # kata tugas harus kecil di tengah judul (title case EYD)
    for word in ("Dan", "Di", "Dari", "Yang", "Untuk", "Pada", "Dengan"):
        hit = con.execute(
            "SELECT pericope FROM verses WHERE pericope GLOB ?", (f"* {word} *",)
        ).fetchall()
        assert not hit, (word, hit[:3])
    # hanya superskripsi Kidung Agung 1:1 yang boleh tanpa perikop
    assert pericope(22, 1, 1) is None
    assert con.execute("SELECT COUNT(*) FROM verses WHERE pericope IS NULL").fetchone()[0] == 1
    bad = con.execute("SELECT book_id, chapter, verse FROM verses WHERE pericope IS NULL "
                      "AND NOT (book_id=22 AND chapter=1 AND verse=1)").fetchall()
    assert not bad, bad
    assert con.execute("SELECT COUNT(*) FROM verses WHERE pericope=''").fetchone()[0] == 0
    for order, name, testament, fname, chapters in books.BOOKS:
        got = con.execute("SELECT COUNT(DISTINCT chapter) FROM verses WHERE book_id=?", (order,)).fetchone()[0]
        assert got == chapters, (name, got, chapters)
    print(f"DB ok: {total} ayat, 66 kitab, 0 duplikat, 0 artefak")


def test_perikop():
    from scrape_perikop import clean_title, parse_page, resolve_book

    # Title case: em dash tanpa spasi, spasi dirapikan
    assert clean_title("Musa  menghadap -- Firaun") == "Musa Menghadap—Firaun"
    assert clean_title("Perletakan dasar bait suci") == "Perletakan Dasar Bait Suci"
    assert clean_title("Keempat binatang dan anak manusia") == "Keempat Binatang dan Anak Manusia"
    assert clean_title("Penglihatan keempat: imam besar Yosua") == "Penglihatan Keempat: Imam Besar Yosua"
    # kata tugas (depan/hubung/partikel/sandang) tetap huruf kecil di tengah
    assert clean_title("Yesus dan hukum Taurat di gunung itu") == "Yesus dan Hukum Taurat di Gunung Itu"
    assert clean_title("raja-raja dari Yehuda serta para imam") == "Raja-raja dari Yehuda serta para Imam"
    # kata pertama setelah "—" dan ":" tetap kapital
    assert clean_title("Ahab melawan -- nabi TUHAN") == "Ahab Melawan—Nabi TUHAN"
    # "sang" tidak pernah diturunkan (gelar sakral)
    assert clean_title("Kerajaan sang Tunas") == "Kerajaan Sang Tunas"
    try:
        clean_title("")
    except ValueError:
        pass
    else:
        raise AssertionError("judul kosong harus ditolak")

    anchor = '<a name="{}" href="x"><span class="vref">1:{}</span></a>'
    page = ('<div class="paragraphtitle">A &amp; B</div>' + anchor.format(1, 1)
            + ' teks <sup><a href="#n1">1</a></sup>'
            + '<div class="paragraphtitle">C</div>' + anchor.format(9, 9))
    assert parse_page(page) == [["A & B", 1], ["C", 9]]

    # judul tanpa anchor berikutnya = milik pasal berikutnya ayat 1
    tail = anchor.format(1, 1) + '<div class="paragraphtitle">Ekor</div>'
    assert parse_page(tail) == [["Ekor", None]]
    starts, warn = resolve_book("X", [parse_page(tail), []], [20, 10])
    assert starts == {"1": [], "2": [[1, "Ekor"]]} and warn == []

    # pasal tanpa judul tetap kosong; build yang mewarisi judul sebelumnya
    starts, _ = resolve_book("X", [parse_page('<div class="paragraphtitle">A</div>' + anchor.format(1, 1)), []], [20, 10])
    assert starts["2"] == []

    # judul di luar jumlah ayat = gagal keras
    try:
        resolve_book("X", [parse_page('<div class="paragraphtitle">A</div>' + anchor.format(21, 21))], [20])
    except ValueError:
        pass
    else:
        raise AssertionError("judul di ayat 21 harus ditolak")
    print("perikop ok")

if __name__ == "__main__":
    test_rules()
    test_structure()
    test_perikop()
    test_db()
    sys.exit(0)
