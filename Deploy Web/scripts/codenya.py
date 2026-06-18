import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.naive_bayes import GaussianNB
import datetime
import sys

# Set output encoding to UTF-8 to support emoji logs on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# ==================================================================
# CONFIG & SIMULASI ENVIRONMENT INTERAKTIF WEBSITE (SMART CITY EWS)
# ==================================================================
# Variabel Kontrol Intervensi Balik (Simulasi Status Tombol di Website)
# Ubah nilai ini untuk menguji fitur "Feedback Loop" peredam risiko
INTERVENSI_WARGA_G1R1 = False   # Set True jika >60% warga klik "Sudah Bersihkan Rumah"
INTERVENSI_DINKES_FOGGING = False  # Set True jika Dinkes klik "Selesai Fogging Fokus"

# Mock Metadata Pendukung Sistem
nama_file_excel = "data_demografi.xlsx" # Mock nama file master wilayah
kolom_terjangkit = "Kasus_2025"
mapping_kelas = {'AMAN': 0, 'WASPADA': 1, 'SIAGA': 2}
label_encoder_classes = ['AMAN', 'WASPADA', 'SIAGA']

# 1. Dummy Peta Distribusi Git Streaming & Historical Anchor
peta_berita_fallback = {'SANGGAU': 0, 'PONTIANAK': 2, 'KUBU_RAYA': 1}
peta_kasus_terakhir_auto = {'SANGGAU': 718, 'PONTIANAK': 412, 'KUBU_RAYA': 1445}

peta_cuaca_fallback = {
    'SANGGAU': {'Suhu': 27.5, 'Kelembapan': 83.0, 'THI': 78.60, 'Total_Jam_Hujan': 18.0},
    'PONTIANAK': {'Suhu': 28.0, 'Kelembapan': 80.0, 'THI': 79.10, 'Total_Jam_Hujan': 6.0},
    'KUBU_RAYA': {'Suhu': 27.2, 'Kelembapan': 85.0, 'THI': 78.20, 'Total_Jam_Hujan': 11.0}
}

URL_BERITA  = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/data/berita_dbd.csv"
URL_CUACA   = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data%20Cuaca%20Harian%20Kalbar/Data_Cuaca_Harian_Kalbar_Hari_Ini.csv"

def hitung_thi(suhu, kelembapan):
    farenheit = (1.8 * suhu) + 32
    idx_lembab = 0.55 - (0.55 * (kelembapan / 100))
    thi = farenheit - idx_lembab * (farenheit - 58)
    return round(thi, 2)

def standardisasi_nama(nama):
    t = str(nama).upper().strip()
    t = t.replace('KAB. ', '').replace('KABUPATEN ', '').replace('KOTA ', '')
    return t.replace(" ", "_")

import re

peta_berita = {}
peta_cuaca = {}

try:
    print("Mengambil data berita live dari GitHub...")
    df_git_berita = pd.read_csv(URL_BERITA)
    df_git_berita.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_berita.columns]
    kab_col = [col for col in df_git_berita.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower()][0]
    total_col = [col for col in df_git_berita.columns if 'total 7' in col.lower() or 'total' in col.lower()][0]
    for _, row in df_git_berita.iterrows():
        key = standardisasi_nama(row[kab_col])
        peta_berita[key] = int(row[total_col])
    print(f"Berita berhasil dimuat ({len(peta_berita)} wilayah)")
except Exception as e:
    print(f"Gagal mengambil berita live, menggunakan data fallback. Error: {e}")
    peta_berita = peta_berita_fallback

try:
    print("Mengambil data cuaca live dari GitHub...")
    df_git_cuaca = pd.read_csv(URL_CUACA)
    df_git_cuaca.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df_git_cuaca.columns]
    kab_col = [col for col in df_git_cuaca.columns if 'kabupaten' in col.lower() or 'wilayah' in col.lower()][0]
    suhu_col = [col for col in df_git_cuaca.columns if 'suhu' in col.lower()][0]
    kelembapan_col = [col for col in df_git_cuaca.columns if 'kelembapan' in col.lower()][0]
    hujan_col = [col for col in df_git_cuaca.columns if 'hujan 7' in col.lower() or 'hujan_7' in col.lower() or 'jam hujan 7' in col.lower()][0]
    df_git_cuaca['Key'] = df_git_cuaca[kab_col].apply(standardisasi_nama)
    df_git_cuaca = df_git_cuaca.drop_duplicates(subset=['Key'], keep='first')
    
    for _, row in df_git_cuaca.iterrows():
        key = row['Key']
        suhu = float(row[suhu_col])
        kelembapan = float(row[kelembapan_col])
        total_jam_hujan = float(row[hujan_col])
        peta_cuaca[key] = {
            'Suhu': suhu,
            'Kelembapan': kelembapan,
            'THI': hitung_thi(suhu, kelembapan),
            'Total_Jam_Hujan': total_jam_hujan
        }
    print(f"Cuaca berhasil dimuat ({len(peta_cuaca)} wilayah)")
