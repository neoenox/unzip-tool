# tools/ 置き場の案内 (UnRAR方針)

方針: **(a) バイナリはgit管理外＋各自/CI調達**。`UnRAR.exe` をコミットしない
(`.gitignore` で `tools/UnRAR.exe` を無視)。このフォルダの文書
(`README.md`、`license.txt`) は管理対象。

## 入手と配置 (いずれか1つ)

1. WinRARをインストールする (インストーラ同梱の `UnRAR.exe` を自動検出)。
2. UnRAR for Windows を [rarlab](https://www.rarlab.com/rar_add.htm) から取得し、
   `tools/UnRAR.exe` として置く。実行時に検出される（exeには同梱しない）。
3. 環境変数 `KANTAN_UNRAR` に `UnRAR.exe` のフルパスを指定する。
   (CIは `choco install unrar -y` で調達し、テストのみに使う。同梱はしない)

検出順は `unzipper.find_unrar_tool()` どおり:
`KANTAN_UNRAR` > `tools/UnRAR.exe` (基点隣接・exe隣・展開先) > WinRAR > PATH。

## ライセンス

UnRARはフリーウェア (作者: Alexander Roshal)。`license.txt` 全文のとおり、
無償での再配布は他ソフト同梱を含め許可されているが、本リポジトリは
バイナリ自体を配布しない。手元で同梱exeを作った場合は、配布物に
`license.txt` の条件が及ぶことを意識すること。

## 確認

```bat
python tests/test_rar.py
REM UnRAR未検出時は実展開テストをスキップし、案内文のテストのみ実行する
```
