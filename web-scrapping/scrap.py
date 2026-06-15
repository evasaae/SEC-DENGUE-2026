import feedparser
from datetime import datetime, timedelta
import pandas as pd
import os

kabupaten = [
    'Sambas', 'Bengkayang', 'Landak', 'Mempawah', 'Sanggau',
    'Ketapang', 'Sintang', 'Kapuas Hulu', 'Sekadau', 'Melawi',
    'Kayong Utara', 'Kubu Raya', 'Pontianak', 'Singkawang'
]

hari_ini = datetime.now().date()
window = [hari_ini - timedelta(days=i) for i in range(6, -1, -1)]
nama_hari = ['Senin','Selasa','Rabu','Kamis','Jumat','Sabtu','Minggu']

harian = {kab: {str(d): 0 for d in window} for kab in kabupaten}

for kab in kabupaten:
    query = f"demam berdarah {kab} kalimantan barat"
    url = f"https://news.google.com/rss/search?q={query.replace(' ','+')}&hl=id&gl=ID&ceid=ID:id"
    feed = feedparser.parse(url)
    
    for berita in feed.entries:
        try:
            tanggal = datetime(*berita.published_parsed[:6]).date()
        except:
            continue
        if str(tanggal) in harian[kab]:
            harian[kab][str(tanggal)] += 1

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

df = pd.DataFrame(rows)

# Simpan ke CSV
os.makedirs('data', exist_ok=True)
df.to_csv('data/berita_dbd.csv', index=False)
print(f"CSV disimpan: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(df.to_string())