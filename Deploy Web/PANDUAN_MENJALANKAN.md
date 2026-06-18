# 📘 PANDUAN MENJALANKAN DASHBOARD EWS DBD KALBAR

> **Sistem Peringatan Dini Demam Berdarah Dengue — Provinsi Kalimantan Barat**
> Berbasis Gaussian Naive Bayes + Data Cuaca Real-Time

---

## 📋 Daftar Isi

1. [Prasyarat](#1-prasyarat)
2. [Instalasi (Sekali Saja)](#2-instalasi-sekali-saja)
3. [Menjalankan Dashboard](#3-menjalankan-dashboard)
4. [Mengakses Dashboard](#4-mengakses-dashboard)
5. [Fitur-Fitur Dashboard](#5-fitur-fitur-dashboard)
6. [Struktur File Proyek](#6-struktur-file-proyek)
7. [Troubleshooting / Masalah Umum](#7-troubleshooting--masalah-umum)
8. [Menghentikan Server](#8-menghentikan-server)
9. [Update Data Peta (Opsional)](#9-update-data-peta-opsional)

---

## 1. Prasyarat

Pastikan hal-hal berikut sudah tersedia di komputer kamu:

| Kebutuhan | Versi Minimum | Cara Cek |
|-----------|---------------|----------|
| **Python** | 3.10+ | Buka CMD/PowerShell, ketik `python --version` |
| **pip** | Bawaan Python | `pip --version` |
| **File Excel Data** | — | Pastikan file `SEC13 SATRIA DATA 2026 REMINDER.xlsx` ada di `D:\SATRIA DATA\SEC-DENGUE-2026\` |
| **Koneksi Internet** | — | Diperlukan untuk mengambil data cuaca dan berita real-time dari GitHub |

---

## 2. Instalasi (Sekali Saja)

Buka **CMD** atau **PowerShell**, lalu jalankan perintah berikut:

```bash
pip install flask flask-cors pandas numpy scikit-learn requests openpyxl
```

**Penjelasan library:**
| Library | Fungsi |
|---------|--------|
| `flask` | Web server untuk dashboard |
| `flask-cors` | Menangani cross-origin request |
| `pandas` | Membaca file Excel data epidemiologi |
| `numpy` | Komputasi numerik |
| `scikit-learn` | Model ML Gaussian Naive Bayes |
| `requests` | Mengambil data cuaca & berita dari internet |
| `openpyxl` | Membaca file `.xlsx` (Excel) |

> **Catatan:** Instalasi hanya perlu dilakukan **SATU KALI**. Setelahnya, kamu bisa langsung menjalankan server.

---

## 3. Menjalankan Dashboard

### Langkah-langkah:

**1. Buka CMD / PowerShell**

**2. Pindah ke folder proyek:**
```bash
cd "D:\SATRIA DATA\SEC-DENGUE-2026\Deploy Web" 
```

**3. Jalankan server:**
```bash
python app.py
```

**4. Tunggu hingga muncul output seperti ini:**
```
============================================================
   EWS DBD KALBAR — Dashboard Server
   Public  : http://localhost:5000
   Admin   : http://localhost:5000/admin
   API     : http://localhost:5000/api/status
============================================================

 * Serving Flask app 'app'
 * Running on http://127.0.0.1:5000
```

✅ Server sudah berjalan! Jangan tutup jendela CMD ini.

---

## 4. Mengakses Dashboard

Buka **browser** (Chrome/Edge/Firefox) dan ketik salah satu URL berikut:

| Halaman | URL | Keterangan |
|---------|-----|------------|
| **Dashboard Utama** | `http://localhost:5000` | Peta choropleth + tabel analisis proaktif |
| **Panel Admin Dinkes** | `http://localhost:5000/admin` | Kontrol fogging per kabupaten (PIN: `4321`) |
| **API Status (JSON)** | `http://localhost:5000/api/status` | Data mentah dalam format JSON |

---

## 5. Fitur-Fitur Dashboard

### 🗺️ Peta Choropleth
- Menampilkan **14 kabupaten/kota** Kalimantan Barat
- Warna otomatis berdasarkan status:
  - 🟢 **Hijau** = AMAN
  - 🟡 **Kuning** = WASPADA
  - 🔴 **Merah** = SIAGA
- Klik wilayah di peta untuk melihat detail (THI, Suhu, Kelembapan, dll.)

### 📊 Tabel Analisis Dinamis Proaktif
- Menampilkan data **per wilayah** secara real-time
- Kolom penting:
  - **THI** (Temperature-Humidity Index)
  - **Analisis Proaktif** — prediksi pergeseran status ke depan
  - **Drift Risk** — persentase risiko eskalasi

### ⚡ Golden Window Trigger
- **Sidebar kiri** yang muncul otomatis jika ada wilayah dengan drift ≥50%
- Bisa dibuka/tutup dengan tombol ⚡ di kiri bawah layar
- Berisi:
  - Daftar wilayah kritis
  - Tombol **Perintah Abatization**
  - Tombol **Simulasi Broadcast Blast WA**

### 🏥 Panel Admin Dinkes
- Akses: `http://localhost:5000/admin`
- **PIN:** `4321`
- Fungsi: Mengaktifkan/menonaktifkan **fogging** per kabupaten
- Saat fogging aktif → risiko sosial turun 85%, THI reset ke 72.0

### 🔄 Auto-Refresh
- Data otomatis diperbarui setiap **5 menit**
- Bisa di-refresh manual dengan tombol **Refresh Data**

---

## 6. Struktur File Proyek

```
D:\SATRIA DATA\Deploy Web\
│
├── app.py                  ← Server Flask utama (JALANKAN FILE INI)
├── engine.py               ← Mesin ML (Gaussian Naive Bayes)
├── codenya.py              ← Logika intervensi fogging
├── index.html              ← Halaman dashboard utama
├── admin.html              ← Halaman admin Dinkes
├── download_geojson.py     ← Script download peta (tidak perlu dijalankan ulang)
│
├── static/
│   ├── style.css                   ← Styling dashboard
│   ├── dashboard.js                ← Logika frontend dashboard
│   ├── admin.css                   ← Styling admin panel
│   ├── admin.js                    ← Logika frontend admin
│   └── kalbar_kabupaten.geojson    ← Data peta 14 kabupaten (sudah terunduh)
│
└── D:\SATRIA DATA\SEC-DENGUE-2026\
    └── SEC13 SATRIA DATA 2026 REMINDER.xlsx  ← Data epidemiologi sumber
```

---

## 7. Troubleshooting / Masalah Umum

### ❌ "ModuleNotFoundError: No module named 'flask'"
**Solusi:** Install ulang dependencies:
```bash
pip install flask flask-cors pandas numpy scikit-learn requests openpyxl
```

### ❌ "FileNotFoundError: SEC13 SATRIA DATA 2026 REMINDER.xlsx"
**Solusi:** Pastikan file Excel ada di:
```
D:\SATRIA DATA\SEC-DENGUE-2026\SEC13 SATRIA DATA 2026 REMINDER.xlsx
```

### ❌ "Address already in use" / Port 5000 sudah dipakai
**Solusi:** Ada server lain yang masih berjalan. Tutup CMD lama, atau hentikan proses:
```bash
taskkill /f /im python.exe
```
Lalu jalankan ulang `python app.py`.

### ❌ Peta tidak muncul / hanya background hitam
**Solusi:** Pastikan file `static/kalbar_kabupaten.geojson` ada. Jika tidak:
```bash
pip install shapely
python download_geojson.py
```
Ini akan mengunduh dan memproses ulang data peta.

### ❌ Data cuaca tidak terupdate
**Solusi:** Periksa koneksi internet. Dashboard mengambil data cuaca dari:
- `https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data Cuaca Harian Kalbar/`

### ❌ "UserWarning: X does not have valid feature names"
**Ini BUKAN error.** Hanya warning dari scikit-learn yang bisa diabaikan. Dashboard tetap berfungsi normal.

### ❌ Browser menampilkan halaman lama (cache)
**Solusi:** Tekan `Ctrl + Shift + R` (hard refresh) di browser.

---

## 8. Menghentikan Server

Untuk menghentikan server, tekan **`Ctrl + C`** di jendela CMD/PowerShell tempat `python app.py` berjalan.

---

## 9. Update Data Peta (Opsional)

File peta (`kalbar_kabupaten.geojson`) sudah tersimpan lokal dan **tidak perlu diunduh ulang** kecuali ingin memperbarui data geografis.

Jika perlu update:
```bash
pip install shapely
python download_geojson.py
```

Script ini akan:
1. Mengunduh ~12MB data GeoJSON dari GitHub
2. Menggabungkan (dissolve) 2.132 desa/kecamatan menjadi 14 kabupaten/kota
3. Menyimpan file ringkas (~58KB) ke `static/kalbar_kabupaten.geojson`

---

## 📌 Ringkasan Cepat (Quick Start)

```bash
# 1. Buka CMD/PowerShell

# 2. Masuk ke folder
cd "D:\SATRIA DATA\Deploy Web"

# 3. Jalankan
python app.py

# 4. Buka browser → http://localhost:5000
```

**Selesai!** 🎉
