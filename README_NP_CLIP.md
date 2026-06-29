# 🛡️ Panduan Pembatas Cerdas: `np.clip` (Penyelamat Eror Cuaca Ekstrem)

Dokumen ini menjelaskan mengapa kita menggunakan fungsi pembatas cerdas **`np.clip`** pada sistem AI Early Warning System (EWS) DBD Kalimantan Barat. Penjelasan ini disajikan dengan bahasa sederhana untuk membantu pemahaman umum maupun penyusunan laporan makalah kompetisi.

---

## 🤖 Mengapa `np.clip` Diperlukan? (Masalah "Out of Distribution")

Di dalam dunia pemrograman dan kecerdasan buatan (*Machine Learning*), model AI dilatih berdasarkan batas-batas data historis di masa lalu (*Training Data*). 

Jika ada data riil di masa depan yang **terlalu ekstrem** (jauh melampaui data latihan historisnya), rumus probabilitas matematika AI akan mengalami **Numerical Underflow** (korsleting matematika).

### 1. Analogi Sederhana: Anak SD Menebak Tipe Bangunan
Bayangkan Anda melatih seorang anak SD (AI Naive Bayes) dengan contoh-contoh rumah yang pernah ada di memori sejarahnya:
* **Rumah Tipe AMAN:** Luasnya 50 m² s/d 100 m²
* **Rumah Tipe WASPADA:** Luasnya 150 m² s/d 250 m²
* **Rumah Tipe SIAGA:** Luasnya 300 m² s/d **400 m²** (Rumah terbesar yang pernah ia lihat)

Suatu hari, Anda mengajak anak tersebut ke lapangan dan menyuruhnya menebak tipe sebuah **Gedung Pencakar Langit** berukuran **6.000 m²** (setara dengan curah hujan sangat ekstrem saat pancaroba). 

Secara logika manusia, kita tahu itu pasti masuk kategori "Siaga" (karena sangat besar). Namun, rumus matematika si anak SD (Naive Bayes) akan menghitung seperti ini:
1. Menghitung kecocokan Gedung 6.000 m² dengan tipe AMAN (50-100 m²) = **0% cocok**.
2. Menghitung kecocokan Gedung 6.000 m² dengan tipe WASPADA (150-250 m²) = **0% cocok**.
3. Menghitung kecocokan Gedung 6.000 m² dengan tipe SIAGA (300-400 m²) = **0% cocok** (karena 6.000 m² terlampau jauh dari memori maksimalnya yang hanya 400 m²).

> [!CAUTION]
> **Korsleting Matematika (Underflow):**
> Karena semua kecocokan bernilai **0%**, otak si anak menjadi *blank* (mengalami pembagian $0/0$ yang ilegal). Akibatnya, ia mengalami disorientasi tebakan. 
> Pustaka AI (`scikit-learn`) akan mengambil jalur darurat (*fallback*) dan **menebak semua daerah sebagai "SIAGA" secara keliru**, sehingga dashboard peta menjadi merah semua.

---

## 🛠️ Bagaimana `np.clip` Menyelesaikannya?

Fungsi `np.clip(nilai, batas_minimum, batas_maksimum)` bertindak sebagai **pagar pembatas cerdas** sebelum data dikirim ke AI. 

Ketika ada data masuk sebesar **6.000 m²**, sebelum diberikan ke AI, kita memotong angkanya dan berkata kepada AI: 
> *"Anggap saja ini rumah berukuran **400 m²** (ukuran maksimal yang pernah kamu pelajari)."*

AI kemudian menghitung ulang secara normal tanpa eror:
* Kecocokan dengan AMAN (50-100 m²) = 0%
* Kecocokan dengan WASPADA (150-250 m²) = 0%
* Kecocokan dengan SIAGA (300-400 m²) = **95% cocok!** (karena nilainya menyentuh batas atas memori latihannya).

Hasilnya, AI dengan sangat yakin memprediksi wilayah tersebut sebagai **SIAGA / WASPADA**, tanpa merusak kalkulasi data dari daerah tetangga lainnya.

---

## 💻 Implementasi Kode Program

Di dalam berkas `prediction.py` dan `engine.py`, fitur ini diterapkan sebelum proses inferensi model dilakukan:

```python
# 1. Mendapatkan batas minimum dan maksimum dari data latih historis
min_bounds = X_train.min()
max_bounds = X_train.max()

# 2. Proyeksi data curah hujan harian ke skala tahunan untuk model
total_hujan_tahunan = round(hujan_7d * 52.18, 2)
hujan_kritis_tahunan = round(hujan_kritis_7d * 52.18, 2)

# 3. Batasi nilai (clipping) agar tidak melompat keluar dari batas distribusi data training
total_hujan_tahunan = float(np.clip(total_hujan_tahunan, min_bounds['Total_Hujan'], max_bounds['Total_Hujan']))
hujan_kritis_tahunan = float(np.clip(hujan_kritis_tahunan, min_bounds['Hujan_Kritis'], max_bounds['Hujan_Kritis']))
```

---

## 🎯 Kesimpulan & Keuntungan Lomba
* **Mencegah Overfitting & Eror Matematika:** Menjaga model AI Naive Bayes tetap bekerja stabil meskipun terjadi anomali cuaca yang sangat ekstrem.
* **Mempertahankan Sensitivitas Klasifikasi:** AI tetap mampu membedakan wilayah aman (seperti Kota Pontianak) dari wilayah waspada/siaga lainnya secara objektif dan akurat.
* **Nilai Tambah Makalah/Esai:** Menjelaskan fitur *feature clipping* (`np.clip`) ini kepada juri lomba akan menunjukkan tingkat kematangan rekayasa data Anda dalam menangani kasus *Out-of-Distribution* di skenario dunia nyata.
