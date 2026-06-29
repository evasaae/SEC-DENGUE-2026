import os
import re
import requests
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score

print("=== STARTING LIVE MLOps PIPELINE (TRAINED ON HISTORICAL DATA) ===")

# ==================================================================
# CONFIG PATH & ENDPOINTS (GIT ACTIONS & REPOSITORI)
# Cek di folder Deploy Web/dataset dulu, jika tidak ada baru cari di root
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) # Folder 'root'
PARENT_DIR = os.path.dirname(BASE_DIR)                # Folder workspace root

if os.path.exists(os.path.join(PARENT_DIR, "Deploy Web", "dataset", "SEC13 SATRIA DATA 2026 REMINDER.xlsx")):
    JALUR_EXCEL = os.path.join(PARENT_DIR, "Deploy Web", "dataset", "SEC13 SATRIA DATA 2026 REMINDER.xlsx")
elif os.path.exists(os.path.join(BASE_DIR, "SEC13 SATRIA DATA 2026 REMINDER.xlsx")):
    JALUR_EXCEL = os.path.join(BASE_DIR, "SEC13 SATRIA DATA 2026 REMINDER.xlsx")
else:
    JALUR_EXCEL = os.path.join(PARENT_DIR, "SEC13 SATRIA DATA 2026 REMINDER.xlsx")

if os.path.exists(os.path.join(PARENT_DIR, "Deploy Web", "dataset", "dataset_tahunan.xlsx")):
    DATASET_TRAINING = os.path.join(PARENT_DIR, "Deploy Web", "dataset", "dataset_tahunan.xlsx")
elif os.path.exists(os.path.join(BASE_DIR, "dataset_tahunan.xlsx")):
    DATASET_TRAINING = os.path.join(BASE_DIR, "dataset_tahunan.xlsx")
else:
    DATASET_TRAINING = os.path.join(PARENT_DIR, "dataset_tahunan.xlsx")

# Git Actions Weather Data (Prioritas URL GitHub Raw)
LOCAL_CUACA_PATH = os.path.join(PARENT_DIR, "Data Cuaca Harian Kalbar", "Data_Cuaca_Harian_Kalbar_Hari_Ini.csv")
URL_CUACA = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data%20Cuaca%20Harian%20Kalbar/Data_Cuaca_Harian_Kalbar_Hari_Ini.csv"

# Git Actions News Data (Prioritas URL GitHub Raw)
LOCAL_BERITA_PATH = os.path.join(PARENT_DIR, "data", "berita_dbd.csv")
URL_BERITA = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/data/berita_dbd.csv"

LOCAL_DETAIL_PATH = os.path.join(PARENT_DIR, "data", "detail_berita.csv")
URL_DETAIL = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/data/detail_berita.csv"

# ==================================================================
# HELPER FUNCTIONS
# ==================================================================
def standardisasi_nama(teks):
    if pd.isna(teks): 
        return ""
    t = str(teks).upper().strip()
    t = t.replace('KAB. ', '').replace('KABUPATEN ', '').replace('KOTA ', '')
    t = " ".join(t.split())
    return t

def hitung_thi(suhu, kelembapan):
    farenheit = (1.8 * suhu) + 32
    idx_lembab = 0.55 - (0.55 * (kelembapan / 100))
    thi = farenheit - idx_lembab * (farenheit - 58)
    return round(thi, 2)

def hitung_hari_kritis_berturut_turut(series_hujan, threshold=10):
    is_heavy = (series_hujan > threshold).astype(int).values
    max_consecutive = 0
    current_consecutive = 0
    for val in is_heavy:
        if val == 1:
            current_consecutive += 1
            if current_consecutive > max_consecutive:
                max_consecutive = current_consecutive
        else:
            current_consecutive = 0
    return max_consecutive

# ----------------------------------------------------
# 1. INGEST DATA NEWS DARI GIT ACTIONS SCRAPER (URL UTAMA)
# ----------------------------------------------------
print("\n[1/5] Membaca data berita dari Git Actions news scraper...")
peta_berita = {}
list_berita = []

