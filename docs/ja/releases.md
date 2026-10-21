# リリースノート

## 0.2.0 / 2026-10-21 {#020-2026-10-21}

### 機能 {#features-020}

- MATLAB に基づく正解情報の準備、アレイ時刻に対応する VAD 処理、単一音源 MUSIC、track 評価を追加しました。解析ガイドには参照した公式 MATLAB の版と関数、指標定義 `locata-torch-v1`、変更点を記載しています。
- 任意の `plot` extra で診断用の図を描けます。reader の import に Matplotlib は必要ありません。
- JSON / CSV と任意の数値 NPZ による結果の保存、録音単位・pooled の集計、公式 submission 形式の書き出しを追加しました。
- 注釈の重複時刻は出現順を保持します。音声範囲内だけを評価する場合は時刻範囲を指定します。

### ドキュメント {#documentation}

- README と導入ガイドを、pip / uv で公開パッケージをインストールし、アプリケーションから使う流れに整理しました。
- データパス、必要容量、ダウンロードの動作を保存先のガイドにまとめました。
- 保守担当者向けの公開手順と、公開済みバージョンの検証記録を整理しました。
- ナビゲーションを利用方法、プロジェクト情報、開発ガイドに分けました。
- 日本語 README と全 15 ガイドを追加しました。Zensical 標準の言語メニューを使い、ナビゲーションと検索 index を言語ごとに持ちます。
- 公開文書からマシン固有のパスと手元環境の一覧を除きました。

### 検証と制約 {#validation-and-limits-020}

必須の合成テストは 193 件通過しました。両言語のビルド、local link、品質検査、wheel / sdist の確認も通過しています。
実データの解析検証には Challenge 時代の snapshot と最終配布版 eval の代表的な録音を使い、LOCATA アーカイブのダウンロードはしていません。
合成テストと実データそれぞれの結果は[検証記録](validation.md)に記載しています。

reader と downloader の契約は 0.1.0 から変えていません。
解析は必要な関数を呼び出して行い、CPU Tensor と欠損注釈を保持します。MUSIC は単一音源 baseline です。
MATLAB を実行した数値比較と、過去の leaderboard の再現は確認していません。

## 0.1.0 / 2026-10-07 {#010-2026-10-07}

[PyPI](https://pypi.org/project/locata-torch/0.1.0/) で公開しています。
`python -m pip install locata-torch` または `uv add locata-torch` でインストールします。
ダウンロード機能には `locata-torch[download]` を使います。

### 機能 {#features-010}

- task 1〜6、4 種のアレイに対応する録音・固定長窓の PyTorch Dataset。決定的な index と WAV の部分読み込み。
- 独立した時刻表、アレイと source の幾何情報、元の source ID、任意の source 音声と VAD を持つ型付き CPU サンプル。
- 長さと mask を返す padding 付き collate。Subset、Sampler、shuffle、spawn worker に対応。
- pose の時刻を照合する world-to-array 変換、方位角、傾斜角の helper。
- 引数 root、`LOCATA_ROOT`、準備済みの管理保存先によるデータ共有。Dataset の構築は読み取り専用。
- 公式配布版の再開、hash、ZIP64 展開、process lock、ファイル一覧、prepared 状態からの復旧を検証する任意の downloader。
- `locata-torch` CLI、コードの Apache-2.0 ライセンス、英語ドキュメント。

### 検証と制約 {#validation-and-limits-010}

Python 3.10〜3.14、Linux / macOS / Windows、最小直接依存を含む構成で、147 件の合成テストが通過しました。
公開 wheel / sdist の hash は検証済み配布物と一致しました。
独立した pip / uv 環境で spawn worker を含む動作を確認し、pip で入れたパッケージで既存データの integration test 12 件も通過しました。

公式最終配布版の音声、注釈、VAD 全体をダウンロードして検証したものではありません。
転送・展開テストは合成アーカイブ、実データテストは既存の Challenge 時代の snapshot を使いました。
この release の範囲と配布物の hash は[検証記録](validation.md)に記載しています。

## 0.1.0rc1 / 2026-10-07 {#010rc1-2026-10-07}

0.1.0 の release candidate として [TestPyPI](https://test.pypi.org/project/locata-torch/0.1.0rc1/) に公開しました。
reader と downloader の API は同じです。stable release の前に CI matrix と独立したインストール環境でのリハーサルを確認しました。
