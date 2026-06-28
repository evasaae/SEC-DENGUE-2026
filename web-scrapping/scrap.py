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
detail_berita = []
kata_kunci_dbd = ['dbd', 'demam berdarah', 'dengue', 'aedes', 'fogging', 'nyamuk']

for kab in kabupaten:
    keywords = [
        f"DBD {kab} kalimantan barat",
        f"demam berdarah dengue {kab}",
        f"wabah DBD {kab}"
    ]
    query = " OR ".join(keywords)
    url = f"https://news.google.com/rss/search?q={query.replace(' ','+')}&hl=id&gl=ID&ceid=ID:id"
    feed = feedparser.parse(url)

    for berita in feed.entries:
        judul_lower = berita.title.lower()

        if not any(kata in judul_lower for kata in kata_kunci_dbd):
            continue

        try:
            tanggal = datetime(*berita.published_parsed[:6]).date()
        except:
            continue

        if str(tanggal) in harian[kab]:
            harian[kab][str(tanggal)] += 1

        if tanggal in window:
            detail_berita.append({
                'kabupaten': kab,
                'tanggal': str(tanggal),
                'hari': nama_hari[tanggal.weekday()],
                'judul': berita.title,
                'link': berita.link,
                'sumber': berita.get('source', {}).get('title', '-')
            })

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

print(f"Selesai: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"Volume:\n{df_volume.to_string()}")
print(f"\nDetail berita: {len(df_detail)} artikel ditemukan")