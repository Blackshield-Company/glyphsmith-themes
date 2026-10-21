# Browser companions

Unsigned, static Firefox (Manifest V2, Firefox 140+) and Chromium (Manifest V3)
themes for **every desktop theme in `themes.json`**:

| Desktop | Firefox | Chromium | Frame | Toolbar |
| --- | --- | --- | --- | --- |
| Neon Horizon | [source](neon-horizon/firefox) | [source](neon-horizon/chromium) | `#0d0717` midnight purple | `#ff4fa3` hot pink |
| Steel & Ember | [source](steel-and-ember/firefox) | [source](steel-and-ember/chromium) | `#0e1013` blue steel | `#f28c38` ember orange |

## Design and provenance

`palettes.json` vendors the required subset of each desktop palette, pinned to
its upstream `colors.toml` commit. No network access is needed to build. Browser
versions are independent of desktop versions; bump the palette's `version` when
changing a published browser package.

The layout follows the existing local Synthwave '84 browser set by synthalorian:
Firefox frame image and full UI colors; Chromium RGB colors, active/inactive
frame images and new-tab image. It does not copy any signed package, cached
browser data, upload IDs or credentials. The collection contains no signed XPI.

The frame is the **darkest non-neutral palette tone**, not pure black. Solid PNG
frame images match that tone, so artwork never masks the chosen frame color.
The selected tab and toolbar use the **actual accent**, not the near-black
desktop background. Dark ink on these bright accents keeps tabs, bookmarks and
icons legible. URL fields and popups stay dark; cyan marks focus and new-tab
links. Text/background combinations are checked for at least 4.5:1 contrast.
Chromium colors available to themes vary by browser/version; no website content,
browser side-panel internals or system window decorations are overridden.

## Build and validate

Python 3.11+; no runtime dependencies, signing tools, credentials or browser
profile access required:

```sh
python3 tools/browser.py generate  # after editing palettes or generator
python3 tools/browser.py check     # verify checked-in manifests and PNG bytes
python3 -m unittest discover -s tests -v
python3 tools/browser.py build     # verify first, then zip each browser/theme
# optional: python3 tools/browser.py build --output /path/to/output
```

Outputs: `dist/browser/<theme>-<browser>-<version>.zip`, with `manifest.json` at
the archive root. Only generated manifest and referenced PNGs enter archives.
ZIP ordering, timestamps and modes are fixed; repeat builds on the same Python/
zlib toolchain are byte-identical. Extra or modified source files fail validation
instead of silently entering an archive. CI also runs Mozilla's `web-ext` linter.

## Local testing (opt-in; build does not install anything)

- **Firefox:** in a separate test profile, open `about:debugging`, choose
  **This Firefox → Load Temporary Add-on**, and select the theme's `manifest.json`.
  Temporary loading is for testing, not permanent installation. Normal release
  Firefox requires Mozilla signing for permanent use. ZIPs here are **not signed
  XPIs**; do not rename one and assume it will install permanently.
- **Chromium:** in a separate test profile, open `chrome://extensions`, enable
  **Developer mode → Load unpacked**, and choose `browser/<theme>/chromium`.
  Themes may not appear as ordinary extension tiles; inspect the toolbar/new-tab
  appearance and reset the theme via Appearance settings when finished.

Before release, visually inspect active/inactive windows, selected/background
tabs, toolbar icons/bookmarks, URL focus/selection, menus, new-tab page and private
windows in real Firefox and Chromium. Automated checks are not visual sign-off.
No theme signing, store submission, publishing or installation is performed by
this tooling or CI.
