import pandas as pd
import requests
import xml.etree.ElementTree as ET
import time
import os
from sklearn.naive_bayes import GaussianNB
from sklearn.preprocessing import LabelEncoder

print("=================================================================================")
print("     EWS DBD KALBAR: PURE GAUSSIAN NAIVE BAYES MULTIDIMENSIONAL FUSION SYSTEM")
print("               (ARSITEKTUR KODE FINAL KOMPETISI SATRIA DATA 2026)")
print("=================================================================================\n")

# 1. KUNCI JALUR ABSOLUT BERKAS EXCEL
jalur_folder = r"D:\SATRIA DATA\SEC-DENGUE-2026"
nama_file = os.path.join(jalur_folder, "SEC13 SATRIA DATA 2026 REMINDER.xlsx")

if not os.path.exists(nama_file):
    print(f"-> GAGAL: Berkas Excel tidak ditemukan pada jalur absolut: {nama_file}")
    exit()

# 2. FUNGSI FEATURE ENGINEERING: TEMPERATURE-HUMIDITY INDEX (THI)
def hitung_thi(suhu, kelembapan):
    farenheit = (1.8 * suhu) + 32
    idx_lembab = 0.55 - (0.55 * (kelembapan / 100))
    thi = farenheit - idx_lembab * (farenheit - 58)
    return round(thi, 2)

# ==================================================================
# TAHAP 1: DATA FUSION HISTORIS & IMPUTASI DATA TRAINING MASA LALU
# ==================================================================
print("[1/4] Memproses peleburan data historis (Kepadatan, Baseline THI, Baseline Berita)...")
try:
    df_kasus = pd.read_excel(nama_file, sheet_name='test 2')
    df_penduduk = pd.read_excel(nama_file, sheet_name='test')
    
    df_kasus['Wilayah'] = df_kasus['Wilayah'].str.upper().str.strip()
    df_penduduk['Wilayah'] = df_penduduk['Wilayah'].str.upper().str.strip()
    
    kolom_tahun_kasus = 'TAHUN' if 'TAHUN' in df_kasus.columns else 'Tahun'
    kolom_tahun_pend = 'TAHUN' if 'TAHUN' in df_penduduk.columns else 'Tahun'
    
    df_gabung = pd.merge(df_kasus, df_penduduk, left_on=[kolom_tahun_kasus, 'Wilayah'], right_on=[kolom_tahun_pend, 'Wilayah'], how='inner')

    # Fitur 1: Hitung Kepadatan Penduduk Historis (Jiwa / km2)
    df_gabung['Kepadatan_Historis'] = df_gabung['Jumlah_Penduduk'] / df_gabung['Luas_Wilayah']

    # Fitur 2: Taktik 1 - Imputasi Konstanta Global untuk Cuaca Masa Lalu (Baseline BPS Kalbar)
    suhu_baseline = 27.3
    lembap_baseline = 84.0
    df_gabung['THI_Historis'] = df_gabung.apply(lambda row: hitung_thi(suhu_baseline, lembap_baseline), axis=1)
    
    # Fitur 3: Imputasi Konstanta Global untuk Berita Masa Lalu
    # Asumsi baseline kondisi tenang/normal di media massa di masa lalu (Rata-rata 5 berita per minggu)
    df_gabung['Berita_Historis'] = 0
    
    # Auto-Labeling Target berbasis batasan kuartil statistik (33% & 66%)
    q1 = df_gabung['Jumlah_Terjangkit'].quantile(0.33)
    q2 = df_gabung['Jumlah_Terjangkit'].quantile(0.66)
    
    def kalkulasi_status(kasus):
        if kasus <= q1: return 'RENDAH'
        elif kasus <= q2: return 'SEDANG'
        else: return 'TINGGI'
        
    df_gabung['Status_DBD'] = df_gabung['Jumlah_Terjangkit'].apply(kalkulasi_status)
    print("   * Sukses: Formulasi 3 Fitur Utama untuk Data Training selesai.")

except Exception as e:
    print(f"-> GAGAL di Langkah 1: Periksa nama sheet/kolom Excel Anda. Error: {e}")
    exit()

# ==================================================================
# TAHAP 2: TRAINING MODEL GAUSSIAN NAIVE BAYES (3 PILAR MULTIDIMENSI)
# ==================================================================
print("[2/4] Melatih model Naive Bayes menggunakan Konvergensi Fitur...")
# Model dilatih menggunakan 3 pilar: Kepadatan (Demografi), THI (Cuaca), Berita (Sosial)
X_train = df_gabung[['Kepadatan_Historis', 'THI_Historis', 'Berita_Historis']]
y_train = df_gabung['Status_DBD']

