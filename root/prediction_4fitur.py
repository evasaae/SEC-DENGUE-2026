import os
import re
import numpy as np
import pandas as pd
from datetime import datetime
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.naive_bayes import GaussianNB
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.metrics import accuracy_score

print("=== STARTING LIVE MLOps PIPELINE (4-FEATURE INDEPENDENT MODEL) ===")

# ==================================================================
# CONFIG PATH & ENDPOINTS
# ==================================================================
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

LOCAL_CUACA_PATH = os.path.join(PARENT_DIR, "Data Cuaca Harian Kalbar", "Data_Cuaca_Harian_Kalbar_Hari_Ini.csv")
URL_CUACA = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data%20Cuaca%20Harian%20Kalbar/Data_Cuaca_Harian_Kalbar_Hari_Ini.csv"

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
# 1. INGEST DATA NEWS DARI GIT ACTIONS SCRAPER
# ----------------------------------------------------
print("\n[1/5] Membaca data berita...")
peta_berita = {}
list_berita = []

df_git_berita = None
try:
    df_git_berita = pd.read_csv(URL_BERITA)
except Exception as e:
    if os.path.exists(LOCAL_BERITA_PATH):
        try:
            df_git_berita = pd.read_csv(LOCAL_BERITA_PATH)
        except Exception as ex:
            pass

if df_git_berita is not None:
    try:
        df_git_berita.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_berita.columns]
        kab_col = [col for col in df_git_berita.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower() or 'kab' in col.lower()][0]
        total_col = [col for col in df_git_berita.columns if 'total 7' in col.lower() or 'total' in col.lower()][0]
        df_git_berita['Key'] = df_git_berita[kab_col].apply(standardisasi_nama)
        peta_berita = dict(zip(df_git_berita['Key'], df_git_berita[total_col]))
    except Exception as e:
        pass

df_git_detail = None
try:
    df_git_detail = pd.read_csv(URL_DETAIL)
except Exception as e:
    if os.path.exists(LOCAL_DETAIL_PATH):
        try:
            df_git_detail = pd.read_csv(LOCAL_DETAIL_PATH)
        except Exception as ex:
            pass

if df_git_detail is not None:
    try:
        df_git_detail.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_detail.columns]
        for _, row in df_git_detail.iterrows():
            judul = row.get('judul', row.get('Judul', 'Tanpa Judul'))
            list_berita.append({
                'Judul': judul,
                'Tanggal': row.get('tanggal', row.get('Tanggal', 'Unknown Date')),
                'Kabupaten': row.get('kabupaten', row.get('Kabupaten', 'Kalbar'))
            })
    except Exception as e:
        pass

# ----------------------------------------------------
# 2. INGEST DATA CUACA HARIAN DARI GIT ACTIONS
# ----------------------------------------------------
print("\n[2/5] Membaca data cuaca harian...")
df_git_cuaca = None
df_local = None
if os.path.exists(LOCAL_CUACA_PATH):
    try:
        df_local = pd.read_csv(LOCAL_CUACA_PATH)
    except Exception as e:
        pass

df_url = None
try:
    df_url = pd.read_csv(URL_CUACA, timeout=5)
except Exception as e:
    pass

if df_local is not None and df_url is not None:
    try:
        tanggal_cols = [c for c in df_local.columns if 'tanggal' in c.lower() or 'waktu' in c.lower()]
        tanggal_col_test = tanggal_cols[0] if len(tanggal_cols) > 0 else df_local.columns[0]
        local_max = pd.to_datetime(df_local[tanggal_col_test]).max()
        url_max = pd.to_datetime(df_url[tanggal_col_test]).max()
        if local_max >= url_max:
            df_git_cuaca = df_local
        else:
            df_git_cuaca = df_url
    except Exception as e:
        df_git_cuaca = df_local if df_local is not None else df_url
elif df_local is not None:
    df_git_cuaca = df_local
elif df_url is not None:
    df_git_cuaca = df_url

if df_git_cuaca is None:
    raise ValueError("Gagal memuat data cuaca.")

df_git_cuaca.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_cuaca.columns]
kab_col = [col for col in df_git_cuaca.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower()][0]
suhu_col = [col for col in df_git_cuaca.columns if 'suhu' in col.lower()][0]
kelembapan_col = [col for col in df_git_cuaca.columns if 'kelembapan' in col.lower()][0]
hujan_col = [col for col in df_git_cuaca.columns if 'hujan' in col.lower() or 'hujan (mm)' in col.lower()][0]

