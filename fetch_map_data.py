"""Download public, MIT-licensed map data for the local footprint page."""

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen


out = Path(__file__).parent / "assets/maps/source"
out.mkdir(parents=True, exist_ok=True)
base = "https://raw.githubusercontent.com/Supeset/China-GeoData/main/"
files = [
    ("geojson/china_province_full.geojson", "china-provinces.geojson"),
    ("LICENSE", "LICENSE-China-GeoData.txt"),
]
sources = []
for path, name in files:
    with urlopen(base + path, timeout=25) as response:
        content = response.read()
    (out / name).write_bytes(content)
    sources.append({"file": name, "url": base + path, "sha256": hashlib.sha256(content).hexdigest()})
    print(name, len(content), "bytes")
(out / "sources.json").write_text(json.dumps(sources, indent=2) + "\n")
data = json.loads((out / "china-provinces.geojson").read_text())
print("features:", len(data["features"]))
for feature in data["features"]:
    properties = feature["properties"]
    print(properties.get("name"), properties.get("adcode"), properties.get("center"), feature["geometry"]["type"])
