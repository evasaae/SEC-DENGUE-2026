import feedparser
from datetime import datetime, timedelta
import pandas as pd
import os
import warnings
import re
from transformers import pipeline

# Redam warning dari huggingface hub
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

print("Memuat model NLP Zero-Shot Classification Pemfilter Konten...")
classifier = pipeline("zero-shot-classification", model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli")

kategori_berita = ["korban pasien meninggal darurat klinis", "sosialisasi edukasi imbauan pencegahan"]

kabupaten = [
    'Sambas', 'Bengkayang', 'Landak', 'Mempawah', 'Sanggau',
    'Ketapang', 'Sintang', 'Kapuas Hulu', 'Sekadau', 'Melawi',
    'Kayong Utara', 'Kubu Raya', 'Pontianak', 'Singkawang'
]

hari_ini = datetime.now().date()
window = [hari_ini - timedelta(days=i) for i in range(6, -1, -1)]
nama_hari = ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu']

harian = {kab: {str(d): 0 for d in window} for kab in kabupaten}
detail_berita = []

KATA_KUNCI_SAMPAH = [r"covid", r"corona", r"korupsi", r"pemberhentian", r"anggaran"]

for kab in kabupaten:
    query = f'("{kab}") AND ("DBD" OR "Demam Berdarah" OR "Dengue")'
    url = f"https://news.google.com/rss/search?q={query.replace(' ','+')}&hl=id&gl=ID&ceid=ID:id"
    feed = feedparser.parse(url)

    print(f"[FETCH] Memeriksa data Google News untuk {kab}...")

    for berita in feed.entries:
        judul = berita.title
        
        # --- PERBAIKAN UTAMA: FILTER CROSS-CHECK TITLE ---
        # Memastikan nama kabupaten yang sedang di-loop benar-benar ada di dalam judul berita
        # Jika sistem sedang mencari "Kapuas Hulu" tapi judulnya tentang "Kubu Raya", maka otomatis di-skip
        if kab.lower() not in judul.lower():
            continue
        # -------------------------------------------------
        
        if any(re.search(pattern, judul.lower()) for pattern in KATA_KUNCI_SAMPAH):
            continue
            
        try:
            tanggal = datetime(*berita.published_parsed[:6]).date()
        except:
            continue

        if tanggal not in window:
            continue

        hasil = classifier(judul, kategori_berita, multi_label=False)
        kategori_teratas = hasil['labels'][0]
        skor_keyakinan = hasil['scores'][0]

        if kategori_teratas != "korban pasien meninggal darurat klinis" or skor_keyakinan < 0.4:
            print(f"  [SKIPPED - NOISE] {judul} ({kategori_teratas} - {skor_keyakinan*100:.1f}%)")
            continue

        # Lolos filter harian
        harian[kab][str(tanggal)] += 1
        link_bersih = berita.link.split("&url=")[-1] if "&url=" in berita.link else berita.link

        print(f"  [LOLOS - KRUSIAL] {judul}")

        detail_berita.append({
            'kabupaten': kab,
            'tanggal': str(tanggal),
            'hari': nama_hari[tanggal.weekday()],
            'judul': judul,
            'link': link_bersih,
            'sumber': berita.get('source', {}).get('title', '-')
        })

# --- PROSES EKSPOR MULTI-OUTPUT ---
rows = []
for kab in kabupaten:
    row = {'Kabupaten': kab}
    total = 0
    for d in window:
        jumlah = harian[kab][str(d)]
        total += jumlah
        kolom = f"{nama_hari[d.weekday()]} {d.strftime('%d/%m')}"
        row[kolom] = jumlah
    row['Total 7 Hari'] = total
    rows.append(row)

df_volume = pd.DataFrame(rows)
df_volume['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')

if detail_berita:
    df_detail = pd.DataFrame(detail_berita)
else:
    df_detail = pd.DataFrame(columns=['kabupaten','tanggal','hari','judul','link','sumber'])

df_detail['generated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')

os.makedirs('data', exist_ok=True)

with open('data/last_updated.txt', 'w') as f:
    f.write(datetime.now().strftime('%Y-%m-%d %H:%M'))

df_volume.to_csv('data/berita_dbd.csv', index=False)
df_detail.to_csv('data/detail_berita.csv', index=False)

print("\n==========================================")
print(f"[SUCCESS] Pipeline Perbaikan Selesai: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"Detail berita bersih: {len(df_detail)} artikel valid ditemukan.")
print("==========================================")