"""ドキュメント内のローカルリンクが実在することを確認する。

リリース検証の手順書や仕様メモは、リンクが切れると「どこを見ればよいか」が
失われる。ビルドにもGUIにも依存しないテキスト検査として置く。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LINK = re.compile(r"\]\(([^)\s]+)\)")
EXTERNAL = ("http://", "https://", "mailto:")


def local_links(text):
    for target in LINK.findall(text):
        if target.startswith(EXTERNAL):
            continue
        path = target.split("#", 1)[0]
        if path:
            yield target, path


class DocumentationLinkTests(unittest.TestCase):
    def documents(self):
        yield ROOT / "README.md"
        yield ROOT / "tools" / "README.md"
        for path in sorted((ROOT / "docs").glob("*.md")):
            yield path

    def test_local_links_point_at_existing_files(self):
        checked = 0
        for document in self.documents():
            text = document.read_text(encoding="utf-8")
            for target, path in local_links(text):
                with self.subTest(document=document.name, link=target):
                    self.assertTrue((document.parent / path).exists(),
                                    f"{document.name} のリンク先がない: {target}")
                    checked += 1
        self.assertGreater(checked, 0, "ローカルリンクを1つも検出できなかった")

    def test_manual_explorer_checklist_is_reachable(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("docs/manual-explorer-qa.md", readme)
        qa = (ROOT / "docs" / "windows-qa.md").read_text(encoding="utf-8")
        self.assertIn("manual-explorer-qa.md", qa)


if __name__ == "__main__":
    unittest.main()
