"""Commit the current album and source files, then trigger Pages with git push."""

import argparse
import json
from pathlib import Path
import subprocess

from build_site import build_site


PROJECT = Path(__file__).parent.resolve()
SOURCE_FILES = [
    ".gitignore", ".github/workflows/deploy-pages.yml", "README.md", "requirements.txt",
    "build_site.py", "publish.py", "publish.command", "start_manager.command",
    "preview.html", "album_helpers.js", "album-manager.js", "album-manager.css",
    "manage_server.py", "album_model.py", "import_photos.py", "test_archive_management.py",
    "build_china_map.py", "fetch_map_data.py", "prepare_city_covers.py", "相册管理说明.md",
    "assets/albums.json", "assets/shooting-notes.json", "assets/city-covers.json",
    "assets/special-albums.json", "assets/special-albums-guide.md", "assets/covers/README.md",
    "assets/maps/README.md", "assets/maps/china-provinces.svg", "assets/maps/city-points.json",
    "assets/maps/source/china-provinces.geojson", "assets/maps/source/china-cities.csv",
    "assets/maps/source/sources.json", "assets/maps/source/LICENSE-China-GeoData.txt",
]


def publication_paths():
    paths = set(SOURCE_FILES)
    manifest = json.loads((PROJECT / "assets/albums.json").read_text())
    for album in manifest["albums"]:
        for photo in album["photos"]:
            paths.add(photo.get("thumb") or photo["src"])
    covers = json.loads((PROJECT / "assets/city-covers.json").read_text())
    paths.update(artwork["src"] for artwork in covers.values())
    for name in paths:
        path = (PROJECT / name).resolve()
        if not path.is_relative_to(PROJECT) or not path.is_file():
            raise ValueError("缺少或无效的发布文件：" + name)
    return sorted(paths)


def git(*args, **kwargs):
    return subprocess.run(["git", "-C", str(PROJECT), *args], check=True, **kwargs)


def stage():
    build_site(PROJECT, PROJECT / "dist")
    paths = publication_paths()
    tracked = git("ls-files", "-z", capture_output=True).stdout.decode().split("\0")
    removed = [p for p in tracked if p.startswith("assets/photos/") and p not in paths]
    if removed:
        git("rm", "--cached", "--", *removed)
    git("add", "--pathspec-from-file=-", "--pathspec-file-nul", input=("\0".join(paths) + "\0").encode())
    return paths


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()
    stage()
    if not args.stage_only:
        changed = subprocess.run(["git", "-C", str(PROJECT), "diff", "--cached", "--quiet"], check=False)
        if changed.returncode == 1:
            git("commit", "-m", "Update photo album")
        elif changed.returncode != 0:
            raise RuntimeError("无法检查待发布的改动。")
        git("push", "origin", "main")
        print("已提交到 GitHub，Actions 正在自动部署。")
