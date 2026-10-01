# かんたん解凍 (unzip-tool)

Windows向けのシンプルな解凍ソフト。Python標準ライブラリのみ、外部依存なし。

## 対応形式 (v1 シンプル版)

- `.zip`
- `.tar` / `.tar.gz` / `.tgz` / `.tar.bz2` / `.tar.xz`

※ `.7z` / `.rar` / パスワード付きは未対応 (あとで追加可能)

## 使い方

```bat
run.bat
REM または
python app.py
```

1. 「参照…」でアーカイブを選択 (内容が一覧表示される)
   またはアーカイブをウィンドウにドラッグ＆ドロップ
2. 解凍先フォルダを確認 (空なら自動で `アーカイブ名/` が入る、フォルダのドロップで指定も可)
3. 「解凍する」を押す

## exe化

```bat
build.bat
REM → dist\KantanKaiko.exe ができる (単一ファイル、Python不要)
```

タグ `v*` をpushすると GitHub Actions が自動ビルドし、Releaseにexeを添付する。

```bat
git tag v0.1.0
git push origin v0.1.0
```

## テスト

```bat
python tests/test_e2e.py
```

実物のAppウィンドウを使い、GUI解凍とOSレベルDnD (WM_DROPFILES送信) を端から端まで検証する。

## 仕様メモ

- 日本語zipの文字化け対策あり (cp437 → cp932 再デコード)
- Zip Slip対策あり (アーカイブ外への書き込みを拒否、危険パスはエラー)
- tarのシンボリックリンク等はスキップ (シンプル版の安全策)
