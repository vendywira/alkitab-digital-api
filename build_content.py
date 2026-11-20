"""Tahap 2: data/json/*.json -> data/output/{alkitab_content.db, alkitab_tb_v{N}.zip, manifest.json}.

Kontrak: alkitab-pwa/docs/backend.md §4-§7. Jalankan manual, jangan via HTTP.

    python clean_json.py            # tahap 1
    python build_content.py --version 1
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import sqlite3
import sys
import zipfile

import books

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "data", "json")
OUT = os.path.join(ROOT, "data", "output")
SCHEMA = os.path.join(ROOT, "schema_content.sql")
PERIKOP = os.path.join(ROOT, "data", "perikop.json")
DB_NAME = "alkitab_content.db"
DB_SCHEMA_VERSION = 2

# sisa artefak cetak yang tidak boleh lolos ("(5-3)" nomor Ibrani = isi asli, jadi tidak dicek)
LEFTOVER = re.compile(r"[/*]|--|(?<![A-Za-z])(?:" + "|".join(
    sorted(map(re.escape, books.SOURCE_MARKER_NAMES), key=len, reverse=True)) + r")\s+\d+\.\d+")


def verse_id(book_order, chapter, verse):
    return book_order * 1_000_000 + chapter * 1_000 + verse


def load_chapters(book):
    order, name, testament, fname, chapter_count = book
    sub, path = books.path_parts(book)
    data = json.load(open(os.path.join(SRC, sub, path), encoding="utf-8"))
    chapters = data["chapters"]
    if len(chapters) != chapter_count:
        sys.exit(f"GAGAL {name}: {len(chapters)} pasal, books.py bilang {chapter_count}")
    return chapters


def load_perikop():
    """data/perikop.json -> {kitab: {pasal: [[ayat_mulai, judul], ...]}}."""
    if not os.path.exists(PERIKOP):
        sys.exit("GAGAL: data/perikop.json belum ada. Jalankan scrape_perikop.py dulu.")
    data = json.load(open(PERIKOP, encoding="utf-8"))["books"]
    missing = [b[1] for b in books.BOOKS if b[1] not in data]
    if missing:
        sys.exit(f"GAGAL: perikop tidak lengkap, kitab hilang: {', '.join(missing)}")
    return data


def pericopes_for_chapters(name, starts, chapters, chapter_count):
    """{(pasal, ayat): judul} — ayat sebelum judul pertama mewarisi judul sebelumnya.

    Judul ekor pasal sudah dipindahkan scrape_perikop.py ke pasal berikutnya.
    """
    if len(starts) != chapter_count:
        sys.exit(f"GAGAL {name}: perikop {len(starts)} pasal, books.py bilang {chapter_count}")
    out, carry = {}, None
    for ch in range(1, chapter_count + 1):
        marks = dict(starts[str(ch)])
        verses = sorted(r["verse"] for r in chapters[str(ch)])
        if any(v not in verses for v in marks):
            sys.exit(f"GAGAL {name} {ch}: judul perikop di ayat yang tidak ada {sorted(set(marks) - set(verses))}")
        for v in verses:
            if v in marks:
                carry = marks[v]
                if not carry:
                    sys.exit(f"GAGAL {name} {ch}:{v}: judul perikop kosong")
            out[(ch, v)] = carry
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", type=int, required=True)
    ap.add_argument("--force", action="store_true", help="izinkan versi sama/lebih kecil dari manifest lama")
    args = ap.parse_args()

    manifest_path = os.path.join(OUT, "manifest.json")
    if os.path.exists(manifest_path) and not args.force:
        old = json.load(open(manifest_path, encoding="utf-8"))["content"]["version"]
        if args.version <= old:
            sys.exit(f"GAGAL: version {args.version} <= manifest lama ({old}). Pakai --force kalau memang mau.")

    os.makedirs(OUT, exist_ok=True)
    db_path = os.path.join(OUT, DB_NAME)
    if os.path.exists(db_path):
        os.remove(db_path)

    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    perikop = load_perikop()
    db = sqlite3.connect(db_path)
    db.executescript(open(SCHEMA, encoding="utf-8").read())
    # drift di klien membandingkan `PRAGMA user_version` dengan schemaVersion-nya;
    # tanpa ini drift menganggap DB lama dan menjalankan migrasi.
    db.execute(f"PRAGMA user_version = {DB_SCHEMA_VERSION}")
    db.execute("INSERT INTO translations VALUES (?,?,?,?,?,?)",
               ("tb", "Terjemahan Baru", "TB", "id", args.version, now))

    total = 0
    for book in books.BOOKS:
        order, name, testament, fname, chapter_count = book
        chapters = load_chapters(book)
        pericope_of = pericopes_for_chapters(name, perikop[name], chapters, chapter_count)
        db.execute("INSERT INTO books VALUES (?,?,?,?,?)", (order, name, testament, order, chapter_count))
        rows = []
        for chapter in sorted(chapters, key=int):
            ch = int(chapter)
            for rec in chapters[chapter]:
                v, text = rec["verse"], rec["text"].strip()
                if not text:
                    sys.exit(f"GAGAL {name} {ch}:{v}: teks kosong")
                if LEFTOVER.search(text):
                    sys.exit(f"GAGAL {name} {ch}:{v}: artefak tersisa -> {text[:80]!r}")
                rows.append((verse_id(order, ch, v), order, ch, v, text, pericope_of[(ch, v)]))
        db.executemany("INSERT INTO verses VALUES (?,?,?,?,?,?)", rows)
        total += len(rows)
        print(f"{name:18s} {chapter_count:3d} pasal  {len(rows):5d} ayat  (kumulatif {total})")

    db.commit()
    ok = db.execute("PRAGMA integrity_check").fetchone()[0]
    dup = db.execute("SELECT COUNT(*) FROM (SELECT book_id, chapter, verse FROM verses "
                     "GROUP BY 1,2,3 HAVING COUNT(*) > 1)").fetchone()[0]
    db.close()
    if ok != "ok":
        sys.exit(f"GAGAL: integrity_check = {ok}")
    if dup:
        sys.exit(f"GAGAL: {dup} (book, chapter, verse) duplikat")
    print(f"total {total} ayat, integrity ok")

    zip_name = f"alkitab_tb_v{args.version}.zip"
    zip_path = os.path.join(OUT, zip_name)
    for stale in os.listdir(OUT):
        if stale.endswith(".zip") and stale != zip_name:
            os.remove(os.path.join(OUT, stale))
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.write(db_path, DB_NAME)

    size = os.path.getsize(zip_path)
    digest = hashlib.sha256()
    with open(zip_path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)

    manifest = {
        "translation": {"id": "tb", "name": "Terjemahan Baru", "abbreviation": "TB", "language": "id"},
        "content": {
            "version": args.version,
            "last_updated": now,
            "zip_url": f"/api/download/{zip_name}",
            "zip_size": size,
            "zip_checksum": "sha256:" + digest.hexdigest(),
            "db_filename": DB_NAME,
            "db_schema_version": DB_SCHEMA_VERSION,
        },
        "audio_packages": [],
    }
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    print(f"zip  {zip_name}  {size} byte  sha256:{digest.hexdigest()}")
    print(f"manifest {os.path.relpath(manifest_path, ROOT)}")


if __name__ == "__main__":
    main()
