# Adding a theme to the collection

Themes are never committed here. Each one ships from its own repo,
`github.com/synthalorian/omarchy-<name>-theme`, and this repo only indexes them in `themes.json`. The index
feeds both the README gallery and the `glyphsmith` picker.

## The release path (Glyphsmith studio)

1. **Release pass.** Run `templates/ship.sh themes/<name>`. It does the audit and scrub, runs the
   validators (`tests/<name>/validate.sh` and/or the shared `tests/validators/validate-theme.sh`), makes a
   reproducible double build, runs the bubblewrap install test with the real `omarchy-theme-set`, and writes
   `releases/<name>-<version>.REPORT.md`.
2. **Sign-off.** synth reviews the report and its sha256.
3. **Publish and index in one step.**
   ```bash
   templates/ship.sh themes/<name> --publish --yes-synth-approved \
     --description "<Title>: <one line>" --topics <extra,topics> --index collection
   ```
   `--index collection` runs only after the release is live and verified. It then:
   - adds or replaces the theme's entry in `themes.json`. Name, title, the one-line description (the first
     paragraph of the theme README), repo, version, sha256, mode and accent come from the theme itself.
   - writes a 640x360 thumbnail of the theme's `preview.png` to `previews/<name>.png`.
   - re-renders the gallery between the `<!-- gallery:start -->` / `<!-- gallery:end -->` markers in README.md.
4. **An already-published theme** (or a new version): `templates/ship.sh <theme-dir> --add-to-index collection`.
5. Commit the changed `themes.json`, `previews/<name>.png` and `README.md` here as synthalorian
   (noreply address), with a message like `Add <Title> <version>`.

Don't edit the gallery by hand; it's regenerated from `themes.json` (`python3 tools/index.py render --collection .`).

## Optional variants

A theme can list variants, such as a light version or a ghostty-, kitty- or vscode-only port, in its `variants` array.
Each one is `{"name": ..., "kind": ..., "url": "https://..."}`, and `kind` is one of light, dark, ghostty, kitty,
alacritty, foot, vscode, neovim, wallpapers or other. They are rendered under the theme in the gallery.
Add them with `tools/index.py upsert ... --variant "Name,kind,https://..."` (repeatable). A later upsert keeps
existing variants unless new ones are passed. The gallery is sorted newest first by `released`, the release's publish time
in ISO 8601 UTC. `python3 tools/index.py check --collection .` validates the index without writing anything.

## Rules for entries

- `repo` must be a plain `https://github.com/OWNER/NAME` URL. The picker refuses anything else.
- The repo name must be `omarchy-<name>-theme`, so that `omarchy-theme-install` installs it as `<name>`.
- Descriptions and credits name people only, and never use a real name. The author is synthalorian.
- Every listed theme must have a published release, and its repo's install-test CI must be passing.
