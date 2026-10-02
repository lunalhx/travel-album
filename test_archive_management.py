"""Exercise edits on an isolated copy; never modify the user's actual albums."""

import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from PIL import Image
from manage_server import Archive
from import_photos import import_photos


class ArchiveManagementTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="album-management-")
        self.root = Path(self.temporary.name)
        project = Path(__file__).parent
        shutil.copytree(project / "assets", self.root / "assets")
        for filename in ["preview.html", "album-manager.js", "album-manager.css", "album_helpers.js"]:
            shutil.copyfile(project / filename, self.root / filename)
        self.archive = Archive(self.root)

    def tearDown(self):
        self.temporary.cleanup()

    def create_album(self):
        state = self.archive.mutate({"action": "createAlbum", "city": "测试城市", "provinceCode": "620000",
                                     "year": "2026", "albumType": "annual", "title": "测试相册"})
        return state["selectedAlbumId"]

    def test_album_date_photo_notes_and_undo(self):
        album_id = self.create_album()
        self.archive.mutate({"action": "addDate", "albumId": album_id, "date": "2026-04-01"})
        self.archive.mutate({"action": "saveNote", "albumId": album_id, "date": "2026-04-01",
                             "note": {"location": "公园", "story": "保留这段文字", "isExample": False}})
        original = self.root / "original.jpg"
        image = Image.new("RGB", (1800, 900), "#718060")
        exif = image.getexif(); exif[274] = 6
        image.save(original, exif=exif)
        original_hash = hashlib.sha256(original.read_bytes()).hexdigest()
        state = self.archive.import_photo(album_id, "2026-04-01", original.name, original.read_bytes())
        album = self.archive.album(state, album_id); photo = album["photos"][0]
        self.assertEqual((photo["width"], photo["height"]), (640, 1280))
        self.assertEqual(photo["src"], photo["thumb"])
        self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), original_hash)
        with Image.open(self.root / photo["src"]) as thumbnail:
            self.assertFalse(thumbnail.getexif())
        moved = self.archive.mutate({"action": "editDate", "albumId": album_id, "date": "2026-04-01", "newDate": "2026-04-03"})
        self.assertEqual(self.archive.album(moved, album_id)["photos"][0]["shotAt"][:10], "2026-04-03")
        self.assertEqual(moved["notes"][album_id + "/2026-04-03"]["story"], "保留这段文字")
        self.assertNotIn(album_id + "/2026-04-01", moved["notes"])
        edited = self.archive.mutate({"action": "editPhoto", "albumId": album_id, "photoId": photo["id"], "date": "2026-04-03", "caption": "新的说明"})
        self.assertEqual(self.archive.album(edited, album_id)["photos"][0]["caption"], "新的说明")
        removed = self.archive.mutate({"action": "removePhotos", "albumId": album_id, "photoIds": [photo["id"]]})
        self.assertEqual(self.archive.album(removed, album_id)["photos"], [])
        restored = self.archive.mutate({"action": "undo"})
        self.assertEqual(len(self.archive.album(restored, album_id)["photos"]), 1)
        without_date = self.archive.mutate({"action": "deleteDate", "albumId": album_id, "date": "2026-04-03"})
        self.assertEqual(self.archive.album(without_date, album_id)["photos"], [])
        self.assertNotIn(album_id + "/2026-04-03", without_date["notes"])
        removed_album = self.archive.mutate({"action": "deleteAlbum", "albumId": album_id})
        self.assertIsNone(self.archive.album(removed_album, album_id))
        self.assertTrue(original.exists())
        reloaded = Archive(self.root).read()
        self.assertIsNone(self.archive.album(reloaded, album_id))

    def test_export_has_only_referenced_thumbnails_and_no_editor_data(self):
        state = self.archive.read()
        expected = {p["thumb"] for a in state["manifest"]["albums"] for p in a["photos"]}
        package = zipfile.ZipFile(io.BytesIO(self.archive.export_zip()))
        names = set(package.namelist())
        self.assertEqual({name for name in names if name.startswith("assets/photos/")}, expected)
        self.assertFalse(any(".local" in name or name.endswith(".py") or name.endswith(".jpg") for name in names))
        manifest = json.loads(package.read("assets/albums.json"))
        for album in manifest["albums"]:
            for photo in album["photos"]:
                self.assertEqual(photo["src"], photo["thumb"])
                self.assertIn(photo["src"], names)
        self.assertIn("index.html", names)
        self.assertNotIn(b"ALBUM_EDITABLE=true", package.read("index.html"))
        self.assertIn("assets/maps/source/LICENSE-China-GeoData.txt", names)

    def test_invalid_date_and_conflicting_notes_are_non_destructive(self):
        album_id = self.create_album()
        self.archive.mutate({"action": "addDate", "albumId": album_id, "date": "2026-04-01"})
        before = copy.deepcopy(self.archive.read())
        with self.assertRaises(ValueError):
            self.archive.mutate({"action": "editDate", "albumId": album_id, "date": "2026-04-01", "newDate": "2027-04-01"})
        self.assertEqual(self.archive.read(), before)
        for day in ["2026-04-01", "2026-04-02"]:
            if day == "2026-04-02":
                self.archive.mutate({"action": "addDate", "albumId": album_id, "date": day})
            self.archive.mutate({"action": "saveNote", "albumId": album_id, "date": day, "note": {"story": day}})
        before = self.archive.read()
        with self.assertRaises(ValueError):
            self.archive.mutate({"action": "editDate", "albumId": album_id, "date": "2026-04-01", "newDate": "2026-04-02"})
        self.assertEqual(self.archive.read(), before)

    def test_deleting_last_album_remains_a_valid_archive(self):
        for album in self.archive.read()["manifest"]["albums"]:
            self.archive.mutate({"action": "deleteAlbum", "albumId": album["id"]})
        state = self.archive.state()
        self.assertEqual(state["manifest"]["albums"], [])
        self.assertEqual(state["storage"]["photoBytes"], 0)
        self.assertTrue(self.archive.export_zip())

    def test_batch_import_undo_removes_the_entire_batch(self):
        album_id = self.create_album()
        contents = io.BytesIO()
        Image.new("RGB", (500, 700), "#b5ad93").save(contents, "PNG")
        for index in range(3):
            self.archive.import_photo(album_id, "2026-05-01", f"test-{index}.png", contents.getvalue(), "test-batch")
        self.assertEqual(len(self.archive.album(self.archive.read(), album_id)["photos"]), 3)
        undone = self.archive.mutate({"action": "undo"})
        self.assertEqual(self.archive.album(undone, album_id)["photos"], [])

    def test_initial_folder_import_generates_one_lightweight_file(self):
        source = self.root / "source" / "重庆"
        source.mkdir(parents=True)
        original = source / "20260401-test.jpg"
        image = Image.new("RGB", (2000, 1600), "#747f67")
        exif = image.getexif(); exif[306] = "2026:04:01 13:20:00"
        image.save(original, exif=exif)
        before = original.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()):
            import_photos(source.parent, self.root / "assets")
        photo = json.loads((self.root / "assets" / "albums.json").read_text())["albums"][0]["photos"][0]
        self.assertEqual(photo["src"], photo["thumb"])
        self.assertEqual(max(photo["width"], photo["height"]), 1280)
        self.assertFalse((self.root / "assets" / "photos" / "chongqing" / "chongqing-20260401-test.webp").exists())
        self.assertEqual(original.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
