import pandas as pd

URL_BERITA  = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/data/berita_dbd.csv"
URL_CUACA   = "https://raw.githubusercontent.com/evasaae/SEC-DENGUE-2026/main/Data%20Cuaca%20Harian%20Kalbar/Data_Cuaca_Harian_Kalbar_Hari_Ini.csv"

print("--- BERITA ---")
try:
    df_berita = pd.read_csv(URL_BERITA)
    print("Columns:", df_berita.columns.tolist())
    print(df_berita.head(3))
except Exception as e:
    print("Berita failed:", e)

print("\n--- CUACA ---")
try:
    df_cuaca = pd.read_csv(URL_CUACA)
    print("Columns:", df_cuaca.columns.tolist())
    print(df_cuaca.head(3))
except Exception as e:
    print("Cuaca failed:", e)
