# Design — Alkitab API (backend + konversi data)

Tanggal: 2026-11-20
Kontrak utama: `alkitab-pwa/docs/backend.md` (spec Flask). Dokumen ini hanya mencatat
penyimpangan yang disetujui dan detail konversi data yang tidak diatur spec.

## 1. Tujuan

PWA (`alkitab-pwa`) tidak boleh membaca Alkitab dari API per-ayat. Ia mengunduh satu
paket: `manifest.json` + ZIP berisi `alkitab_content.db` (SQLite read-only), verifikasi
SHA-256, lalu semua query jalan lokal.

Backend menghasilkan paket itu dari sumber JSON di `alkitab-api/lib/{pl,pb}`.

## 2. Non-goal

- Tidak ada endpoint per-ayat, pencarian, atau audio.
- Tidak ada user data (`highlights`, `bookmarks`) di DB konten — itu milik `user_data.db` Flutter.
- Tidak ada auto-rebuild dari HTTP. Build selalu manual/SSH/cron.

## 3. Penyimpangan dari spec (disetujui)

| Spec | Keputusan |
|---|---|
| Folder `alkitab-backend/` | Pakai `alkitab-api/` (sudah berisi `lib/`) |
| Sumber JSON disalin ke `data/json/` tiap build | `lib/` tetap immutable; hasil bersih ditulis ke `data/json/` oleh tahap 1 |
| Satu script `build_content.py` | Dua tahap: `clean_json.py` lalu `build_content.py` (opsi B, agar diff pembersihan bisa diaudit) |

## 4. Alur (dua tahap)

```
lib/pl/*.json, lib/pb/*.json      (sumber mentah, tidak pernah ditulis)
        |  python clean_json.py
        v
data/json/pl/*.json, data/json/pb/*.json   (bersih, bentuk sama)
data/reports/clean_report.json             (setiap perubahan, per ayat)
        |  python build_content.py --version N
        v
data/output/alkitab_content.db
data/output/alkitab_tb_v{N}.zip
data/output/manifest.json
```

Bentuk JSON dipertahankan (`{"book": "...", "chapters": {"1": [{"verse":1,"text":"..."}]}}`)
supaya bisa di-diff langsung terhadap `lib/`. `data/json/` deterministik: key diurutkan,
tanpa timestamp, indent 2.

## 5. Tahap 1 — `clean_json.py`

### 5.1 Arti artefak (riset alkitab.sabda.org, 2026-11-20)

Dibandingkan langsung dengan TB di sabda.org (`passage.php?mode=print`, `bible.php?tab=text`):

| Artefak | Arti | Tindakan |
|---|---|---|
| `(5-3)`, `(22-44)` | Nomor ayat **Ibrani** — isi asli TB, sabda.org juga menampilkannya | dipertahankan |
| `Bilangan 6.23–7.3 40` | **Running head + nomor halaman** edisi cetak (nomor halaman naik monoton per kitab); sabda tidak memuatnya | dibuang |
| `/` | Awal baris/paragraf cetak; selalu di posisi 0 atau setelah spasi, diikuti `"`/huruf besar | jadi spasi |
| `*` | Anchor footnote; teks catatannya tidak ada di sumber (2.052 ayat ber-`/` juga ber-`*`) | dibuang |
| `--`, `- -` | Em dash cetak, sebagian terpotong page break (`kedua belas- -yakni`) | `—` |
| `...suara-Nya, Yohanes ` | Nama kitab sisa running head di akhir ayat (selalu diikuti spasi ekor) | dibuang |

### 5.2 Temuan di sumber (31.108 record)

| Temuan | Jumlah |
|---|---|
| Penanda halaman (nama kitab + rentang ayat + nomor halaman) | 3.801 |
| Nomor Ibrani `(c-v)` (isi asli, dipertahankan) | 1.319 ayat |
| `/` dan `*` | 2.052 ayat (selalu berpasangan) |
| `--` / `- -` | 590 / 35 ayat |
| Kata terpotong `anak- anak` | 2.274 ayat |
| Nama kitab di ekor ayat | 59 |
| Record sambungan page break berawalan `)` | 3 (Mzm 5, 8, 68) |
| Record berawalan penanda halaman | 4 (1 Raj 1, 1 Taw 2/3/4) |
| Ayat tidak ada di sumber, diisi dari sabda | 1 (1 Raj 4:32) |

