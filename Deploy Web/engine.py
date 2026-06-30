r"""
EWS DBD Kalbar — Engine ML
Port dari prediction.py & StrategiC_Alert3.py untuk digunakan sebagai modul Flask API.
Menggunakan model latih riil dari dataset_tahunan.xlsx (6 fitur) dan data BMKG/Google News.
Output: list of dicts (JSON-serializable)
"""

import pandas as pd
import os
import numpy as np
import re
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import MinMaxScaler, StandardScaler
from sklearn.cluster import KMeans
from sklearn.model_selection import GridSearchCV
from scipy.special import logsumexp

# ==================================================================
# CUSTOM WEIGHTED NAIVE BAYES CLASS
# ==================================================================
class WeightedGaussianNB(GaussianNB):
    def __init__(self, var_smoothing=1e-9, feature_weights=None):
        super().__init__(var_smoothing=var_smoothing)
        self.feature_weights = feature_weights

    def predict_log_proba(self, X):
        from sklearn.utils.validation import check_is_fitted
        check_is_fitted(self)
        
        X = np.asarray(X)
        n_samples, n_features = X.shape
        n_classes = len(self.classes_)
        
        log_prior = np.log(self.class_prior_)
        jll = np.zeros((n_samples, n_classes))
        
        for i in range(n_classes):
            theta = self.theta_[i]
            var = self.var_[i]
            
            log_prob_features = -0.5 * np.log(2 * np.pi * var) - 0.5 * ((X - theta) ** 2) / var
            
            if self.feature_weights is not None:
                weights = np.asarray(self.feature_weights)
                log_prob_features = log_prob_features * weights
                
            jll[:, i] = log_prior[i] + np.sum(log_prob_features, axis=1)
            
        log_prob = jll - logsumexp(jll, axis=1, keepdims=True)
        return log_prob

    def predict_proba(self, X):
        return np.exp(self.predict_log_proba(X))

    def predict(self, X):
        return self.classes_[np.argmax(self.predict_log_proba(X), axis=1)]

# ==================================================================
# CONFIG PATH — Dinamis menyesuaikan letak folder
# ==================================================================
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(CURRENT_DIR)

# Cek di folder dataset lokal Deploy Web dulu, lalu folder root Deploy Web, baru parent
if os.path.exists(os.path.join(CURRENT_DIR, "dataset", "SEC13 SATRIA DATA 2026 REMINDER.xlsx")):
    JALUR_EXCEL = os.path.join(CURRENT_DIR, "dataset", "SEC13 SATRIA DATA 2026 REMINDER.xlsx")
elif os.path.exists(os.path.join(CURRENT_DIR, "SEC13 SATRIA DATA 2026 REMINDER.xlsx")):
    JALUR_EXCEL = os.path.join(CURRENT_DIR, "SEC13 SATRIA DATA 2026 REMINDER.xlsx")
else:
    JALUR_EXCEL = os.path.join(PARENT_DIR, "SEC13 SATRIA DATA 2026 REMINDER.xlsx")

if os.path.exists(os.path.join(CURRENT_DIR, "dataset", "dataset_tahunan.xlsx")):
    DATASET_TRAINING = os.path.join(CURRENT_DIR, "dataset", "dataset_tahunan.xlsx")
elif os.path.exists(os.path.join(CURRENT_DIR, "dataset_tahunan.xlsx")):
    DATASET_TRAINING = os.path.join(CURRENT_DIR, "dataset_tahunan.xlsx")
else:
    DATASET_TRAINING = os.path.join(PARENT_DIR, "dataset_tahunan.xlsx")
URL_BERITA  = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/data/berita_dbd.csv"
URL_CUACA   = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data%20Cuaca%20Harian%20Kalbar/Data_Cuaca_Harian_Kalbar_Hari_Ini.csv"
URL_DETAIL  = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/data/detail_berita.csv"

# ==================================================================
# HELPER FUNCTIONS
# ==================================================================
def hitung_thi(suhu, kelembapan):
    farenheit = (1.8 * suhu) + 32
    idx_lembab = 0.55 - (0.55 * (kelembapan / 100))
    thi = farenheit - idx_lembab * (farenheit - 58)
    return round(thi, 2)

def standardisasi_nama(teks):
    if pd.isna(teks): return ""
    t = str(teks).upper().strip()
    t = t.replace('KAB. ', '').replace('KABUPATEN ', '').replace('KOTA ', '')
    t = " ".join(t.split())
    return t

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

