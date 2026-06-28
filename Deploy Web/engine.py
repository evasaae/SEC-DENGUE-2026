r"""
EWS DBD Kalbar — Engine ML
Port dari StrategiC_Alert3.py untuk digunakan sebagai modul Flask API.
Sumber data Excel: D:\SATRIA DATA\SEC-DENGUE-2026\
Output: list of dicts (JSON-serializable)
"""

import pandas as pd
import os
import numpy as np
import re
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import LabelEncoder, MinMaxScaler

# ==================================================================
# CONFIG PATH — Sumber dari SEC-DENGUE-2026
# ==================================================================
JALUR_EXCEL = r"C:\Users\user\SIGAP-DBD\Deploy Web\SEC13 SATRIA DATA 2026 REMINDER.xlsx"
URL_BERITA  = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/data/berita_dbd.csv"
URL_CUACA   = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data%20Cuaca%20Harian%20Kalbar/Data_Cuaca_Harian_Kalbar_Hari_Ini.csv"

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
    # TAHAP 1: STREAMING DATA EKSTERNAL (GIT SOURCES)
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
        errors.append(f"Berita Git error: {e}")

    peta_cuaca = {}
    try:
        df_git_cuaca = pd.read_csv(URL_CUACA)
        df_git_cuaca.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_cuaca.columns]
        kab_col = [col for col in df_git_cuaca.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower()][0]
        suhu_col = [col for col in df_git_cuaca.columns if 'suhu' in col.lower()][0]
        kelembapan_col = [col for col in df_git_cuaca.columns if 'kelembapan' in col.lower()][0]
        hujan_col = [col for col in df_git_cuaca.columns if 'hujan 7' in col.lower() or 'hujan_7' in col.lower() or 'jam hujan 7' in col.lower()][0]
        
        # default fallback jika kolom tanggal tidak ditemukan
        tanggal_cols = [col for col in df_git_cuaca.columns if 'tanggal' in col.lower() or 'waktu' in col.lower()]
        tanggal_col = tanggal_cols[0] if len(tanggal_cols) > 0 else df_git_cuaca.columns[0]
        
        df_git_cuaca['Key'] = df_git_cuaca[kab_col].apply(standardisasi_nama)
        
        # Urutkan berdasarkan Key dan Tanggal menaik untuk rolling window kronologis
        df_git_cuaca = df_git_cuaca.sort_values(by=['Key', tanggal_col], ascending=True)
        
        # default fallback jika kolom jam hujan harian tidak ditemukan
        jam_hujan_harian_cols = [col for col in df_git_cuaca.columns if 'jam hujan' in col.lower() and '7' not in col.lower()]
        if len(jam_hujan_harian_cols) > 0:
            jam_hujan_harian_col = jam_hujan_harian_cols[0]
            df_git_cuaca['Hujan_Lebat_Harian'] = (df_git_cuaca[jam_hujan_harian_col] > 5).astype(int)
        else:
            df_git_cuaca['Hujan_Lebat_Harian'] = (df_git_cuaca[hujan_col] / 7.0 > 5.0 / 7.0).astype(int)

        # Hitung Hujan_Kritis_3D (rolling sum 3 hari >= 3)
        df_git_cuaca['Hujan_Kritis_3D'] = df_git_cuaca.groupby('Key')['Hujan_Lebat_Harian'].transform(
            lambda x: (x.rolling(window=3, min_periods=1).sum() >= 3).astype(int)
        )
        
        # Ambil baris terakhir (terbaru) untuk masing-masing wilayah
        df_git_cuaca_latest = df_git_cuaca.drop_duplicates(subset=['Key'], keep='last')
        
        for _, baris in df_git_cuaca_latest.iterrows():
            kab_key = baris['Key']
            suhu = float(baris[suhu_col])
            kelembapan = float(baris[kelembapan_col])
            total_jam_hujan = float(baris[hujan_col])
            hujan_kritis = int(baris['Hujan_Kritis_3D'])
            peta_cuaca[kab_key] = {
                'Suhu': suhu,
                'Kelembapan': kelembapan,
                'THI': hitung_thi(suhu, kelembapan),
                'Total_Jam_Hujan': total_jam_hujan,
                'Hujan_Kritis_3D': hujan_kritis
            }
    except Exception as e:
        errors.append(f"Cuaca Git error: {e}")

    # ------------------------------------------------------------------
    # TAHAP 2: DATA EKSTERNAL KASUS
    # ------------------------------------------------------------------
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
        return {"error": f"Gagal membaca data kasus Excel: {e}"}

    # ------------------------------------------------------------------
    # TAHAP 3: TRAINING TUNED NAIVE BAYES MODEL
    # ------------------------------------------------------------------
    try:
        np.random.seed(42)
        n_samples = 300

        hist_kepadatan = np.random.uniform(10, 200, n_samples)
        hist_kasus_lalu = np.random.randint(50, 1600, n_samples)
        hist_thi = np.random.uniform(72, 83, n_samples)
        hist_total_hujan = np.random.uniform(0, 80, n_samples)
        hist_hujan_kritis = np.random.choice([0, 1], size=n_samples, p=[0.6, 0.4])

        X_historical = np.column_stack((hist_kepadatan, hist_kasus_lalu, hist_thi, hist_total_hujan, hist_hujan_kritis))

        y_historical = []
        for i in range(n_samples):
            if X_historical[i, 2] > 78.5 and X_historical[i, 4] == 1:
                status = 2  # SIAGA
            elif X_historical[i, 1] > 600 or X_historical[i, 3] > 40:
                status = 1  # WASPADA
            else:
                status = 0  # AMAN
                
            # Noise 10%
            if np.random.rand() < 0.10:
                status = np.random.choice([0, 1, 2])
            y_historical.append(status)
        y_historical = np.array(y_historical)

        # DataFrame untuk outlier removal
        df_hist = pd.DataFrame(X_historical, columns=['Kepadatan', 'Kasus', 'THI', 'Hujan', 'Hujan_Kritis'])
        df_hist['Target'] = y_historical

        # Outlier removal
        for col in ['Kasus', 'Hujan']:
            Q1 = df_hist[col].quantile(0.25)
            Q3 = df_hist[col].quantile(0.75)
            IQR = Q3 - Q1
            df_hist = df_hist[~((df_hist[col] < (Q1 - 1.5 * IQR)) | (df_hist[col] > (Q3 + 1.5 * IQR)))]

        X_clean = df_hist.drop(columns=['Target']).values
        y_clean = df_hist['Target'].values

        # Split & Fit Scaler
        from sklearn.model_selection import train_test_split, GridSearchCV
        from sklearn.preprocessing import StandardScaler
        
        X_train, X_test, y_train, y_test = train_test_split(
            X_clean, y_clean, test_size=0.2, random_state=42, stratify=y_clean
        )

        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)

        # Tuning GridSearchCV
        base_nb = GaussianNB()
        param_grid = {'var_smoothing': np.logspace(0, -9, num=100)}
        grid_search = GridSearchCV(base_nb, param_grid, cv=5, scoring='accuracy')
        grid_search.fit(X_train_scaled, y_train)

        model_nb_tuned = grid_search.best_estimator_
        mapping_kelas = {0: 'AMAN', 1: 'WASPADA', 2: 'SIAGA'}
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
        kepadatan  = penduduk / luas
        total_berita = int(peta_berita.get(kab_key, 0))

        cuaca = peta_cuaca.get(kab_key, {
            'Suhu': 27.2, 
            'Kelembapan': 82.0, 
            'THI': 78.4, 
            'Total_Jam_Hujan': 3.0,
            'Hujan_Kritis_3D': 0
        })

        koleksi_fitur_live.append({
            'raw_nama': raw_nama,
            'kab_key': kab_key,
            'kepadatan': kepadatan,
            'suhu': cuaca['Suhu'],
            'kelembapan': cuaca['Kelembapan'],
            'thi': cuaca['THI'],
            'hujan_7d': cuaca['Total_Jam_Hujan'],
            'hujan_kritis_3d': cuaca['Hujan_Kritis_3D'],
            'berita': total_berita,
            'kasus_lalu': peta_kasus_terakhir.get(kab_key, rata_rata_regional),
            'fogging_active': fogging_overrides.get(raw_nama, False)
        })

    df_inferensi = pd.DataFrame(koleksi_fitur_live)
    
    # Kepadatan scaled untuk log-drift di AMAN (range 8.0 s/d 58.0)
    scaler_kepadatan = MinMaxScaler(feature_range=(8.0, 58.0))
    df_inferensi['kepadatan_scaled'] = scaler_kepadatan.fit_transform(np.log1p(df_inferensi[['kepadatan']]))

    laporan_final = []
    for _, row in df_inferensi.iterrows():
        kasus_live = row['kasus_lalu'] if row['kasus_lalu'] != 10 else rata_rata_regional

        kepadatan_inj = row['kepadatan']
        thi_inj = row['thi']
        hujan_inj = row['hujan_7d']
        hujan_kritis_inj = row['hujan_kritis_3d']

        # Jika fogging aktif, override output status dan drift risk sesuai user request
        if row['fogging_active']:
            status_final = 'SIAGA (Fogging Dijalankan)'
            persen_drift = 15.0
            analisis_proaktif = '[PENANGANAN] Fogging Dijalankan'
            keyakinan_sistem = 100.0  # Keyakinan sistem untuk intervensi
            p_aman = 0.85             # Karena 85% risk reduced
            p_waspada = 0.10
            p_siaga = 0.05
            golden_window = False
        else:
            # Lakukan prediksi model
            data_uji = [[kepadatan_inj, kasus_live, thi_inj, hujan_inj, hujan_kritis_inj]]
            data_uji_scaled = scaler.transform(data_uji)
            peluang_array = model_nb_tuned.predict_proba(data_uji_scaled)[0]

            p_aman = float(peluang_array[0])
            p_waspada = float(peluang_array[1])
            p_siaga = float(peluang_array[2])

            prediksi_idx = int(np.argmax(peluang_array))
            status_final = mapping_kelas[prediksi_idx]
            
            efek_iklim = (row['thi'] - 74) * 2.0
            persen_drift = 0.0

            if status_final == 'AMAN':
                base_drift = (p_waspada / (p_aman + p_waspada)) * 100 if (p_aman + p_waspada) > 0 else 0
                persen_ke_waspada = round(max(5.0, min(95.0, (row['kepadatan_scaled'] + efek_iklim) if base_drift < 0.001 else (base_drift + efek_iklim))), 1)
                analisis_proaktif = f"[RAWAN] {persen_ke_waspada}% Menuju WASPADA"
                keyakinan_sistem = round(100.0 - persen_ke_waspada, 1)
                persen_drift = persen_ke_waspada
                golden_window = False

            elif status_final == 'WASPADA':
                base_drift = (p_siaga / (p_waspada + p_siaga)) * 100 if (p_waspada + p_siaga) > 0 else 0
                persen_ke_siaga = round(max(5.0, min(95.0, (45.0 + efek_iklim + row['hujan_7d'] * 1.5) if base_drift < 0.001 else (base_drift + efek_iklim))), 1)
                analisis_proaktif = f"[KRITIS] {persen_ke_siaga}% Menuju SIAGA"
                keyakinan_sistem = round(100.0 - persen_ke_siaga, 1)
                persen_drift = persen_ke_siaga
                golden_window = persen_ke_siaga > 50  # GOLDEN WINDOW TRIGGER

            elif status_final == 'SIAGA':
                keyakinan_sistem = round(peluang_array[prediksi_idx] * 100, 1)
                if keyakinan_sistem > 88 or row['thi'] > 78.4:
                    analisis_proaktif = "[DARURAT] AKUT (KLB)"
                else:
                    analisis_proaktif = "[SIAGA] Monitor Ketat Wilayah"
                persen_drift = 100.0
                golden_window = False

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
            'persen_drift': persen_drift,
            'golden_window': golden_window,
            'fogging_active': bool(row['fogging_active']),
            'p_aman': round(p_aman * 100, 1),
            'p_waspada': round(p_waspada * 100, 1),
            'p_siaga': round(p_siaga * 100, 1),
        })

    return laporan_final
