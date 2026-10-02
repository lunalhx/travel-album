# 中国足迹地图资源

源数据：https://github.com/Supeset/China-GeoData

许可：MIT，Copyright (c) 2025 圈集；完整许可保留在 source/LICENSE-China-GeoData.txt。
源文件 URL 与 SHA-256 保存在 source/sources.json。地图数据来自项目公开的省级 GeoJSON 与城市 CSV。

build_china_map.py 生成本地 SVG：34 个省级区域，南海诸岛及源数据提供的海上虚线置于附图。
主图使用球面 Albers 等积圆锥投影，标准纬线 25°、47°，中央经线 105°；附图单独缩放。
当前页面不使用城市标记，只根据相册 provinceCode 为省份着色并浏览该区域的相册。city-points.json 为早期构建留下的城市数据，页面不加载它。

该页面无需在线地图 SDK、Key 或第三方地图瓦片服务；构建完成后地图资源随网站一起托管。