### 5.3 Aturan (urut, deterministik, tiap temuan dicatat)

Perapian record dulu, baru transformasi teks (urutan ini wajib):

1. Record berawalan `)` → sambungan ayat sebelumnya (page break), teks ditempel, record dibuang (3).
2. Record berawalan penanda halaman → setelah penanda dibuang: kosong = buang (2: 1 Taw 2, 1 Taw 3); ada isi = sambung ke record sebelumnya (2: 1 Raj 1:30, 1 Taw 4:9).
3. Transformasi teks: `- -`→`--` → `--`→`—` → buang penanda halaman → `(5-)`→`(5-2)` (digit hilang saat judul mazmur terpotong) → `/`→spasi → buang `*` → buang nama kitab + spasi ekor → sisip spasi setelah `,;:` sebelum huruf → `kata- kata`→`kata-kata` → rapatkan spasi.
4. Pasal yang masih punya nomor ayat duplikat → gagal keras (harus 0 setelah aturan 1–2).
5. Ayat yang tidak ada di rentang 1..max → diisi dari `data/patches.json`; kalau tidak ada patch → gagal keras dengan daftar ayat. Patch yang tidak terpakai juga gagal (mencegah patch basi).

### 5.4 Patches dari sabda.org

Hanya ayat yang tidak ada / rusak di sumber, sumbernya sabda.org (TB):

| Ayat | Sumber teks |
|---|---|
| 1 Raj 4:32 | hilang di `lib/pl/1_raja_raja.json`; diambil dari sabda |
| 2 Taw 18:5 | terpotong di tengah kalimat di sumber; dilengkapi dari sabda |
| 1 Sam 24:11 | ekor ayat diganti teks asing di sumber; dilengkapi dari sabda |
| 2 Sam 2:2 | isi ayat salah di sumber; diganti dari sabda |

Verifikasi yang sudah dijalankan: himpunan nomor ayat per pasal **identik dengan sabda untuk 1.189 pasal** (31.102 ayat) — tidak ada ayat hilang/berlebih lain.

### 5.5 Yang sengaja TIDAK diubah

- Nomor Ibrani `(c-v)` dipertahankan apa adanya, termasuk yang berada di tengah ayat (mis. `1 Raj 22:43`), karena itu teks TB resmi.
- Tidak ada normalisasi ejaan, tidak ada penggabungan ayat lintas nomor, tidak ada penomoran ulang.
- Nama kitab, urutan, jumlah pasal dari `books.py`; jumlah pasal JSON diverifikasi sama (gagal keras kalau beda).

### 5.6 Output audit

`data/reports/clean_report.json`: `total_verses_in` (31.108), `total_verses_out` (31.102), `counts` per aturan, `patched`, `records` (setiap record yang berubah: aksi, sebelum, sesudah). Console: ringkas per kitab.

## 6. Tahap 2 — `build_content.py`

1. Hapus `data/output/alkitab_content.db` lama.
2. Buat skema dari `schema_content.sql` (spec §5, tanpa tabel user).
3. Insert translation (`tb`, Terjemahan Baru, TB, id, version=N).
4. Loop 66 kitab urut kanon → `books` (id = order_no) → `verses` batch insert.
5. `id = book_order * 1_000_000 + chapter * 1_000 + verse` (spec §6).
6. Commit, `PRAGMA integrity_check`.
7. ZIP → `data/output/alkitab_tb_v{N}.zip`, isi `alkitab_content.db`.
8. SHA-256 ZIP → `manifest.json` (skema spec §4, `db_schema_version: 1`).
9. Print progres per kitab; `sys.exit(1)` kalau ada error.

Argumen: `--version N` (wajib). Guard: tolak jalan kalau `N <= version` di manifest lama,
kecuali `--force`.

Validasi sebelum tulis ZIP (gagal → exit non-zero):
- 66 kitab, `chapter_count` cocok dengan `books.py`;
- jumlah ayat = jumlah ayat `data/json`;
- `id` unik, `(book_id, chapter, verse)` unik, tidak ada teks kosong;
- tidak ada sisa artefak (`/`, `*`, penanda bagian) di `verses.text`.

