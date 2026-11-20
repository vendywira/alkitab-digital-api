# alkitab-api

Backend Flask untuk aplikasi Alkitab PWA. Tugasnya cuma satu: menyajikan
`manifest.json` + satu file ZIP berisi `alkitab_content.db` (SQLite) yang diunduh
sekali oleh aplikasi, lalu semua pencarian ayat jalan lokal di HP.

Tidak ada endpoint per-ayat, tidak ada pencarian server-side, tidak ada auto-rebuild
dari HTTP. Kontrak lengkapnya: `../alkitab-pwa/docs/backend.md`.

---

## 1. Isi folder

```
alkitab-api/
  app.py                 # server Flask (3 endpoint)
  passenger_wsgi.py      # entry point cPanel/Passenger
  requirements.txt       # Flask saja
  .htaccess              # blokir akses web ke script & sumber

  clean_json.py          # tahap 1: lib/ -> data/json/  (bersihkan artefak OCR)
  scrape_perikop.py      # sumber judul perikop TB: sabda.org -> data/perikop.json
  build_content.py       # tahap 2: data/json/ -> db + zip + manifest
  books.py               # tabel 66 kitab (urutan, nama, file, jumlah pasal)
  schema_content.sql     # skema alkitab_content.db
  test_pipeline.py       # cek hasil (tanpa framework)

  data/patches.json      # ayat yang hilang/rusak di sumber (teks dari sabda.org)
  data/perikop.json      # judul perikop per ayat mulai (hasil scrape_perikop.py)
  data/sabda/            # cache HTML scrape (tidak di-deploy; dibuat ulang otomatis)
  data/json/             # hasil tahap 1 (jangan diedit manual)
  data/reports/          # laporan audit (tidak di-deploy; ditulis ulang saat build)
  data/output/           # yang disajikan ke publik: db, zip, manifest.json,
                         #   translations.json (opsional, katalog tambahan)

  lib/pl/*.json          # sumber Perjanjian Lama (read-only, jangan ditulis)
  lib/pb/*.json          # sumber Perjanjian Baru (read-only)
```

Alur:

```
lib/{pl,pb}/*.json  --clean_json.py-->  data/json/  --build_content.py-->  data/output/
                                                                           alkitab_content.db
                                                                           alkitab_tb_v{N}.zip
                                                                           manifest.json
```

Isi paket: 66 kitab, 1.189 pasal, **31.102 ayat**, TB (Terjemahan Baru).

---

## 2. Prasyarat

- Python 3.11 atau lebih baru (`python3 -V`)
- Tidak perlu database server, tidak perlu Node, tidak perlu Redis

Cek versi:

```bash
python3 -V
```

---

## 3. Jalanin lokal (pertama kali)

```bash
cd alkitab-api

# 1. buat lingkungan Python khusus proyek (sekali saja)
python3 -m venv .venv

# 2. pasang Flask ke dalamnya (sekali saja)
.venv/bin/pip install -r requirements.txt

# 3. jalankan server
.venv/bin/python app.py
```

Server hidup di **http://127.0.0.1:5000**. Biarkan terminal terbuka.

Hentikan: `Ctrl+C`.

### Kenapa `.venv/bin/python`, bukan `python3`?

Flask dipasang di dalam folder `.venv/`, bukan di Python sistem. Kalau pakai
`python3 app.py` hasilnya:

```
ModuleNotFoundError: No module named 'flask'
```

Kalau tidak mau menulis `.venv/bin/` terus, aktifkan dulu:

```bash
source .venv/bin/activate     # prompt berubah, `python` sekarang = python proyek
python app.py
deactivate                    # kalau sudah selesai
```

### Kalau `.venv/` hilang atau rusak

Hapus foldernya, ulangi langkah 1–2 di atas. Tidak ada data yang hilang —
`.venv/` cuma berisi Python + Flask.

---

## 4. Tes API

Lewat browser:

- http://127.0.0.1:5000/api/health
- http://127.0.0.1:5000/api/translations
- http://127.0.0.1:5000/api/manifest
- http://127.0.0.1:5000/api/manifest?id=tb
- http://127.0.0.1:5000/api/download/alkitab_tb_v1.zip

Lewat terminal (terminal kedua, server tetap jalan):

```bash
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/translations
curl http://127.0.0.1:5000/api/manifest
curl "http://127.0.0.1:5000/api/manifest?id=tb"
curl -O http://127.0.0.1:5000/api/download/alkitab_tb_v1.zip

# ukuran & sha256 ZIP harus sama dengan yang tertulis di manifest.json
shasum -a 256 alkitab_tb_v1.zip
```

Endpoint:

| Metode | Path | Balasan |
|---|---|---|
| GET | `/api/health` | `{"status":"ok","manifest_exists":true,"translations":1}` |
| GET | `/api/translations` | `{"translations":[...]}` dari `translations.json` + manifest; **503** kalau kosong |
| GET | `/api/manifest` | isi `data/output/manifest.json`; dengan `?id=<id>` memilih entri katalog (**404** bila tak ada); **503** kalau belum di-build |
| GET | `/api/download/<nama>.zip` | file ZIP; 400 kalau bukan `.zip`, 404 kalau tidak ada |

Semua balasan diberi `Access-Control-Allow-Origin: *` (API read-only publik), jadi build
web Flutter boleh memanggil domain API ini langsung dari browser tanpa proxy.

---

## 5. Bikin ulang data

