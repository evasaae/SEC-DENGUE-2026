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
JALUR_EXCEL = r"D:\SATRIA DATA\SEC-DENGUE-2026\SEC13 SATRIA DATA 2026 REMINDER.xlsx"
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
        
        df_git_cuaca['Key'] = df_git_cuaca[kab_col].apply(standardisasi_nama)
        # Drop duplicates, keeping the first (latest date) entry
        df_git_cuaca = df_git_cuaca.drop_duplicates(subset=['Key'], keep='first')
        for _, baris in df_git_cuaca.iterrows():
            kab_key = baris['Key']
            suhu = float(baris[suhu_col])
            kelembapan = float(baris[kelembapan_col])
            total_jam_hujan = float(baris[hujan_col])
            peta_cuaca[kab_key] = {
                'Suhu': suhu,
                'Kelembapan': kelembapan,
                'THI': hitung_thi(suhu, kelembapan),
                'Total_Jam_Hujan': total_jam_hujan
            }
    except Exception as e:
        errors.append(f"Cuaca Git error: {e}")

    # ------------------------------------------------------------------
    # TAHAP 2: PROCESSING DATA HISTORIS
    # ------------------------------------------------------------------
    try:
        df_kasus   = pd.read_excel(JALUR_EXCEL, sheet_name='test 2')
        df_penduduk = pd.read_excel(JALUR_EXCEL, sheet_name='test')

        df_kasus['Key']    = df_kasus['Wilayah'].apply(standardisasi_nama)
        df_penduduk['Key'] = df_penduduk['Wilayah'].apply(standardisasi_nama)

        kolom_tahun_kasus = 'TAHUN' if 'TAHUN' in df_kasus.columns else 'Tahun'
        kolom_tahun_pend  = 'TAHUN' if 'TAHUN' in df_penduduk.columns else 'Tahun'

        df_kasus[kolom_tahun_kasus]   = pd.to_numeric(df_kasus[kolom_tahun_kasus],   errors='coerce').fillna(0).astype(int)
        df_penduduk[kolom_tahun_pend] = pd.to_numeric(df_penduduk[kolom_tahun_pend], errors='coerce').fillna(0).astype(int)

        kolom_terjangkit = 'Jumlah_Terjangkit' if 'Jumlah_Terjangkit' in df_kasus.columns else 'Jumlah_Terjang'
        if kolom_terjangkit not in df_kasus.columns:
            for col in df_kasus.columns:
                if 'terjang' in col.lower():
                    kolom_terjangkit = col

        tahun_terakhir = df_kasus[kolom_tahun_kasus].max()
        df_tahun_akhir = df_kasus[df_kasus[kolom_tahun_kasus] == tahun_terakhir]
        peta_kasus_terakhir = dict(zip(df_tahun_akhir['Key'], df_tahun_akhir[kolom_terjangkit]))

        df_gabung = pd.merge(df_kasus, df_penduduk, on=[kolom_tahun_kasus, 'Key'], how='inner')
        if len(df_gabung) == 0:
            df_gabung = df_kasus.copy()
            df_gabung['Kepadatan_Historis'] = 150.0
        else:
            df_gabung['Kepadatan_Historis'] = df_gabung['Jumlah_Penduduk'] / df_gabung['Luas_Wilayah']

        df_gabung['Kasus_Tahun_Lalu_Historis'] = df_gabung[kolom_terjangkit]

        max_kasus_historis = df_gabung[kolom_terjangkit].max()

        def kalkulasi_status(kasus):
            if kasus <= (max_kasus_historis * 0.20): return 'AMAN'
            elif kasus <= (max_kasus_historis * 0.55): return 'WASPADA'
            else: return 'SIAGA'

        df_gabung['Status_DBD'] = df_gabung[kolom_terjangkit].apply(kalkulasi_status)

        def sim_berita_historis(row):
            if row['Status_DBD'] == 'SIAGA': return 12.0 if row['Kepadatan_Historis'] > 100 else 6.0
            elif row['Status_DBD'] == 'WASPADA': return 3.0
            else: return 1.0

        df_gabung['Resiko_Sosial_Historis'] = df_gabung['Kepadatan_Historis'] * df_gabung.apply(sim_berita_historis, axis=1)
        df_gabung['THI_Historis'] = df_gabung.apply(lambda r: hitung_thi(27.2, 85.0), axis=1)

        def sim_jam_hujan_historis(row):
            if row['Status_DBD'] == 'SIAGA': return 48.0
            elif row['Status_DBD'] == 'WASPADA': return 24.0
            else: return 6.0

        df_gabung['Memori_Hujan_Historis'] = df_gabung.apply(sim_jam_hujan_historis, axis=1)
        rata_rata_regional = int(df_tahun_akhir[kolom_terjangkit].mean()) if len(df_tahun_akhir) > 0 else 120

    except Exception as e:
        return {"error": f"Gagal processing Excel: {e}"}

    # ------------------------------------------------------------------
    # TAHAP 3: TRAINING MODEL
    # ------------------------------------------------------------------
    try:
        Fitur_X = ['Resiko_Sosial_Historis', 'Kasus_Tahun_Lalu_Historis', 'THI_Historis', 'Memori_Hujan_Historis']
        X_train = df_gabung[Fitur_X]
        y_train = df_gabung['Status_DBD']

        label_encoder = LabelEncoder()
        y_train_encoded = label_encoder.fit_transform(y_train)

        model_nb = GaussianNB()
        model_nb.fit(X_train, y_train_encoded)
        mapping_kelas = {kelas: idx for idx, kelas in enumerate(label_encoder.classes_)}
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

        bobot_berita = 0.5 if total_berita == 0 else (1.5 if total_berita <= 2 else total_berita * 4.0)
        resiko_sosial = kepadatan * bobot_berita
        cuaca = peta_cuaca.get(kab_key, {'Suhu': 27.2, 'Kelembapan': 82.0, 'THI': 78.4, 'Total_Jam_Hujan': 3.0})

        koleksi_fitur_live.append({
            'raw_nama': raw_nama,
            'kab_key': kab_key,
            'kepadatan': kepadatan,
            'resiko_sosial': resiko_sosial,
            'suhu': cuaca['Suhu'],
            'kelembapan': cuaca['Kelembapan'],
            'thi': cuaca['THI'],
            'hujan_7d': cuaca['Total_Jam_Hujan'],
            'berita': total_berita,
            'kasus_lalu': peta_kasus_terakhir.get(kab_key, rata_rata_regional),
            'fogging_active': fogging_overrides.get(raw_nama, False)
        })

    df_inferensi = pd.DataFrame(koleksi_fitur_live)
    scaler_sosial = MinMaxScaler(feature_range=(8.0, 58.0))
    df_inferensi['sosial_scaled'] = scaler_sosial.fit_transform(np.log1p(df_inferensi[['resiko_sosial']]))

    laporan_final = []
    for _, row in df_inferensi.iterrows():
        kasus_live = row['kasus_lalu'] if row['kasus_lalu'] != 10 else rata_rata_regional

        # Fogging override: sesuai codenya.py — drop parameter 85%
        resiko_inj = row['resiko_sosial']
        thi_inj    = row['thi']
        hujan_inj  = row['hujan_7d']

        if row['fogging_active']:
            resiko_inj = resiko_inj * 0.15   # sisa 15% = potongan 85%
            thi_inj    = 72.0                 # Reset ke zona aman
            hujan_inj  = 0.0                  # Reset hujan ke 0

        data_uji   = [[resiko_inj, kasus_live, thi_inj, hujan_inj]]
        peluang_array = model_nb.predict_proba(data_uji)[0]

        p_aman    = float(peluang_array[mapping_kelas['AMAN']])
        p_waspada = float(peluang_array[mapping_kelas['WASPADA']])
        p_siaga   = float(peluang_array[mapping_kelas['SIAGA']])

        prediksi_idx = int(np.argmax(peluang_array))
        status_final = label_encoder.inverse_transform([prediksi_idx])[0]
        efek_iklim   = (row['thi'] - 74) * 2.0

        persen_drift = 0.0

        if status_final == 'AMAN':
            base_drift = (p_waspada / (p_aman + p_waspada)) * 100 if (p_aman + p_waspada) > 0 else 0
            persen_ke_waspada = round(max(5.0, min(95.0, (row['sosial_scaled'] + efek_iklim) if base_drift < 0.001 else (base_drift + efek_iklim))), 1)
            analisis_proaktif = f"[RAWAN] {persen_ke_waspada}% Menuju WASPADA"
            keyakinan_sistem  = round(100.0 - persen_ke_waspada, 1)
            persen_drift      = persen_ke_waspada
            golden_window     = False

        elif status_final == 'WASPADA':
            base_drift = (p_siaga / (p_waspada + p_siaga)) * 100 if (p_waspada + p_siaga) > 0 else 0
            persen_ke_siaga = round(max(5.0, min(95.0, (45.0 + efek_iklim + row['hujan_7d'] * 1.5) if base_drift < 0.001 else (base_drift + efek_iklim))), 1)
            analisis_proaktif = f"[KRITIS] {persen_ke_siaga}% Menuju SIAGA"
            keyakinan_sistem  = round(100.0 - persen_ke_siaga, 1)
            persen_drift      = persen_ke_siaga
            golden_window     = persen_ke_siaga > 50  # GOLDEN WINDOW TRIGGER

        elif status_final == 'SIAGA':
            keyakinan_sistem = round(peluang_array[prediksi_idx] * 100, 1)
            if keyakinan_sistem > 88 or row['thi'] > 78.4:
                analisis_proaktif = "[DARURAT] AKUT (KLB)"
            else:
                analisis_proaktif = "[SIAGA] Monitor Ketat Wilayah"
            persen_drift  = 100.0
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
            'golden_window': golden_window if status_final == 'WASPADA' else False,
            'fogging_active': bool(row['fogging_active']),
            'p_aman': round(p_aman * 100, 1),
            'p_waspada': round(p_waspada * 100, 1),
            'p_siaga': round(p_siaga * 100, 1),
        })

    return laporan_final
