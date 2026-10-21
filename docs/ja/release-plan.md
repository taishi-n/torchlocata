# 公開手順

`locata-torch` の新しいバージョンを公開する保守担当者向けの手順です。
利用時のインストールは[使い始める](getting-started.md)、データ準備は[データの保存先](storage.md)、公開履歴は[リリースノート](releases.md)を参照してください。

## 公開 workflow {#publication-workflow}

`.github/workflows/release.yml` は CI 全体を呼び、検証済みの wheel と sdist を GitHub OIDC で公開します。
パッケージ metadata と tag は完全に一致する必要があります。

| 開始条件 | 公開先 | 文書の deploy |
| --- | --- | --- |
| stable tag `vX.Y.Z` | PyPI、environment `pypi` | パッケージ公開の成功後 |
| release candidate tag `vX.Y.ZrcN` | TestPyPI、environment `testpypi` | なし |
| `release.yml` の manual 実行 | 検証だけ | なし |

バージョンは正規の `X.Y.Z` または `X.Y.ZrcN` を使い、他の prerelease 表記は拒否します。
一致する tag の push で公開 workflow が始まり、保護された package environment の承認が必要になります。

検証は Python 3.10〜3.14、Linux / macOS / Windows、最小直接依存、lint、format、型、配布物、README、独立環境へのインストール、strict 文書ビルドを含みます。
必須テストには合成 WAV / TXT、local HTTP server、小さな ZIP64 を使い、CI は LOCATA アーカイブを取得しません。

publisher は検証済み artifact の `SHA256SUMS` を確認し、再ビルドや source の checkout をせず upload します。
[check_release.py](https://github.com/taishi-n/torchlocata/blob/main/scripts/check_release.py) は tag とバージョン、依存、license metadata、`py.typed`、CLI entry point、データ本体や生成物の混入を検証し、新しい配布物の SHA-256 一覧を書きます。

## Trusted Publishing と environment {#trusted-publishing-and-environments}

PyPI と TestPyPI の publisher は、それぞれ次の内容で登録します。

| 項目 | 値 |
| --- | --- |
| Project | `locata-torch` |
| GitHub owner | `taishi-n` |
| Repository | `torchlocata` |
| Workflow | `release.yml` |
| PyPI environment | `pypi` |
| TestPyPI environment | `testpypi` |

GitHub の `pypi` と `testpypi` environment は、`taishi-n` の review と `v*` tag を要求します。
publishing job には `id-token: write` を付け、長期 upload token はリポジトリに保存しません。
公開処理を変更する場合は、publisher の workflow / environment 名も揃えてください。
アカウント側の設定は [PyPI Trusted Publishing](https://docs.pypi.org/trusted-publishers/using-a-publisher/) を参照してください。

GitHub Pages の source は GitHub Actions です。
`github-pages` environment は `v*` tag と `main` の文書 deploy を許可します。
公開 URL は `https://taishi.org/torchlocata/` で、package metadata と README のリンクもこの URL に揃えます。

## release candidate を準備する {#prepare-a-release-candidate}

1. 変更と仕様・release note の更新を終え、[開発チェック](development.md#install-and-run-checks)を実行します。合成テストと任意の実データ結果を分けて記録します。
2. `pyproject.toml` の `[project].version` に candidate のバージョンを設定し、`uv lock` を実行して対応する配布物をビルド・検証します。`0.2.0rc1` を設定した場合の例です。

   ```sh
   uv build --no-sources --clear
   uv run twine check --strict dist/*.whl dist/*.tar.gz
   uv run python scripts/check_release.py --tag v0.2.0rc1
   ```

3. review 済みの candidate を commit / push し、CI の全 job が通過することを確認します。`v0.2.0rc1` などの一致する署名付き tag を作成して push します。
4. release workflow の検証と artifact 一覧を確認し、`testpypi` environment を承認します。正確な candidate が TestPyPI に出たことを確認してください。
5. checkout の外の新しい環境でインストールします。依存を PyPI から解決し、TestPyPI の指定配布物を依存解決なしで入れます。

   ```sh
   python -m pip install torch numpy soundfile platformdirs filelock
   python -m pip install --index-url https://test.pypi.org/simple/ --no-deps "locata-torch[download]==0.2.0rc1"
   locata-torch --help
   ```

   コマンド中のバージョンは例なので、公開するバージョンに置き換えてください。
   import 先が独立環境の `site-packages` であることを確認し、録音、窓、padding、CLI の root 検索、spawn 2 worker を試します。
   合成データまたは既存の `LOCATA_ROOT=/path/to/LOCATA` を使い、この確認のためにデータ本体をダウンロードする必要はありません。

## stable を公開する {#publish-a-stable-version}

1. stable バージョンを設定し、lock と release note を更新して、必要なチェックを再実行します。review 済みの変更を commit / push し、CI 通過後に一致する署名付き `vX.Y.Z` tag を作成・push します。
2. stable の検証済み artifact を確認し、`pypi` environment を承認します。workflow はその artifact を公開し、成功後に検証済み文書を deploy します。
3. PyPI の正確なバージョン、metadata、wheel / sdist の hash を、元の検証済み artifact 一覧と比較します。その一覧を保持してください。`check_release.py` の再実行は新しい一覧を作るため、元の release hash の比較には代えられません。
4. 独立した pip 環境と uv プロジェクトで、[導入例](getting-started.md)と spawn worker を確認します。合成または既存データを使い、実行した範囲と未検証のデータを[検証記録](validation.md)に残します。

build 設定を変える場合は、[uv packaging guide](https://docs.astral.sh/uv/guides/package/) と [Python packaging metadata guide](https://packaging.python.org/en/latest/guides/writing-pyproject-toml/) を参照してください。
Python パッケージと固定 LOCATA 配布版のバージョンは独立しており、ライブラリの更新でデータ本体を置き換えることはありません。

## 文書だけを deploy する {#deploy-documentation-changes}

パッケージ公開後の文書変更はまずローカルで両言語を検証します。

```sh
uv run --group docs zensical build --clean --strict --config-file zensical.toml
uv run --group docs zensical build --clean --strict --config-file zensical.ja.toml
uv run python scripts/check_docs_links.py site --multilingual
```

`main` への commit / push 後、manual workflow を実行します。

```sh
gh workflow run docs.yml --ref main --repo taishi-n/torchlocata
```

この workflow はサイトをビルド・検証して Pages へ deploy し、Python パッケージは公開しません。
既存の PyPI 配布物の README はその release の内容です。ソース上の文書変更は次の配布物に入り、hosted site は独立して更新できます。
