"""
EWS DBD Kalbar — Flask API Server
Jalankan dengan: python app.py
Akses di: http://localhost:5000
Admin panel: http://localhost:5000/admin
"""

from flask import Flask, jsonify, request, send_from_directory, send_file, render_template
from flask_cors import CORS
from engine import run_model
import time
import os
import json
import requests as http_requests

app = Flask(__name__, static_folder='static')
CORS(app)

# Nonaktifkan caching HTTP agar browser selalu memuat JS dan data terbaru
@app.after_request
def add_header(r):
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

# ==================================================================
# IN-MEMORY STATE (per session server)
# ==================================================================
fogging_state = {}   # { "PONTIANAK": True/False }
pe_timers     = {}   # { "PONTIANAK": unix_timestamp_start }
cache_data    = {"ts": 0, "data": None}
CACHE_TTL_SECONDS = 300  # 5 menit

# ==================================================================
# HELPER: get cached model output
# ==================================================================
def get_data():
    now = time.time()
    if cache_data["data"] is None or (now - cache_data["ts"]) > CACHE_TTL_SECONDS:
        result = run_model(fogging_overrides=fogging_state)
        cache_data["data"] = result
        cache_data["ts"]   = now
    return cache_data["data"]

def invalidate_cache():
    cache_data["ts"] = 0

# ==================================================================
# ROUTES — Static files
# ==================================================================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/admin')
def admin():
    return render_template('admin.html')

@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# ==================================================================
# API: GET /api/status — Data model semua kabupaten
# ==================================================================
@app.route('/api/status')
def api_status():
    try:
        data = get_data()
        if isinstance(data, dict) and 'error' in data:
            return jsonify(data), 500

        # Inject PE timer info
        now = time.time()
        for item in data:
            kab = item['kabupaten']
            if kab in pe_timers:
                elapsed   = now - pe_timers[kab]
                remaining = max(0, 86400 - elapsed)
                item['pe_active']            = True
                item['pe_remaining_seconds'] = int(remaining)
                item['pe_start_ts']          = pe_timers[kab]
            else:
                item['pe_active']            = False
                item['pe_remaining_seconds'] = 0

        return jsonify({
            "success": True,
            "data": data,
            "last_update": int(cache_data["ts"]),
            "fogging_state": fogging_state
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================================
# API: POST /api/fogging — Toggle status fogging
# ==================================================================
@app.route('/api/fogging', methods=['POST'])
def api_fogging():
    try:
        body    = request.json
        kabupaten = body.get('kabupaten', '').upper().strip()
        action    = body.get('action', '')  # 'selesai' or 'reset'

        if not kabupaten:
            return jsonify({"error": "kabupaten required"}), 400

        fogging_state[kabupaten] = (action == 'selesai')
        invalidate_cache()

        return jsonify({
            "success": True,
            "kabupaten": kabupaten,
            "fogging_active": fogging_state[kabupaten]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================================
# API: POST /api/pe-start — Mulai Penyelidikan Epidemiologi
# ==================================================================
@app.route('/api/pe-start', methods=['POST'])
def api_pe_start():
    try:
        body      = request.json
        kabupaten = body.get('kabupaten', '').upper().strip()
        if not kabupaten:
            return jsonify({"error": "kabupaten required"}), 400

        pe_timers[kabupaten] = time.time()
        invalidate_cache()

        return jsonify({
            "success": True,
            "kabupaten": kabupaten,
            "start_ts": pe_timers[kabupaten],
            "deadline_ts": pe_timers[kabupaten] + 86400
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================================
# API: POST /api/pe-reset — Reset timer PE
# ==================================================================
@app.route('/api/pe-reset', methods=['POST'])
def api_pe_reset():
    try:
        body      = request.json
        kabupaten = body.get('kabupaten', '').upper().strip()
        if kabupaten in pe_timers:
            del pe_timers[kabupaten]
        invalidate_cache()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================================
# API: GET /api/summary — Ringkasan statistik
# ==================================================================
@app.route('/api/summary')
def api_summary():
    try:
        data = get_data()
        if isinstance(data, dict) and 'error' in data:
            return jsonify(data), 500

        n_aman    = sum(1 for d in data if 'AMAN' in d['status'].upper())
        n_waspada = sum(1 for d in data if 'WASPADA' in d['status'].upper())
        n_siaga   = sum(1 for d in data if 'SIAGA' in d['status'].upper())
        n_golden  = sum(1 for d in data if d.get('golden_window', False))
        n_fogging = sum(1 for d in data if d.get('fogging_active', False))

        return jsonify({
            "total": len(data),
            "aman": n_aman,
            "waspada": n_waspada,
            "siaga": n_siaga,
            "golden_window_count": n_golden,
            "fogging_active_count": n_fogging
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==================================================================
# API: GET /api/geojson — Proxy GeoJSON Kalbar (cached)
# ==================================================================
geojson_cache = {"data": None}

LOCAL_GEOJSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'kalbar_kabupaten.geojson')

@app.route('/api/geojson')
def api_geojson():
    if geojson_cache["data"] is not None:
        return jsonify(geojson_cache["data"])

    # 1. Try local pre-downloaded file first
    if os.path.exists(LOCAL_GEOJSON):
        try:
            with open(LOCAL_GEOJSON, 'r', encoding='utf-8') as f:
                geo = json.load(f)
            geojson_cache["data"] = geo
            print(f"   GeoJSON loaded from local file: {LOCAL_GEOJSON}")
            return jsonify(geo)
        except Exception as e:
            print(f"   Local GeoJSON failed: {e}")

    # 2. Fallback to GitHub
    sources = [
        "https://raw.githubusercontent.com/JfrAziz/indonesia-district/master/id61_kalimantan_barat/id61_kalimantan_barat_district.geojson",
    ]

    for url in sources:
        try:
            resp = http_requests.get(url, timeout=30)
            if resp.status_code == 200:
                geo = resp.json()
                geojson_cache["data"] = geo
                print(f"   GeoJSON loaded from: {url}")
                return jsonify(geo)
        except Exception as e:
            print(f"   GeoJSON source failed: {url} ({e})")
            continue

    return jsonify({"error": "All GeoJSON sources failed"}), 503

# ==================================================================
# RUN SERVER
# ==================================================================
if __name__ == '__main__':
    print("\n" + "="*60)
    print("   EWS DBD KALBAR — Dashboard Server")
    print("   Public  : http://localhost:5000")
    print("   Admin   : http://localhost:5000/admin")
    print("   API     : http://localhost:5000/api/status")
    print("="*60 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
