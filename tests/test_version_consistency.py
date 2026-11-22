"""リリース版数の一元管理を守るテスト。

- `version.py` の `VERSION` が唯一の出所であること。
- PRのCIとリリースが共通の `windows-build.yml` でその値を読み、版数を直書きしないこと。
- リリースworkflowがタグと `VERSION` の一致を検証し続けること。
- READMEの「現在の版」と、手順に載っているインストーラー名・タグ例が追随していること。

純粋なテキスト検査なのでGUIは不要。どこでも動く。
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from version import VERSION  # noqa: E402

SETUP_EXE = re.compile(r"KantanKaiko-Setup-(\d+\.\d+\.\d+)\.exe")
CURRENT_VERSION = re.compile(r"現在は `v(\d+\.\d+\.\d+)`")


class VersionConsistencyTests(unittest.TestCase):
    def setUp(self):
        self.ci = (ROOT / ".github" / "workflows" / "ci.yaml").read_text(encoding="utf-8")
        self.build = (ROOT / ".github" / "workflows" / "windows-build.yml").read_text(encoding="utf-8")
        self.release = (ROOT / ".github" / "workflows" / "build-exe.yaml").read_text(encoding="utf-8")
        self.readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.iss = (ROOT / "installer" / "KantanKaiko.iss").read_text(encoding="utf-8")

    def test_version_is_a_release_number(self):
        self.assertRegex(VERSION, r"^\d+\.\d+\.\d+$")

    def test_ci_reads_the_version_instead_of_hardcoding_it(self):
        for name, text in (("ci.yaml", self.ci), ("windows-build.yml", self.build)):
            self.assertNotIn(VERSION, text, f"{name} は版数を直書きしない（version.py から読む）")
            self.assertNotRegex(text, r"KantanKaiko-Setup-\d+\.\d+\.\d+\.exe")
        self.assertIn("version.py", self.build)
        self.assertIn("GITHUB_ENV", self.build)
        self.assertIn("APP_VERSION", self.build)

    def test_ci_passes_the_resolved_version_to_the_installer_scripts(self):
        for call in ("build-installer.ps1", "test-installer.ps1"):
            self.assertRegex(self.build, rf"{re.escape(call)}[^\n]*\$env:APP_VERSION")

    def test_release_workflow_keeps_checking_tag_against_version(self):
        self.assertIn("from version import VERSION", self.release)
        self.assertIn("RELEASE_TAG", self.release)
        self.assertIn("git merge-base --is-ancestor HEAD origin/main", self.release)

    def test_readme_states_the_current_version(self):
        found = CURRENT_VERSION.findall(self.readme)
        self.assertEqual(found, [VERSION], "README の「現在は `vX.Y.Z`」が version.py と一致しない")

    def test_readme_examples_use_the_current_version(self):
        examples = {
            "インストーラー名": SETUP_EXE.findall(self.readme),
            "build-installer の引数": re.findall(r"-Version (\d+\.\d+\.\d+)", self.readme),
            "タグ例": re.findall(r"git (?:tag|push origin) v(\d+\.\d+\.\d+)", self.readme),
            "タグの説明": re.findall(r"`v(\d+\.\d+\.\d+)`", self.readme),
        }
        for label, values in examples.items():
            self.assertTrue(values, f"README から{label}を1つも見つけられなかった")
            self.assertEqual(set(values), {VERSION}, f"README の{label}が version.py と一致しない")

    def test_installer_scripts_read_the_version_from_version_py(self):
        for name in ("build-installer.ps1", "test-installer.ps1", "verify-release.ps1"):
            text = (ROOT / "scripts" / name).read_text(encoding="utf-8")
            with self.subTest(script=name):
                self.assertNotIn(VERSION, text, f"{name} は版数を直書きしない")
                self.assertNotRegex(text, r"= '\d+\.\d+\.\d+'")
                self.assertIn("version.py", text)

    def test_inno_setup_requires_the_version_defines(self):
        self.assertNotIn(VERSION, self.iss, "KantanKaiko.iss は版数を直書きしない")
        self.assertNotRegex(self.iss, r'#define (?:AppVersion|NumericVersion) "[\d.]+"')
        self.assertIn("#error", self.iss)
        self.assertIn("/DAppVersion=", self.iss)
        self.assertIn("AppVersion={#AppVersion}", self.iss)


if __name__ == "__main__":
    unittest.main()
