# locata-torch

[English](https://github.com/taishi-n/torchlocata/blob/main/README.md) | 日本語

LOCATA の録音・時刻・位置注釈を、PyTorch の `Dataset` と `DataLoader` から読み込むライブラリです。
[locata-torch](https://pypi.org/project/locata-torch/) をインストールし、`locata_torch` として import します。

録音単位のデータセット、固定長の窓、可変長バッチ、座標変換、定位・評価処理、公式データのダウンロードに対応しています。
返す Tensor はすべて CPU 上にあります。TorchRIR とは独立して動作します。

## インストール

Python 3.10 以降が必要です。利用する環境に合わせてインストールしてください。

| 環境 | 既存データの読み込み | ダウンロード機能も使う場合 |
| --- | --- | --- |
| pip | `python -m pip install locata-torch` | `python -m pip install "locata-torch[download]"` |
| uv プロジェクト | `uv add locata-torch` | `uv add "locata-torch[download]"` |

実行時の依存は PyTorch、NumPy、SoundFile、platformdirs です。
`download` extra は filelock を追加します。LOCATA のデータ本体は別途用意します。

## 最初の読み込み

展開済みの `dev/` または `eval/` が入ったディレクトリを指定します。

```python
from locata_torch import LocataDataset, collate_locata
from torch.utils.data import DataLoader

dataset = LocataDataset(
    root="/path/to/LOCATA",
    split="dev",
    tasks=(1, 2, 3, 4, 5, 6),
    arrays=("eigenmike",),
)
sample = dataset[0]
waveform = sample["waveform"]  # [channels, samples], CPU float32
windows = dataset.windows(num_samples=48000, hop_samples=24000, drop_last=True)
loader = DataLoader(
    windows,
    batch_size=4,
    shuffle=True,
    num_workers=0,
    collate_fn=collate_locata,
)
batch = next(iter(loader))
waveforms = batch["waveform"]  # [batch, channels, padded_samples]
```

`/path/to/LOCATA` をデータの保存先に置き換えてください。
窓の長さは WAV のフレーム数で指定します。48000 フレームが 1 秒に相当するのは、サンプリング周波数が 48 kHz の場合です。
読み込みには実際の WAV ヘッダーを使い、振幅、チャンネル順、サンプリング周波数を保持します。

1 件の録音は `(split, task, recording, array)` に対応します。
`split`、`tasks`、`recordings`、`arrays` で対象を選択できます。
対応範囲は task 1〜6 と `benchmark2`、`dicit`、`dummy`、`eigenmike` です。
task と recording を数値順に並べ、同じ選択では常に同じ順序の index を作ります。
録音単位と窓単位の両方で、`Subset`、標準 Sampler、shuffle を使えます。

波形の既定 dtype は `torch.float32` です。`dtype=torch.float64` で変更できます。
source 音声は `load_source_audio=True` を指定したときだけ読み込みます。
複数 worker を使う場合は、[DataLoader ガイド](https://taishi.org/torchlocata/ja/io-and-dataloader.html#multiple-workers-and-samplers)の例に従い、`spawn` と `__main__` guard を使ってください。

## 既存データを複数のアプリケーションで共有する

環境変数に保存先を設定すると、同じデータを複数のアプリケーションから参照できます。

```sh
export LOCATA_ROOT=/path/to/LOCATA
locata-torch path
```

設定後は `LocataDataset(split="dev", arrays=("eigenmike",))` のように `root` を省略できます。
保存先は引数 `root`、`LOCATA_ROOT`、準備済みの管理保存先の順に探します。
無効なパスを設定した場合はエラーになります。`~` はホームディレクトリに展開します。
Dataset の構築時にはダウンロードもファイルの書き込みも行いません。

## LOCATA をダウンロードする

`download` extra をインストールし、DataLoader の worker を作成する前にデータを準備します。

```python
from locata_torch import LocataDataset, download_locata

root = download_locata(split="dev", data_dir="/path/to/locata-store")
dataset = LocataDataset(root=root, split="dev", arrays=("eigenmike",))
```

CLI からも利用できます。管理保存先を共有する場合は `LOCATA_DATA_DIR` を設定してください。

```sh
export LOCATA_DATA_DIR=/path/to/locata-store
locata-torch download --split dev --split eval
```

uv プロジェクトでは CLI コマンドの前に `uv run` を付けます。
`LOCATA_DATA_DIR` はダウンロード用の管理保存先、`LOCATA_ROOT` は展開済みデータの root を指定します。
保存先を指定しない場合は、OS 標準のユーザーデータディレクトリを使います。

対象は [LOCATA 公式の最終配布版](https://zenodo.org/records/3630471)、DOI `10.5281/zenodo.3630471` です。
split 全体を取得し、サイズと MD5 を検証します。識別済みの途中ファイルから再開し、作業用ディレクトリで ZIP64 を展開してから配置します。
同じデータを再度要求した場合は、準備済みのファイルを検証して再利用します。
両 split の ZIP と展開済みデータを保持すると約 103.8 GB になるため、新規導入時は少なくとも 120 GB の空きを用意してください。
split ごとのサイズ、整合性確認、復旧手順は[データの保存先](https://taishi.org/torchlocata/ja/storage.html)を参照してください。

## データ形式

各 item は `LocataSample` 型の dict で、次のフィールドを持ちます。

- `waveform`、`sample_rate`、フレームごとの `audio_time`。
- `time_origin`。録音全体のアレイ音声の最初のカレンダー時刻です。小数秒を保持し、各時刻をこの原点からの相対秒で表します。
- `required_time`。推定対象時刻と `valid_flag`。
- `array_pose`。アレイの位置、参照ベクトル、回転、マイク位置と、それぞれの時刻。
- `sources`。元の source ID をキーとする位置・姿勢、任意の音声と VAD。
- `metadata`。録音 ID、パス、フレーム区間、時刻の範囲。

時刻と幾何情報は float64、フラグは bool です。音声と注釈は、それぞれの時刻表を保持します。
注釈がない場合は `None`、ファイルはあるものの窓内に該当する行がない場合は空の Tensor を返します。
source の有無は dev/eval の名前ではなく、ファイルの存在から判断します。
`valid_flag` と VAD は別の情報です。欠損した正解をゼロで補うことはありません。
source 音声が無響の clean speech であることは保証していません。

窓は必要な WAV フレームだけを読み、録音全体の時刻原点を保ちます。
注釈は各時刻表に従い、開始を含み終了を含まない区間で切り出します。
`drop_last=False` の短い末尾は`collate_locata` でバッチ化するまで短いままです。
バッチには `lengths` と padding 部分を区別する `audio_mask` を付けます。
注釈と source の辞書はサンプルごとの list として保持します。
バッチ内ではアレイ、サンプリング周波数、チャンネル数、波形の dtype を揃えてください。

座標変換には LOCATA の `R.T @ (h - p)` を使います。
`locata_doa` は同じ時刻の pose を要求し、+y を基準とする方位角 `[-pi, pi)`、+z から測る傾斜角 `[0, pi]`、距離を返します。
角度の単位は rad、距離は m です。

## 定位と評価

ここで説明する定位・評価 API には 0.2.0 以降が必要です。
診断用の描画も使う場合は `plot` extra を含めてインストールしてください。

```sh
python -m pip install "locata-torch[plot]>=0.2.0"
```

解析 API は主催者の MATLAB [I/O framework](https://github.com/cevers/sap_locata_io/tree/632468f49b13ca5a9f2f51c064d91183c06622fa) と [evaluation framework](https://github.com/cevers/sap_locata_eval/tree/2787cdabf21bc96453c0d4f3c66db9c9c9f40434) に基づきます。
Dataset の出力とは別に呼び出して使います。
対応する MATLAB 関数、単位、式、変更点、検証範囲は[定位と評価](https://taishi.org/torchlocata/ja/analysis.html)に記載しています。

```python
from locata_torch import (
    MusicConfig,
    evaluate_locata,
    music_localize,
    prepare_ground_truth,
)

truth = prepare_ground_truth(sample, time_bounds=sample["metadata"]["time_bounds"])
estimate = music_localize(sample, config=MusicConfig())
# Evaluation requires source poses and known array-aligned VAD at every
# selected time. Missing annotations raise an error rather than imply silence.
result = evaluate_locata(truth, [estimate["track"]])
metrics = result["metrics"]  # Per-recording metrics, with explicit denominators.
```

`prepare_ground_truth` は有効な required time を選び、時刻を照合して pose を対応付けます。行番号での対応付けや回転の補間はしません。
`align_vad` は VAD 自身の時刻を使い、直前サンプルの値を保持して対象時刻へ対応付けます。
VAD の範囲外は NaN、不在は `None` のままです。`activity_periods` は既知の活動区間を半開の index 区間として返します。

`music_stft` は参照コードのフレーム分割と対称 Hamming 窓を再現します。
`music_localize` は単一音源の MUSIC baseline です。マイク選択、ブロック処理、推定値の補間を設定でき、source の正解情報は使いません。
ブロックごとの推定値と検証済みの `DOATrack` を返します。
`validate_tracks` は ID、時刻、shape、角度の単位、NaN による未推定値を確認します。
`EvaluationConfig` でゲートと OSPA のパラメータを指定します。
計算できないスカラー指標は `None`、フレームごとの誤差は NaN とし、ゼロ誤差には置き換えません。

`plot` extra を使うと `plot_scene`、`plot_doa`、`plot_evaluation` を利用できます。
いずれも Matplotlib の Figure を返し、表示や保存は呼び出し側で行います。
ライブラリの import 時には Matplotlib を読み込みません。
[解析の実行例](https://github.com/taishi-n/torchlocata/blob/main/examples/analyze_locata.py)には定位、評価、保存、描画をまとめています。

`aggregate_results` では集計対象と重み付け `recording` または `pooled` を指定します。
`write_results` と `read_results` はバージョン付き JSON、CSV、必要に応じて pickle を使わない NPZ を読み書きします。
`write_submission` は公式のタブ区切り結果形式への書き出しです。
すべての書き出しで保存先を指定し、データ本体の root 配下には書き込めません。
欠損値、分母、単位、交換形式は[結果の保存と集計](https://taishi.org/torchlocata/ja/results-design.html)を参照してください。
データ本体の書き換えと MATLAB workspace の変換は対象外です。

## ドキュメントと問い合わせ

ドキュメントは [English](https://taishi.org/torchlocata/) と[日本語](https://taishi.org/torchlocata/ja/index.html)で読めます。
Zensical 標準のヘッダーメニューから各言語のトップページへ移動できます。
生成した HTML ファイルを直接開いて読むこともできます。
[使い始める](https://taishi.org/torchlocata/ja/getting-started.html)、[API リファレンス](https://taishi.org/torchlocata/ja/api.html)、[データ形式](https://taishi.org/torchlocata/ja/data-model.html)、[時刻と窓](https://taishi.org/torchlocata/ja/time-and-windows.html)、[座標と到来方向](https://taishi.org/torchlocata/ja/geometry.html)を用意しています。

reader は無音除去、リサンプリング、正規化、補間、無効行の削除を自動では行いません。解析処理は必要なものを呼び出して使います。
データの修復、RIR 合成、モデル学習、他 corpus は対象外です。
[検証記録](https://taishi.org/torchlocata/ja/validation.html)では合成テスト、既存実データでの検証、未検証の範囲を区別しています。
不具合は [issue tracker](https://github.com/taishi-n/torchlocata/issues)で報告してください。

コードのライセンスは [Apache-2.0](https://github.com/taishi-n/torchlocata/blob/main/LICENSE) です。
MATLAB の出典は [NOTICE](https://github.com/taishi-n/torchlocata/blob/main/NOTICE) に記載しています。
LOCATA データには別途 ODC-BY 1.0 の帰属表示条件があり、パッケージにはデータ本体を含みません。
詳細は[参考資料とライセンス](https://taishi.org/torchlocata/ja/references.html)、開発への参加は[開発手順](https://taishi.org/torchlocata/ja/development.html)を参照してください。