tanggal_cols = [col for col in df_git_cuaca.columns if 'tanggal' in col.lower() or 'waktu' in col.lower()]
tanggal_col = tanggal_cols[0] if len(tanggal_cols) > 0 else df_git_cuaca.columns[0]

df_git_cuaca['Key'] = df_git_cuaca[kab_col].apply(standardisasi_nama)
df_git_cuaca = df_git_cuaca.sort_values(by=['Key', tanggal_col], ascending=True)

df_git_cuaca[tanggal_col] = pd.to_datetime(df_git_cuaca[tanggal_col])
latest_date = df_git_cuaca[tanggal_col].max()

df_cuaca_latest = df_git_cuaca[df_git_cuaca[tanggal_col] == latest_date]
df_cuaca_7d = df_git_cuaca[df_git_cuaca[tanggal_col] >= latest_date - pd.Timedelta(days=6)]

peta_cuaca = {}
for kab, group in df_cuaca_7d.groupby('Key'):
    baris_terbaru = df_cuaca_latest[df_cuaca_latest['Key'] == kab]
    if len(baris_terbaru) > 0:
        suhu_hari_ini = float(baris_terbaru[suhu_col].values[0])
        kelembapan_hari_ini = float(baris_terbaru[kelembapan_col].values[0])
    else:
        suhu_hari_ini = float(group[suhu_col].mean())
        kelembapan_hari_ini = float(group[kelembapan_col].mean())
        
    total_hujan_7d = float(group[hujan_col].sum())
    hujan_kritis_berturut_7d = hitung_hari_kritis_berturut_turut(group[hujan_col], threshold=10)
    
    peta_cuaca[kab] = {
        'Suhu': round(suhu_hari_ini, 2),
        'Kelembapan': round(kelembapan_hari_ini, 2),
        'THI': hitung_thi(suhu_hari_ini, kelembapan_hari_ini),
        'Hujan_7D': round(total_hujan_7d, 2),
        'Hujan_Kritis_Berturut_7D': hujan_kritis_berturut_7d
    }

# ----------------------------------------------------
# 3. INGEST DATA DEMOGRAFI
# ----------------------------------------------------
print("\n[3/5] Membaca data kependudukan...")
try:
    df_master = pd.read_excel(JALUR_EXCEL, sheet_name='Master_Wilayah')
except Exception as e:
    df_master = pd.DataFrame([
        {"Wilayah": "KOTA PONTIANAK", "Penduduk_Terbaru": 672440, "Luas_Wilayah": 107.82}
    ])

# ----------------------------------------------------
# 4. TRAINING MODEL: 4-FEATURE MODEL (INDEPENDENT)
# ----------------------------------------------------
print("\n[4/5] Melatih Model Naive Bayes 4 Fitur...")
try:
    df_train = pd.read_excel(DATASET_TRAINING)
    
    # 1. K-Means menggunakan 6 fitur lengkap untuk membuat label klaster historis yang objektif
    fitur_lengkap = ['Kepadatan', 'Suhu', 'Kelembapan', 'THI', 'Total_Hujan', 'Hujan_Kritis']
    X_kmeans = df_train[fitur_lengkap]
    scaler_kmeans = StandardScaler()
    X_kmeans_scaled = scaler_kmeans.fit_transform(X_kmeans)
    
    kmeans_model = KMeans(n_clusters=3, random_state=42, n_init=10)
    y_train = kmeans_model.fit_predict(X_kmeans_scaled)
    
    # 2. Naive Bayes HANYA dilatih menggunakan 4 fitur independen (Suhu & Lembap DIBUANG)
    fitur_nb = ['Kepadatan', 'THI', 'Total_Hujan', 'Hujan_Kritis']
    X_train_nb = df_train[fitur_nb]
    min_bounds = X_train_nb.min()
    max_bounds = X_train_nb.max()
    
    scaler_nb = StandardScaler()
    X_train_nb_scaled = scaler_nb.fit_transform(X_train_nb)
    
    # Latih Gaussian Naive Bayes dengan Tuning Hyperparameter
    base_nb = GaussianNB()
    param_grid = {'var_smoothing': np.logspace(0, -9, num=100)}
    grid_search = GridSearchCV(base_nb, param_grid, cv=3, scoring='accuracy')
    grid_search.fit(X_train_nb_scaled, y_train)
    
    model_nb_tuned = grid_search.best_estimator_
    
    # Hitung akurasi latihan
    y_pred_train = model_nb_tuned.predict(X_train_nb_scaled)
    train_acc = accuracy_score(y_train, y_pred_train) * 100
    
    print(f"      -> Best var_smoothing  : {grid_search.best_params_['var_smoothing']:.2E}")
    print(f"      -> Akurasi Training NB : {train_acc:.2f}%")
    
    arti_status = {
        0: "WASPADA (Endemisitas Sedang - Faktor Kelembapan)",
        1: "SIAGA (Risiko Tinggi - Kerawanan Curah Hujan Ekstrem)",
        2: "AMAN (Kondisi Stabil - Dampak Kepadatan Terkendali)"
    }
