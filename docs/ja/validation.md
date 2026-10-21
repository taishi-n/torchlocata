# 検証記録

## 多言語ドキュメント: 2026-10-21 {#bilingual-documentation-2026-10-21}

英語と日本語の各 15 ページを用意しています。英語の既存 URL は保ち、日本語は `ja/` に配置します。
両言語の strict build と local link を検証し、ページの対応と HTML の言語設定を確認しました。
Zensical 標準のヘッダーメニューには、公開サイトの各言語トップページへのリンクがあります。
文書テストは 19 件通過し、両言語の導入例とコードブロックの一致を確認しています。Ruff、format、ty も通過しました。
API のシグネチャと docstring は共通の Python module から生成します。
日本語の API ページには機能一覧を添え、共通の英語 docstring を掲載しています。

## 未リリースの MATLAB ベース解析: 2026-10-21 {#unreleased-matlab-based-analysis-update-2026-10-21}

以下は現在のソース変更に対する確認で、新しい PyPI release の検証ではありません。
参照 MATLAB の commit、式、変更点、指標定義 `locata-torch-v1` は[解析ガイド](analysis.md)に記載しています。
[NOTICE](https://github.com/taishi-n/torchlocata/blob/main/NOTICE) は wheel / sdist の両方に含めています。
データ本体はすべて読み取り専用で扱い、この更新のための LOCATA アーカイブのダウンロードはしていません。

| 検証 | 結果 |
| --- | --- |
| 必須の合成テスト | 184 件通過、integration 18 件を対象外とした。`plot` extra を入れたため描画も実行。意図的に ZIP 名を重複させた fixture の警告が 1 件。 |
| 既存の Challenge 時代の snapshot | integration 16 件通過。新しい代表的な選択のうち 2 件はデータがなく skip。従来の reader 12 件は、spawn と 4 ms の差も含めて通過。 |
| 管理保存先の最終配布版 eval | integration 10 件通過、dev 用 8 件は eval のみの root のため skip。新しい task / array の 6 ケースはすべて実行。 |
| 数値の参照計算 | 独立した NumPy の STFT と MUSIC のブロック peak、解析的な角度・追跡の例、小さな長方形割り当ての全探索が通過。 |
| 品質・配布物 | Ruff lint / format、ty、wheel / sdist build、strict metadata、NOTICE と任意依存の確認が通過。 |
| 文書 | Zensical strict build と local ページ・anchor・asset の検証が通過。 |
| 独立したインストール環境 | Matplotlib を必須にせず、読み込み、解析、JSON / CSV / NPZ の往復、公式形式の出力、CLI、spawn 2 worker が通過。 |
| 一連の実行例 | 最終 eval の task 1、recording 1、benchmark2 全体で、粗い MUSIC 格子、評価、bundle / submission 出力、PNG を確認。動作確認であり、baseline の精度 benchmark ではない。 |

複数 platform の CI 設定にも `plot` extra を加えていますが、この更新に対する remote matrix は実行していません。

新しい実データケースは各 eval task の recording 1 です。
task 1〜6 に対して順に benchmark2、dicit、dummy、eigenmike、eigenmike、benchmark2 を使い、中ほどの 1 秒を解析しました。
複数音源と移動アレイを含み、最終配布版では source pose とアレイ VAD、oracle track の整合性、MUSIC、保存を確認しています。
旧 snapshot では eval の注釈の不在を扱い、無音ラベルを作らないことを確認しました。
テスト前後でファイルのサイズと更新時刻は一致し、録音をリポジトリにコピーしていません。

実データでは、同じ量子化時刻に異なる pose が並ぶ場合と、有効な required time が音声・VAD の範囲外にある場合が見つかりました。
出現順による照合と、必要な場合に音声区間を指定する処理をテストしています。既定の処理は未知ラベルを保持します。
失敗するケースを確認した後で修正を検証しました。

MATLAB / Octave は実行していません。数値の実行一致や過去の leaderboard の再現を確認したものではありません。
最終配布版のテストは代表的な録音に限り、全録音の網羅検証ではありません。
以下の過去の制約は旧 release の記録で、上記のケースで確認した範囲だけを更新しています。

## 公開済み 0.1.0 の検証 {#published-010-validation}

以下は 2026-10-07 に確認した [0.1.0 release](https://pypi.org/project/locata-torch/0.1.0/) の記録です。
署名付き tag `v0.1.0` は commit `23cf99c` を指します。
合成テスト、既存実データ、公開パッケージのインストールを分けて記載しています。
コマンドのデータパスは placeholder です。

## 自動 release 検証 {#automated-release-checks}

公開前に [stable CI](https://github.com/taishi-n/torchlocata/actions/runs/37613092362) と [release workflow](https://github.com/taishi-n/torchlocata/actions/runs/37613092841) が通過しました。

| 検証 | 結果 |
| --- | --- |
| 必須の合成テスト | 各 test job で 147 件通過、integration 12 件を対象外とした |
| Python / platform | Linux Python 3.10〜3.14、macOS Python 3.12、Windows Python 3.12 が通過 |
| 最小直接依存 | Linux Python 3.10、Torch 2.4.0、NumPy 1.26.0、SoundFile 0.12.0、platformdirs 4.3.8、filelock 3.20.0 が通過 |
| 品質 | Ruff、format、ty、lock の整合性が通過 |
| 配布物 | wheel / sdist build、metadata、license、型マーカー、entry point、asset の確認が通過 |
| README | 両配布物で `twine check --strict` が通過 |
| 独立した環境 | base wheel、download extra の wheel、sdist を checkout 外へ入れ、spawn 2 worker を含めて通過 |
| 文書 | Zensical strict build と local のページ・anchor・asset 検証が通過 |

表には検証済みの platform と最小依存の組み合わせを記載しています。
他の依存の組み合わせを網羅的に検証したものではありません。

### 合成テストの範囲 {#synthetic-coverage}

必須テストでは一時ディレクトリに小さな WAV とタブ区切り TXT を作ります。
数値順の index、複数アレイ・source ID、任意ファイルの不在、不正ファイル、波形と dtype、独立した時刻表、小数秒、日付跨ぎ、注釈時刻の重複、有効性フラグ、非自明な回転、角度境界を確認しました。

窓と loader では hop、末尾、短い録音、注釈の境界、部分読み込み、疎な TXT cache の上限、padding、mask、Subset、Sampler、shuffle、pickle、spawn 2 worker を確認しました。
README と tutorial は placeholder の root だけを fixture に置き換えて実行しています。

downloader には local HTTP server と合成 ZIP64 を使いました。
再開、Range の無視と不正、応答サイズ、再試行、hash、lock、空き容量、危険な元の ZIP 名、CRC エラー、作業用ディレクトリでの展開、ファイル一覧、prepared 状態からの復旧を確認しました。
これらは公式アーカイブや実際の音声・VAD 本体を検証するテストではありません。

## 既存データでの integration {#existing-data-integration}

Challenge 時代の既存 snapshot に対し、読み取り専用の 12 件がすべて通過しました。
pip でインストールした 0.1.0 でも確認しています。実行コマンドの例です。

```sh
LOCATA_ROOT=/path/to/LOCATA uv run pytest -m integration -v
```

ヘッダーから dev 72、eval 154 件のアレイ WAV を検出しました。
確認したヘッダーは dicit 15、dummy 4、eigenmike 32、benchmark2 12 チャンネル、48 kHz でした。
件数はこの snapshot の記録で、実装上の固定条件ではありません。波形本体の検証は代表的な録音を対象にしています。

| 録音 | 確認した構成 |
| --- | --- |
| `dev/task1/recording1/benchmark2` | 静止音源 `loudspeaker1` |
| `dev/task2/recording1/dicit` | 複数音源 `loudspeaker3`、`loudspeaker4` |
| `dev/task3/recording2/dummy` | 移動音源 `hendrik`、重複 pose 時刻 |
| `dev/task5/recording1/eigenmike` | 移動アレイ、音源 `christine` |
| `dev/task6/recording3/benchmark2` | 移動アレイ、音源 `christine`、`hendrik` |
| `eval/task1/recording1/eigenmike` | source 正解・音声・VAD なし |
| `eval/task4/recording3/dummy` | source ファイルなし |
| `eval/task6/recording3/benchmark2` | 移動アレイ、source ファイルなし |

部分波形は独立した SoundFile の読み込みと一致しました。
マイクの幾何情報、時刻表、存在する source pose と音声も確認しています。
静止音源の参照録音は全体を読み、155072 フレームと pose 389 行を確認しました。
音声は `15:40:25.068`、pose と required time は `15:40:25.064` から始まり、相対時刻は `0` と `-0.004` 秒です。
固定補正を加えず、実測の差を保持しました。全体読み込みの slice と窓の読み込みは完全に一致しました。

WAV のない `eval/task4/recording4/dicit` と `eval/task6/recording5/dicit` は除外し、警告と `missing_audio` に記録しました。
代表的な読み込みの前後でファイルサイズと更新時刻は一致しました。
データ本体の変更やリポジトリへのコピーはしていません。
実データの例はworker 0 と spawn 2 worker の両方で、48 kHz、`[4, 32, 48000]` のバッチを返しました。

## 公開配布物と独立した利用環境 {#published-distributions-and-independent-consumers}

PyPI の metadata は Apache-2.0、Python `>=3.10`、公開文書の URL を示していました。
公開 wheel / sdist の SHA-256 は、元の検証済み release 一覧および取得した配布物の byte と一致しました。

| 配布物 | SHA-256 |
| --- | --- |
| `locata_torch-0.1.0-py3-none-any.whl` | `611a166915b28ffab0a4dec93a2ae73c5ebb2dfc0ad2463b28ca3f382eaf2fb5` |
| `locata_torch-0.1.0.tar.gz` | `9a5440b772f0306ea7d9daa9daeeedbadea1f7023b9674655155340e0b3a9af9` |

| 利用環境の検証 | 結果 |
| --- | --- |
| 新しい Python 3.12 環境 | `python -m pip install "locata-torch==0.1.0"` で公開パッケージと依存をインストール |
| import 先 | 独立環境の `site-packages` を参照 |
| インストール後の smoke | 波形、時刻、padding、CLI、spawn 2 worker が通過 |
| pip で入れたパッケージと既存 snapshot | integration 12 件がすべて通過 |
| 実データの文書例 | worker 0 と 2 で期待する shape とサンプリング周波数を確認 |
| 別の uv プロジェクト、Python 3.13 | `uv add "locata-torch[download]"` で 0.1.0 を入れ、smoke と spawn が通過 |

stable の前には [0.1.0rc1 の TestPyPI リハーサル](https://github.com/taishi-n/torchlocata/actions/runs/37611388927)でも matrix と独立環境を確認しました。
両 index への upload は GitHub OIDC を使いました。

公開サイト `https://taishi.org/torchlocata/` の概要、tutorial、API は HTTP 200 を返しました。
[公開後 CI](https://github.com/taishi-n/torchlocata/actions/runs/37614741244) と [文書 deploy](https://github.com/taishi-n/torchlocata/actions/runs/37614811737) も通過しました。
[公開手順](release-plan.md#deploy-documentation-changes)に従い、hosted site は tag 付きパッケージとは独立して更新できます。

## 初回 release 検証の限界 {#limits-of-the-original-release-verification}

- この検証では公式 LOCATA アーカイブ全体をダウンロードしておらず、最終配布版の音声・注釈・VAD 本体は未検証でした。範囲を制限した ZIP64 directory の調査では、パス、ファイル名、展開サイズを確認し、member の内容は確認していません。
- 既存 snapshot には VAD と eval の source ファイルがありませんでした。合成 fixture での VAD と eval 正解の確認は、最終配布版の実ファイルを使う integration には代えられません。
- 座標の式は公式ソースと合成の軸・回転テストで確認しましたが、MATLAB を実行した比較はしていません。

確認したデータのバージョンと fingerprint は[参考資料](references.md)、固定アーカイブの metadata は[データの保存先](storage.md#release-and-disk-space)を参照してください。
raw reader は補間、リサンプリング、dense なラベル生成、評価を自動では行いません。
後から追加した解析 API は、このページの上部と[解析ガイド](analysis.md)に記載しています。