# Baca berita DBD per kabupaten (News Count)
df_git_berita = None
try:
    print(f"      -> Mengunduh count berita dari GitHub...")
    df_git_berita = pd.read_csv(URL_BERITA)
    print(f"      -> Sukses mengunduh dari: {URL_BERITA}")
except Exception as e:
    print(f"      [!] Gagal mengunduh: {e}. Mencoba berkas lokal...")
    if os.path.exists(LOCAL_BERITA_PATH):
        try:
            df_git_berita = pd.read_csv(LOCAL_BERITA_PATH)
            print(f"      -> Sukses membaca count berita lokal: '{LOCAL_BERITA_PATH}'")
        except Exception as ex:
            print(f"      [!] Gagal membaca count berita lokal: {ex}")

if df_git_berita is not None:
    try:
        df_git_berita.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_berita.columns]
        kab_col = [col for col in df_git_berita.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower() or 'kab' in col.lower()][0]
        total_col = [col for col in df_git_berita.columns if 'total 7' in col.lower() or 'total' in col.lower()][0]
        df_git_berita['Key'] = df_git_berita[kab_col].apply(standardisasi_nama)
        peta_berita = dict(zip(df_git_berita['Key'], df_git_berita[total_col]))
    except Exception as e:
        print(f"      [!] Gagal parse count berita: {e}")

# Baca detail berita untuk dicantumkan di laporan
df_git_detail = None
try:
    df_git_detail = pd.read_csv(URL_DETAIL)
except Exception as e:
    print(f"      [!] Gagal mengunduh detail berita: {e}. Mencoba berkas lokal...")
    if os.path.exists(LOCAL_DETAIL_PATH):
        try:
            df_git_detail = pd.read_csv(LOCAL_DETAIL_PATH)
        except Exception as ex:
            print(f"      [!] Gagal membaca detail berita lokal: {ex}")

if df_git_detail is not None:
    try:
        df_git_detail.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_detail.columns]
        for _, row in df_git_detail.iterrows():
            judul = row.get('judul', row.get('Judul', 'Tanpa Judul'))
            # Filter hanya berita yang benar-benar memuat topik DBD / Demam Berdarah
            if any(kw in str(judul).lower() for kw in ['dbd', 'demam berdarah', 'fogging', 'aedes']):
                list_berita.append({
                    'Judul': judul,
                    'Tanggal': row.get('tanggal', row.get('Tanggal', 'Unknown Date')),
                    'Kabupaten': row.get('kabupaten', row.get('Kabupaten', 'Kalbar'))
                })
        print(f"      -> Sukses memfilter {len(list_berita)} detail berita DBD relevan untuk laporan.")
    except Exception as e:
        print(f"      [!] Gagal parse detail berita: {e}")

# ----------------------------------------------------
# 2. INGEST DATA CUACA HARIAN DARI GIT ACTIONS (URL UTAMA)
# ----------------------------------------------------
print("\n[2/5] Membaca data cuaca harian Kalbar...")
df_git_cuaca = None

df_local = None
if os.path.exists(LOCAL_CUACA_PATH):
    try:
        df_local = pd.read_csv(LOCAL_CUACA_PATH)
    except Exception as e:
        print(f"      [!] Gagal membaca cuaca lokal: {e}")

df_url = None
try:
    print(f"      -> Mengunduh data cuaca dari GitHub Actions...")
    df_url = pd.read_csv(URL_CUACA, timeout=5)
    print(f"      -> Sukses mengunduh dari: {URL_CUACA}")
except Exception as e:
    print(f"      [!] Gagal mengunduh: {e}")

# Bandingkan tanggal terbaru dari kedua sumber untuk menghindari data usang (stale data)
if df_local is not None and df_url is not None:
    try:
        # Deteksi nama kolom tanggal
        tanggal_cols = [c for c in df_local.columns if 'tanggal' in c.lower() or 'waktu' in c.lower()]
        tanggal_col_test = tanggal_cols[0] if len(tanggal_cols) > 0 else df_local.columns[0]
        
        local_max = pd.to_datetime(df_local[tanggal_col_test]).max()
        url_max = pd.to_datetime(df_url[tanggal_col_test]).max()
        if local_max >= url_max:
            df_git_cuaca = df_local
            print(f"      -> Menggunakan data cuaca lokal karena lebih baru/setara (terbaru: {local_max.strftime('%Y-%m-%d')})")
        else:
            df_git_cuaca = df_url
            print(f"      -> Menggunakan data cuaca online karena lebih baru (terbaru: {url_max.strftime('%Y-%m-%d')})")
    except Exception as e:
        print(f"      [!] Gagal membandingkan tanggal cuaca: {e}")
        df_git_cuaca = df_local if df_local is not None else df_url