Jalankan hanya kalau `lib/` atau `data/patches.json` berubah. Urutannya wajib:
tahap 1 dulu, baru tahap 2.

```bash
cd alkitab-api

# tahap 1: bersihkan artefak OCR -> data/json/ + data/reports/clean_report.json
.venv/bin/python clean_json.py

# perikop: scrape judul TB -> data/perikop.json (cache di data/sabda/)
.venv/bin/python scrape_perikop.py

# tahap 2: -> data/output/alkitab_content.db, alkitab_tb_v{N}.zip, manifest.json
.venv/bin/python build_content.py --version 2

# cek hasil
.venv/bin/python test_pipeline.py
```

Catatan:

- `scrape_perikop.py` idempoten: HTML yang sudah ada di `data/sabda/` tidak
  diunduh ulang. Gagal keras kalau jumlah ayat SABDA beda dari `data/json/`.

- `--version N` harus **lebih besar** dari versi di `manifest.json`. Kalau memang
  mau menimpa versi yang sama: `--version 1 --force`.
- ZIP lama di `data/output/` dihapus otomatis; hanya ZIP versi terbaru yang ada.
- Tahap 1 **gagal keras** kalau: ada ayat hilang tanpa patch, ada patch yang tidak
  terpakai, ada nomor ayat duplikat, atau jumlah pasal beda dari `books.py`.
  Pesan errornya menyebut kitab/pasal/ayat yang bermasalah.
- `lib/` tidak pernah ditulis. Sumber selalu utuh, hasil bersih ada di `data/json/`.

Mau lihat dulu tanpa menulis file:

```bash
.venv/bin/python clean_json.py --dry-run
```

### Menambah patch

Hanya untuk ayat yang **hilang** atau **rusak** di sumber. Teksnya diambil dari
alkitab.sabda.org (TB), lalu ditulis ke `data/patches.json`:

```json
{
  "2_tawarikh/18/5": "Lalu raja Israel mengumpulkan para nabi, ..."
}
```

Format kunci: `<nama_file_tanpa_json>/<pasal>/<ayat>`. Contoh lain: `1_raja_raja/4/32`.
Ayat hilang diisi, ayat yang sudah ada ditimpa. Setelah menambah patch, jalankan
tahap 1 lagi — kalau patch ternyata tidak dipakai (sumber sudah benar), build gagal
supaya patch basi tidak menumpuk.

---

## 6. Deploy ke cPanel (Phusion Passenger)

1. Upload ke hosting. Yang **wajib** hanya: `app.py`, `passenger_wsgi.py`,
   `requirements.txt`, `.htaccess`, dan `data/output/`.
   Tambahkan `books.py`, `schema_content.sql`, `build_content.py`, `clean_json.py`,
   `scrape_perikop.py`, `test_pipeline.py`, `data/json/`, `data/perikop.json`,
   `data/patches.json`, `lib/` hanya kalau build ulang dilakukan di server.
   Jangan unggah `.venv/`, `__pycache__/`, `data/sabda/` (cache scrape, ~64 MB),
   `data/reports/`, `.DS_Store`.
2. cPanel → **Setup Python App** → Python 3.11+ → application root = folder ini
   (mis. `public_html/alkitabdigital.my.id/api`), application startup file =
   `passenger_wsgi.py`.
3. cPanel membuat virtualenv sendiri di `~/virtualenv/<app root>/<versi>/`; pasang
   dependensi: `pip install -r requirements.txt` (menu "Run Pip Install", atau
   `source ~/virtualenv/<app root>/<versi>/bin/activate`).
4. Tidak ada path interpreter yang perlu diedit. `passenger_wsgi.py` hanya
   `from app import app as application`; Passenger yang memilih venv sesuai
   langkah 2. Kalau Flask tidak ketemu, berarti aplikasi cPanel belum diarahkan
   ke venv yang benar — perbaiki di menu Setup Python App, bukan di kode.
5. Pastikan `data/output/` bisa ditulis user cPanel (dibutuhkan saat build ulang).
6. Build di server (SSH), lalu cek `https://domain-anda.com/api/health`.

`python app.py` itu server development — jangan dipakai di produksi. Di server,
Passenger yang menjalankan `app.py` lewat `passenger_wsgi.py`.

`.htaccess` memblokir akses web ke `*.py`, `*.sql`, `*.md`, `*.log`, `lib/`,
`data/json/`, `data/reports/`, dan dotfiles. Yang boleh diakses hanya isi
`data/output/`.

---

## 7. Kalau ada masalah

| Gejala | Sebab / solusi |
|---|---|
| `ModuleNotFoundError: No module named 'flask'` | pakai `.venv/bin/python`, atau `source .venv/bin/activate` dulu |
| `/api/manifest` balas 503 | `data/output/manifest.json` belum ada → jalankan `build_content.py` |
| `/api/download/...zip` balas 404 | nama file salah, atau ZIP lama sudah dihapus saat rebuild |
| `GAGAL: version N <= manifest lama` | naikkan `--version`, atau tambah `--force` |
| `GAGAL: patch tidak terpakai` | hapus entri itu dari `data/patches.json` |
| `GAGAL ... ayat hilang tanpa patch` | tambahkan entri ke `data/patches.json` dari sabda.org |
| `Address already in use` | port 5000 dipakai proses lain: `pkill -f "python app.py"` |

Log build tahap 1 ada di `data/reports/clean_report.json` — tiap ayat yang berubah
dicatat lengkap dengan teks sebelum/sesudah.
