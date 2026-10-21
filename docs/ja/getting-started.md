# 使い始める

## インストール {#install-the-package}

Python 3.10 以降が必要です。
PyPI の配布名は [`locata-torch`](https://pypi.org/project/locata-torch/)、import 名は `locata_torch` です。
アプリケーションの Python 環境でインストールしてください。

```sh
python -m pip install locata-torch
```

uv プロジェクトでは依存に追加します。

```sh
uv add locata-torch
```

ダウンロード機能を使う場合は、`download` extra を含めます。

```sh
python -m pip install "locata-torch[download]"
```

uv の場合は次のコマンドです。

```sh
uv add "locata-torch[download]"
```

0.1.0 を再現する場合は、`"locata-torch==0.1.0"` または `"locata-torch[download]==0.1.0"` と指定します。
パッケージのインストールには LOCATA データ本体を含みません。
展開済みデータを指定するか、[split をダウンロード](#download-a-split)してください。

## 録音とバッチを読む {#read-a-recording-and-a-batch}

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
print(waveforms.shape, batch["lengths"], sample["sample_rate"])
```

`/path/to/LOCATA` を、`dev/` または `eval/` が入った展開済みディレクトリに置き換えます。
例をアプリケーションの `read_locata.py` に保存し、パッケージをインストールした環境で実行します。

```sh
python read_locata.py
```

uv プロジェクトでは次のように実行します。

```sh
uv run python read_locata.py
```

`dataset[0]` は録音全体を読みます。窓を返す Dataset view は指定した WAV フレームだけを読みます。
`num_samples` と `hop_samples` はフレーム数です。48000 フレームが 1 秒になるのは 48 kHz の WAV に限ります。
`drop_last=True` では短い末尾を除きます。末尾も含める場合は `False` とし、バッチ化で padding します。

波形は CPU 上にあります。GPU などへの転送はアプリケーションで `batch["waveform"]` に対して行います。
注釈は独立した時刻を持ち、バッチ内ではサンプルごとの list になります。
DataLoader が学習用の dense なラベルを生成することはありません。

## 既存データを共有する {#share-an-existing-dataset}

複数のアプリケーションで共通の root を使うには、macOS/Linux の shell で次のように設定します。

```sh
export LOCATA_ROOT=/path/to/LOCATA
locata-torch path
```

PowerShell では `$env:LOCATA_ROOT = "/path/to/LOCATA"` とし、実際の Windows パスを指定します。
uv プロジェクトでは CLI の前に `uv run` を付けてください。
設定後はコンストラクタの `root` を省略できます。

```python
from locata_torch import LocataDataset

dataset = LocataDataset(split="dev", arrays=("eigenmike",))
sample = dataset[0]
```

保存先は引数 `root`、`LOCATA_ROOT`、準備済みの管理保存先の順に探します。
別のデータを選ぶ場合は `root` を指定すると環境変数より優先されます。
`~` はホームディレクトリに展開し、空または無効な設定はエラーにします。
reader の構築時にはダウンロードもディレクトリ作成も行いません。

## split をダウンロードする {#download-a-split}

`download` extra が必要です。DataLoader の worker を作る前にデータを準備します。

### Python API

```python
from locata_torch import LocataDataset, download_locata

root = download_locata(split="dev", data_dir="/path/to/locata-store")
dataset = LocataDataset(root=root, split="dev", arrays=("eigenmike",))
sample = dataset[0]
```

`/path/to/locata-store` は管理保存先に置き換えてください。既存の展開済みデータとは別のディレクトリを使います。
戻り値の root を指定すれば、`LOCATA_ROOT` が別のデータを指していても、このインストールを選べます。
両 split を扱う場合は、downloader と `LocataDataset` の両方に `split=("dev", "eval")` を渡します。

### CLI {#command-line-interface}

pip でインストールした環境では次のように実行します。

```sh
locata-torch download --split dev --data-dir /path/to/locata-store
```

uv プロジェクトでは次のコマンドです。

```sh
uv run locata-torch download --split dev --data-dir /path/to/locata-store
```

コマンドは展開後の root を出力します。そのパスを Dataset の `root` に指定してください。
`--split dev --split eval` のように `--split` を繰り返すと、両方を準備できます。

共通の保存先を継続して使う場合は、アプリケーションの環境変数に `LOCATA_DATA_DIR=/path/to/locata-store` を設定し、`--data-dir` を省略します。
PowerShell では `$env:LOCATA_DATA_DIR = "/path/to/locata-store"` を使います。
`LOCATA_ROOT` が未設定なら、reader はこの保存先の準備済みデータを探します。
`locata-torch path` で解決後の root を表示できます。
保存先の指定がなければ、OS 標準のユーザーデータディレクトリを使います。

`LOCATA_DATA_DIR` は管理保存先、`LOCATA_ROOT` は展開済みデータの root です。
再度ダウンロードを要求すると、準備済みデータを検証して再利用します。
[公式アーカイブ](https://zenodo.org/records/3630471)は split 全体を含み、読み込み時の task や array の選択では転送量を減らせません。
両 split の ZIP と展開済みデータを保持する場合は、少なくとも 120 GB の空きを用意してください。
サイズ、再開、検証、復旧の詳細は[データの保存先](storage.md)に記載しています。

## 録音を選ぶ {#select-recordings}

1 item は `(split, task, recording, array)` に対応します。

| 引数 | 既定値 | 指定できる値 |
| --- | --- | --- |
| `root` | `None` | 展開済み root の `str` / `Path`、または設定から検索 |
| `split` | `"dev"` | `"dev"`、`"eval"`、またはそれらの列 |
| `tasks` | `(1, 2, 3, 4, 5, 6)` | 1〜6 の整数からなる空でない列 |
| `recordings` | `None` | 全録音、または正の録音番号からなる空でない列 |
| `arrays` | `None` | 対応アレイすべて、またはアレイ名からなる空でない列 |
| `dtype` | `torch.float32` | `torch.float32` / `torch.float64` |
| `load_source_audio` | `False` | 利用できる source WAV を読むか |
| `cache_size` | `16` | worker ごとに保持する timestamp / VAD index の最大数。ゼロで cache を無効化 |
| `cache_bytes` | `16777216` | worker ごとの index の推定 byte 数。ゼロで cache を無効化 |

recording 番号の条件は選択したすべての task に適用します。有効な選択でも、該当する WAV がなければ長さはゼロです。
`drop_last=True` で全録音が窓より短い場合も、空の窓 Dataset になります。

`dataset.index` は変更できない `RecordingInfo` の tuple で、split 名、task 番号、recording 番号、array 名の順に並べます。
task と recording の番号、各サンプル内の source ID の番号部分は数値として並べます。
WAV のない既存アレイディレクトリは `dataset.missing_audio` と `MissingAudioWarning` で知らせます。
既存 WAV の必須ファイルが不正な場合は、パスと原因を含むエラーにします。

## source 音声と float64 {#load-source-audio-or-use-float64}

```python
import torch
from locata_torch import LocataDataset

dataset = LocataDataset(
    root="/path/to/LOCATA",
    split=("dev", "eval"),
    tasks=(1, 2),
    recordings=(1,),
    arrays=("benchmark2",),
    dtype=torch.float64,
    load_source_audio=True,
)
```

source の pose と VAD はsource 音声の読み込み設定にかかわらず、利用できる場合に返します。
dev/eval のどちらでもファイルの存在で判断します。
source 音声にはスピーカーからの再生音や close-talking 録音があり、無響の clean speech とは限りません。欠損した注釈は `None` のままです。

## 複数 worker を使う {#use-multiple-workers}

複数 worker での読み込みは[読み込みと DataLoader](io-and-dataloader.md#multiple-workers-and-samplers)の例を参照してください。
`spawn` と `__main__` guard を含むスクリプトをアプリケーションに保存し、`python read_locata.py` または `uv run python read_locata.py` で実行します。

サンプルとバッチの詳細は[データ形式](data-model.md)、時刻の扱いは[時刻と窓](time-and-windows.md)、シグネチャは [API リファレンス](api.md)に記載しています。
