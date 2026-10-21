# 読み込みと DataLoader

## 録音の検出とエラー {#recording-discovery-and-errors}

Dataset の構築時には、ディレクトリ名、アレイ WAV のヘッダー、必須ファイルの存在を確認します。
波形本体や音声サンプルごとの時刻表は読み込みません。
実在する WAV を基準に録音の index を作り、ZIP、結果ファイル、MATLAB コードは対象にしません。

選択対象のアレイディレクトリはあるものの WAV がない場合は index から除き、`missing_audio` と `MissingAudioWarning` で知らせます。
全録音に全アレイがあるとは仮定しません。存在しないディレクトリに対する警告も作りません。

| 状態 | 動作 |
| --- | --- |
| 既存のアレイディレクトリにアレイ WAV がない | 警告して index から除く |
| 既存 WAV のヘッダーが無効、または必須ファイルがない | 構築時に `LocataError` |
| TXT 行・値の異常、行数の不一致 | 最初の関連アクセスで `LocataError` |
| 任意の注釈がない | split に関係なく `None` |
| 読み込んだ任意ファイルが不正 | パスと原因を含む `LocataError` |

必須ファイルはアレイ WAV、その時刻 TXT、アレイ位置 TXT、`required_time.txt` です。
source ファイルの有無はそれぞれ独立に扱います。
source 音声を読まず、source VAD もその時刻表を必要としない場合、source WAV と時刻表の内容の検証は保留します。
既存ファイルの不正を、データの不在として処理することはありません。

## 部分読み込みと worker の cache {#partial-reads-and-bounded-worker-caches}

窓は SoundFile で WAV 内の必要位置へ移動し、指定されたフレームだけを読みます。
録音全体を読み込んでから窓を切り出す処理は行いません。

音声時刻表と VAD は各 worker の最初のアクセスで全体を逐次読み込みし、検証します。
4096 行ごとにファイル位置を記録し、以後は対象区間の近くから読みます。
非等間隔の場合も含め、実際の時刻を保持します。未検証の等間隔の時刻には置き換えません。
比較的小さい pose と required time の表は item ごとに読み、時刻で切り出します。

worker ごとの LRU cache は、既定で `cache_size=16` ファイル、推定 index サイズ `cache_bytes=16777216` byte を上限とします。
上限を超える index はそのアクセスで利用しますが、cache に残しません。
cache からの削除後や、いずれかの上限をゼロにした場合は、次のアクセスで再び全体を検証します。
検証中の一時メモリと返すサンプルは、この cache 上限とは別です。

Dataset は開いたファイルハンドルを保持しません。pickle 化や process の変更で cache をリセットします。
データ本体の下に disk cache や index を書き込むこともありません。
Dataset を使っている間は入力ファイルを変更しないでください。

## バッチ化 {#collation}

`collate_locata(samples)` は空でないバッチを受け取り、アレイ、サンプリング周波数、チャンネル数、波形の dtype が共通であることを要求します。
混在する場合は、理由が分かる `ValueError` を返します。

| バッチのフィールド | 表現 |
| --- | --- |
| `waveform` | `[B, C, T_max]`、右側をゼロで padding |
| `lengths` | `[B]`、int64、元の波形の長さ |
| `audio_mask` | `[B, T_max]`、bool、元の音声フレームだけ True |
| `sample_rate` | 共通の `int`、Hz |
| `audio_time`、`time_origin` | サンプルごとの元の値を持つ list |
| `required_time`、`array_pose` | 元の型付き注釈を持つ list |
| `sources`、`metadata` | 音源の辞書と録音 ID をサンプルごとに保持する list |

`audio_mask=False` は padding だけを表し、無音、音源の活動、`valid_flag` は表しません。
注釈の長さや音源数はサンプル間で異なることがあります。
collate は補間、正解の padding、dense なラベルの生成をしません。

Dataset の Tensor は CPU 上にあります。
バッチを読み込んでから、`batch["waveform"].to(device)` などで波形を転送してください。

## 複数 worker と Sampler {#multiple-workers-and-samplers}

録音と窓の Dataset、およびトップレベルの collate 関数は pickle 化できます。
標準の `Subset`、`SequentialSampler`、`RandomSampler`、DataLoader の shuffle に対応します。

複数 worker では `multiprocessing_context="spawn"` を使い、loader の作成と反復を main guard の内側に置きます。

```python
from locata_torch import LocataDataset, collate_locata
from torch.utils.data import DataLoader


def main():
    dataset = LocataDataset(root="/path/to/LOCATA", arrays=("eigenmike",))
    windows = dataset.windows(num_samples=48000, hop_samples=24000)
    loader = DataLoader(
        windows,
        batch_size=4,
        shuffle=True,
        num_workers=2,
        multiprocessing_context="spawn",
        collate_fn=collate_locata,
    )
    batch = next(iter(loader))
    print(batch["waveform"].shape)


if __name__ == "__main__":
    main()
```

[DataLoader の実行例](https://github.com/taishi-n/torchlocata/blob/main/examples/read_locata.py)も用意しています。
取得とセットアップは[開発手順](development.md#install-and-run-checks)、worker 0 と spawn の確認結果は[検証記録](validation.md)を参照してください。
上流の multiprocessing の仕様は [PyTorch DataLoader documentation](https://docs.pytorch.org/docs/2.9/data.html)に記載されています。
