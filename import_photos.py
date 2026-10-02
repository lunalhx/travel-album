"""Generate local website copies of photos without modifying source files."""

import argparse
import io
import json
from datetime import datetime
from pathlib import Path

from PIL import ExifTags, Image, ImageCms, ImageDraw, ImageOps
from album_model import CITY_INFO, annual_albums, special_albums


def import_photos(source, output):
    previous_path = output / "albums.json"
    previous = json.loads(previous_path.read_text())["albums"] if previous_path.exists() else []
    city_photos = {}
    source_bytes = 0
    gps_count = 0
    all_thumbs = []
    target_profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
    output.mkdir(parents=True, exist_ok=True)

    for city, info in CITY_INFO.items():
        slug = info["slug"]
        paths = sorted((source / city).rglob("*.jpg"))
        if not paths:
            continue
        records = []
        for path in paths:
            source_bytes += path.stat().st_size
            with Image.open(path) as raw:
                exif = raw.getexif()
                details = exif.get_ifd(ExifTags.IFD.Exif)
                has_gps = bool(exif.get_ifd(ExifTags.IFD.GPSInfo))
                gps_count += has_gps
                taken = details.get(36867) or exif.get(306)
                if not taken:
                    raise ValueError(f"Missing capture date: {path.name}")
                shot_at = datetime.strptime(taken, "%Y:%m:%d %H:%M:%S")
                photo = ImageOps.exif_transpose(raw).convert("RGB")
                original_profile = raw.info.get("icc_profile")
                if original_profile:
                    source_profile = ImageCms.ImageCmsProfile(io.BytesIO(original_profile))
                    photo = ImageCms.profileToProfile(
                        photo, source_profile, target_profile, outputMode="RGB"
                    )
                else:
                    print(f"No ICC profile, assuming sRGB: {path.name}")

                image_id = f"{slug}-{path.stem.lower()}"
                image_dir = output / "photos" / slug
                image_dir.mkdir(parents=True, exist_ok=True)
                thumb = photo.copy()
                thumb.thumbnail((1280, 1280), Image.Resampling.LANCZOS)
                thumb_path = image_dir / f"{image_id}-thumb.webp"
                thumb.save(thumb_path, "WEBP", quality=78, method=6)
                records.append({
                    "id": image_id,
                    "src": thumb_path.relative_to(output.parent).as_posix(),
                    "thumb": thumb_path.relative_to(output.parent).as_posix(),
                    "width": thumb.width,
                    "height": thumb.height,
                    "ratio": round(thumb.width / thumb.height, 5),
                    "shotAt": shot_at.isoformat(),
                    "filename": path.name,
                    "caption": f"{city} · {shot_at:%m月%d日 %H:%M}",
                    "bytes": thumb_path.stat().st_size,
                })
                all_thumbs.append((thumb.copy(), f"{slug} / {path.stem}"))

        city_photos[city] = records

    albums = annual_albums(city_photos, previous)
    definition_path = output / "special-albums.json"
    definitions = json.loads(definition_path.read_text()) if definition_path.exists() else []
    albums.extend(special_albums(definitions, city_photos))
    albums.sort(key=lambda item: (item["dateEnd"], item["id"]), reverse=True)
    manifest = {"version": 2, "albums": albums}
    (output / "albums.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    published_paths = {photo["thumb"] for album in albums for photo in album["photos"]}
    published_bytes = sum((output.parent / path).stat().st_size for path in published_paths)
    report = {
        "count": len(all_thumbs),
        "sourceBytes": source_bytes,
        "displayBytes": published_bytes,
        "photosWithGps": gps_count,
        "colorSpace": "sRGB",
        "sourceFilesModified": False,
    }
    (output.parent / "import_report.json").write_text(json.dumps(report, indent=2) + "\n")

    cols, cell_w, cell_h = 4, 310, 245
    rows = (len(all_thumbs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w, rows * cell_h), "#171a19")
    drawing = ImageDraw.Draw(sheet)
    for index, (thumb, label) in enumerate(all_thumbs):
        x, y = index % cols * cell_w, index // cols * cell_h
        image = ImageOps.contain(thumb, (cell_w - 16, cell_h - 38))
        sheet.paste(image, (x + (cell_w - image.width) // 2, y + 6))
        drawing.text((x + 8, y + cell_h - 22), label, fill="#f2efe8")
    sheet.save(output.parent / "contact-sheet.jpg", quality=88)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "assets")
    args = parser.parse_args()
    import_photos(args.source, args.output)
