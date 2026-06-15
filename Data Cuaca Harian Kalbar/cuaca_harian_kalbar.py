import os
from datetime import datetime, timedelta
import pandas as pd
import requests

# 1. Daftar Koordinat Resmi 14 Kabupaten/Kota di Kalimantan Barat
WILAYAH_KALBAR = {
    "Kota Pontianak": {"lat": -0.0263, "lon": 109.3425},
    "Kota Singkawang": {"lat": 0.9114, "lon": 108.9852},
    "Kab. Kubu Raya": {"lat": -0.1566, "lon": 109.3425},
    "Kab. Mempawah": {"lat": 0.3687, "lon": 108.9613},
    "Kab. Sambas": {"lat": 1.3622, "lon": 109.3068},
    "Kab. Bengkayang": {"lat": 0.8211, "lon": 109.4894},
    "Kab. Landak": {"lat": 0.4243, "lon": 109.9616},
    "Kab. Sanggau": {"lat": 0.1235, "lon": 110.5891},
    "Kab. Sekadau": {"lat": -0.0336, "lon": 110.9509},
    "Kab. Sintang": {"lat": 0.0712, "lon": 111.4985},
    "Kab. Melawi": {"lat": -0.3411, "lon": 111.6982},
    "Kab. Kapuas Hulu": {"lat": 0.8175, "lon": 112.9329},
    "Kab. Ketapang": {"lat": -1.8506, "lon": 110.0044},
    "Kab. Kayong Utara": {"lat": -1.1114, "lon": 109.9575},
}

list_lat = [str(info["lat"]) for info in WILAYAH_KALBAR.values()]
list_lon = [str(info["lon"]) for info in WILAYAH_KALBAR.values()]

lats_param = ",".join(list_lat)
lons_param = ",".join(list_lon)

URL_API = f"https://api.open-meteo.com/v1/forecast?latitude={lats_param}&longitude={lons_param}&hourly=temperature_2m,relative_humidity_2m,precipitation,weather_code&timezone=Asia%2FJakarta&forecast_days=1"

print("[*] Menghubungi Open-Meteo untuk data harian terbaru..." )

try:
    response = requests.get(URL_API, timeout=20)
    if response.status_code == 200:
        responses_json = response.json()
        if isinstance(responses_json, dict):
            responses_json = [responses_json]

        data_hari_ini = []
        nama_wilayah_list = list(WILAYAH_KALBAR.keys())
        tanggal_sekarang = datetime.now().strftime("%Y-%m-%d")

        for index, data_wilayah in enumerate(responses_json):
            nama_wilayah = nama_wilayah_list[index]
            hourly_data = data_wilayah.get("hourly", {})

            list_suhu = hourly_data.get("temperature_2m", [])
            list_kelembapan = hourly_data.get("relative_humidity_2m", [])
            list_hujan = hourly_data.get("precipitation", [])
            list_kode = hourly_data.get("weather_code", [])

            if list_suhu:
                suhu_rata = round(sum(list_suhu) / len(list_suhu), 1)
                kelembapan_rata = round(sum(list_kelembapan) / len(list_kelembapan), 1)
                total_volume_hujan = round(sum(list_hujan), 1)

                jam_hujan = 0
                jam_tidak_hujan = 0
                for kode in list_kode:
                    if kode >= 51:
                        jam_hujan += 1
                    else:
                        jam_tidak_hujan += 1

                ringkasan_wilayah = {
                    "Tanggal": tanggal_sekarang,
                    "Kabupaten / Kota": nama_wilayah,
                    "Rata-rata Suhu (°C)": suhu_rata,
                    "Rata-rata Kelembapan (%)": kelembapan_rata,
                    "Akumulasi Hujan (mm)": total_volume_hujan,
                    "Total Jam Hujan (Jam)": jam_hujan,
                    "Total Jam Tidak Hujan (Jam)": jam_tidak_hujan,
                    "Total Jam Hujan 7 Hari": 0
                }
                data_hari_ini.append(ringkasan_wilayah)

        df_baru = pd.DataFrame(data_hari_ini)

        folder_skrip = os.path.dirname(os.path.abspath(__file__))
        nama_file_csv = os.path.join(folder_skrip, "Data_Cuaca_Harian_Kalbar_Hari_Ini.csv")

        if os.path.exists(nama_file_csv):
            try:
                df_lama = pd.read_csv(nama_file_csv)
                df_total = pd.concat([df_lama, df_baru], ignore_index=True)
            except Exception:
                df_total = df_baru
        else:
            df_total = df_baru

        df_total["Tanggal"] = pd.to_datetime(df_total["Tanggal"], format="mixed")

        df_total.drop_duplicates(subset=["Tanggal", "Kabupaten / Kota"], keep="last", inplace=True)

        batas_bawah_tanggal = pd.to_datetime(datetime.now().date() - timedelta(days=6))
        df_total = df_total[df_total["Tanggal"] >= batas_bawah_tanggal]

        df_total["Total Jam Hujan 7 Hari"] = df_total.groupby("Kabupaten / Kota")["Total Jam Hujan (Jam)"].transform("sum")

        df_total["Tanggal"] = df_total["Tanggal"].dt.strftime("%Y-%m-%d")

        df_total.sort_values(by=["Tanggal", "Kabupaten / Kota"], ascending=[False, True], inplace=True)

        df_total.to_csv(nama_file_csv, index=False)
        print(f"\n[SUKSES] Sinkronisasi data aman! File CSV berhasil diperbarui di dalam folder yang sama.")

    else:
        print(f"[Gagal] Server Open-Meteo mengirim status: {response.status_code}")
except Exception as e:
    print(f"[Error] Terjadi kegagalan pemrosesan data: {e}")