elif df_local is not None:
    df_git_cuaca = df_local
    print("      -> Menggunakan data cuaca lokal (data online gagal diunduh).")
elif df_url is not None:
    df_git_cuaca = df_url
    print("      -> Menggunakan data cuaca online (data lokal tidak ditemukan).")

if df_git_cuaca is None:
    raise ValueError("Tidak dapat memuat data cuaca harian baik dari GitHub maupun berkas lokal.")

# Clean & sort cuaca
df_git_cuaca.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_cuaca.columns]
kab_col = [col for col in df_git_cuaca.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower()][0]
suhu_col = [col for col in df_git_cuaca.columns if 'suhu' in col.lower()][0]
kelembapan_col = [col for col in df_git_cuaca.columns if 'kelembapan' in col.lower()][0]
hujan_col = [col for col in df_git_cuaca.columns if 'akumulasi hujan' in col.lower() or 'hujan (mm)' in col.lower() or 'hujan' in col.lower()][0]

tanggal_cols = [col for col in df_git_cuaca.columns if 'tanggal' in col.lower() or 'waktu' in col.lower()]
tanggal_col = tanggal_cols[0] if len(tanggal_cols) > 0 else df_git_cuaca.columns[0]

df_git_cuaca['Key'] = df_git_cuaca[kab_col].apply(standardisasi_nama)
df_git_cuaca = df_git_cuaca.sort_values(by=['Key', tanggal_col], ascending=True)

# Ambil data cuaca harian terbaru untuk Suhu & Kelembapan, serta 7 hari terakhir untuk Hujan
df_git_cuaca[tanggal_col] = pd.to_datetime(df_git_cuaca[tanggal_col])
latest_date = df_git_cuaca[tanggal_col].max()

df_cuaca_latest = df_git_cuaca[df_git_cuaca[tanggal_col] == latest_date]
df_cuaca_7d = df_git_cuaca[df_git_cuaca[tanggal_col] >= latest_date - pd.Timedelta(days=6)]

peta_cuaca = {}
for kab, group in df_cuaca_7d.groupby('Key'):
    # Cari baris cuaca terbaru (hari ini) untuk Suhu & Kelembapan
    baris_terbaru = df_cuaca_latest[df_cuaca_latest['Key'] == kab]
    if len(baris_terbaru) > 0:
        suhu_hari_ini = float(baris_terbaru[suhu_col].values[0])
        kelembapan_hari_ini = float(baris_terbaru[kelembapan_col].values[0])
    else:
        suhu_hari_ini = float(group[suhu_col].mean())
        kelembapan_hari_ini = float(group[kelembapan_col].mean())
        
    # Akumulasi Hujan dan Hari Hujan Kritis Berturut-turut dihitung dalam kurun minggu itu (7 hari terakhir)
    total_hujan_7d = float(group[hujan_col].sum())
    hujan_kritis_berturut_7d = hitung_hari_kritis_berturut_turut(group[hujan_col], threshold=10)
    
    peta_cuaca[kab] = {
        'Suhu': round(suhu_hari_ini, 2),
        'Kelembapan': round(kelembapan_hari_ini, 2),
        'THI': hitung_thi(suhu_hari_ini, kelembapan_hari_ini),
        'Hujan_7D': round(total_hujan_7d, 2),
        'Hujan_Kritis_Berturut_7D': hujan_kritis_berturut_7d
    }
print("      -> Sukses memuat data cuaca harian terbaru dengan akumulasi hujan mingguan.")

