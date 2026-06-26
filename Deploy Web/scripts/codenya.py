import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import accuracy_score, classification_report
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

print("=== SYSTEM STARTING: TUNED NAIVE BAYES FOR SMART CITY EWS ===")

INTERVENSI_DINKES_FOGGING = True   

# ==================================================================
# STEP 1 & 2: DATA GENERATION DENGAN REALISTIC NOISE
# ==================================================================
np.random.seed(42)
n_samples = 300 # Kita naikkan jumlah sampel agar statistik Naive Bayes lebih stabil

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
        
    # TAMBAHKAN NOISE REALISTIS (10% data memiliki anomali/gangguan alam nyata)
    if np.random.rand() < 0.10:
        status = np.random.choice([0, 1, 2])
    y_historical.append(status)
y_historical = np.array(y_historical)

# Konversi ke DataFrame untuk mempermudah pembersihan outlier
df_hist = pd.DataFrame(X_historical, columns=['Kepadatan', 'Kasus', 'THI', 'Hujan', 'Hujan_Kritis'])
df_hist['Target'] = y_historical

# --- TRIK 1: ADVANCED OUTLIER REMOVAL (MEMBERSIHKAN DATA EKSTREM) ---
# Kita buang baris data training yang nilainya terlalu menyimpang jauh agar tidak merusak kurva Gaussian
for col in ['Kasus', 'Hujan']:
    Q1 = df_hist[col].quantile(0.25)
    Q3 = df_hist[col].quantile(0.75)
    IQR = Q3 - Q1
    # Filter data yang berada di dalam batas normal
    df_hist = df_hist[~((df_hist[col] < (Q1 - 1.5 * IQR)) | (df_hist[col] > (Q3 + 1.5 * IQR)))]

X_clean = df_hist.drop(columns=['Target']).values
y_clean = df_hist['Target'].values

# ==================================================================
# STEP 3: SPLIT DATA & STANDARD SCALING
# ==================================================================
# Naive Bayes berbasis distribusi jarak/kurva sangat menyukai StandardScaler dibanding RobustScaler
X_train, X_test, y_train, y_test = train_test_split(
    X_clean, y_clean, test_size=0.2, random_state=42, stratify=y_clean
)

scaler = StandardScaler()
X_train_scaled = scaler.fit_transform(X_train)
X_test_scaled = scaler.transform(X_test)

# ==================================================================
# STEP 4: HYPERPARAMETER TUNING VIA GRIDSEARCHCV (PENCARIAN OTOMATIS)
# ==================================================================
print("[4/5] Menjalankan Hyperparameter Tuning pada Naive Bayes...")

base_nb = GaussianNB()

# Kita uji berbagai nilai varians smoothing untuk mencari yang paling akurat
param_grid = {'var_smoothing': np.logspace(0, -9, num=100)}
grid_search = GridSearchCV(base_nb, param_grid, cv=5, scoring='accuracy')
grid_search.fit(X_train_scaled, y_train)

# Ambil model terbaik hasil tuning
model_nb_tuned = grid_search.best_estimator_

y_pred_test = model_nb_tuned.predict(X_test_scaled)
print(f"\n--> Nilai Tuning var_smoothing Terbaik: {grid_search.best_params_['var_smoothing']:.2E}")
print(f"📈 AKURASI BARU NAIVE BAYES (TUNED): {accuracy_score(y_test, y_pred_test) * 100:.2f}%\n")
print(classification_report(y_test, y_pred_test, target_names=['AMAN', 'WASPADA', 'SIAGA']))

# ==================================================================
# STEP 5: LIVE INFERENCE UTK MONITORING COMMAND CENTER
# ==================================================================
# (Gunakan data rekap harian Kubu Raya, Pontianak, Sanggau dari kode sebelumnya)
data_log_cuaca = {
    'Wilayah': ['Sanggau']*5 + ['Pontianak']*5 + ['Kubu Raya']*5,
    'Hari': [1,2,3,4,5] * 3,
    'Suhu': [27.5, 27.8, 27.2, 27.4, 27.6,  28.0, 28.2, 28.1, 27.9, 28.0,  27.2, 27.3, 27.1, None, None],
    'Kelembapan': [83, 85, 82, 84, 83,  80, 81, 79, 80, 82,  85, 86, 84, 85, 85],
    'Jam_Hujan': [12, 15, 8, 20, 18,  4, 2, 0, 6, 5,  14, 16, 11, 13, 12]
}
df_cuaca_multi_hari = pd.DataFrame(data_log_cuaca)
df_cuaca_multi_hari['Suhu'] = df_cuaca_multi_hari.groupby('Wilayah')['Suhu'].transform(lambda x: x.fillna(x.mean()))

