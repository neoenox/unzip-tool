"""Policy test for #15: UnRAR binary management is option (a).

- The binary stays git-ignored (never committed).
- Policy docs (tools/README.md, tools/license.txt) are tracked.
- README documents procurement (rarlab, placement, KANTAN_UNRAR) so every
  developer build behaves the same (rar works iff a tool is found).
- .gitignore ignores only binaries, not the whole tools/ directory.

Pure text/git test: no GUI, runs anywhere in a checkout.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _git(*args):
    return subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True,
        check=False, timeout=30,
    )


def tracked():
    proc = _git("ls-files")
    if proc.returncode != 0:
        raise unittest.SkipTest("not a git checkout")
    return set(proc.stdout.splitlines())


def ignored(path):
    return _git("check-ignore", path).returncode == 0


class UnrarPolicyTests(unittest.TestCase):
    def test_binary_is_ignored_but_docs_are_tracked(self):
        self.assertTrue(ignored("tools/UnRAR.exe"), "binary must stay ignored")
        self.assertTrue(ignored("tools/unrar.exe"), "lowercase binary must stay ignored")
        files = tracked()
        self.assertIn("tools/README.md", files)
        self.assertIn("tools/license.txt", files)
        self.assertNotIn("tools/UnRAR.exe", files)
        self.assertNotIn("tools/unrar.exe", files)

    def test_procurement_is_documented(self):
        tools_readme = (ROOT / "tools" / "README.md").read_text(encoding="utf-8")
        for keyword in ("rarlab", "KANTAN_UNRAR", "tools/UnRAR.exe", "choco install unrar"):
            self.assertIn(keyword, tools_readme, keyword)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for keyword in ("git管理外", "tools/README.md", "tools/license.txt", "KANTAN_UNRAR"):
            self.assertIn(keyword, readme, keyword)

    def test_gitignore_matches_reality(self):
        gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        # A blanket tools/ ignore would also hide the policy docs.
        self.assertNotIn("\ntools/\n", "\n" + gitignore + "\n")
        self.assertIn("tools/UnRAR.exe", gitignore)


if __name__ == "__main__":
    unittest.main()
