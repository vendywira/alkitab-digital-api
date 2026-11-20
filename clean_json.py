"""Tahap 1: bersihkan lib/{pl,pb}/*.json -> data/json/{pl,pb}/*.json.

Sumber mentah tidak pernah ditulis. Setiap perubahan dicatat di
data/reports/clean_report.json supaya bisa diaudit.

Arti artefak (riset alkitab.sabda.org, lihat docs/specs §5):
  "(5-3)"      nomor ayat Ibrani, isi asli TB      -> dipertahankan
  "Mazmur 5.12–6.5 7"  running head + nomor halaman -> dibuang
  "/"          awal baris cetak                    -> spasi
  "*"          anchor footnote (teksnya tak ada)   -> dibuang
  "--", "- -"  em dash (terpotong page break)      -> "—"
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

import books

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "lib")
DST = os.path.join(ROOT, "data", "json")
REPORT = os.path.join(ROOT, "data", "reports", "clean_report.json")
PATCHES = os.path.join(ROOT, "data", "patches.json")

# "Bilangan 6.23–7.3 40": nama kitab + rentang ayat di halaman + nomor halaman.
# Nomor halaman wajib ada, jadi "Yesaya 53:2" di dalam teks tidak tersentuh.
MARKER = re.compile(
    r"(?<![A-Za-z])(" + "|".join(sorted(map(re.escape, books.SOURCE_MARKER_NAMES), key=len, reverse=True))
    + r")\s+\d+\.\d+(?:[–\-]\d+(?:\.\d+)?)?\s+\d+"
)
BARE_NAMES = "|".join(sorted(map(re.escape, books.SOURCE_MARKER_NAMES), key=len, reverse=True))

# urutan wajib: "- -" dulu, baru "--", supaya em dash hasil page break ikut jadi "—"
RULES = [
    ("dash_wrap", lambda t: t.replace("- -", "--")),
    ("em_dash", lambda t: t.replace("--", "—")),
    ("page_marker", lambda t: MARKER.sub(" ", t)),
    # digit nomor Ibrani hilang saat judul mazmur terpotong: "(5-" + ") Berilah"
    ("paren_lost_digit", lambda t: re.sub(r"\((\d+)-\)", r"(\1-2)", t)),
    ("line_break", lambda t: t.replace("/", " ")),
    ("footnote", lambda t: t.replace("*", "")),
    # running head di page break, mis. '...suara-Nya, Yohanes ' -> nama kitab + spasi ekor.
    # Teks sah tidak pernah berakhir dengan nama kitab + spasi (mis. Yoh 4:1 '...dari pada Yohanes')
    ("book_tail", lambda t: re.sub(r"\s+(?:" + BARE_NAMES + r")\s+$", "", t)),
    ("punct_space", lambda t: re.sub(r"([,;:])(?=[A-Za-z])", r"\1 ", t)),
    ("hyphen_join", lambda t: re.sub(r"(\w)- (\w)", r"\1-\2", t)),
    ("collapse", lambda t: re.sub(r"\s+", " ", t).strip()),
]


def structure(records, log):
    """Rapikan record per pasal sebelum transformasi teks.

    - record yang diawali ")" = sambungan ayat sebelumnya yang terpotong page break
    - record yang diawali penanda halaman: kosong -> buang, ada isi -> sambung
    """
    out = []
    for rec in records:
        t = rec["text"]
        if t.startswith(")") and out:
            log.append(("merge_split", rec["verse"], out[-1]["text"], out[-1]["text"] + t))
            out[-1]["text"] += t
            continue
        if MARKER.match(t):
            rest = MARKER.sub("", t).strip()
            if not rest:
                log.append(("drop_heading", rec["verse"], t, ""))
                continue
            if out:
                log.append(("merge_heading", rec["verse"], t, out[-1]["text"] + " " + t))
                out[-1]["text"] = out[-1]["text"] + " " + t
                continue
        out.append(dict(rec))
    return out


def clean_text(text, counts):
    for name, fn in RULES:
        new = fn(text)
        if new != text:
            counts[name] += 1
            text = new
    return text


def load_patches():
    if not os.path.exists(PATCHES):
        return {}
    return json.load(open(PATCHES, encoding="utf-8"))


def main():
    dry = "--dry-run" in sys.argv
    patches = load_patches()
    report = {"total_verses_in": 0, "total_verses_out": 0, "counts": Counter(),
              "patched": [], "records": [], "missing": []}
    used_patches = set()

    for order, name, testament, fname, chapters in books.BOOKS:
        sub, path = books.path_parts((order, name, testament, fname, chapters))
        src = json.load(open(os.path.join(SRC, sub, path), encoding="utf-8"))
        got = sorted(src["chapters"], key=int)
        if len(got) != chapters:
            sys.exit(f"GAGAL {name}: {len(got)} pasal di sumber, books.py bilang {chapters}")

        out_chapters = {}
        for ch in got:
            # urutan file, BUKAN urutan nomor: record sambungan page break punya
            # nomor ayat salah (1) dan harus tetap menempel ke tetangganya
            recs = src["chapters"][ch]
            report["total_verses_in"] += len(recs)
            log = []
            recs = structure(recs, log)

            for rec in recs:
                before = rec["text"]
                rec["text"] = clean_text(before, report["counts"])
                if rec["text"] != before:
                    log.append(("rewrite", rec["verse"], before, rec["text"]))

            verses = {r["verse"]: r["text"] for r in recs}
            if len(verses) != len(recs):
                sys.exit(f"GAGAL {name} {ch}: nomor ayat duplikat setelah pembersihan")

            for v in range(1, (max(verses) if verses else 0) + 1):
                if v in verses:
                    continue
                key = f"{fname}/{ch}/{v}"
                if key not in patches:
                    report["missing"].append(key)
                    continue
                verses[v] = clean_text(patches[key], report["counts"])
                used_patches.add(key)
                report["patched"].append(key)

            # patch yang menimpa ayat yang ada = ayat rusak di sumber
            for key, text in patches.items():
                p_fname, p_ch, p_v = key.split("/")
                v = int(p_v)
                if key in used_patches or p_fname != fname or int(p_ch) != int(ch) or v not in verses:
                    continue
                before = verses[v]
                verses[v] = clean_text(text, report["counts"])
                used_patches.add(key)
                report["patched"].append(key)
                log.append(("replace", v, before, verses[v]))

            out = [{"verse": v, "text": verses[v]} for v in sorted(verses)]
            if any(not r["text"] for r in out):
                sys.exit(f"GAGAL {name} {ch}: ada ayat kosong")
            out_chapters[ch] = out
            report["total_verses_out"] += len(out)
            for action, verse, before, after in log:
                report["records"].append({"book": fname, "chapter": int(ch), "verse": verse,
                                          "action": action, "before": before, "after": after})

        if not dry:
            dest = os.path.join(DST, sub)
            os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, path), "w", encoding="utf-8") as fh:
                json.dump({"book": src["book"], "chapters": out_chapters}, fh,
                          ensure_ascii=False, indent=2, sort_keys=False)
                fh.write("\n")
        print(f"{name:18s} {len(out_chapters):3d} pasal  "
              f"{report['total_verses_out']:6d} ayat kumulatif")

    unused = sorted(set(patches) - used_patches)
    if unused:
        sys.exit(f"GAGAL: patch tidak terpakai (sumber sudah punya): {unused}")
    if report["missing"]:
        print("\nAYAT HILANG tanpa patch:")
        for key in report["missing"]:
            print("  ", key)
        sys.exit(f"GAGAL: {len(report['missing'])} ayat hilang; isi data/patches.json dari sabda.org")

    report["counts"] = dict(report["counts"])
    print(f"\nmasuk {report['total_verses_in']} -> keluar {report['total_verses_out']} ayat")
    print("aturan:", json.dumps(report["counts"], indent=2))
    print("patch dipakai:", report["patched"])
    if not dry:
        os.makedirs(os.path.dirname(REPORT), exist_ok=True)
        json.dump(report, open(REPORT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("laporan:", os.path.relpath(REPORT, ROOT))


if __name__ == "__main__":
    main()
