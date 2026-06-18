"""
Download dan dissolve GeoJSON Kalimantan Barat ke level Kabupaten.
Sumber: JfrAziz/indonesia-district (level desa) -> dissolved ke Kabupaten.
Menggunakan Shapely untuk menggabungkan polygon sehingga garis internal hilang.
Output: static/kalbar_kabupaten.geojson
"""
import requests
import json
import os
from shapely.geometry import shape, mapping
from shapely.ops import unary_union

URL = "https://raw.githubusercontent.com/JfrAziz/indonesia-district/master/id61_kalimantan_barat/id61_kalimantan_barat_district.geojson"
OUTPUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "kalbar_kabupaten.geojson")

print("Downloading GeoJSON Kalimantan Barat (~12MB)...")
resp = requests.get(URL, timeout=60)
resp.raise_for_status()
data = resp.json()

print(f"  Total features (desa/kecamatan): {len(data['features'])}")

# Group features by kabupaten name (property: 'regency')
kab_groups = {}
for feat in data['features']:
    props = feat['properties']
    kab_name = str(props.get('regency', 'UNKNOWN')).upper().strip()
    if kab_name not in kab_groups:
        kab_groups[kab_name] = []
    kab_groups[kab_name].append(feat)

print(f"  Kabupaten ditemukan: {len(kab_groups)}")

# Dissolve: gabungkan semua polygon per kabupaten menjadi 1 polygon tunggal
output_features = []
for kab_name, feats in kab_groups.items():
    print(f"    Dissolving {kab_name} ({len(feats)} sub-polygons)...")

    # Konversi ke Shapely geometries
    geometries = []
    for f in feats:
        try:
            geom = shape(f['geometry'])
            if geom.is_valid:
                geometries.append(geom)
            else:
                geometries.append(geom.buffer(0))  # fix invalid geometry
        except Exception:
            pass

    if not geometries:
        print(f"      SKIP: no valid geometries")
        continue

    # Dissolve semua menjadi satu polygon
    merged = unary_union(geometries)

    # Simplify untuk mengurangi ukuran file (~100m tolerance)
    merged = merged.simplify(0.005, preserve_topology=True)

    merged_feature = {
        "type": "Feature",
        "properties": {
            "NAME_2": kab_name,
            "name": kab_name,
            "kabupaten": kab_name,
            "regency": kab_name
        },
        "geometry": mapping(merged)
    }
    output_features.append(merged_feature)

output_geo = {
    "type": "FeatureCollection",
    "features": output_features
}

# Round coordinates to 4 decimal places
def round_coords(obj):
    if isinstance(obj, (list, tuple)):
        if len(obj) >= 2 and isinstance(obj[0], (int, float)):
            return [round(obj[0], 4), round(obj[1], 4)]
        return [round_coords(x) for x in obj]
    return obj

for feat in output_geo['features']:
    feat['geometry']['coordinates'] = round_coords(feat['geometry']['coordinates'])

# Save
os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(output_geo, f, separators=(',', ':'))

size = os.path.getsize(OUTPUT)
print(f"\nDONE - Saved: {OUTPUT}")
print(f"  Size: {size / 1024:.0f} KB ({len(output_features)} kabupaten)")
print(f"  Garis internal kecamatan sudah di-dissolve!")
