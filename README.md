# 🦟 EWS DBD Kalbar (Early Warning System Demam Berdarah Dengue)

Sistem Peringatan Dini (EWS) Demam Berdarah Dengue (DBD) berbasis Machine Learning di Provinsi Kalimantan Barat. Aplikasi ini menggunakan pendekatan model hibrida (**K-Means Clustering + Tuned Gaussian Naive Bayes**) untuk memprediksi tingkat kerawanan DBD berdasarkan parameter cuaca riil (BMKG/satelit) dan kepadatan penduduk.

---

## 📁 Struktur Repositori

Untuk memudahkan pemeliharaan jangka panjang dan pemisahan tugas (*separation of concerns*), repositori ini dibagi menjadi dua bagian utama:

```text
SEC-DENGUE-2026/
├── root/                           <-- MODUL RISET & EVALUASI OFFLINE
│   ├── training_model.py           <-- Skrip Pelatihan & Uji Akurasi (80:20 Split)
│   ├── prediction.py               <-- Skrip Prediksi Cuaca Harian & Laporan Offline
│   ├── laporan_pantauan_terkini.txt <-- Output Laporan Prediksi Teks (.txt)
│   └── hasil_prediksi_risiko_dbd.xlsx <-- Output Pengelompokan Data Historis (.xlsx)
├── Deploy Web/                     <-- MODUL WEB INTERAKTIF ONLINE
│   ├── app.py                      <-- Backend Server Flask
│   ├── engine.py                   <-- Mesin Hitung ML (Prediksi Web Real-time)
│   ├── dataset/                    <-- Berkas Dataset Excel (Latih & Master)
│   ├── templates/                  <-- Halaman HTML (Dashboard & Admin)
│   └── static/                     <-- Aset Visual (CSS & JavaScript Dashboard)
├── Data Cuaca Harian Kalbar/       <-- Data Ingest Cuaca Harian (Scraper)
└── data/                           <-- Data Ingest Berita Kasus DBD (Scraper)
```

---

## 🧠 Alur Kerja Machine Learning (Pipeline ML)

Sistem EWS menggunakan rantai algoritma yang saling memengaruhi untuk menghasilkan diagnosis tingkat risiko (AMAN, WASPADA, SIAGA):

1.  **Normalisasi Fitur (`StandardScaler`):**
    Menyamakan skala angka pada 6 fitur utama (Kepadatan Penduduk, Suhu, Kelembapan, THI, Total Curah Hujan, dan Hari Hujan Kritis) agar fitur dengan nilai satuan besar tidak mendominasi fitur bernilai satuan kecil.
2.  **Klasterisasi Otomatis (`K-Means`):**
    Karena data sejarah tidak memiliki label target, K-Means mengelompokkan data tahunan menjadi 3 zona risiko secara objektif. Hasil klasterisasi ini menjadi label latih bagi model berikutnya.
3.  **Klasifikasi Probabilitas (`Gaussian Naive Bayes` + `GridSearchCV`):**
    Melatih model klasifikasi Naive Bayes berdasarkan label dari K-Means. `GridSearchCV` digunakan untuk mencari nilai parameter toleransi terbaik (`var_smoothing`) untuk menghasilkan akurasi model optimal (di atas 90%).

---

## 🏫 Perbedaan Proses: Training (Riset) vs Prediction (Operasional)

Berikut adalah penjelasan mengenai cara kerja dan pembagian tugas algoritma pada sistem EWS:

### **1. Berkas `training_model.py` (Uji Coba & Rapor Akurasi)**
*   **Fungsi:** Sebagai "Laboratorium Riset" untuk mengukur performa kehebatan model di atas kertas sebelum digunakan di lapangan.
*   **Pembagian Data (80:20 Split):** Menggunakan pembagian data latih (80%) dan data uji (20%). Ini digunakan untuk menerbitkan **satu raport nilai akurasi tunggal** (Confusion Matrix & Classification Report) yang bersih untuk laporan kompetisi.

### **2. Berkas `prediction.py` & `engine.py` (Operasional Lapangan)**
*   **Fungsi:** Mengambil data cuaca harian aktual hari ini, memprosesnya, dan langsung meramal status kerawanan 14 daerah secara nyata (ditampilkan lewat file teks atau dashboard peta web).
*   **Tanpa Split Data:** Di dunia nyata, kita tidak melakukan split data karena kita ingin model belajar menggunakan **100% data sejarah** secara maksimal tanpa membuang ilmu dari 20% data uji.
*   **5-Fold Cross Validation (`cv=5`):** Proses pelatihan di dalam program menggunakan validasi silang 5 putaran. Hal ini memastikan hyperparameter model disetel dengan sangat presisi dan adil pada seluruh bagian data sebelum model memprediksi data cuaca baru hari ini.

---

## ⚡ Mekanisme Belajar Ulang Dinamis (Retraining In-Memory)

*   **Apakah program melatih model setiap hari?** 
    **Ya.** Setiap kali berkas `prediction.py` dijalankan atau halaman website dimuat, backend web akan melatih ulang model secara instan di dalam memori komputer.
*   **Mengapa dilakukan?**
    Karena ukuran data sejarah kita kecil (puluhan baris), proses melatih ulang dari nol hanya memakan waktu **di bawah 0,1 detik**. Pendekatan ini sangat menguntungkan karena **jika ada pembaruan data tahunan baru di file Excel**, website akan langsung otomatis mengetahuinya dan belajar secara mandiri tanpa perlu instruksi training ulang secara manual dari developer.

---

## 🚀 Cara Menjalankan Website Secara Lokal

1. Masuk ke folder web:
   ```bash
   cd "Deploy Web"
   ```
2. Jalankan server Flask:
   ```bash
   python app.py
   ```
3. Buka browser Anda dan akses alamat:
   ```text
   http://127.0.0.1:5000/
   ```
