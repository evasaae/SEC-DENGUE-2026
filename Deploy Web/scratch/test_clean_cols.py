import pandas as pd
import re

URL_CUACA   = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data%20Cuaca%20Harian%20Kalbar/Data_Cuaca_Harian_Kalbar_Hari_Ini.csv"

df = pd.read_csv(URL_CUACA)
print("Original columns:", df.columns.tolist())

# Strategy 1: Replace non-ascii
df.columns = [re.sub(r'[^\x00-\x7F]+', ' ', col).strip() for col in df.columns]
print("Cleaned columns:", df.columns.tolist())

# Try finding temperature column dynamically
suhu_col = [col for col in df.columns if 'suhu' in col.lower()][0]
kelembapan_col = [col for col in df.columns if 'kelembapan' in col.lower()][0]
hujan_col = [col for col in df.columns if 'hujan 7 hari' in col.lower() or 'hujan 7d' in col.lower() or 'jam hujan 7' in col.lower()][0]

print("Found Suhu:", suhu_col)
print("Found Kelembapan:", kelembapan_col)
print("Found Hujan:", hujan_col)
