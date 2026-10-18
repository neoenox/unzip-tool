"""テストが実ユーザーの `%APPDATA%\\KantanKaiko\\settings.json` を触らないようにする (#24)。

`tests/run_all.py` は子プロセスへ同じ環境変数を渡すので、こちらは pytest 実行時用。
"""
import pytest


@pytest.fixture(autouse=True)
def isolate_app_settings(tmp_path, monkeypatch):
    monkeypatch.setenv("KANTAN_SETTINGS_DIR", str(tmp_path / "kantan-settings"))