farenheit = (1.8 * df_cuaca_multi_hari['Suhu']) + 32
idx_lembab = 0.55 - (0.55 * (df_cuaca_multi_hari['Kelembapan'] / 100))
df_cuaca_multi_hari['THI'] = round(farenheit - idx_lembab * (farenheit - 58), 2)
df_cuaca_multi_hari['Hujan_Lebat_Harian'] = df_cuaca_multi_hari['Jam_Hujan'] > 5
fitur_hujan_berturut = df_cuaca_multi_hari.groupby('Wilayah')['Hujan_Lebat_Harian'].transform(lambda x: x.rolling(window=3, min_periods=1).sum())
df_cuaca_multi_hari['Hujan_Kritis_3D'] = (fitur_hujan_berturut >= 3).astype(int)

df_live_rekap = df_cuaca_multi_hari[df_cuaca_multi_hari['Hari'] == 5].copy()
df_master_wilayah = pd.DataFrame({
    'Wilayah': ['Sanggau', 'Pontianak', 'Kubu Raya'], 'Penduduk': [484297, 672440, 611569],
    'Luas': [12857.70, 107.82, 6985.20], 'Kasus_Lalu': [718, 412, 1445]
})
df_live_final = pd.merge(df_live_rekap, df_master_wilayah, on='Wilayah')
df_live_final['Kepadatan'] = df_live_final['Penduduk'] / df_live_final['Luas']
total_hujan_5d = df_cuaca_multi_hari.groupby('Wilayah')['Jam_Hujan'].sum().reset_index()
df_live_final = pd.merge(df_live_final.drop(columns=['Jam_Hujan']), total_hujan_5d, on='Wilayah')

mapping_kelas = {0: 'AMAN', 1: 'WASPADA', 2: 'SIAGA'}
laporan_dashboard = []

for _, baris in df_live_final.iterrows():
    nama_raw = baris['Wilayah']
    kepadatan = baris['Kepadatan']
    kasus_lalu = baris['Kasus_Lalu']
    thi_aktual = baris['THI']
    total_hujan = baris['Jam_Hujan']
    hujan_kritis = baris['Hujan_Kritis_3D']
    
    vektor_cek = scaler.transform(np.array([[kepadatan, kasus_lalu, thi_aktual, total_hujan, hujan_kritis]]))
    status_dasar = mapping_kelas[model_nb_tuned.predict(vektor_cek)[0]]
    
    status_intervensi = "TIDAK ADA AKSI"
    is_fogged = False
    
    if INTERVENSI_DINKES_FOGGING and status_dasar == 'SIAGA':
        kepadatan, thi_aktual, total_hujan, hujan_kritis = kepadatan * 0.15, 72.0, 0.0, 0
        status_intervensi = "⚡ FOGGING FOKUS AKTIF"
        is_fogged = True
        
    vektor_input = np.array([[kepadatan, kasus_lalu, thi_aktual, total_hujan, hujan_kritis]])
    vektor_input_scaled = scaler.transform(vektor_input)
    
    status_final = mapping_kelas[model_nb_tuned.predict(vektor_input_scaled)[0]]
    nilai_keyakinan = round(model_nb_tuned.predict_proba(vektor_input_scaled)[0][model_nb_tuned.predict(vektor_input_scaled)[0]] * 100, 1)
    
    status_visual = "🟡 SIAGA (Dalam Penanganan)" if is_fogged else f"🟢 {status_final}" if status_final == 'AMAN' else f"🟡 {status_final}" if status_final == 'WASPADA' else f"🔴 {status_final}"
    rekomendasi = "✅ Fogging Selesai." if is_fogged else "Edukasi PSN." if status_final == 'AMAN' else "⚠️ Kirim SMS Blast!" if status_final == 'WASPADA' else "🚨 SLA 24 JAM!"

    laporan_dashboard.append({
        'Wilayah': nama_raw.upper(),
        'STATUS MONITORING': status_visual,
        'KEYAKINAN AI': f"{nilai_keyakinan}%",
        'INTERVENSI': status_intervensi
    })

print("="*100)
print(pd.DataFrame(laporan_dashboard).to_string(index=False))
print("="*100)