except Exception as e:
    print(f"Gagal mengambil cuaca live, menggunakan data fallback. Error: {e}")
    peta_cuaca = peta_cuaca_fallback

# ==================================================================
# TAHAP 2 & 3: HISTORICAL BRAIN (MODEL SIMULASI NAIVE BAYES)
# ==================================================================
# Membuat data historis dummy yang mewakili distribusi epidemiologi Kalbar
X_train = np.array([
    # [Resiko_Sosial, Kasus_Lalu, THI, Jam_Hujan]
    [10.0, 50, 72.0, 2.0],   # Klaster AMAN
    [15.0, 120, 74.5, 5.0],  # Klaster AMAN
    [35.0, 300, 76.5, 15.0], # Klaster WASPADA
    [45.0, 600, 78.0, 24.0], # Klaster WASPADA
    [90.0, 800, 79.5, 48.0], # Klaster SIAGA
    [120.0, 1500, 81.0, 60.0] # Klaster SIAGA
])
y_train = np.array([0, 0, 1, 1, 2, 2]) # 0: AMAN, 1: WASPADA, 2: SIAGA

model_nb = GaussianNB()
model_nb.fit(X_train, y_train)

# ==================================================================
# TAHAP 4: INTERACTIVE INFERENSI AKTUAL & FEEDBACK LOOP ARCHITECTURE
# ==================================================================
print("[4/5] Mengintegrasikan data harian & mengevaluasi aksi intervensi...")

# Mock membaca df_master wilayah Kalbar
df_master = pd.DataFrame({
    'Wilayah': ['Sanggau', 'Pontianak', 'Kubu Raya'],
    'Penduduk_Terbaru': [484297, 672440, 611569],
    'Luas_Wilayah': [12857.70, 107.82, 6985.20]
})

laporan_final = []
rata_rata_regional = 120
koleksi_fitur_live = []

for indeks, baris in df_master.iterrows():
    raw_nama = str(baris['Wilayah']).upper().strip()
    kab_key = standardisasi_nama(raw_nama)
    
    penduduk_live = baris['Penduduk_Terbaru']
    luas_live = baris['Luas_Wilayah']
    kepadatan_live = penduduk_live / luas_live
    total_berita_live = int(peta_berita.get(kab_key, 0))
    
    # Perhitungan Bobot Spasial Strategi C
    bobot_berita = 0.5 if total_berita_live == 0 else (1.5 if total_berita_live <= 2 else total_berita_live * 4.0)
    resiko_sosial_live = kepadatan_live * bobot_berita
    
    cuaca_aktual = peta_cuaca.get(kab_key, {'Suhu': 27.2, 'Kelembapan': 82.0, 'THI': 78.4, 'Total_Jam_Hujan': 3.0})
    
    koleksi_fitur_live.append({
        'indeks_asli': indeks,
        'raw_nama': raw_nama,
        'kab_key': kab_key,
        'kepadatan': kepadatan_live,
        'resiko_sosial': resiko_sosial_live,
        'suhu': cuaca_aktual['Suhu'],
        'kelembapan': cuaca_aktual['Kelembapan'],
        'thi': cuaca_aktual['THI'],
        'hujan_7d': cuaca_aktual['Total_Jam_Hujan'],
        'berita': total_berita_live,
        'kasus_lalu': peta_kasus_terakhir_auto.get(kab_key, rata_rata_regional)
    })

df_inferensi = pd.DataFrame(koleksi_fitur_live)

# Mengompres nilai risiko sosial ke dalam skala relatif range 8% hingga 58% via Scaler Formal
scaler_sosial = MinMaxScaler(feature_range=(8.0, 58.0))
df_inferensi['sosial_scaled'] = scaler_sosial.fit_transform(np.log1p(df_inferensi[['resiko_sosial']]))