except Exception as e:
    raise ValueError(f"Gagal melatih model: {e}")

# ----------------------------------------------------
# 5. INFERENCE: DIAGNOSIS STATUS LEVEL RISIKO
# ----------------------------------------------------
print("\n[5/5] Melakukan diagnosis level risiko DBD...")
laporan_final = []

for _, baris in df_master.iterrows():
    raw_nama = str(baris['Wilayah']).upper().strip()
    kab_key = standardisasi_nama(raw_nama)
    
    # Ambil kepadatan dari training dataset
    df_2023 = df_train[df_train['Tahun'] == 2023]
    peta_kepadatan = dict(zip(df_2023['Wilayah'].apply(standardisasi_nama), df_2023['Kepadatan']))
    kepadatan = peta_kepadatan.get(kab_key, 50.0)
    
    # Ambil data cuaca
    cuaca = peta_cuaca.get(kab_key, {
        'Suhu': 27.2, 
        'Kelembapan': 82.0, 
        'THI': 78.4, 
        'Hujan_7D': 65.0,
        'Hujan_Kritis_Berturut_7D': 1
    })
    
    thi = cuaca['THI']
    hujan_7d = cuaca['Hujan_7D']
    hujan_kritis_7d = cuaca['Hujan_Kritis_Berturut_7D']
    
    # Proyeksi
    total_hujan_tahunan = round(hujan_7d * 52.18, 2)
    hujan_kritis_tahunan = round(hujan_kritis_7d * 52.18, 2)
    
    # np.clip
    total_hujan_tahunan = float(np.clip(total_hujan_tahunan, min_bounds['Total_Hujan'], max_bounds['Total_Hujan']))
    hujan_kritis_tahunan = float(np.clip(hujan_kritis_tahunan, min_bounds['Hujan_Kritis'], max_bounds['Hujan_Kritis']))
    
    # Vektor input 4 fitur
    vektor_input = pd.DataFrame([[kepadatan, thi, total_hujan_tahunan, hujan_kritis_tahunan]], columns=fitur_nb)
    vektor_input_scaled = scaler_nb.transform(vektor_input)
    
    # Prediksi
    prediksi_idx = int(model_nb_tuned.predict(vektor_input_scaled)[0])
    status_final = arti_status[prediksi_idx]
    
    peluang_array = model_nb_tuned.predict_proba(vektor_input_scaled)[0]
    keyakinan_sistem = round(peluang_array[prediksi_idx] * 100, 1)
    jumlah_berita = int(peta_berita.get(kab_key, 0))
    
    laporan_final.append({
        'Wilayah': raw_nama,
        'Kepadatan': round(kepadatan, 1),
        'THI': thi,
        'Hujan 7D (mm)': hujan_7d,
        'Hujan Kritis Konsekutif 7D (Hari)': hujan_kritis_7d,
        'Berita': jumlah_berita,
        'Status': status_final
    })

df_laporan = pd.DataFrame(laporan_final)

# ==================================================================
# 6. REPORT GENERATION: MENERBITKAN DOKUMEN LOG BARU
# ==================================================================
log_output = f"""================================================================================
LAPORAN OTOMATIS: EARLY WARNING SYSTEM DBD KALBAR (MODEL 4 FITUR INDEPENDEN)
Dieksekusi Otomatis Pada : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================================================================

1. HASIL DIAGNOSIS MODEL AI HYBRID TUNED (4 FITUR: Kepadatan, THI, Hujan, Hujan Kritis):
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

# Simpan ke berkas laporan baru
laporan_baru_path = os.path.join(BASE_DIR, "laporan_pantauan_terkini_4fitur.txt")
with open(laporan_baru_path, "w", encoding="utf-8") as f:
    f.write(log_output)

print(f"\n=== SELESAI! Laporan baru disimpan di: '{laporan_baru_path}' ===")
print(log_output)