# ----------------------------------------------------
# 3. INGEST DATA DEMOGRAFI & HISTORIS KASUS
# ----------------------------------------------------
print("\n[3/5] Membaca data kependudukan dari Excel...")
try:
    df_master = pd.read_excel(JALUR_EXCEL, sheet_name='Master_Wilayah')
    print(f"      -> Sukses memuat data demografi {len(df_master)} wilayah.")
except Exception as e:
    print(f"      [!] Gagal membaca dari Excel: {e}. Menggunakan default data.")
    df_master = pd.DataFrame([
        {"Wilayah": "KOTA PONTIANAK", "Penduduk_Terbaru": 672440, "Luas_Wilayah": 107.82},
        {"Wilayah": "KAB. KUBU RAYA", "Penduduk_Terbaru": 611569, "Luas_Wilayah": 6985.20},
        {"Wilayah": "KAB. SANGGAU", "Penduduk_Terbaru": 484297, "Luas_Wilayah": 12857.70}
    ])

# ----------------------------------------------------
# 4. TRAINING MODEL: BELAJAR DARI DATASET TRAINING (dataset_tahunan.xlsx)
# ----------------------------------------------------
print("\n[4/5] Melatih Model ML (Belajar dari training dataset)...")
try:
    df_train = pd.read_excel(DATASET_TRAINING)
    
    # Ekstrak data kepadatan tahun terbaru (2023) langsung dari dataset tahunan
    df_2023 = df_train[df_train['Tahun'] == 2023]
    peta_kepadatan = {}
    for _, r in df_2023.iterrows():
        key = standardisasi_nama(r['Wilayah'])
        peta_kepadatan[key] = float(r['Kepadatan'])
        
    fitur_kolom = ['Kepadatan', 'Suhu', 'Kelembapan', 'THI', 'Total_Hujan', 'Hujan_Kritis']
    X_train = df_train[fitur_kolom]
    min_bounds = X_train.min()
    max_bounds = X_train.max()
    
    # Standardisasi
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    
    # Klasterisasi KMeans (Zonasi Peringatan Dini) seperti training_model.py
    kmeans_model = KMeans(n_clusters=3, random_state=42, n_init=10)
    y_train = kmeans_model.fit_predict(X_train_scaled)
    
    # Latih Gaussian Naive Bayes dengan Hyperparameter Tuning
    base_nb = GaussianNB()
    param_grid = {'var_smoothing': np.logspace(0, -9, num=100)}
    grid_search = GridSearchCV(base_nb, param_grid, cv=5, scoring='accuracy')
    grid_search.fit(X_train_scaled, y_train)
    
    model_nb_tuned = grid_search.best_estimator_
    
    # Hitung akurasi pada data training
    y_pred_train = model_nb_tuned.predict(X_train_scaled)
    train_acc = accuracy_score(y_train, y_pred_train) * 100
    
    print(f"      -> Data Training loaded: {len(df_train)} baris.")
    print(f"      -> Best var_smoothing  : {grid_search.best_params_['var_smoothing']:.2E}")
    print(f"      -> Akurasi Training NB : {train_acc:.2f}%")
    
    # Arti Cluster
    arti_status = {
        0: "WASPADA (Endemisitas Sedang - Faktor Kelembapan)",
        1: "SIAGA (Risiko Tinggi - Kerawanan Curah Hujan Ekstrem)",
        2: "AMAN (Kondisi Stabil - Dampak Kepadatan Terkendali)"
    }
except Exception as e:
    raise ValueError(f"Gagal memuat dataset training atau melatih model: {e}")

# ----------------------------------------------------
# 5. INFERENCE: DIAGNOSIS STATUS LEVEL RISIKO
# ----------------------------------------------------
print("\n[5/5] Melakukan diagnosis level risiko DBD untuk seluruh wilayah...")
laporan_final = []

