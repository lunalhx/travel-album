"""Build yearly city albums and optional special collections from photo metadata."""

from collections import defaultdict


CITY_INFO = {
    "兰州": {"slug": "lanzhou", "place": "甘肃 · 兰州", "provinceCode": "620000"},
    "重庆": {"slug": "chongqing", "place": "重庆", "provinceCode": "500000"},
}


def date_fields(photos):
    dates = sorted({photo["shotAt"][:10] for photo in photos})
    start, end = dates[0], dates[-1]
    date = start.replace("-", ".")
    if start != end:
        date += " — " + end.replace("-", ".")
    return {"dateStart": start, "dateEnd": end, "date": date, "captureDays": len(dates)}


def annual_albums(city_photos, previous_albums=()):
    previous = {(a.get("year"), a.get("city")): a for a in previous_albums if a.get("albumType", "annual") == "annual"}
    result = []
    for city, records in city_photos.items():
        info = CITY_INFO[city]
        years = defaultdict(list)
        for photo in records:
            years[photo["shotAt"][:4]].append(photo)
        for year, photos in years.items():
            photos = sorted(photos, key=lambda photo: (photo["shotAt"], photo["id"]))
            old = previous.get((year, city), {})
            cover_id = old.get("coverId")
            if cover_id not in {photo["id"] for photo in photos}:
                preferred = "p1023579" if city == "兰州" else "p1023357"
                cover_id = next((p["id"] for p in photos if preferred in p["id"]), photos[0]["id"])
            dates = date_fields(photos)
            result.append({
                "id": f"{info['slug']}-{year}",
                "title": f"{year} · {city}",
                "albumType": "annual",
                "place": info["place"],
                "provinceCode": info["provinceCode"],
                "city": city,
                "year": year,
                **dates,
                "coverId": cover_id,
                "tag": "城市年度相册",
                "note": f"{len(photos)} 张照片 · {dates['captureDays']} 天拍摄记录",
                "story": old.get("story", ""),
                "locationSource": "folder",
                "photos": photos,
            })
    return sorted(result, key=lambda album: (album["dateEnd"], album["id"]), reverse=True)


def special_albums(definitions, city_photos):
    """A special album references existing photo files; it does not duplicate them."""
    result = []
    for definition in definitions:
        city = definition["city"]
        info = CITY_INFO[city]
        available = {photo["id"]: photo for photo in city_photos[city]}
        ids = list(dict.fromkeys(definition["photoIds"]))
        if not ids:
            raise ValueError(f"Empty special album: {definition['id']}")
        photos = sorted((available[photo_id] for photo_id in ids), key=lambda photo: photo["shotAt"])
        dates = date_fields(photos)
        cover = definition.get("coverId", photos[0]["id"])
        if cover not in ids:
            raise ValueError(f"Special album cover not in photoIds: {definition['id']}")
        result.append({
            "id": definition["id"], "title": definition["title"],
            "albumType": "special", "city": city, "place": info["place"],
            "provinceCode": info["provinceCode"], "year": dates["dateStart"][:4],
            **dates, "coverId": cover, "tag": "独立旅行相册",
            "note": f"{len(photos)} 张照片 · {dates['captureDays']} 天拍摄记录",
            "story": definition.get("story", ""), "locationSource": "folder",
            "photos": photos,
        })
    return result
