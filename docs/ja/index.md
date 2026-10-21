# locata-torch

LOCATA の音声と注釈を、PyTorch の map-style `Dataset` と `DataLoader` で読み込みます。
[PyPI の locata-torch](https://pypi.org/project/locata-torch/) をインストールし、アプリケーションで `locata_torch` を import してください。Python 3.10 以降が必要です。

録音単位のデータセット、固定長の窓、padding 付きバッチ、LOCATA の座標変換、任意のダウンロード機能を備えています。
返す Tensor はすべて CPU 上にあります。
task 1〜6 と `benchmark2`、`dicit`、`dummy`、`eigenmike` に対応し、複数音源と移動アレイも扱います。

## 目的から探す {#start-here}

| 目的 | ガイド |
| --- | --- |
| pip / uv でインストールし、最初のバッチを読む | [使い始める](getting-started.md) |
| 既存データを共有する、split をダウンロードする | [データの保存先](storage.md) |
| クラス、関数、型定義を調べる | [API リファレンス](api.md) |
| 複数 worker、Sampler、可変長バッチを使う | [読み込みと DataLoader](io-and-dataloader.md) |
| MATLAB に基づく MUSIC、GT/VAD 処理、評価、描画を使う | [定位と評価](analysis.md) |
| 結果を保存する、集計の重みを選ぶ | [結果の保存と集計](results-design.md) |

展開済みデータの構成は次のとおりです。

```text
LOCATA/
├── dev/
│   └── task1/
│       └── recording1/
│           └── benchmark2/
│               ├── audio_array_benchmark2.wav
│               ├── audio_array_timestamps_benchmark2.txt
│               ├── position_array_benchmark2.txt
│               └── required_time.txt
└── eval/
    └── task1/...
```

実在する WAV を基準に index を作ります。チャンネル数、サンプリング周波数、フレーム数は WAV ヘッダーから取得します。
source の位置・姿勢、音声、VAD は任意です。dev/eval のどちらでも、ファイルの存在から利用できる情報を判断します。

## 注釈を扱う {#work-with-annotations}

Tensor の shape、単位、source ID、欠損値は[データ形式](data-model.md)に記載しています。
独立した時刻表、カレンダー時刻の原点、窓の区間は[時刻と窓](time-and-windows.md)、回転と角度の定義は[座標と到来方向](geometry.md)を参照してください。

reader は振幅、チャンネル順、時刻、無効な注釈行を保持します。
無音除去、リサンプリング、正規化、補間、dense なラベルへの変換は自動では行いません。
欠損した正解は欠損のまま保持し、有効性フラグと音声活動を区別します。

## プロジェクト情報 {#project-information}

コードは Apache-2.0、LOCATA データには別途 ODC-BY 1.0 の帰属表示条件が適用されます。
出典、ライセンス、設計方針は[参考資料](references.md)、確認済みの構成と未検証の範囲は[検証記録](validation.md)にまとめています。

履歴は[リリースノート](releases.md)、開発・文書ビルドは[開発手順](development.md)、保守担当者向けの操作は[公開手順](release-plan.md)を参照してください。
データの修復、RIR 合成、学習、公式評価指標、他 corpus は raw reader の対象外です。
解析 API は LOCATA に基づく指標を別途提供します。MATLAB を実行した数値比較や過去の leaderboard の再現は確認していません。
TorchRIR への依存はありません。

解析 API には 0.2.0 以降が必要です。描画には `plot` extra も必要です。
インストール、録音の読み込み、ダウンロードは[使い始める](getting-started.md)を参照してください。