for _, baris in df_master.iterrows():
    raw_nama = str(baris['Wilayah']).upper().strip()
    kab_key = standardisasi_nama(raw_nama)
    
    # Ambil kepadatan 2023 langsung dari training dataset
    kepadatan = peta_kepadatan.get(kab_key, 50.0)
    
    # Ambil data cuaca harian aktual 7-hari dari peta_cuaca
    cuaca = peta_cuaca.get(kab_key, {
        'Suhu': 27.2, 
        'Kelembapan': 82.0, 
        'THI': 78.4, 
        'Hujan_7D': 65.0,
        'Hujan_Kritis_Berturut_7D': 1
    })
    
    suhu = cuaca['Suhu']
    kelembapan = cuaca['Kelembapan']
    thi = cuaca['THI']
    hujan_7d = cuaca['Hujan_7D']
    hujan_kritis_7d = cuaca['Hujan_Kritis_Berturut_7D']
    
    # Proyeksikan data mingguan cuaca ke skala tahunan secara internal untuk model ML
    total_hujan_tahunan = round(hujan_7d * 52.18, 2)
    hujan_kritis_tahunan = round(hujan_kritis_7d * 52.18, 2)
    
    # Batasi agar tidak melompat keluar dari batas distribusi data training (out-of-distribution)
    total_hujan_tahunan = float(np.clip(total_hujan_tahunan, min_bounds['Total_Hujan'], max_bounds['Total_Hujan']))
    hujan_kritis_tahunan = float(np.clip(hujan_kritis_tahunan, min_bounds['Hujan_Kritis'], max_bounds['Hujan_Kritis']))
    
    # Format vektor input model (sesuai skala dataset_tahunan.xlsx)
    vektor_input = pd.DataFrame([[kepadatan, suhu, kelembapan, thi, total_hujan_tahunan, hujan_kritis_tahunan]], columns=fitur_kolom)
    vektor_input_scaled = scaler.transform(vektor_input)
    
    # Prediksi
    prediksi_idx = int(model_nb_tuned.predict(vektor_input_scaled)[0])
    status_final = arti_status[prediksi_idx]
    
    peluang_array = model_nb_tuned.predict_proba(vektor_input_scaled)[0]
    keyakinan_sistem = round(peluang_array[prediksi_idx] * 100, 1)
    jumlah_berita = int(peta_berita.get(kab_key, 0))
    
    laporan_final.append({
        'Wilayah': raw_nama,
        'Kepadatan': round(kepadatan, 1),
        'Suhu (°C)': suhu,
        'Lembap (%)': kelembapan,
        'THI': thi,
        'Hujan 7D (mm)': hujan_7d,
        'Hujan Kritis Konsekutif 7D (Hari)': hujan_kritis_7d,
        'Berita': jumlah_berita,
        'Status': status_final
    })

df_laporan = pd.DataFrame(laporan_final)

# ==================================================================
# 6. REPORT GENERATION: MENERBITKAN DOKUMEN LOG
# ==================================================================
log_output = f"""================================================================================
LAPORAN OTOMATIS: EARLY WARNING SYSTEM DBD KALBAR (INTEGRASI ONLINE GIT)
Dieksekusi Otomatis Pada : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

1. HASIL DIAGNOSIS MODEL AI HYBRID TUNED (K-MEANS + NAIVE BAYES):
{df_laporan.to_string(index=False)}

2. RINGKASAN MONITORING WILAYAH:
   - AMAN (DENSITY URBAN)        : {sum(df_laporan['Status'].str.contains('AMAN'))} Wilayah
   - WASPADA (HUMIDITY RISK)     : {sum(df_laporan['Status'].str.contains('WASPADA'))} Wilayah
   - SIAGA (RAIN EXTREME)        : {sum(df_laporan['Status'].str.contains('SIAGA'))} Wilayah

3. TRACKING MEDIA MONITORING (WEB SCRAPING DARI GIT ACTIONS):
"""
if list_berita:
    for idx, b in enumerate(list_berita, 1):
        log_output += f"   [{idx}] [{b['Kabupaten'].upper()}] {b['Judul']} ({b['Tanggal']})\n"
else:
    log_output += "   [-] Tidak ada berita DBD baru terdeteksi dalam 24 jam terakhir.\n"

log_output += "================================================================================\n"

# Simpan hasil laporan ke repositori
with open(os.path.join(BASE_DIR, "laporan_pantauan_terkini.txt"), "w", encoding="utf-8") as f:
    f.write(log_output)

print("\n=== PIPELINE AUTOMATION SUCCESSFUL ===")
print(log_output)