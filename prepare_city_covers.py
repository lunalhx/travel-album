"""Copy user-provided city artwork without altering it; write the cover registry."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--lanzhou", type=Path, required=True)
parser.add_argument("--chongqing", type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).parent
output = root / "assets/covers"
output.mkdir(parents=True, exist_ok=True)
registry = {}
for city, slug, english, source in [
    ("兰州", "lanzhou", "LANZHOU", args.lanzhou),
    ("重庆", "chongqing", "CHONGQING", args.chongqing),
]:
    destination = output / f"{slug}.png"
    shutil.copyfile(source, destination)
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    assert source_hash == hashlib.sha256(destination.read_bytes()).hexdigest()
    registry[city] = {
        "src": destination.relative_to(root).as_posix(),
        "english": english,
        "width": 1536,
        "height": 1024,
        "alt": f"{city}城市线稿",
    }
    print(city, destination.stat().st_size, "bytes; identical to original PNG")
(root / "assets/city-covers.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n")
(output / "README.md").write_text("""# 城市线稿封面

使用用户提供的 AI 生成 PNG，源文件未改写，项目内副本与原文件 SHA-256 相同。
兰州：江畔古桥与山城塔影.png；重庆：重庆山城江畔线描全景.png。

封面为 3:2。网页完整展示图像，城市名、年份和英文名通过 SVG 文字层排版，不修改图片像素。
同城不同年份复用图像。assets/city-covers.json 提供城市与素材的映射，重新导入相册不会覆盖它。
插画不计入相册照片数。相册中的真实照片仍保留原来的日期分段和全屏浏览。
""")
