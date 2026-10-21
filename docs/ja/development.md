# 開発手順

## リポジトリの構成 {#repository-structure}

| パス | 内容 |
| --- | --- |
| [src/locata_torch/](https://github.com/taishi-n/torchlocata/tree/main/src/locata_torch) | Dataset、バッチ化、座標、型、保存先、downloader、CLI |
| [tests/](https://github.com/taishi-n/torchlocata/tree/main/tests) | 合成 fixture と、root を指定した場合だけ実行する実データテスト |
| [examples/read_locata.py](https://github.com/taishi-n/torchlocata/blob/main/examples/read_locata.py) | spawn worker と main guard を含む読み込み例 |
| [examples/analyze_locata.py](https://github.com/taishi-n/torchlocata/blob/main/examples/analyze_locata.py) | 定位、評価、保存、描画の実行例 |
| [docs/](https://github.com/taishi-n/torchlocata/tree/main/docs) | 英語文書と、対応する `docs/ja/` の日本語文書 |
| [zensical.toml](https://github.com/taishi-n/torchlocata/blob/main/zensical.toml) | 英語版のナビゲーション、テーマ、API 生成設定 |
| [zensical.ja.toml](https://github.com/taishi-n/torchlocata/blob/main/zensical.ja.toml) | 日本語版の設定 |
| [scripts/check_docs_links.py](https://github.com/taishi-n/torchlocata/blob/main/scripts/check_docs_links.py) | HTML のページ、anchor、asset、翻訳先の確認 |
| [scripts/check_release.py](https://github.com/taishi-n/torchlocata/blob/main/scripts/check_release.py) | 配布物の metadata、内容、バージョン、hash の確認 |
| [scripts/smoke_installed.py](https://github.com/taishi-n/torchlocata/blob/main/scripts/smoke_installed.py) | インストール後の読み込み、CLI、spawn の確認 |
| `site/` | 生成 HTML。Git の追跡対象外 |

[README.md](https://github.com/taishi-n/torchlocata/blob/main/README.md) は API の概要と詳細文書への入口です。
root の [AGENTS.md](https://github.com/taishi-n/torchlocata/blob/main/AGENTS.md) にも開発の指針を記載しています。

## セットアップとチェック {#install-and-run-checks}

リポジトリを取得し、root で開発コマンドを実行します。

```sh
git clone https://github.com/taishi-n/torchlocata.git
cd torchlocata
uv sync --locked --python 3.12 --extra download --extra plot --group docs --group release
uv run pytest -m "not integration"
uv run ruff check .
uv run ruff format --check .
uv run ty check
uv build --no-sources --clear
uv run twine check --strict dist/*.whl dist/*.tar.gz
uv run python scripts/check_release.py
```

Python は 4 space の indent と Ruff の 88 文字幅を使います。
関数・module は `snake_case`、クラスは `PascalCase`、公開 interface には型注釈を付けます。
整形は `uv run ruff format .` です。
実行時の依存は PyTorch、NumPy、SoundFile、platformdirs を中心とし、filelock は `download` extra、Matplotlib は `plot` extra に分けます。
文書と release のツールは dependency group に置き、CI では描画テストのために `plot` extra を入れます。

最初に仕様文書を更新し、動作を表すテストの失敗を確認してから、必要な実装を加えます。
変更後はコードと文書の対応を確認し、対応する操作ごとに公開 API を一つに揃えます。

## テストの範囲 {#test-boundaries}

pytest の一時ディレクトリに小さな WAV とタブ区切り TXT を作ります。
ファイル名は `test_*.py`、関数名は `test_*` としてください。
観測できる動作、独立した時刻表、欠損、部分読み込み、DataLoader を検証します。数値の coverage 閾値は設けていません。

実データのテストは root を指定して実行し、入力は読み取り専用で扱います。

```sh
LOCATA_ROOT=/path/to/LOCATA uv run pytest -m integration -v
```

`LOCATA_ROOT` がなければ integration test は skip します。skip と実行済みを区別し、実音声をリポジトリにコピーしたり、データ本体の下に cache を作ったりしないでください。
確認した snapshot、platform matrix、検証範囲は[検証記録](validation.md)に記載しています。
手元のデータで実行例を確認するには次のコマンドを使います。

```sh
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 0
uv run python examples/read_locata.py --root /path/to/LOCATA --workers 2
```

## 文書のビルドと表示 {#preview-and-build-documentation}

英語版の既存 URL を保ち、日本語版を `ja/` に配置します。
ファイル名は両言語で揃えています。
Zensical の `theme.language` で表示言語を設定し、`extra.alternate` で標準のヘッダーメニューを表示します。
このメニューから各言語のトップページへ移動できます。
ナビゲーションと検索 index は言語ごとに持ち、API とコード例は共通です。
シグネチャと英語の docstring は、共通の Python ソースから生成します。

`docs` dependency group を入れ、両言語をビルドして確認します。

```sh
uv sync --group docs
uv run zensical build --clean --strict --config-file zensical.toml
uv run zensical build --clean --strict --config-file zensical.ja.toml
uv run python scripts/check_docs_links.py site --multilingual
```

`site/index.html` または `site/ja/index.html` を直接開けます。全体を HTTP で表示する場合は次のコマンドを使います。

```sh
uv run python -m http.server --directory site 8000
```

表示先は `http://localhost:8000` です。
Zensical は project ごとに一つの言語を設定するため、英語には `zensical.toml`、日本語には `zensical.ja.toml` を使います。
英語の clean build が `site/` を作り直し、日本語のビルドが `site/ja/` を加えるので、この順序で実行してください。
標準の言語メニューは公開サイトのトップページへ移動します。
ローカルで確認するときは、preview server の `/index.html` と `/ja/index.html`、または `site/` 内の各ファイルを開いてください。
ガイドを追加・変更するときは両言語を更新し、API 名、数値、コード例、検証の限界を揃えてください。

`use_directory_urls=false` により、リンクは具体的な HTML ファイルを指します。
offline mode ではローカル検索を使えます。ローカルファイルを読む場合、テーマが iframe-worker polyfill を CDN から取得することがあります。
ページ本文とナビゲーションは preview server なしで利用できます。

文書内のリンクは `[データ形式](data-model.md)` のように Markdown のファイル名で書きます。
root からの絶対パスや生成後の HTML パスは、文書内リンクには使いません。
API は `src/locata_torch` から mkdocstrings で生成します。
変更後は strict build と link checker を実行してください。checker は local のページ、anchor、asset を検証し、外部サイトへはアクセスしません。
README は PyPI 上でもリンクが機能するよう、公開文書の絶対 URL を使います。
`docs/` の外にあるファイルは GitHub の `blob/main/` または `tree/main/` にリンクします。
データや出力先は `/path/to/LOCATA`、`/path/to/experiment` の placeholder で示し、個人環境のパスやファイル URL を公開本文に埋め込みません。

CI は Python 3.10〜3.14 と Linux / macOS / Windows、および Python 3.10 の最小直接依存を確認します。
Ruff、ty、配布物の内容と metadata、独立環境への wheel / sdist インストール、strict 文書ビルド、リンク検証を実行します。
ダウンロードの必須テストには local HTTP server と合成 ZIP64 を使い、LOCATA 本体は取得しません。

`release.yml` は同じ検証 workflow を呼び、検証済み配布物を OIDC で公開します。
一致する stable tag は PyPI、RC tag は TestPyPI に送り、manual 実行では検証だけを行います。
stable release ではパッケージ公開後に文書を deploy します。
manual の `docs.yml` は `main` からサイトをビルド・検証し、パッケージとは別に Pages へ deploy します。

```sh
gh workflow run docs.yml --ref main --repo taishi-n/torchlocata
```

publisher と保護された environment は[公開手順](release-plan.md)を参照してください。

## 変更の提案 {#contributions}

commit は `feat: add ...`、`chore: release ...` などの Conventional Commits に揃えます。
`feat`、`fix`、`docs`、`chore` を使い、変更後の動作が分かる、対象を絞った subject にしてください。
PR は動作、文書、実行した検証、残る制約を説明し、関連 issue があればリンクします。
commit、push、公開は、それぞれ明示された場合に実行します。
