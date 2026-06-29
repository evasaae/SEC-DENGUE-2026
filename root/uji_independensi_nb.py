import pandas as pd
import numpy as np
import os
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.naive_bayes import GaussianNB
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

print("=== STARTING NAIVE BAYES INDEPENDENCE EXPERIMENT ===")

# 1. Tentukan path dataset_tahunan.xlsx
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(BASE_DIR)

if os.path.exists(os.path.join(BASE_DIR, "dataset_tahunan.xlsx")):
    file_dataset = os.path.join(BASE_DIR, "dataset_tahunan.xlsx")
elif os.path.exists(os.path.join(PARENT_DIR, "Deploy Web", "dataset", "dataset_tahunan.xlsx")):
    file_dataset = os.path.join(PARENT_DIR, "Deploy Web", "dataset", "dataset_tahunan.xlsx")
else:
    file_dataset = os.path.join(PARENT_DIR, "dataset_tahunan.xlsx")

df = pd.read_excel(file_dataset)

# 2. Definisikan label target menggunakan K-Means dari 6 fitur lengkap (Zonasi standar)
fitur_lengkap = ['Kepadatan', 'Suhu', 'Kelembapan', 'THI', 'Total_Hujan', 'Hujan_Kritis']
X_kmeans = df[fitur_lengkap]
scaler_kmeans = StandardScaler()
X_kmeans_scaled = scaler_kmeans.fit_transform(X_kmeans)

kmeans_model = KMeans(n_clusters=3, random_state=42, n_init=10)
y = kmeans_model.fit_predict(X_kmeans_scaled)

# 3. Konfigurasi Eksperimen Fitur
konfigurasi = {
    "Model A (6 Fitur - Default)": ['Kepadatan', 'Suhu', 'Kelembapan', 'THI', 'Total_Hujan', 'Hujan_Kritis'],
    "Model B (4 Fitur - Murni THI)": ['Kepadatan', 'THI', 'Total_Hujan', 'Hujan_Kritis'],
    "Model C (5 Fitur - Tanpa THI)": ['Kepadatan', 'Suhu', 'Kelembapan', 'Total_Hujan', 'Hujan_Kritis']
}

hasil_eksperimen = []

for nama_model, list_fitur in konfigurasi.items():
    print(f"\nMengevaluasi: {nama_model}...")
    X_sub = df[list_fitur]
    
    # Standardisasi fitur spesifik
    scaler_sub = StandardScaler()
    X_sub_scaled = scaler_sub.fit_transform(X_sub)
    
    # Split 80:20
    X_train, X_test, y_train, y_test = train_test_split(
        X_sub_scaled, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # Tuning Hyperparameter var_smoothing
    base_nb = GaussianNB()
    param_grid = {'var_smoothing': np.logspace(0, -9, num=100)}
    grid_search = GridSearchCV(base_nb, param_grid, cv=3, scoring='accuracy')  # Menggunakan CV=3 karena data kecil
    grid_search.fit(X_train, y_train)
    
    model_nb = grid_search.best_estimator_
    y_pred = model_nb.predict(X_test)
    
    # Metrik Evaluasi
    acc = accuracy_score(y_test, y_pred) * 100
    cv_score = grid_search.best_score_ * 100
    prec = precision_score(y_test, y_pred, average='weighted', zero_division=0) * 100
    rec = recall_score(y_test, y_pred, average='weighted', zero_division=0) * 100
    f1 = f1_score(y_test, y_pred, average='weighted', zero_division=0) * 100
    
    hasil_eksperimen.append({
        "Model": nama_model,
        "Jumlah Fitur": len(list_fitur),
        "Akurasi Test (%)": round(acc, 2),
        "Akurasi CV (%)": round(cv_score, 2),
        "Precision (%)": round(prec, 2),
        "Recall (%)": round(rec, 2),
        "F1-Score (%)": round(f1, 2),
        "Best var_smoothing": f"{grid_search.best_params_['var_smoothing']:.2E}"
    })

# 4. Tampilkan Tabel Perbandingan
df_hasil = pd.DataFrame(hasil_eksperimen)
print("\n" + "="*80)
print("HASIL PERBANDINGAN MODEL NAIVE BAYES")
print("="*80)
print(df_hasil.to_string(index=False))
print("="*80)
print("\nAnalisis Kesimpulan:")
print("- Model A menggunakan Suhu, Kelembapan, dan THI secara bersamaan (ada redundansi fitur).")
print("- Model B mematuhi aturan independensi Naive Bayes dengan hanya menggunakan THI.")
print("- Model C menggunakan Suhu & Kelembapan asli dan membuang indeks buatan THI.")
