#!/usr/bin/env python3
"""Maintain the Glyphsmith collection: themes.json, preview thumbnails and the README gallery.

  index.py upsert --collection DIR --theme-dir THEME --name N --title T --version V --repo URL
                  [--sha256 S] [--released ISO8601] [--variant NAME,KIND,URL ...]
  index.py render --collection DIR          (re-render the README gallery from themes.json)
  index.py check  --collection DIR          (validate themes.json without writing anything)

Optional per-theme `variants`: [{"name": ..., "kind": one of VARIANT_KINDS, "url": "https://..."}].
The gallery is sorted newest first by `released` (the release's publish time, ISO 8601 UTC).
Upsert keeps an entry's existing variants unless --variant is given.
"""
import argparse, json, re, sys, time, tomllib
from pathlib import Path

START, END = "<!-- gallery:start -->", "<!-- gallery:end -->"
VARIANT_KINDS = ("light", "dark", "ghostty", "kitty", "alacritty", "foot", "vscode", "neovim", "wallpapers", "other")

def validate(data: dict) -> list:
    errs = []
    for t in data.get("themes", []):
        n = t.get("name", "?")
        for k in ("name", "title", "description", "repo", "version", "released", "preview"):
            if not t.get(k): errs.append(f"{n}: missing {k}")
        if not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+", t.get("repo", "")): errs.append(f"{n}: bad repo URL")
        if t.get("released") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", t["released"]): errs.append(f"{n}: released must be ISO 8601 UTC")
        for v in t.get("variants", []) or []:
            if set(v) != {"name", "kind", "url"}: errs.append(f"{n}: variant needs exactly name, kind, url: {v}")
            elif v["kind"] not in VARIANT_KINDS: errs.append(f"{n}: variant kind {v['kind']!r} not in {VARIANT_KINDS}")
            elif not re.fullmatch(r"https://[^\s()<>]+", v["url"]): errs.append(f"{n}: variant url must be https: {v['url']}")
    return errs

def tagline(readme: Path) -> str:
    for line in readme.read_text().splitlines()[1:]:
        if line.strip() and not line.startswith(("#", "!", "*", "|", "<")):
            return line.strip()
    return ""

def load(col: Path) -> dict:
    p = col / "themes.json"
    return json.loads(p.read_text()) if p.exists() else {"schema": 1, "themes": []}

def save(col: Path, data: dict) -> None:
    data["themes"].sort(key=lambda t: t["name"])
    (col / "themes.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")

def thumbnail(src: Path, dst: Path) -> None:
    from PIL import Image
    im = Image.open(src).convert("RGB")
    im.thumbnail((640, 360), Image.LANCZOS)
    im.save(dst, "PNG", optimize=True)

def render(col: Path) -> None:
    data = load(col)
    errs = validate(data)
    if errs: sys.exit("themes.json invalid:\n  " + "\n  ".join(errs))
    rows = []
    for t in sorted(data["themes"], key=lambda t: (t["released"], t["name"]), reverse=True):
        variants = ""
        if t.get("variants"):
            variants = "Variants:\n\n" + "".join(f"- [{v['name']}]({v['url']}) ({v['kind']})\n" for v in t["variants"]) + "\n"
        rows.append(
            f"### [{t['title']}]({t['repo']})\n\n"
            f"[![{t['title']} preview]({t['preview']})]({t['repo']})\n\n"
            f"{t['description']}\n\n"
            f"`{t['mode']}` · accent `{t['accent']}` · v{t['version']}, released {t['released'][:10]} · [repo]({t['repo']}) · [release]({t['repo']}/releases/tag/v{t['version']})\n\n"
            f"```bash\nomarchy-theme-install {t['repo']}\n```\n"
            + ("\n" + variants if variants else ""))
    body = "\n".join(rows) if rows else "_No themes yet._\n"
    readme = col / "README.md"
    s = readme.read_text()
    if START not in s or END not in s:
        sys.exit("README.md has no gallery markers")
    s = s[: s.index(START) + len(START)] + "\n\n" + body + "\n" + s[s.index(END):]
    readme.write_text(s)

def upsert(a) -> None:
    col, theme = Path(a.collection), Path(a.theme_dir)
    if not re.fullmatch(r"https://github\.com/[\w.-]+/[\w.-]+", a.repo):
        sys.exit(f"repo must be an https://github.com/OWNER/NAME URL: {a.repo}")
    if not re.fullmatch(r"[a-z0-9_][a-z0-9._+-]*", a.name):
        sys.exit(f"bad theme name {a.name}")
    c = tomllib.load(open(theme / "colors.toml", "rb"))
    (col / "previews").mkdir(exist_ok=True)
    thumbnail(theme / "preview.png", col / "previews" / f"{a.name}.png")
    entry = {
        "name": a.name, "title": a.title, "description": tagline(theme / "README.md"),
        "repo": a.repo, "version": a.version, "sha256": a.sha256 or None,
        "mode": c.get("mode", "dark"), "accent": c.get("accent"),
        "preview": f"previews/{a.name}.png",
    }
    data = load(col)
    old = next((t for t in data["themes"] if t["name"] == a.name), {})
    entry["released"] = a.released or old.get("released") or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    if a.variant:
        entry["variants"] = [dict(zip(("name", "kind", "url"), v.split(",", 2))) for v in a.variant]
    elif old.get("variants"):
        entry["variants"] = old["variants"]
    data["themes"] = [t for t in data["themes"] if t["name"] != a.name] + [entry]
    errs = validate(data)
    if errs: sys.exit("refusing to write an invalid index:\n  " + "\n  ".join(errs))
    save(col, data)
    render(col)
    print(f"[index] {a.name} {a.version} -> {col / 'themes.json'}")

ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
u = sub.add_parser("upsert")
for f in ("collection", "theme-dir", "name", "title", "version", "repo"):
    u.add_argument("--" + f, required=True)
u.add_argument("--sha256", default="")
u.add_argument("--released", default="", help="ISO 8601 UTC publish time (default: keep, else now)")
u.add_argument("--variant", action="append", default=[], help="NAME,KIND,URL (repeatable)")
for c in ("render", "check"):
    sub.add_parser(c).add_argument("--collection", required=True)
a = ap.parse_args()
if a.cmd == "upsert": upsert(a)
elif a.cmd == "render": render(Path(a.collection))
else:
    e = validate(load(Path(a.collection))); print("\n".join(e) or "themes.json OK"); sys.exit(1 if e else 0)
