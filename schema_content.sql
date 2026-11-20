-- Skema alkitab_content.db (kontrak: alkitab-pwa/docs/backend.md §5).
-- Hanya tabel konten. Data user ada di user_data.db milik Flutter.

CREATE TABLE translations (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  abbreviation TEXT NOT NULL,
  language TEXT NOT NULL,
  version INTEGER NOT NULL,
  last_updated TEXT
);

CREATE TABLE books (
  id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  testament TEXT NOT NULL,
  order_no INTEGER NOT NULL,
  chapter_count INTEGER NOT NULL
);

CREATE TABLE verses (
  id INTEGER PRIMARY KEY,
  book_id INTEGER NOT NULL,
  chapter INTEGER NOT NULL,
  verse INTEGER NOT NULL,
  text TEXT NOT NULL,
  pericope TEXT
);

CREATE INDEX idx_verses_lookup ON verses(book_id, chapter, verse);
