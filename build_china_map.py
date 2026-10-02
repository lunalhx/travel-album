"""Build a local vector China map and city-level album marker positions."""

import csv
import html
import json
import math
from pathlib import Path


ROOT = Path(__file__).parent / "assets/maps"
SOURCE = ROOT / "source"
WIDTH, HEIGHT = 1000, 720


def project(lon, lat):
    # Spherical Albers equal-area conic; parallels suited to a China overview.
    p1, p2, p0 = map(math.radians, (25, 47, 35))
    n = (math.sin(p1) + math.sin(p2)) / 2
    c = math.cos(p1) ** 2 + 2 * n * math.sin(p1)
    rho = math.sqrt(c - 2 * n * math.sin(math.radians(lat))) / n
    rho0 = math.sqrt(c - 2 * n * math.sin(p0)) / n
    theta = n * math.radians(lon - 105)
    return rho * math.sin(theta), rho0 - rho * math.cos(theta)


def polygons(feature):
    geometry = feature["geometry"]
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return geometry["coordinates"]
    raise ValueError(geometry["type"])


data = json.loads((SOURCE / "china-provinces.geojson").read_text())
features = data["features"]
assert len([f for f in features if f["properties"].get("name")]) == 34
mainland = []
for feature in features:
    if not feature["properties"].get("name"):
        continue
    for polygon in polygons(feature):
        if max(lat for _, lat in polygon[0]) >= 18:
            mainland.extend(project(lon, lat) for ring in polygon for lon, lat in ring)
xmin = min(x for x, _ in mainland)
xmax = max(x for x, _ in mainland)
ymin = min(y for _, y in mainland)
ymax = max(y for _, y in mainland)
scale = min((WIDTH - 90) / (xmax - xmin), (HEIGHT - 90) / (ymax - ymin))
xoff = (WIDTH - (xmax - xmin) * scale) / 2
yoff = 32


def screen(lon, lat):
    x, y = project(lon, lat)
    return xoff + (x - xmin) * scale, yoff + (ymax - y) * scale


def path_for(items, transform):
    result = []
    for polygon in items:
        for ring in polygon:
            points = [transform(lon, lat) for lon, lat in ring]
            result.append("M" + "L".join(f"{x:.2f},{y:.2f}" for x, y in points) + "Z")
    return "".join(result)


svg = [f'''<svg xmlns="http://www.w3.org/2000/svg" id="chinaMap" viewBox="0 0 {WIDTH} {HEIGHT}" role="group" aria-label="中国省级足迹地图">
<title>中国足迹地图</title>
<desc>中国省级区划和南海诸岛附图。金色区域表示有旅行相册，点击区域可浏览不同的相册。</desc>
<defs><clipPath id="southSeaClip"><rect x="825" y="459" width="125" height="191" rx="1"/></clipPath></defs>
<g id="provinceShapes">''']
for feature in features:
    properties = feature["properties"]
    name = properties.get("name")
    if not name:
        continue
    items = [p for p in polygons(feature) if max(lat for _, lat in p[0]) >= 18]
    name = html.escape(name)
    code = properties["adcode"]
    svg.append(f'<g class="province" data-code="{code}" data-name="{name}"><title>{name}</title><path d="{path_for(items, screen)}" fill-rule="evenodd"/></g>')
svg.append('</g><g class="south-sea-inset" aria-label="南海诸岛附图">')
svg.append('<rect class="inset-frame" x="825" y="459" width="125" height="191" rx="1"/>')
svg.append('<g clip-path="url(#southSeaClip)">')


def inset(lon, lat):
    return 825 + (lon - 105) / 20 * 125, 459 + (25 - lat) / 23 * 191


for feature in features:
    # Clip all source geometry into the inset, including the supplied dotted line.
    code = feature["properties"].get("adcode")
    css = "inset-dotted-line" if code == "100000_JD" else "inset-land"
    svg.append(f'<path class="{css}" d="{path_for(polygons(feature), inset)}" fill-rule="evenodd"/>')
svg.append('</g><text class="inset-caption" x="887.5" y="670" text-anchor="middle">南海诸岛</text></g>')
svg.append('</svg>')
(ROOT / "china-provinces.svg").write_text("\n".join(svg) + "\n")

province_codes = {"兰州": "620000", "重庆": "500000"}
city_points = {}
with (SOURCE / "china-cities.csv").open() as handle:
    for city in csv.DictReader(handle):
        if city["name"] not in province_codes:
            continue
        lon, lat = float(city["lon"]), float(city["lat"])
        x, y = screen(lon, lat)
        city_points[city["name"]] = {
            "provinceCode": province_codes[city["name"]],
            "longitude": lon,
            "latitude": lat,
            "x": round(x, 2),
            "y": round(y, 2),
            "precision": "city",
            "source": "China-GeoData/csv/china_cities.csv",
        }
assert set(city_points) == set(province_codes)
(ROOT / "city-points.json").write_text(json.dumps(city_points, ensure_ascii=False, indent=2) + "\n")
(ROOT / "README.md").write_text('''# 中国足迹地图资源

源数据：https://github.com/Supeset/China-GeoData

许可：MIT，Copyright (c) 2025 圈集；完整许可保留在 source/LICENSE-China-GeoData.txt。
源文件 URL 与 SHA-256 保存在 source/sources.json。地图数据来自项目公开的省级 GeoJSON 与城市 CSV。

build_china_map.py 生成本地 SVG：34 个省级区域，南海诸岛及源数据提供的海上虚线置于附图。
主图使用球面 Albers 等积圆锥投影，标准纬线 25°、47°，中央经线 105°；附图单独缩放。
城市标记是公开城市中心位置，用于旅行相册归档，不代表照片 GPS。省份高亮表示存在该省相册。

该页面无需在线地图 SDK、Key 或第三方地图瓦片服务；构建完成后地图资源随网站一起托管。
''')
print("Built", ROOT / "china-provinces.svg", (ROOT / "china-provinces.svg").stat().st_size, "bytes")
print(json.dumps(city_points, ensure_ascii=False))