# ==================================================================
# MAIN MODEL RUNNER
# ==================================================================
def run_model(fogging_overrides=None):
    """
    Menjalankan model EWS DBD.
    fogging_overrides: dict {kabupaten_raw_nama: True} 
                       → kabupaten tsb dipotong risiko sosial 85%
    Returns: list of dicts dengan semua metrik
    """
    if fogging_overrides is None:
        fogging_overrides = {}

    errors = []

    # ------------------------------------------------------------------
    # TAHAP 1: STREAMING DATA EKSTERNAL (GIT SOURCES / LOKAL)
    # ------------------------------------------------------------------
    peta_berita = {}
    try:
        df_git_berita = pd.read_csv(URL_BERITA)
        df_git_berita.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_berita.columns]
        kab_col = [col for col in df_git_berita.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower()][0]
        total_col = [col for col in df_git_berita.columns if 'total 7' in col.lower() or 'total' in col.lower()][0]
        df_git_berita['Key'] = df_git_berita[kab_col].apply(standardisasi_nama)
        peta_berita = dict(zip(df_git_berita['Key'], df_git_berita[total_col]))
    except Exception as e:
        errors.append(f"Gagal memuat berita dari URL: {e}")

    peta_detail_berita = {}
    df_git_detail = None
    try:
        df_git_detail = pd.read_csv(URL_DETAIL)
    except Exception as e:
        errors.append(f"Gagal memuat detail berita dari URL: {e}")
        
    # 4. Parsing dan kelompokkan berita per wilayah
    if df_git_detail is not None:
        try:
            df_git_detail.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_detail.columns]
            kab_col_det = [col for col in df_git_detail.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower() or 'kab' in col.lower()][0]
            judul_col = [col for col in df_git_detail.columns if 'judul' in col.lower()][0]
            link_col = [col for col in df_git_detail.columns if 'link' in col.lower()][0]
            
            for _, row_detail in df_git_detail.iterrows():
                kab_val = standardisasi_nama(row_detail[kab_col_det])
                judul_val = str(row_detail[judul_col]).strip()
                link_val = str(row_detail[link_col]).strip()
                
                if kab_val not in peta_detail_berita:
                    peta_detail_berita[kab_val] = []
                peta_detail_berita[kab_val].append({
                    'judul': judul_val,
                    'link': link_val
                })
        except Exception as e:
            errors.append(f"Gagal memproses detail berita: {e}")

    peta_cuaca = {}
    df_git_cuaca = None
    
    try:
        df_git_cuaca = pd.read_csv(URL_CUACA)
    except Exception as e:
        errors.append(f"Gagal mengunduh cuaca dari URL: {e}")

    if df_git_cuaca is not None:
        try:
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
        except Exception as e:
            errors.append(f"Cuaca Git parse error: {e}")

    # ------------------------------------------------------------------
    # TAHAP 2: DATA EKSTERNAL KASUS HISTORIS (UNTUK TAMPILAN)
    # ------------------------------------------------------------------
    peta_kasus_terakhir = {}
    rata_rata_regional = 120
    try:
        df_kasus = pd.read_excel(JALUR_EXCEL, sheet_name='test 2')
        df_kasus['Key'] = df_kasus['Wilayah'].apply(standardisasi_nama)
        kolom_tahun_kasus = 'TAHUN' if 'TAHUN' in df_kasus.columns else 'Tahun'
        df_kasus[kolom_tahun_kasus] = pd.to_numeric(df_kasus[kolom_tahun_kasus], errors='coerce').fillna(0).astype(int)
        
        kolom_terjangkit = 'Jumlah_Terjangkit' if 'Jumlah_Terjangkit' in df_kasus.columns else 'Jumlah_Terjang'
        if kolom_terjangkit not in df_kasus.columns:
            for col in df_kasus.columns:
                if 'terjang' in col.lower():
                    kolom_terjangkit = col

        tahun_terakhir = df_kasus[kolom_tahun_kasus].max()
        df_tahun_akhir = df_kasus[df_kasus[kolom_tahun_kasus] == tahun_terakhir]
        peta_kasus_terakhir = dict(zip(df_tahun_akhir['Key'], df_tahun_akhir[kolom_terjangkit]))
        rata_rata_regional = int(df_tahun_akhir[kolom_terjangkit].mean()) if len(df_tahun_akhir) > 0 else 120
    except Exception as e:
        errors.append(f"Gagal membaca data kasus Excel: {e}")

    # ------------------------------------------------------------------
    # TAHAP 3: TRAINING RIIL MODEL DARI DATASET TAHUNAN
    # ------------------------------------------------------------------
    try:
        df_train = pd.read_excel(DATASET_TRAINING)
        
        # Ekstrak data kepadatan tahun terbaru (2023) langsung dari dataset tahunan
        df_2023 = df_train[df_train['Tahun'] == 2023]
        peta_kepadatan = {}
        for _, r in df_2023.iterrows():
            key = standardisasi_nama(r['Wilayah'])
            peta_kepadatan[key] = float(r['Kepadatan'])
            
        fitur_kolom = ['Kepadatan', 'Suhu', 'Kelembapan', 'THI', 'Total_Hujan', 'Hujan_Kritis']
        X_kmeans = df_train[fitur_kolom]
        
        scaler_kmeans = StandardScaler()
        X_kmeans_scaled = scaler_kmeans.fit_transform(X_kmeans)
        
        kmeans_model = KMeans(n_clusters=3, random_state=42, n_init=10)
        y_train = kmeans_model.fit_predict(X_kmeans_scaled)
        
        # 4 features for Weighted Naive Bayes
        fitur_nb = ['Kepadatan', 'THI', 'Total_Hujan', 'Hujan_Kritis']
        X_train_nb = df_train[fitur_nb]
        
        min_bounds = X_train_nb.min()
        max_bounds = X_train_nb.max()
        
        scaler = StandardScaler()
        X_train_nb_scaled = scaler.fit_transform(X_train_nb)
        
        bobot_fitur = [1.0, 0.5, 0.25, 0.25]
        base_nb = WeightedGaussianNB(feature_weights=bobot_fitur)
        param_grid = {'var_smoothing': np.logspace(0, -9, num=100)}
        grid_search = GridSearchCV(base_nb, param_grid, cv=5, scoring='accuracy')
        grid_search.fit(X_train_nb_scaled, y_train)
        
        model_nb_tuned = grid_search.best_estimator_
        
        # Mapping kelas baru (sesuai prediction.py)
        # Cluster 0 = WASPADA, Cluster 1 = SIAGA, Cluster 2 = AMAN
        mapping_kelas = {0: 'WASPADA', 1: 'SIAGA', 2: 'AMAN'}
    except Exception as e:
        return {"error": f"Gagal training model: {e}"}

    # ------------------------------------------------------------------
    # TAHAP 4: INFERENSI AKTUAL
    # ------------------------------------------------------------------
    try:
        df_master = pd.read_excel(JALUR_EXCEL, sheet_name='Master_Wilayah')
    except Exception as e:
        return {"error": f"Gagal membaca Master_Wilayah: {e}"}

    koleksi_fitur_live = []
    for _, baris in df_master.iterrows():
        raw_nama   = str(baris['Wilayah']).upper().strip()
        kab_key    = standardisasi_nama(raw_nama)
        penduduk   = baris['Penduduk_Terbaru']
        luas       = baris['Luas_Wilayah']
        
        # Prioritas kepadatan dari 2023 dataset_tahunan, fallback ke hitungan Master_Wilayah
        kepadatan = peta_kepadatan.get(kab_key, penduduk / luas)
        total_berita = int(peta_berita.get(kab_key, 0))

        cuaca = peta_cuaca.get(kab_key, {
            'Suhu': 27.2, 
            'Kelembapan': 82.0, 
            'THI': 78.4, 
            'Hujan_7D': 65.0,
            'Hujan_Kritis_Berturut_7D': 1
        })

        koleksi_fitur_live.append({
            'raw_nama': raw_nama,
            'kab_key': kab_key,
            'kepadatan': kepadatan,
            'suhu': cuaca['Suhu'],
            'kelembapan': cuaca['Kelembapan'],
            'thi': cuaca['THI'],
            'hujan_7d': cuaca['Hujan_7D'],
            'hujan_kritis_7d': cuaca['Hujan_Kritis_Berturut_7D'],
            'berita': total_berita,
            'kasus_lalu': peta_kasus_terakhir.get(kab_key, rata_rata_regional),
            'fogging_active': fogging_overrides.get(raw_nama, False)
        })

    df_inferensi = pd.DataFrame(koleksi_fitur_live)
    
    # Kepadatan scaled untuk log-drift (range 8.0 s/d 58.0)
    scaler_kepadatan = MinMaxScaler(feature_range=(8.0, 58.0))
    df_inferensi['kepadatan_scaled'] = scaler_kepadatan.fit_transform(np.log1p(df_inferensi[['kepadatan']]))

    laporan_final = []
    for _, row in df_inferensi.iterrows():
        kasus_live = row['kasus_lalu']

        kepadatan_inj = row['kepadatan']
        suhu_inj = row['suhu']
        kelembapan_inj = row['kelembapan']
        thi_inj = row['thi']
        hujan_7d = row['hujan_7d']
        hujan_kritis_7d = row['hujan_kritis_7d']

        # Proyeksi data cuaca harian ke skala tahunan untuk model
        total_hujan_tahunan = round(hujan_7d * 52.18, 2)
        hujan_kritis_tahunan = round(hujan_kritis_7d * 52.18, 2)

        # Batasi agar tidak melompat keluar dari batas distribusi data training (out-of-distribution)
        total_hujan_tahunan = float(np.clip(total_hujan_tahunan, min_bounds['Total_Hujan'], max_bounds['Total_Hujan']))
        hujan_kritis_tahunan = float(np.clip(hujan_kritis_tahunan, min_bounds['Hujan_Kritis'], max_bounds['Hujan_Kritis']))

        # Jika fogging aktif, override output status sesuai user request
        if row['fogging_active']:
            status_final = 'SIAGA (Fogging Dijalankan)'
            analisis_proaktif = '[PENANGANAN] Fogging Dijalankan'
            keyakinan_sistem = 100.0  # Keyakinan sistem untuk intervensi
            p_aman = 85.0             # Karena 85% risk reduced
            p_waspada = 10.0
            p_siaga = 5.0
        else:
            # Lakukan prediksi model (4 fitur: Kepadatan, THI, Total Hujan, Hujan Kritis)
            data_uji = pd.DataFrame([[kepadatan_inj, thi_inj, total_hujan_tahunan, hujan_kritis_tahunan]], 
                                    columns=['Kepadatan', 'THI', 'Total_Hujan', 'Hujan_Kritis'])
            data_uji_scaled = scaler.transform(data_uji)
            peluang_array = model_nb_tuned.predict_proba(data_uji_scaled)[0]

            # Urutan peluang sesuai cluster index: 0=WASPADA, 1=SIAGA, 2=AMAN
            p_waspada = float(peluang_array[0])
            p_siaga = float(peluang_array[1])
            p_aman = float(peluang_array[2])

            prediksi_idx = int(np.argmax(peluang_array))
            
            arti_status = {
                0: "WASPADA (Endemisitas Sedang - Faktor Kelembapan)",
                1: "SIAGA (Risiko Tinggi - Kerawanan Curah Hujan Ekstrem)",
                2: "AMAN (Kondisi Stabil - Dampak Kepadatan Terkendali)"
            }
            status_final = arti_status[prediksi_idx]
            keyakinan_sistem = round(peluang_array[prediksi_idx] * 100, 1)

            # Deskripsi analisis proaktif
            if prediksi_idx == 2: # AMAN
                analisis_proaktif = "[RAWAN] Kepadatan penduduk terkendali"
            elif prediksi_idx == 0: # WASPADA
                analisis_proaktif = "[KRITIS] Kelembapan udara memicu transmisi"
            else: # SIAGA
                analisis_proaktif = "[DARURAT] Curah hujan ekstrem di wilayah"

        laporan_final.append({
            'kabupaten': row['raw_nama'],
            'kepadatan': round(float(row['kepadatan']), 1),
            'kasus_lalu': int(kasus_live),
            'suhu': float(row['suhu']),
            'kelembapan': float(row['kelembapan']),
            'thi': float(row['thi']),
            'hujan_7d': float(row['hujan_7d']),
            'berita': int(row['berita']),
            'status': status_final,
            'keyakinan': f"{keyakinan_sistem}%",
            'keyakinan_num': keyakinan_sistem,
            'analisis_proaktif': analisis_proaktif,
            'golden_window': False,
            'fogging_active': bool(row['fogging_active']),
            'p_aman': round(p_aman * 100, 1),
            'p_waspada': round(p_waspada * 100, 1),
            'p_siaga': round(p_siaga * 100, 1),
            'detail_berita': peta_detail_berita.get(row['kab_key'], [])
        })

    return laporan_final
