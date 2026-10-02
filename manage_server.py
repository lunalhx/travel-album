"""Local photo-album editor. Run with a Python environment containing Pillow."""

import argparse
import copy
import io
import json
import mimetypes
import secrets
import threading
import zipfile
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit
import xml.etree.ElementTree as ET

from PIL import ExifTags, Image, ImageCms, ImageOps, UnidentifiedImageError


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)


def checked_date(value):
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ValueError("请选择有效的拍摄日期。")


def session_dates(album):
    return sorted(set(album.get("sessions", [])) | {p["shotAt"][:10] for p in album["photos"]})


def update_album(album):
    album["photos"].sort(key=lambda p: (p["shotAt"], p["id"]))
    dates = session_dates(album)
    album["sessions"] = dates
    album["captureDays"] = len(dates)
    album["dateStart"] = dates[0] if dates else ""
    album["dateEnd"] = dates[-1] if dates else ""
    album["date"] = dates[0].replace("-", ".") if dates else "尚无拍摄记录"
    if len(dates) > 1:
        album["date"] += " — " + dates[-1].replace("-", ".")
    album["note"] = f"{len(album['photos'])} 张照片 · {len(dates)} 天拍摄记录"
    ids = {p["id"] for p in album["photos"]}
    if album.get("coverId") not in ids:
        album["coverId"] = album["photos"][0]["id"] if ids else ""
    if album["albumType"] == "special" and dates:
        album["year"] = dates[0][:4]


