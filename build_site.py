"""Build the read-only website, using only referenced lightweight photos."""

import argparse
import json
from pathlib import Path
import shutil

from manage_server import Archive


def build_site(project, destination):
    project, destination = Path(project).resolve(), Path(destination).resolve()
    if destination == project or project.is_relative_to(destination) or destination.is_relative_to(project / "assets"):
        raise ValueError("构建目录不能覆盖项目或照片目录。")
    files = Archive(project).export_files()
    if destination.exists():
        if any(destination.iterdir()) and not (destination / ".nojekyll").exists():
            raise ValueError("目标目录已有其他内容，请选择新的构建目录。")
        shutil.rmtree(destination)
    destination.mkdir(parents=True)
    for name, contents in files.items():
        path = (destination / name).resolve()
        if not path.is_relative_to(destination):
            raise ValueError("发布资料包含无效路径。")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents)
    (destination / ".nojekyll").touch()
    manifest = json.loads(files["assets/albums.json"])
    for album in manifest["albums"]:
        for photo in album["photos"]:
            if photo["src"] != photo["thumb"] or not (destination / photo["src"]).is_file():
                raise ValueError("发布照片必须指向存在的轻量副本。")
    print(json.dumps({"albums": len(manifest["albums"]),
                      "photos": sum(len(a["photos"]) for a in manifest["albums"]),
                      "files": len(files) + 1, "bytes": sum(len(data) for data in files.values())}, ensure_ascii=False))
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "dist")
    args = parser.parse_args()
    build_site(Path(__file__).parent, args.output)