label_encoder = LabelEncoder()
y_train_encoded = label_encoder.fit_transform(y_train)

model_nb = GaussianNB()
model_nb.fit(X_train, y_train_encoded)
print("-> Sukses: Otak Naive Bayes telah memetakan ruang probabilitas Gauss.\n")

# ==================================================================
# TAHAP 3: REAL-TIME STREAMING FORECAST & LIVE INFERENCE
# ==================================================================
print("[3/4] Ekstraksi live API Nowcast BMKG & Estimasi Probabilitas Bersyarat...")
try:
    df_master = pd.read_excel(nama_file, sheet_name='Master_Wilayah')
except Exception as e:
    print(f"-> GAGAL membaca sheet 'Master_Wilayah'. Error: {e}")
    exit()

laporan_final = []

for indeks, baris in df_master.iterrows():
    nama_kab = str(baris['Wilayah']).upper().strip()
    kode_cap = str(baris['KODE']).strip()
    penduduk_live = baris['Penduduk_Terbaru']
    luas_live = baris['Luas_Wilayah']
    
    # Membaca kolom Jumlah_Berita dari Excel (jika tidak ada, auto-set default = 5)
    jumlah_berita_live = baris['Jumlah_Berita'] if 'Jumlah_Berita' in baris.index else 0
    
    # Hitung data Kepadatan aktual jam ini
    kepadatan_live = penduduk_live / luas_live
    
    # Streaming data cuaca instan langsung dari radar BMKG
    url_xml = f"https://www.bmkg.go.id/alerts/nowcast/en/{kode_cap}_alert.xml"
    suhu_live, kelembapan_live = 28.0, 83.0  # Fallback angka aman jika stasiun BMKG lokal offline
    
    try:
        res = requests.get(url_xml, timeout=4)
        if res.status_code == 200:
            root = ET.fromstring(res.content)
            namespace = {'ns': 'urn:oasis:names:tc:emergency:cap:1.2'}
            for param in root.findall('.//ns:parameter', namespace):
                v_name = param.find('ns:valueName', namespace).text.lower()
                v_value = param.find('ns:value', namespace).text
                if 'temperature' in v_name: suhu_live = float(v_value)
                elif 'humidity' in v_name: kelembapan_live = float(v_value)
    except:
        pass
        
    # Meleburkan parameter cuaca live menjadi 1 Indeks THI Terintegrasi
    thi_nowcast = hitung_thi(suhu_live, kelembapan_live)
    
    # INFERENSI MATEMATIS PURE NAIVE BAYES
    # Memasukkan paket 3 fitur kontingensi: [Kepadatan, THI, Berita]
    data_uji_aktual = [[kepadatan_live, thi_nowcast, jumlah_berita_live]]
    
    prediksi_idx = model_nb.predict(data_uji_aktual)[0]
    status_final = label_encoder.inverse_transform([prediksi_idx])[0]
    
    laporan_final.append({
        'Kabupaten/Kota': nama_kab,
        'Kepadatan (Jiwa/km2)': round(kepadatan_live, 2),
        'Indeks THI BMKG': thi_nowcast,
        'Intensitas Berita': jumlah_berita_live,
        'STATUS RISIKO FINAL': status_final.upper()
    })
    print(f"   * Sukses menghitung probabilitas gabungan untuk wilayah: {nama_kab}")
    time.sleep(0.1)

# ==================================================================
# TAHAP 4: MENAMPILKAN DAN MENYIMPAN HASIL LAPORAN MATRIX KOMPETISI
# ==================================================================
print("\n[4/4] Menyusun matriks laporan evaluasi spasial-sosio-klimatologi...")
df_laporan = pd.DataFrame(laporan_final)

print("\n=========================================================================================================")
print("             TABEL MONITORING REAL-TIME DETEKSI RISIKO DBD PROVINSI KALBAR")
print("                 (ARSITEKTUR MURNI: MULTIDIMENSIONAL GAUSSIAN NAIVE BAYES)")
print("=========================================================================================================\n")
print(df_laporan.to_string(index=False))
print("\n=========================================================================================================")

file_output = os.path.join(jalur_folder, "laporan_output_satriadata_pure_nb.xlsx")
df_laporan.to_excel(file_output, index=False)
print(f"-> BERHASIL EKSEKUSI: Output matriks klasifikasi murni disimpan di '{file_output}'\n")