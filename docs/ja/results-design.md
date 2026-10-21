# 結果の保存と集計

録音ごとの評価は型付きの辞書と CPU Tensor を返します。
保存にはバージョン付き JSON、CSV、任意の NPZ を使います。
描画関数は Figure を返し、保存先は呼び出し側で決めます。

## 保存する情報 {#goals}

JSON と CSV は Python、MATLAB、R、Julia、CLI ツールから読めます。
source / track ID、時刻原点、単位、欠損値、評価パラメータ、集計対象、指標の分母を保存し、後から再解析できます。
結果は読み取り専用の LOCATA データ本体とは別に保存します。

## bundle の構成 {#bundle-layout}

```text
experiment/
  manifest.json
  recordings.csv
  sources.csv
  periods.csv
  details/<recording-key>.npz   # Optional large frame-level arrays
```

UTF-8 の JSON manifest は、スキーマとパッケージのバージョン、参照 MATLAB の commit、指標定義の ID、データの release ID、アルゴリズム設定、座標の定義、単位、呼び出し側の出典情報を持ちます。
録音はマシン固有のパスでなく split / task / recording / array で識別します。カレンダー原点は小数秒を保持します。
JSON の欠損スカラーは `null` とし、NaN / Infinity は拒否します。配列は manifest に埋め込みません。

CSV は決まったヘッダーと 1 観測 1 行の形式で、文字列 ID を保持し、列名に SI 単位を示します。
数値の空欄は利用不能を表し、ゼロとは区別します。理由と、対象・観測の個数も残します。
音源別・区間別の表は再集計に必要な統計量を持ちます。spreadsheet の式、Python オブジェクト表現、入れ子の dict 文字列は出力しません。

任意の圧縮 NPZ は数値と bool の配列だけを保存し、`allow_pickle=False` で読みます。
shape と単位は JSON に記載します。NaN は未知値や誤差の意味を定義した配列だけで使えます。
大きな Python の解析では NPZ を使い、NPZ reader のないツールとは CSV を交換できます。
フレーム単位の CSV 書き出しには対応していません。MAT、HDF5、Parquet への依存はありません。

## 集計方法 {#aggregation-contract}

データ release、split、task、array、アルゴリズム設定、指標定義を指定して集計します。
評価設定が両立しない場合はエラーにし、dev/eval、ゲート閾値、角度の定義を混ぜません。

重み付けは録音を等しく扱う `recording` と、対象観測を集約する `pooled` から選びます。選択した方法は集計行に残します。
pooled の検出確率は検出数 / 機会数、誤警報率は誤 track 数 / 時間、角度誤差は誤差の合計 / 対応フレーム数です。
音声活動中の時間と録音時間を区別します。
完全に未検出の区間は遅延平均から除き、その区間数と検出確率は報告します。
未定義の値には分母と欠損数を付け、すべて欠損のグループも欠損のままにします。
既計算の平均を重みなしで平均しないでください。録音 ID の重複は拒否するか、別 trial として識別します。

`recordings.csv` は録音・指標ごとに 1 行、`sources.csv` は source ID を加えた表です。
両方に録音の識別情報、指標名、値、分子、分母、単位、欠損理由を残します。
`periods.csv` は開始・終了時刻、半開の行 index、活動・検出数、swap、fragment、遅延、方位角・傾斜角の誤差合計と個数を持ちます。
これらを使えば、元の MATLAB MAT workspace を使わず、発話単位の重み付けを外部で再計算できます。

集計結果は通常の dict です。各行は重み付け、単位、分子・分母、有効・欠損録音数を持ちます。
split、アルゴリズム、データ release、指標定義、評価設定の ID も保持します。
評価結果だけからアルゴリズムやデータ release は推定できないため、入力の一貫性は呼び出し側で管理してください。
bundle は指定した出典情報を保持します。

```python
from locata_torch import aggregate_results, read_results, write_results

write_results(
    [result],
    "/path/to/experiment/results",
    corpus_roots=("/path/to/LOCATA",),
    include_frame_arrays=True,
    provenance={"algorithm": "my-method", "corpus_release": "zenodo-3630471"},
)
bundle = read_results("/path/to/experiment/results")
summary = aggregate_results(
    bundle, group_by=("split", "task", "array"), weighting="pooled"
)
```

集計結果は標準の `json.dump` や `csv.DictWriter` で保存できます。pandas への変換や MAT への書き出しは必要ありません。

## 交換形式と公式 submission {#alternatives-and-compatibility}

JSON と CSV は内容を確認しやすく、多くのツールで読めます。NPZ を加えても表のスキーマは変わりません。
Parquet は大規模な解析に適していますが Arrow が必要で、現状の API には含めていません。
HDF5 は大きな配列に対応する一方、依存とスキーマの説明が必要です。
MAT は元の MATLAB 環境に合いますが、ツール間で共通に使う中心形式にはしていません。

`write_submission` は検証済み track から、主催者のタブ区切り DOA source ファイルを書きます。
カレンダー秒と track ID を保持し、指定した出力先の下だけに書き込み、実測の `telapsed.txt` を付けます。
数値時刻の原点は raw required time 表全体から決めます。
原点を選ぶ際は無効行も残しますが、推定値の出力からは除きます。
この形式と結果 bundle は別です。データ本体の再生成と MATLAB workspace の変換は reader の対象外です。

## API {#api-surface}

`locata_torch` から次の関数を import できます。

```python
write_results(results, output_dir, *, corpus_roots, include_frame_arrays=False)
read_results(output_dir)
aggregate_results(results, *, group_by, weighting)
write_submission(tracks, output_dir, *, required_time, corpus_roots, elapsed_seconds)
```

フレーム単位の診断結果には NPZ、ツール間の交換には小さい CSV 表を使います。
書き込み時には、環境変数とは別の場所でも実際に使っている corpus root を指定してください。
symlink を解決した保存先がその root 内にある場合や、保存先にすでに内容がある場合は拒否します。
`read_results` は manifest、録音別・音源別・区間別の表、任意のフレーム配列を持つ `ResultBundle` を返します。
スカラー CSV から `EvaluationResult` 全体を復元したことにはしません。
`aggregate_results` は `ResultBundle` も受け取り、NPZ がなくても再集計できます。
