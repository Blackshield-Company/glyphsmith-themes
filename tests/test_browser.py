"""Offline validation of every generated theme and unsigned archive."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from zipfile import ZipFile
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import browser


class BrowserTests(unittest.TestCase):
    def setUp(self):
        self.palettes = browser.load_palettes()

    def fixture(self, root, palettes=None):
        (root / "browser").mkdir()
        (root / "themes.json").write_bytes((browser.ROOT / "themes.json").read_bytes())
        (root / "browser/palettes.json").write_text(json.dumps(palettes or self.palettes))

    def test_collection_coverage_and_generated_files(self):
        themes = browser.generate(check=True)
        self.assertEqual(len(themes), 2 * len(self.palettes))
        self.assertEqual({n for n, _, _, _ in themes}, set(self.palettes))

    def test_manifest_roles_and_permissions(self):
        ids = set()
        for name, p in self.palettes.items():
            for target in browser.BROWSERS:
                with self.subTest(theme=name, browser=target):
                    files = browser.theme_files(name, p, target)
                    m = json.loads(files["manifest.json"])
                    self.assertNotIn("permissions", m)
                    self.assertNotIn("background", m)
                    self.assertEqual(m["name"], p["title"])
                    self.assertEqual(m["version"], p["version"])
                    self.assertEqual(m["manifest_version"], 2 if target == "firefox" else 3)
                    c = m["theme"]["colors"]
                    convert = (lambda x: x) if target == "firefox" else browser.rgb
                    self.assertEqual(c["frame"], convert(p["darker_background"]))
                    self.assertEqual(c["frame_inactive"], c["frame"])
                    self.assertEqual(c["toolbar"], convert(p["accent"]))
                    self.assertEqual(c["toolbar_text"], c["frame"])
                    self.assertEqual(c["tab_text"], c["frame"])
                    if target == "firefox":
                        gecko = m["browser_specific_settings"]["gecko"]
                        self.assertNotIn(gecko["id"], ids)
                        ids.add(gecko["id"])
                        self.assertEqual(gecko["data_collection_permissions"], {"required": ["none"]})
                    else:
                        for value in c.values():
                            self.assertEqual(len(value), 3)
                            self.assertTrue(all(type(x) is int and 0 <= x <= 255 for x in value))
                    for key, path in m["theme"]["images"].items():
                        self.assertIn(path, files)
                        self.assertFalse(Path(path).is_absolute())
                        self.assertNotIn("..", Path(path).parts)
                        color = p["background"] if key == "theme_ntp_background" else p["darker_background"]
                        self.assert_png(files[path], color)

    def assert_png(self, data, color):
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        offset, compressed = 8, b""
        while offset < len(data):
            size = struct.unpack(">I", data[offset:offset + 4])[0]
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + size]
            crc = struct.unpack(">I", data[offset + 8 + size:offset + 12 + size])[0]
            self.assertEqual(crc, zlib.crc32(kind + payload) & 0xffffffff)
            if kind == b"IHDR":
                width, height, depth, mode, _, _, _ = struct.unpack(">IIBBBBB", payload)
                self.assertEqual((depth, mode), (8, 2))
            elif kind == b"IDAT":
                compressed += payload
            offset += size + 12
        self.assertEqual(zlib.decompress(compressed),
                         (b"\0" + bytes(browser.rgb(color)) * width) * height)

    def test_text_and_icon_contrast(self):
        for name, p in self.palettes.items():
            for bg, fg in (("accent", "darker_background"),
                           ("darker_background", "foreground"),
                           ("dark_background", "bright_foreground"),
                           ("background", "bright_foreground"), ("background", "cyan")):
                with self.subTest(theme=name, pair=(bg, fg)):
                    self.assertGreaterEqual(browser.contrast(p[bg], p[fg]), 4.5)

    def test_rgb_validation(self):
        self.assertEqual(browser.rgb("#ff0080"), [255, 0, 128])
        for bad in (None, [1, 2, 3], "black", "#fff", "#12345g", "#1234567"):
            with self.subTest(color=bad), self.assertRaises(ValueError):
                browser.rgb(bad)

    def test_unknown_browser_rejected(self):
        with self.assertRaises(ValueError):
            browser.theme_files("neon-horizon", self.palettes["neon-horizon"], "other")

    def test_missing_palette_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            palettes = copy.deepcopy(self.palettes)
            palettes.pop("neon-horizon")
            self.fixture(root, palettes)
            with self.assertRaisesRegex(ValueError, "cover exactly"):
                browser.load_palettes(root)

    def test_bad_palette_rejected(self):
        cases = (("accent", "#000000", "match index"),
                 ("source", "https://example.org/colors.toml", "pin upstream"),
                 ("version", "v1", "invalid browser version"),
                 ("darker_background", "#000000", "chromatic"),
                 ("darker_background", "#123456", "darkest"),
                 ("foreground", "#111112", "contrast"))
        for key, value, error in cases:
            with self.subTest(key=key), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                palettes = copy.deepcopy(self.palettes)
                palettes["neon-horizon"][key] = value
                self.fixture(root, palettes)
                with self.assertRaisesRegex(ValueError, error):
                    browser.load_palettes(root)

    def test_unsafe_name_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            palettes = copy.deepcopy(self.palettes)
            palettes["../escape"] = palettes.pop("neon-horizon")
            self.fixture(root, palettes)
            index = json.loads((root / "themes.json").read_text())
            index["themes"][0]["name"] = "../escape"
            (root / "themes.json").write_text(json.dumps(index))
            with self.assertRaisesRegex(ValueError, "unsafe theme name"):
                browser.load_palettes(root)

    def test_missing_modified_and_extra_files_rejected(self):
        for operation in ("missing", "modified", "extra"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.fixture(root)
                browser.generate(root)
                target = root / "browser/neon-horizon/firefox/manifest.json"
                if operation == "missing":
                    target.unlink()
                elif operation == "modified":
                    target.write_text("{}")
                else:
                    target.with_name("unexpected.key").write_text("not for packaging")
                with self.assertRaisesRegex(ValueError, "generated files differ"):
                    browser.build(root)
                self.assertFalse((root / "dist").exists())

    def test_reproducible_unsigned_archives(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            browser.generate(root)
            first = browser.build(root, root / "first")
            second = browser.build(root, root / "second")
            self.assertEqual(len(first), len(self.palettes) * 2)
            expected = {f"{n}-{b}-{p['version']}.zip": browser.theme_files(n, p, b)
                        for n, p in self.palettes.items() for b in browser.BROWSERS}
            self.assertEqual({p.name for p in first}, set(expected))
            for a, b in zip(first, second):
                self.assertEqual(a.read_bytes(), b.read_bytes())
                with ZipFile(a) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(set(archive.namelist()), set(expected[a.name]))
                    self.assertIn("manifest.json", archive.namelist())
                    self.assertFalse(any(n.lower().startswith("meta-inf/") for n in archive.namelist()))
                    for entry in archive.infolist():
                        self.assertEqual(entry.date_time, (1980, 1, 1, 0, 0, 0))
                        self.assertEqual(archive.read(entry), expected[a.name][entry.filename])


if __name__ == "__main__":
    unittest.main()
