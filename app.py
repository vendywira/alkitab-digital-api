"""Flask app: katalog terjemahan + manifest + download ZIP + health.

Kontrak: alkitab-pwa/docs/backend.md §4.
"""
import json
import os

from flask import Flask, abort, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(BASE_DIR, "data", "output")
MANIFEST_PATH = os.path.join(OUTPUT_DIR, "manifest.json")
TRANSLATIONS_PATH = os.path.join(OUTPUT_DIR, "translations.json")

app = Flask(__name__)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _translation_id(entry):
    translation = entry.get("translation") or {}
    return str(translation.get("id", "")).strip().lower()


def _catalogue():
    """Daftar terjemahan: `translations.json` (opsional) + manifest default.

    `translations.json` berisi list entri berskema sama dengan `/api/manifest`.
    Manifest default selalu ikut supaya katalog tidak pernah kosong selama
    paket utama tersedia.
    """
    items = []
    if os.path.exists(TRANSLATIONS_PATH):
        payload = _read_json(TRANSLATIONS_PATH)
        if isinstance(payload, dict):
            payload = payload.get("translations") or []
        items = [item for item in payload if isinstance(item, dict)]

    if os.path.exists(MANIFEST_PATH):
        default = _read_json(MANIFEST_PATH)
        default_id = _translation_id(default)
        if default_id and not any(
            _translation_id(item) == default_id for item in items
        ):
            items.insert(0, default)
    return items


@app.route("/api/translations", methods=["GET"])
def get_translations():
    items = _catalogue()
    if not items:
        abort(503, description="Belum ada terjemahan yang tersedia.")
    return jsonify({"translations": items})


@app.route("/api/manifest", methods=["GET"])
def get_manifest():
    translation_id = str(request.args.get("id", "")).strip().lower()
    if translation_id:
        for item in _catalogue():
            if _translation_id(item) == translation_id:
                return jsonify(item)
        abort(404, description="Terjemahan tidak tersedia.")

    if not os.path.exists(MANIFEST_PATH):
        abort(503, description="Manifest belum tersedia.")
    return jsonify(_read_json(MANIFEST_PATH))


@app.route("/api/download/<filename>", methods=["GET"])
def download_zip(filename):
    if not filename.endswith(".zip"):
        abort(400, description="Hanya file ZIP yang diizinkan.")
    if ".." in filename or "/" in filename or "\\" in filename:
        abort(400, description="Nama file tidak valid.")
    if not os.path.isfile(os.path.join(OUTPUT_DIR, filename)):
        abort(404, description="File tidak ditemukan.")
    return send_from_directory(OUTPUT_DIR, filename, as_attachment=True)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "manifest_exists": os.path.exists(MANIFEST_PATH),
            "translations": len(_catalogue()),
        }
    )


@app.after_request
def cors(resp):
    # API read-only publik: cukup origin bebas. Juga menjawab preflight OPTIONS,
    # karena Flask otomatis menangani OPTIONS untuk tiap route.
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    return resp


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