## 7. Tahap 3 — Flask (`app.py`)

Persis spec §4: `/api/manifest` (503 kalau belum ada), `/api/download/<filename>`
(hanya `.zip` di `data/output/`, tolak `..` dan `/`), `/api/health`. Plus
`passenger_wsgi.py`, `requirements.txt` (Flask saja), `.htaccess`.

Satu tambahan di luar spec: `after_request` memasang `Access-Control-Allow-Origin: *`
+ `Access-Control-Allow-Methods: GET, OPTIONS` supaya build web PWA bisa memanggil
`/api/manifest` dan `/api/download/*` dari origin lain (mis. `localhost:8080`) tanpa
proxy. Aman karena API hanya-baca dan tanpa kredensial; jangan tambah
`Allow-Credentials` selama origin masih `*`.

`.htaccess` memblokir `*.py`, `*.sql`, `.env`, dan seluruh `lib/`, `data/json/`,
`data/reports/` — hanya `data/output/` yang boleh diakses.

## 8. File

```
alkitab-api/
  app.py                 # Flask, kontrak spec §4
  build_content.py       # tahap 2
  clean_json.py          # tahap 1
  books.py               # 66 kitab: order, nama, testament, file, jumlah pasal
  schema_content.sql
  passenger_wsgi.py
  requirements.txt       # Flask
  .htaccess
  lib/{pl,pb}/*.json     # sumber, read-only
  data/json/{pl,pb}/*.json
  data/reports/clean_report.json
  data/output/{alkitab_content.db, alkitab_tb_v{N}.zip, manifest.json}
  docs/specs/2026-11-20-alkitab-api-design.md
```

## 9. Verifikasi

Sudah dijalankan (hasil nyata, bukan rencana):

| Cek | Hasil |
|---|---|
| `python clean_json.py` | 31.108 → **31.102** ayat, 0 duplikat, `data/reports/clean_report.json` tertulis |
| Himpunan nomor ayat per pasal vs sabda.org | **1.189/1.189 pasal identik**, 0 selisih |
| Isi teks vs sabda (2 metode silang) | print-page TB 66 kitab: 400 "lebih panjang di sabda" → semua judul pasal cetak, kecuali 2 Taw 18:5 (di-patch). Halaman per-pasal `bible.php?tab=text` 13 kitab pertama (12.017 ayat): 43 flag, semua footer situs / nomor strong, 1 beda batas ayat (1 Sam 4:1). **0 ayat terpotong** |
| Sisa artefak (`/`, `*`, running head, `(c-` tanpa digit) | 0 |
| `python build_content.py --version 1` | 5,9 MB DB, `alkitab_tb_v1.zip` 2.052.997 byte, `PRAGMA integrity_check` = ok, 31.102 baris |
| Zip vs manifest | `zip_size` & `sha256` cocok; isi ZIP hanya `alkitab_content.db` |
| `sqlite3` spot-check | `id 1001001`, `43003016` (Yoh 3:16), Mzm 119 (176 ayat), 1 Raj 4:32 = patch |
| `app.py` test client | `/api/health` 200, `/api/manifest` 200, `/api/download/*.zip` 200; `../app.py`, `x.txt`, `../../etc/passwd`, `nope.zip` ditolak 400/404 |
| `python test_pipeline.py` | aturan bersih, perapian record, invariant DB — semua lolos |

`test_pipeline.py` = satu file assert tanpa framework: 10 assert aturan teks, 2 kasus
perapian record, lalu invariant DB (66 kitab, 0 duplikat, 0 artefak, jumlah pasal per kitab).

## 10. Yang diserahkan ke builder

- `books.py`, `clean_json.py`, `build_content.py`, `schema_content.sql`, `app.py`,
  `passenger_wsgi.py`, `.htaccess`, `requirements.txt`, `test_pipeline.py` — sudah jadi.
- `data/patches.json` (4 ayat: 1 Raj 4:32, 2 Sam 2:2, 1 Sam 24:11, 2 Taw 18:5) beserta
  aturan: patch untuk ayat hilang **dan** ayat rusak; patch yang tidak terpakai = gagal keras.
- Regex & urutan aturan final, teruji pada 31.108 record.
