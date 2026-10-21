# データ形式

`LocataSample` は公開の `TypedDict` です。Dataset が返す Tensor はすべて CPU 上にあります。
波形には選択した float32 または float64、時刻と幾何情報には float64、フラグと VAD には bool を使います。

`T` は音声フレーム数、`C` は WAV のチャンネル数、`P` は各注釈表の行数を表します。
注釈表ごとに行数は異なります。音声サンプル番号と注釈の行番号は、対応する index として扱いません。

## 録音と窓のサンプル {#recording-and-window-samples}

| フィールド | shape / 型 | 内容 |
| --- | --- | --- |
| `waveform` | `[C, T]`、float32 / float64 | 元の WAV の振幅とチャンネル順 |
| `sample_rate` | `int` | WAV ヘッダーのサンプリング周波数、Hz |
| `audio_time` | `[T]`、float64 | アレイ音声の時刻、原点からの相対秒 |
| `time_origin` | `CalendarTime` | 録音全体のアレイ音声の最初の時刻 |
| `required_time` | `RequiredTime` | 推定対象時刻と、その有効性フラグ |
| `array_pose` | `ArrayPose` | アレイの基準点、姿勢、マイクの幾何情報 |
| `sources` | `dict[str, Source]` | 音源ごとの位置・姿勢、任意の音声と VAD |
| `metadata` | `RecordingMetadata` | 録音 ID、パス、フレーム区間、時刻範囲 |

`CalendarTime` は `(year, month, day, hour, minute, second)` で、先頭 5 要素が整数、小数秒を含む最後の要素が float です。
source 音声を含め、すべての時刻表がこの原点を共有します。
カレンダー時刻の変換と区間の定義は[時刻と窓](time-and-windows.md)を参照してください。

`RecordingMetadata` は `id`、`split`、`task`、`recording`、`array`、`path`、`start_frame`、`stop_frame`、`num_frames`、`time_bounds` を持ちます。
ID は `split/taskN/recordingN/array`、`path` はアレイディレクトリを表す `Path` です。
`num_frames` はアレイ WAV 全体の長さ、`[start_frame, stop_frame)` は item が返す区間です。
`time_bounds` は開始と終了の相対秒を格納した組です。

## 推定対象時刻 {#required-estimation-times}

| フィールド | shape | 内容 |
| --- | --- | --- |
| `time` | `[P]`、float64 | `required_time.txt` の時刻、相対秒 |
| `valid_flag` | `[P]`、bool | 元の 0/1 の有効性フラグ |

`valid_flag` と VAD は独立した情報です。無効行も保持し、活動ラベルへの変換や自動の行削除は行いません。

## 位置・姿勢とマイク位置 {#poses-and-microphone-positions}

`Pose` は 1 音源の位置・姿勢の表です。`ArrayPose` はマイク位置も持ちます。

| フィールド | shape | 内容 |
| --- | --- | --- |
| `time` | `[P]` | この位置ファイルの時刻、相対秒 |
| `time_origin` | カレンダー時刻の組 | サンプルの共通原点 |
| `position` | `[P, 3]` | 基準点の world xyz、m |
| `ref_vec` | `[P, 3]` | world 座標の参照ベクトル、無次元 |
| `rotation` | `[P, 3, 3]` | local から world への回転、行・列の順 |
| `microphone_position` | `[P, C, 3]` | アレイのみ。各マイクの world xyz、m |

OptiTrack の world 座標軸は East、North、Up で、録音ごとの校正基準に従います。
world 原点が異なる録音間で共通とは限りません。
回転は `rotation_ij` の列を保持します。マイクは `mic1`〜`micC` を WAV のチャンネル順に並べます。
world からアレイへの変換は[座標と到来方向](geometry.md)に記載しています。

raw サンプルに含まれる幾何情報の NaN は保持します。
有効性フラグと時刻をどう利用するかは呼び出し側で決めます。DOA helper は有限でない幾何情報をエラーにします。

## 複数音源と任意の source 音声 {#multiple-sources-and-optional-audio}

source ID は位置、音声、時刻、対応する VAD のファイル名から検出します。
元の文字列を保持し、番号部分を数値として並べます。
複数音源に対応し、dev/eval のどちらでも存在する正解注釈を読みます。
source のファイルがなければ `sources` は空の dict です。

各 `sources[id]` は次のフィールドを持ちます。

| フィールド | 型 | 内容 |
| --- | --- | --- |
| `pose` | `Pose` / `None` | 利用できる音源の位置・姿勢 |
| `audio` | `SourceAudio` / `None` | 要求した場合だけ読む source WAV |
| `audio_available` | `bool` | 読み込みの設定にかかわらず、source WAV が存在するか |
| `vad` | `SourceVAD` | アレイ時刻と source 時刻の VAD を別々に保持 |

`SourceAudio` は `waveform [C_source, T_source]`、`sample_rate`、`audio_time [T_source]`、`start_frame`、`stop_frame` を持ちます。
WAV ヘッダーと時刻表はアレイ音声とは独立しています。時刻はサンプルの共通原点からの相対秒です。
source 音声が無響の clean speech であることは保証していません。

## 音声活動 {#voice-activity}

`SourceVAD` は `array` と `source` を持ちます。
それぞれ `time [T_vad]` と bool の `values [T_vad]` を持つ `TimedVAD`、または `None` です。時刻の単位は相対秒です。

- `array` は `VAD_{array}_{id}.txt` をアレイ音声の時刻表に対応付けます。
- `source` は `VAD_source_{id}.txt` をその source 音声の時刻表に対応付けます。

VAD TXT はタブ区切りで、`VAD` 列の値は 0 または 1 です。
WAV、時刻表、VAD の行数は一致する必要があります。
source VAD には source WAV と時刻ファイルが必要ですが、WAV の波形本体を読むかは別途選択できます。

## 欠損、空の区間、非活動の区別 {#missing-empty-and-inactive-data}

| 表現 | 意味 |
| --- | --- |
| `None` | 注釈が利用できない、または source 音声の読み込みが無効 |
| `audio_available=True`、`audio=None` | source 音声はあるが読み込みを要求していない |
| 末尾の次元を保った空の Tensor | ファイルはあるが、この窓に該当する行や音声フレームがない |
| VAD の `False` | 利用できる VAD 時刻での既知の非活動 |
| `valid_flag=False` | 活動とは独立した、無効な推定対象時刻 |

欠損した正解と VAD をゼロで補うことはありません。存在する音源が無音であることと、注釈の不在を区別します。
バッチの shape と padding mask は[バッチ化](io-and-dataloader.md#collation)を参照してください。