class Archive:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.assets = self.root / "assets"
        self.lock = threading.RLock()
        self.history = self.root / ".local" / "history"
        self.history.mkdir(parents=True, exist_ok=True)
        self.import_batches = set()
        tree = ET.parse(self.assets / "maps" / "china-provinces.svg")
        self.provinces = [{"code": el.attrib["data-code"], "name": el.attrib["data-name"]}
                          for el in tree.iter() if "data-code" in el.attrib]
        self.province_names = {p["code"]: p["name"] for p in self.provinces}

    def read(self):
        manifest = json.loads((self.assets / "albums.json").read_text())
        notes = json.loads((self.assets / "shooting-notes.json").read_text())
        for album in manifest["albums"]:
            update_album(album)
        return {"manifest": manifest, "notes": notes}

    def save(self, state, previous, batch_id=None):
        for album in state["manifest"]["albums"]:
            update_album(album)
        state["manifest"]["albums"].sort(key=lambda a: (a["dateEnd"] or a["year"], a["id"]), reverse=True)
        if not batch_id or batch_id not in self.import_batches:
            write_json(self.history / (datetime.now().strftime("%Y%m%d-%H%M%S-%f") + ".json"), previous)
            if batch_id:
                self.import_batches.add(batch_id)
        try:
            write_json(self.assets / "albums.json", state["manifest"])
            write_json(self.assets / "shooting-notes.json", state["notes"])
        except OSError:
            write_json(self.assets / "albums.json", previous["manifest"])
            write_json(self.assets / "shooting-notes.json", previous["notes"])
            raise

    def state(self):
        with self.lock:
            result = self.read()
            result["provinces"] = self.provinces
            result["canUndo"] = any(self.history.glob("*.json"))
            paths = {p.get("thumb") or p["src"] for a in result["manifest"]["albums"] for p in a["photos"]}
            result["storage"] = {"photoBytes": sum((self.root / path).stat().st_size for path in paths if (self.root / path).is_file()), "photoFiles": len(paths)}
            return result

    def album(self, state, album_id):
        return next((a for a in state["manifest"]["albums"] if a["id"] == album_id), None)

    def check_album_date(self, album, value):
        value = checked_date(value)
        if album["albumType"] == "annual" and value[:4] != album["year"]:
            raise ValueError(f"这本年度相册属于 {album['year']} 年，请选择同年的日期。")
        return value

    def mutate(self, body):
        with self.lock:
            state = self.read()
            previous = copy.deepcopy(state)
            action = body.get("action")
            if action == "undo":
                snapshots = sorted(self.history.glob("*.json"))
                if not snapshots:
                    raise ValueError("还没有可以撤销的操作。")
                restored = json.loads(snapshots[-1].read_text())
                write_json(self.assets / "albums.json", restored["manifest"])
                write_json(self.assets / "shooting-notes.json", restored["notes"])
                snapshots[-1].unlink()
                return self.state()
            if action in {"createAlbum", "updateAlbum"}:
                city = str(body.get("city", "")).strip()
                province = str(body.get("provinceCode", ""))
                year = str(body.get("year", ""))
                kind = body.get("albumType", "annual")
                if not city or len(city) > 60 or province not in self.province_names:
                    raise ValueError("请填写城市，并选择所属地区。")
                if not year.isdigit() or not 1900 <= int(year) <= 2100 or kind not in {"annual", "special"}:
                    raise ValueError("请选择有效的年份与相册类型。")
                if kind == "annual" and any(a["id"] != body.get("albumId") and a["city"] == city and a["year"] == year and a["albumType"] == kind
                                           for a in state["manifest"]["albums"]):
                    raise ValueError("同年同城的年度相册已存在，请在原相册中添加拍摄日期。")
                title = str(body.get("title", "")).strip()[:120] or f"{year} · {city}"
                album = self.album(state, body.get("albumId")) if action == "updateAlbum" else None
                if action == "updateAlbum" and not album:
                    raise ValueError("相册不存在。")
                if album and kind == "annual" and any(day[:4] != year for day in session_dates(album)):
                    raise ValueError("现有拍摄日期与这个年份不同，请先整理照片日期。")
                if not album:
                    album = {"id": "album-" + secrets.token_hex(8), "photos": [], "sessions": [], "story": "", "coverId": ""}
                    state["manifest"]["albums"].append(album)
                album.update({"title": title, "city": city,
                         "provinceCode": province, "place": city, "year": year, "albumType": kind,
                         "tag": "城市年度相册" if kind == "annual" else "独立旅行相册"})
                created_id = album["id"]
            else:
                album = self.album(state, body.get("albumId"))
                if not album:
                    raise ValueError("这本相册已不存在，请刷新重试。")
                created_id = album["id"]
                if action == "deleteAlbum":
                    state["manifest"]["albums"].remove(album)
                    state["notes"] = {k: v for k, v in state["notes"].items() if not k.startswith(album["id"] + "/")}
                elif action in {"addDate", "editDate", "deleteDate"}:
                    old_date = checked_date(body.get("date"))
                    if action == "addDate":
                        self.check_album_date(album, old_date)
                        if old_date in album["sessions"]:
                            raise ValueError("这个拍摄日期已经存在。")
                        album["sessions"].append(old_date)
                    else:
                        if old_date not in album["sessions"]:
                            raise ValueError("这个拍摄日期已不存在。")
                        old_key = album["id"] + "/" + old_date
                        if action == "deleteDate":
                            album["photos"] = [p for p in album["photos"] if p["shotAt"][:10] != old_date]
                            state["notes"].pop(old_key, None)
                        else:
                            new_date = self.check_album_date(album, body.get("newDate"))
                            new_key = album["id"] + "/" + new_date
                            if old_date == new_date:
                                return self.state()
                            if old_key in state["notes"] and new_key in state["notes"]:
                                raise ValueError("目标日期已有手记，请先合并手记再修改日期。")
                            for photo in album["photos"]:
                                if photo["shotAt"][:10] == old_date:
                                    photo["shotAt"] = new_date + photo["shotAt"][10:]
                            album["sessions"].append(new_date)
                            if old_key in state["notes"]:
                                state["notes"][new_key] = state["notes"].pop(old_key)
                        album["sessions"].remove(old_date)
                elif action == "removePhotos":
                    ids = set(body.get("photoIds", []))
                    if not ids or not ids <= {p["id"] for p in album["photos"]}:
                        raise ValueError("请选择仍在这本相册中的照片。")
                    album["photos"] = [p for p in album["photos"] if p["id"] not in ids]
                elif action == "editPhoto":
                    photo = next((p for p in album["photos"] if p["id"] == body.get("photoId")), None)
                    if not photo:
                        raise ValueError("这张照片已不存在。")
                    new_date = self.check_album_date(album, body.get("date"))
                    photo["shotAt"] = new_date + photo["shotAt"][10:]
                    photo["caption"] = str(body.get("caption", "")).strip()[:300] or photo["filename"]
                elif action == "saveNote":
                    day = checked_date(body.get("date"))
                    if day not in album["sessions"]:
                        raise ValueError("请先添加这个拍摄日期。")
                    note = body.get("note", {})
                    if any(len(str(note.get(field, ""))) > 20000 for field in ["location", "camera", "companions", "story"]):
                        raise ValueError("手记单个字段不能超过 20000 字。")
                    state["notes"][album["id"] + "/" + day] = {field: str(note.get(field, ""))
                                                                  for field in ["location", "camera", "companions", "story"]}
                    state["notes"][album["id"] + "/" + day]["isExample"] = bool(note.get("isExample"))
                else:
                    raise ValueError("不支持的管理操作。")
            self.save(state, previous)
            result = self.state()
            result["selectedAlbumId"] = created_id
            return result

    def import_photo(self, album_id, day, filename, contents, batch_id=None):
        with self.lock:
            state = self.read()
            previous = copy.deepcopy(state)
            album = self.album(state, album_id)
            if not album:
                raise ValueError("相册不存在。")
            day = self.check_album_date(album, day)
            try:
                with Image.open(io.BytesIO(contents)) as raw:
                    raw.load()
                    exif = raw.getexif()
                    details = exif.get_ifd(ExifTags.IFD.Exif)
                    captured = str(details.get(36867) or exif.get(306) or "")
                    clock = captured[11:19] if len(captured) >= 19 else "00:00:00"
                    photo = ImageOps.exif_transpose(raw).convert("RGB")
                    if raw.info.get("icc_profile"):
                        source = ImageCms.ImageCmsProfile(io.BytesIO(raw.info["icc_profile"]))
                        target = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
                        photo = ImageCms.profileToProfile(photo, source, target, outputMode="RGB")
                    photo.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
            except (UnidentifiedImageError, OSError, ValueError) as error:
                raise ValueError("无法读取这张照片，请使用 JPG、PNG 或 WebP 图片。") from error
            photo_id = "photo-" + secrets.token_hex(12)
            path = self.assets / "photos" / "uploads" / (photo_id + "-thumb.webp")
            path.parent.mkdir(parents=True, exist_ok=True)
            photo.save(path, "WEBP", quality=78, method=6)
            relative = path.relative_to(self.root).as_posix()
            record = {"id": photo_id, "src": relative, "thumb": relative, "width": photo.width,
                      "height": photo.height, "ratio": round(photo.width / photo.height, 5),
                      "shotAt": day + "T" + clock, "filename": Path(filename).name,
                      "caption": f"{album['city']} · {day.replace('-', '.')}", "bytes": path.stat().st_size}
            album["photos"].append(record)
            self.save(state, previous, batch_id)
            return self.state()

    def export_files(self):
        with self.lock:
            state = self.read()
            manifest = copy.deepcopy(state["manifest"])
            files = {}
            for album in manifest["albums"]:
                for photo in album["photos"]:
                    relative = photo.get("thumb") or photo["src"]
                    path = (self.root / relative).resolve()
                    if not path.is_relative_to(self.assets / "photos") or not path.is_file():
                        raise ValueError("相册引用的图片不存在，请检查后再导出。")
                    files[relative] = path.read_bytes()
                    photo["src"] = photo["thumb"] = relative
                    photo["bytes"] = len(files[relative])
            html = (self.root / "preview.html").read_text()
            html = html.replace("<title>山野之间 · 旅行相册设计示意</title>", "<title>山野之间 · 旅行相册</title>")
            html = html.replace("设计示意 / 非已发布相册", "个人旅行相册")
            html = html.replace("</head>", "<style>[data-admin],#designOpen,#designFooter,#noteEdit{display:none!important}</style></head>")
            files["index.html"] = html.encode()
            for name in ["album_helpers.js", "album-manager.js", "album-manager.css"]:
                files[name] = (self.root / name).read_bytes()
            files["assets/albums.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode()
            files["assets/shooting-notes.json"] = json.dumps(state["notes"], ensure_ascii=False, indent=2).encode()
            covers = json.loads((self.assets / "city-covers.json").read_text())
            cities = {album["city"] for album in manifest["albums"]}
            covers = {city: artwork for city, artwork in covers.items() if city in cities}
            files["assets/city-covers.json"] = json.dumps(covers, ensure_ascii=False).encode()
            for artwork in covers.values():
                relative = artwork["src"]
                files[relative] = (self.root / relative).read_bytes()
            files["assets/maps/china-provinces.svg"] = (self.assets / "maps" / "china-provinces.svg").read_bytes()
            files["assets/maps/source/LICENSE-China-GeoData.txt"] = (self.assets / "maps" / "source" / "LICENSE-China-GeoData.txt").read_bytes()
            photo_bytes = sum(len(value) for key, value in files.items() if key.startswith("assets/photos/"))
            files["README.txt"] = ("这是可发布的静态相册。将本目录的内容提交到用于 GitHub Pages 的仓库。\n"
                                   "网站仅包含照片的轻量副本；完整原图仍由你在本地保存。\n"
                                   "管理与编辑在本机 manage_server.py 中进行，重新导出后发布更新。\n"
                                   f"照片轻量副本：{photo_bytes:,} bytes；照片文件："
                                   f"{sum(key.startswith('assets/photos/') for key in files)} 个。\n").encode()
            return files

    def export_zip(self):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for name, contents in self.export_files().items():
                archive.writestr(name, contents)
        return output.getvalue()


def handler_for(archive, token):
    class Handler(BaseHTTPRequestHandler):
        def reply(self, status, contents, content_type="application/json; charset=utf-8", filename=None):
            if isinstance(contents, dict):
                contents = json.dumps(contents, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(contents)))
            self.send_header("Cache-Control", "no-store")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(contents)

        def do_GET(self):
            path = unquote(urlsplit(self.path).path)
            try:
                if self.headers.get("Host") not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}:
                    return self.reply(403, {"error": "仅允许通过本机地址访问。"})
                if path == "/api/state":
                    return self.reply(200, {**archive.state(), "token": token})
                if path == "/api/export":
                    if self.headers.get("X-Album-Token") != token:
                        return self.reply(403, {"error": "请从管理页面导出。"})
                    return self.reply(200, archive.export_zip(), "application/zip", "travel-album-site.zip")
                if path in {"/", "/preview.html", "/index.html"}:
                    html = (archive.root / "preview.html").read_text()
                    html = html.replace("</head>", "<script>window.ALBUM_EDITABLE=true;</script></head>")
                    return self.reply(200, html.encode(), "text/html; charset=utf-8")
                file = (archive.root / path.lstrip("/")).resolve()
                if not file.is_relative_to(archive.root) or not file.is_file() or not (
                    path.startswith("/assets/") or path in {"/album_helpers.js", "/album-manager.js", "/album-manager.css", "/设计方案.md"}
                ):
                    return self.reply(404, {"error": "没有这个资源。"})
                self.reply(200, file.read_bytes(), mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            except (ValueError, OSError) as error:
                self.reply(400, {"error": str(error)})

        def do_POST(self):
            origin = self.headers.get("Origin")
            host = self.headers.get("Host")
            if host not in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"} or self.headers.get("X-Album-Token") != token or (origin and origin != "http://" + host):
                return self.reply(403, {"error": "请刷新本机管理页面后重试。"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                path = urlsplit(self.path).path
                limit = 80 * 1024 * 1024 if path == "/api/photos" else 256 * 1024
                if not 0 < length <= limit:
                    raise ValueError("文件过大，请分批导入较小的照片。")
                contents = self.rfile.read(length)
                if path == "/api/photos":
                    query = parse_qs(urlsplit(self.path).query)
                    result = archive.import_photo(query.get("albumId", [""])[0], query.get("date", [""])[0], query.get("filename", ["photo.jpg"])[0], contents, query.get("batchId", [None])[0])
                elif path == "/api/action":
                    result = archive.mutate(json.loads(contents))
                else:
                    return self.reply(404, {"error": "没有这个操作。"})
                self.reply(200, {**result, "token": token})
            except (ValueError, TypeError, KeyError, OSError) as error:
                self.reply(400, {"error": str(error)})
    return Handler


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--export", type=Path, help="Create a static publication ZIP and exit")
    args = parser.parse_args()
    archive = Archive(args.root)
    if args.export:
        args.export.write_bytes(archive.export_zip())
        print(args.export.resolve())
    else:
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(archive, secrets.token_urlsafe(32)))
        print(f"本机相册管理：http://127.0.0.1:{args.port}/preview.html", flush=True)
        server.serve_forever()
