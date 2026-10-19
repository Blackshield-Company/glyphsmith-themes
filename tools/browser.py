#!/usr/bin/env python3
"""Generate, check and reproducibly package unsigned browser themes (stdlib only)."""
import argparse
import binascii
import json
from pathlib import Path
import re
import struct
import sys
import zlib
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
BROWSERS = ("firefox", "chromium")
PALETTE_COLORS = (
    "darker_background", "dark_background", "background", "foreground",
    "bright_foreground", "accent", "cyan",
)


def rgb(color):
    if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
        raise ValueError(f"invalid RGB color: {color!r}")
    return [int(color[i:i + 2], 16) for i in (1, 3, 5)]


def luminance(color):
    channels = [c / 255 for c in rgb(color)]
    return sum(w * (c / 12.92 if c <= 0.04045 else ((c + .055) / 1.055) ** 2.4)
               for w, c in zip((.2126, .7152, .0722), channels))


def contrast(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + .05) / (lo + .05)


def load_palettes(root=ROOT):
    palettes = json.loads((root / "browser/palettes.json").read_text())
    index = json.loads((root / "themes.json").read_text())["themes"]
    if set(palettes) != {t["name"] for t in index}:
        raise ValueError("browser palettes must cover exactly every indexed desktop theme")
    for theme in index:
        name = theme["name"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            raise ValueError(f"unsafe theme name: {name}")
        p = palettes[name]
        for key in PALETTE_COLORS:
            rgb(p[key])
        if p["accent"] != theme["accent"] or p["title"] != theme["title"]:
            raise ValueError(f"{name}: palette must match index title/accent")
        if not re.fullmatch(re.escape(theme["repo"]) + r"/blob/[0-9a-f]{40}/colors\.toml", p["source"]):
            raise ValueError(f"{name}: palette source must pin upstream colors.toml")
        if not re.fullmatch(r"\d+\.\d+\.\d+", p["version"]):
            raise ValueError(f"{name}: invalid browser version")
        frame = p["darker_background"]
        if len(set(rgb(frame))) == 1:
            raise ValueError(f"{name}: frame must be chromatic, not black/grey")
        if luminance(frame) != min(luminance(p[k]) for k in PALETTE_COLORS):
            raise ValueError(f"{name}: frame must use darkest palette tone")
        for bg, fg in ((frame, p["foreground"]), (p["accent"], frame),
                       (p["dark_background"], p["bright_foreground"]),
                       (p["background"], p["cyan"])):
            if contrast(bg, fg) < 4.5:
                raise ValueError(f"{name}: insufficient text contrast: {bg}/{fg}")
    return palettes


def png(color, width=256, height=128):
    """Solid chromatic frames: images cannot mask the requested frame color."""
    def chunk(kind, data):
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", binascii.crc32(kind + data) & 0xffffffff))
    raw = (b"\0" + bytes(rgb(color)) * width) * height
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def theme_files(name, p, browser):
    frame, field, base = (p[k] for k in ("darker_background", "dark_background", "background"))
    accent, text, bright, cyan = (p[k] for k in ("accent", "foreground", "bright_foreground", "cyan"))
    manifest = {
        "manifest_version": 2 if browser == "firefox" else 3,
        "name": p["title"], "version": p["version"],
        "description": f"{p['title']} browser theme by synthalorian: chromatic frame and accent toolbar.",
    }
    if browser == "firefox":
        manifest["browser_specific_settings"] = {"gecko": {
            "id": f"{name}@themes.glyphsmith.synthalorian",
            "strict_min_version": "140.0",
            "data_collection_permissions": {"required": ["none"]},
        }}
        colors = {
            "frame": frame, "frame_inactive": frame,
            "tab_background_text": text, "tab_text": frame,
            "tab_selected": accent, "tab_line": cyan, "tab_loading": cyan,
            "toolbar": accent, "toolbar_text": frame,
            "toolbar_field": field, "toolbar_field_text": bright,
            "toolbar_field_border": frame, "toolbar_field_focus": field,
            "toolbar_field_text_focus": bright, "toolbar_field_border_focus": cyan,
            "toolbar_field_highlight": accent, "toolbar_field_highlight_text": frame,
            "toolbar_top_separator": accent, "toolbar_bottom_separator": accent,
            "toolbar_vertical_separator": frame, "icons": frame, "icons_attention": field,
            "bookmark_text": frame, "popup": field, "popup_text": bright,
            "popup_border": accent, "popup_highlight": accent, "popup_highlight_text": frame,
            "sidebar": base, "sidebar_text": bright, "sidebar_border": accent,
            "sidebar_highlight": accent, "sidebar_highlight_text": frame,
            "ntp_background": base, "ntp_text": bright,
            "button_background_hover": cyan, "button_background_active": text,
            "tab_background_separator": accent,
        }
        images = {"theme_frame": "images/theme_frame.png"}
        manifest["theme"] = {"images": images, "colors": colors}
    elif browser == "chromium":
        colors = {
            "frame": frame, "frame_inactive": frame,
            "frame_incognito": frame, "frame_incognito_inactive": frame,
            "toolbar": accent, "toolbar_text": frame, "toolbar_button_icon": frame,
            "tab_text": frame, "background_tab": frame, "background_tab_inactive": frame,
            "background_tab_incognito": frame, "background_tab_incognito_inactive": frame,
            "tab_background_text": text, "tab_background_text_inactive": text,
            "tab_background_text_incognito": text, "tab_background_text_incognito_inactive": text,
            "bookmark_text": frame, "button_background": accent,
            "omnibox_background": field, "omnibox_text": bright,
            "ntp_background": base, "ntp_text": bright, "ntp_link": cyan, "ntp_header": text,
        }
        images = {"theme_frame": "images/theme_frame.png",
                  "theme_frame_inactive": "images/theme_frame_inactive.png",
                  "theme_ntp_background": "images/theme_ntp_background.png"}
        manifest["theme"] = {
            "colors": {k: rgb(v) for k, v in colors.items()}, "images": images,
            "properties": {"ntp_background_alignment": "center", "ntp_background_repeat": "repeat"},
        }
    else:
        raise ValueError(f"unknown browser: {browser}")
    files = {"manifest.json": (json.dumps(manifest, indent=2) + "\n").encode()}
    for key, path in images.items():
        files[path] = png(base if key == "theme_ntp_background" else frame)
    return files


def generate(root=ROOT, check=False):
    result = []
    for name, palette in sorted(load_palettes(root).items()):
        for browser in BROWSERS:
            directory = root / "browser" / name / browser
            files = theme_files(name, palette, browser)
            if check:
                actual = {str(p.relative_to(directory)): p.read_bytes()
                          for p in directory.rglob("*") if p.is_file()}
                if actual != files:
                    raise ValueError(f"{name}/{browser}: generated files differ; run tools/browser.py generate")
            else:
                for path, content in files.items():
                    target = directory / path
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
            result.append((name, palette["version"], browser, files))
    return result


def build(root=ROOT, output=None):
    themes = generate(root, check=True)
    output = output or root / "dist/browser"
    output.mkdir(parents=True, exist_ok=True)
    archives = []
    for name, version, browser, files in themes:
        path = output / f"{name}-{browser}-{version}.zip"
        with ZipFile(path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
            for filename, content in sorted(files.items()):
                info = ZipInfo(filename, date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, content, compresslevel=9)
        archives.append(path)
    return archives


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("generate", "check", "build"))
    parser.add_argument("--output", type=Path, help="build output directory (default: dist/browser)")
    args = parser.parse_args()
    try:
        if args.command == "build":
            for path in build(output=args.output):
                print(path)
        else:
            themes = generate(check=args.command == "check")
            print(f"{args.command}: {len(themes)} browser themes OK")
    except (ValueError, KeyError, OSError) as error:
        sys.exit(str(error))


if __name__ == "__main__":
    main()
