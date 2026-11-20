"""66 kitab kanonik: urutan, nama, perjanjian, file sumber, jumlah pasal.

Nama harus persis sama dengan `alkitab-pwa/lib/core/db/book_data.dart`
(client memakai nama ini untuk resolusi referensi). Jumlah pasal dipakai
sebagai guard build: JSON sumber yang tidak cocok -> gagal keras.
"""

BOOKS = [
    # order, name, testament, file, chapters
    (1, "Kejadian", "PL", "kejadian", 50),
    (2, "Keluaran", "PL", "keluaran", 40),
    (3, "Imamat", "PL", "imamat", 27),
    (4, "Bilangan", "PL", "bilangan", 36),
    (5, "Ulangan", "PL", "ulangan", 34),
    (6, "Yosua", "PL", "yosua", 24),
    (7, "Hakim", "PL", "hakim_hakim", 21),
    (8, "Rut", "PL", "rut", 4),
    (9, "1 Samuel", "PL", "1_samuel", 31),
    (10, "2 Samuel", "PL", "2_samuel", 24),
    (11, "1 Raja-raja", "PL", "1_raja_raja", 22),
    (12, "2 Raja-raja", "PL", "2_raja_raja", 25),
    (13, "1 Tawarikh", "PL", "1_tawarikh", 29),
    (14, "2 Tawarikh", "PL", "2_tawarikh", 36),
    (15, "Ezra", "PL", "ezra", 10),
    (16, "Nehemia", "PL", "nehemia", 13),
    (17, "Ester", "PL", "ester", 10),
    (18, "Ayub", "PL", "ayub", 42),
    (19, "Mazmur", "PL", "mazmur", 150),
    (20, "Amsal", "PL", "amsal", 31),
    (21, "Pengkhotbah", "PL", "pengkotbah", 12),
    (22, "Kidung Agung", "PL", "kidung_agung", 8),
    (23, "Yesaya", "PL", "yesaya", 66),
    (24, "Yeremia", "PL", "yeremia", 52),
    (25, "Ratapan", "PL", "ratapan", 5),
    (26, "Yehezkiel", "PL", "yehezkiel", 48),
    (27, "Daniel", "PL", "daniel", 12),
    (28, "Hosea", "PL", "hosea", 14),
    (29, "Yoel", "PL", "yoel", 3),
    (30, "Amos", "PL", "amos", 9),
    (31, "Obaja", "PL", "obaja", 1),
    (32, "Yunus", "PL", "yunus", 4),
    (33, "Mikha", "PL", "mikha", 7),
    (34, "Nahum", "PL", "nahum", 3),
    (35, "Habakuk", "PL", "habakuk", 3),
    (36, "Zefanya", "PL", "zefanya", 3),
    (37, "Hagai", "PL", "hagai", 2),
    (38, "Zakharia", "PL", "zakaria", 14),
    (39, "Maleakhi", "PL", "maleakhi", 4),
    (40, "Matius", "PB", "matius", 28),
    (41, "Markus", "PB", "markus", 16),
    (42, "Lukas", "PB", "lukas", 24),
    (43, "Yohanes", "PB", "yohanes", 21),
    (44, "Kisah Para Rasul", "PB", "kisah_para_rasul", 28),
    (45, "Roma", "PB", "roma", 16),
    (46, "1 Korintus", "PB", "1_korintus", 16),
    (47, "2 Korintus", "PB", "2_korintus", 13),
    (48, "Galatia", "PB", "galatia", 6),
    (49, "Efesus", "PB", "efesus", 6),
    (50, "Filipi", "PB", "filipi", 4),
    (51, "Kolose", "PB", "kolose", 4),
    (52, "1 Tesalonika", "PB", "1_tesalonika", 5),
    (53, "2 Tesalonika", "PB", "2_tesalonika", 3),
    (54, "1 Timotius", "PB", "1_timotius", 6),
    (55, "2 Timotius", "PB", "2_timotius", 4),
    (56, "Titus", "PB", "titus", 3),
    (57, "Filemon", "PB", "filemon", 1),
    (58, "Ibrani", "PB", "ibrani", 13),
    (59, "Yakobus", "PB", "yakobus", 5),
    (60, "1 Petrus", "PB", "1_petrus", 5),
    (61, "2 Petrus", "PB", "2_petrus", 3),
    (62, "1 Yohanes", "PB", "1_yohanes", 5),
    (63, "2 Yohanes", "PB", "2_yohanes", 1),
    (64, "3 Yohanes", "PB", "3_yohanes", 1),
    (65, "Yudas", "PB", "yudas", 1),
    (66, "Wahyu", "PB", "wahyu", 22),
]

# nama kitab sebagaimana muncul di penanda halaman sumber (varian lebih pendek)
SOURCE_MARKER_NAMES = [
    "Kejadian", "Keluaran", "Imamat", "Bilangan", "Ulangan", "Yosua",
    "Hakim-hakim", "Rut", "1 Samuel", "2 Samuel", "1 Raja-raja", "2 Raja-raja",
    "Raja-raja", "1 Tawarikh", "2 Tawarikh", "Tawarikh", "Ezra", "Nehemia",
    "Ester", "Ayub", "Mazmur", "Amsal", "Pengkhotbah", "Kidung Agung",
    "Yesaya", "Yeremia", "Ratapan", "Yehezkiel", "Daniel", "Hosea", "Yoel",
    "Amos", "Obaja", "Yunus", "Mikha", "Nahum", "Habakuk", "Zefanya", "Hagai",
    "Zakaria", "Maleakhi", "Matius", "Markus", "Lukas", "Yohanes",
    "Kisah Para Rasul", "Roma", "1 Korintus", "2 Korintus", "Galatia",
    "Efesus", "Filipi", "Kolose", "1 Tesalonika", "2 Tesalonika",
    "1 Timotius", "2 Timotius", "Titus", "Filemon", "Ibrani", "Yakobus",
    "1 Petrus", "2 Petrus", "1 Yohanes", "2 Yohanes", "3 Yohanes", "Yudas",
    "Wahyu",
]


def path_parts(book):
    """('pl'|'pb', '<file>.json') untuk satu baris BOOKS."""
    return ("pl" if book[2] == "PL" else "pb", book[3] + ".json")
