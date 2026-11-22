import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "tools/index.py"


class IndexCheckTest(unittest.TestCase):
    def check(self, mutate):
        data = json.loads((ROOT / "themes.json").read_text())
        mutate(data["themes"][0])
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy(ROOT / "README.md", tmp)
            Path(tmp, "themes.json").write_text(json.dumps(data))
            return subprocess.run([sys.executable, str(INDEX), "check", "--collection", tmp],
                                  capture_output=True, text=True)

    def test_published_index_passes(self):
        self.assertEqual(self.check(lambda t: None).returncode, 0)

    def test_missing_mode_or_accent_fails_check_not_render(self):
        for key in ("mode", "accent"):
            result = self.check(lambda t: t.pop(key))
            self.assertEqual(result.returncode, 1, key)
            self.assertIn(f"missing {key}", result.stdout)

    def test_repo_must_be_ascii_like_the_picker(self):
        result = self.check(lambda t: t.update(repo="https://github.com/s\u00ffnth/omarchy-neon-horizon-theme"))
        self.assertEqual(result.returncode, 1)
        self.assertIn("bad repo URL", result.stdout)

    def test_dot_segments_rejected(self):
        result = self.check(lambda t: t.update(repo="https://github.com/../.."))
        self.assertEqual(result.returncode, 1)
        self.assertIn("bad repo URL", result.stdout)


if __name__ == "__main__":
    unittest.main()
