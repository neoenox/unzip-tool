# かんたん解凍 (unzip-tool)

Windows向けのシンプルな解凍ソフト。zip/tarは依存なし、rarのみ外部ツールが必要。

## 対応形式

- `.zip` (パスワード対応)
- `.7z` (パスワード対応)
- `.rar` (RAR4/5、パスワード対応、要UnRAR)
- `.tar` / `.tar.gz` / `.tgz` / `.tar.bz2` / `.tar.xz`

※ 分割アーカイブ / 自己解凍形式は未対応 (あとで追加可能)

## RARに必要なもの

いずれか1つ。無ければrar選択時に案内が出る。

1. WinRARをインストール (UnRAR.exe を自動検出)
2. `tools/UnRAR.exe` を置く (同梱のexe化も可能→下記)
3. 環境変数 `KANTAN_UNRAR` にUnRAR.exeのパスを指定

UnRARはフリーウェア ([rarlab](https://www.rarlab.com/rar_add.htm) のUnRAR for Windows)。

## 使い方

```bat
run.bat
REM または
python app.py
```

1. 「参照…」でアーカイブを選択 (内容が一覧表示される)
   またはアーカイブをウィンドウにドラッグ＆ドロップ
2. パスワード付きなら欄が出るので入力 (不要な時は出ない)
3. 解凍先フォルダを確認 (空なら自動で `アーカイブ名/` が入る、フォルダのドロップで指定も可)
4. 「解凍する」を押す (パスワード欄ではEnterでも可)

## exe化

```bat
build.bat
REM → dist\KantanKaiko.exe ができる (単一ファイル、Python不要)
REM tools\UnRAR.exe があれば同梱され、そのexe単体でrarも解凍できる
```

タグ `v*` をpushすると GitHub Actions が自動ビルドし、Releaseにexeを添付する。

```bat
git tag v0.1.0
git push origin v0.1.0
```

## テスト

```bat
python tests/test_e2e.py
python tests/test_xproc_dnd.py
python tests/test_rar.py
python tests/test_7z.py
python tests/test_password.py
```

実物のAppウィンドウを使い、GUI解凍・同一プロセス内DnD・別プロセス通知の堅牢性を検証する。
真のExplorerドロップ配送はOLE共有メモリ経由のため合成不可。初回は手で1回試すこと。

## 仕様メモ

- DnDはpoll方式: WndProc内ではTkを一切触らない (別プロセス通知時の再入で落ちるため)
- 日本語zipの文字化け対策あり (cp437 → cp932 再デコード)
- Zip Slip対策あり (アーカイブ外への書き込みを拒否、危険パスはエラー)
- tarのシンボリックリンク等はスキップ (シンプル版の安全策)
