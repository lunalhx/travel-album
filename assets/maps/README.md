# 中国足迹地图资源

源数据：https://github.com/Supeset/China-GeoData

许可：MIT，Copyright (c) 2025 圈集；完整许可保留在 source/LICENSE-China-GeoData.txt。
源文件 URL 与 SHA-256 保存在 source/sources.json。地图使用该项目的省级 GeoJSON。

build_china_map.py 生成本地 SVG：34 个省级区域，南海诸岛及源数据提供的海上虚线置于附图。
主图使用球面 Albers 等积圆锥投影，标准纬线 25°、47°，中央经线 105°；附图单独缩放。
页面根据相册 provinceCode 为省份着色并浏览该区域的相册，不使用城市点位数据。

该页面无需在线地图 SDK、Key 或第三方地图瓦片服务；构建完成后地图资源随网站一起托管。
