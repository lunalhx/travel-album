# 所至所及 · 旅行相册

按年份和城市整理照片，按拍摄日期记录地点、器材、同行人与当天的故事。

- 网站：<https://lunalhx.github.io/travel-album/>
- 自动部署：<https://github.com/lunalhx/travel-album/actions>

## 本机使用

双击 `start_manager.command`，然后打开 <http://127.0.0.1:8765/preview.html>。在「管理相册」中添加和整理照片。终端窗口保持运行。

其他电脑首次使用：

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python manage_server.py
```

## 管理相册

在本机页面点击「管理相册」，可以：

- 新建、删除相册，修改名称、年份、城市和所属地区。
- 添加、修改、移除拍摄日期；修改整组日期时，照片和手记一起移动。
- 批量添加 JPG、PNG 或 WebP，自动生成最长边 1280px 的轻量副本；HEIC 需先转换。
- 修改照片日期和说明，批量移除照片引用。
- 记录拍摄地点、器材、同行人和故事。
- 撤销最后一次改动，一次批量添加可一起撤销。

年度册的拍摄日期必须属于该年份。同城同年使用同一本年度册；两个日期都有手记时，需要先整理内容再合并日期。

修改保存在 `assets/albums.json`、`assets/shooting-notes.json` 和 `assets/photos/uploads/`。撤销记录保存在 `.local/history/`；这些备份请保留。删除相册或移除照片只改变引用，原图与其他相册不受影响。

终端窗口需保持运行，按 Ctrl+C 可停止服务。端口占用时先检查是否已启动另一个管理窗口。

需要手动发布包时，可点击管理页「导出发布包」，或运行：

```sh
python manage_server.py --export /tmp/travel-album-site.zip
```

首次批量导入使用 `import_photos.py`；之后通过管理页继续添加，避免重新导入覆盖手工整理。导入报告和联系表保存在 `.local/imports/`，不进入仓库。

## 更新网站

本机编辑完成后，双击 `publish.command`。脚本会检查并提交当前相册资料、手记、引用的轻量照片和网页源码，再推送到 `main`；GitHub Actions 自动构建并部署。

也可以运行：

```sh
python publish.py
```

GitHub CLI 登录或 Git 的 HTTPS 凭据需有效。部署进度见上方 Actions 链接。

## 存储与发布

完整原图由你保存在本地。新添加的图片自动生成最长边 1280px 的 WebP 轻量副本。照片墙和放大查看都使用轻量副本；公开网站不会访问你电脑上的原图。

GitHub Actions 运行 `build_site.py`，仅将生成的 `dist/` 发布到 Pages。本机服务、备份、完整原图、旧 2400px 副本和工作记录不进入网站。仓库提交也通过发布清单排除它们；不再引用的照片会从当前 Git 文件清单移除，本地图片文件保留。

公开仓库与 Pages 中的照片和手记可以被他人查看。不要在发布资料中保存不想公开的内容。

## 浏览验证

公开页面先显示「我叫什么名字」的问题，答对后才加载相册、手记和地图。验证状态只保存在当前标签页的会话中，刷新无需重复回答；本机管理服务直接进入编辑页面。浏览器不允许会话存储时，仍可验证进入，刷新后需要重新回答。

这是前端浏览门槛，不是私密相册权限。即使答案只保存为 SHA-256 摘要，访客仍能绕过前端逻辑、猜测答案，或者直接访问公开的图片与 JSON 文件。需要保护这些资源时，应改用服务端认证。

## 检查

```sh
python -m unittest -v test_archive_management
python build_site.py
```

当前覆盖相册/日期/照片编辑、手记随日期迁移、删除与撤销、批量撤销、原图不变和静态导出资源。

地图源数据：<https://github.com/Supeset/China-GeoData>（MIT），许可保留在 `assets/maps/source/LICENSE-China-GeoData.txt`。照片与城市封面不授予公开复用许可。

## 项目文件

- `preview.html`、`album-manager.js`、`album-manager.css`、`album_helpers.js`：网页和管理界面。
- `assets/`：相册资料、手记、照片、城市封面和地图；不要随意删除。
- `manage_server.py`：本机管理服务；`build_site.py`、`publish.py`：构建和发布。
- `import_photos.py`、`album_model.py`：首次导入与相册分组。
- `build_china_map.py`、`fetch_map_data.py`、`prepare_city_covers.py`：地图与封面维护工具。
- `test_archive_management.py`、`.github/`：检查与自动部署。
- `.local/`：本机撤销备份与导入报告，不提交；`dist/` 是可重新生成的发布目录。