# Loop Evaluasi Probabilitas Pasca-Standardisasi & Simulasi Intervensi Web
for _, row in df_inferensi.iterrows():
    kab_key = row['kab_key']
    kasus_live = row['kasus_lalu']
    
    # Ambil Parameter Asli dari Sensor Streaming Git
    resiko_sosial_inj = row['resiko_sosial']
    thi_inj = row['thi']
    hujan_inj = row['hujan_7d']
    
    # --------------------------------------------------------------
    # INTERACTIVE WIDGET LOGIC: SIMULASI TOMBOL INTERVENSI WEBSITE
    # --------------------------------------------------------------
    status_intervensi = "TIDAK ADA AKSI"
    
    # Skenario 1: Jika warga mengaktifkan G1R1 di fase Waspada (Meredam Risiko Hujan 50%)
    if INTERVENSI_WARGA_G1R1 and kab_key == 'SANGGAU':
        hujan_inj = hujan_inj * 0.50
        status_intervensi = "AKTIF - INTERVENSI G1R1 WARGA (Hujan Diredam 50%)"
        
    # Skenario 2: Jika Dinkes klik "Selesai Fogging Fokus" di fase Siaga (Dradis Drop 85%)
    if INTERVENSI_DINKES_FOGGING and kab_key == 'SANGGAU':
        resiko_sosial_inj = resiko_sosial_inj * 0.15
        thi_inj = 72.0
        hujan_inj = 0.0
        status_intervensi = "AKTIF - FOGGING FOKUS DINKES (Parameter Drop 85%)"
    # --------------------------------------------------------------
    
    # Inferensi murni Naive Bayes menggunakan Parameter Hasil Intervensi
    data_uji = [[resiko_sosial_inj, kasus_live, thi_inj, hujan_inj]]
    peluang_array = model_nb.predict_proba(data_uji)[0]
    
    p_aman = peluang_array[mapping_kelas['AMAN']]
    p_waspada = peluang_array[mapping_kelas['WASPADA']]
    p_siaga = peluang_array[mapping_kelas['SIAGA']]
    
    prediksi_idx = np.argmax(peluang_array)
    status_final = label_encoder_classes[prediksi_idx]
    
    # Penghitungan matematis drift penambah risiko dari parameter iklim real-time (THI)
    efek_iklim = (thi_inj - 74) * 2.0
    keyakinan_sistem = round(peluang_array[prediksi_idx] * 100, 1)
    
    # Penentuan Arah Gerakan Proaktif & Sistem Rekomendasi Pintar (Website Output)
    if status_final == 'AMAN':
        base_drift = (p_waspada / (p_aman + p_waspada)) * 100 if (p_aman + p_waspada) > 0 else 0
        persen_ke_waspada = round(max(5.0, min(95.0, base_drift + efek_iklim)), 1)
        analisis_proaktif = f"[RAWAN] {persen_ke_waspada}% Menuju WASPADA"
        rekomendasi_web = "Edukasi Rutin PSN 3M Plus via Posyandu."
            
    elif status_final == 'WASPADA':
        base_drift = (p_siaga / (p_waspada + p_siaga)) * 100 if (p_waspada + p_siaga) > 0 else 0
        persen_ke_siaga = round(max(5.0, min(95.0, base_drift + efek_iklim + (hujan_inj * 1.5))), 1)
        
        # FITUR 3: Golden Window Trigger jika transisi > 50%
        if persen_ke_siaga > 50.0:
            analisis_proaktif = f"[GOLDEN WINDOW] {persen_ke_siaga}% Menuju SIAGA"
            rekomendasi_web = "⚠️ ALARM PREEMPTIF! Picu WA Blast Warga & Drop Abate Massal ke Puskesmas (Fase Jentik)."
        else:
            analisis_proaktif = f"[KRITIS] {persen_ke_siaga}% Menuju SIAGA"
            rekomendasi_web = "Gerakan Mandiri G1R1 oleh Kader Jumantik."
            
    elif status_final == 'SIAGA':
        # FITUR 4: Pemicu Countdown SLA 24 Jam Medis
        analisis_proaktif = "[🚨 SIAGA AKUT] Vektor Udara Aktif!"
        rekomendasi_web = "🔴 SLA 24 JAM: Kirim Tim Penyelidikan Epidemiologi (PE). Siapkan Insektisida Fogging Fokus!"
            
    laporan_final.append({
        'Kabupaten/Kota': row['raw_nama'],
        'Live Jam Hujan': f"{hujan_inj} Jam",
        'STATUS AKHIR': status_final,
        'AKURASI MODEL': f"{keyakinan_sistem}%",
        'ANALISIS PROAKTIF': analisis_proaktif,
        'REKOMENDASI SITUS': rekomendasi_web,
        'STATUS INTERVENSI WEB': status_intervensi
    })

# Tampilkan Hasil Evaluasi Akhir Sistem dalam bentuk DataFrame scannable
df_dashboard_final = pd.DataFrame(laporan_final)
print("\n" + "="*100)
print("                       SMART CITY COMMAND CENTER LOG - STRATEGI C DBD                       ")
print("="*100)
print(df_dashboard_final.to_string(index=False))
print("="*100)