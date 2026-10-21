# MATLAB に基づく定位と評価

LOCATA 主催者の MATLAB ツールに基づき、定位・評価のアルゴリズムを Python で実装しています。
Dataset の読み込みとは別に呼び出して使います。raw reader は元の時刻表、無効行、欠損注釈を保持します。
評価には以下の指標定義を使い、過去の leaderboard との一致は確認していません。

## 出典 {#provenance}

| Python の機能 | 基になる MATLAB コード |
| --- | --- |
| `prepare_ground_truth`, `locata_doa` | [`get_truth.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/get_truth.m), [`mycart2sph.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/mycart2sph.m) |
| `align_vad`, `activity_periods` | [`read_ground_truth.m`](https://github.com/cevers/sap_locata_eval/blob/2787cdabf21bc96453c0d4f3c66db9c9c9f40434/functions/read_ground_truth.m) |
| `music_stft`, `music_localize`, `MusicConfig` | [`stft.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/stft.m), [`MUSIC.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/MUSIC.m), [`init.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/init.m) |
| `validate_tracks` | [`check_results.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/check_results.m) |
| `evaluate_locata`, `EvaluationConfig` | [`measures.m`](https://github.com/cevers/sap_locata_eval/blob/2787cdabf21bc96453c0d4f3c66db9c9c9f40434/functions/measures.m) |
| `plot_scene`, `plot_doa`, `plot_evaluation` | [`plot_results.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/plot_results.m), 描画部分: `measures.m` |
| `write_submission` | [`results2csv.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/results2csv.m) |
| `aggregate_results`, portable bundles | [`measures_statistics.m`](https://github.com/cevers/sap_locata_eval/blob/2787cdabf21bc96453c0d4f3c66db9c9c9f40434/functions/measures_statistics.m) が集計の出発点。[保存形式](results-design.md)は独自の設計 |

I/O framework は commit `632468f49b13ca5a9f2f51c064d91183c06622fa`（2020-01-31）、evaluation framework は `2787cdabf21bc96453c0d4f3c66db9c9c9f40434`（2020-02-06）を確認しました。確認日は 2026-10-21 です。
該当する MATLAB ヘッダーには Christine Evers、Heiner Löllmann と ODC-BY 1.0 の記載があり、[NOTICE](https://github.com/taishi-n/torchlocata/blob/main/NOTICE) に帰属を残しています。
Python の Tensor / 配列処理は独自に書いたもので、MATLAB ファイルや同梱の第三者製 Hungarian / Munkres 実装を再配布・翻訳したものではありません。
Python コードは Apache-2.0 です。データのライセンスと原著論文は[参考資料](references.md)を参照してください。

## 正解情報と音声活動 {#ground-truth-and-voice-activity}

`prepare_ground_truth(sample, time_bounds=None)` は `GroundTruth` を返します。
`time` は `required_time.valid_flag` で選んだ float64 `[T]`、`array_pose` は時刻で選んだ pose です。
`sources` は source ID を保持し、各音源の `doa: DOA | None` と `activity: Tensor | None` を格納します。
録音 ID などは `metadata` に残します。

pose の照合は 1 ns 以内で一致する時刻を要求します。
量子化された同じ時刻に異なる pose が並ぶ場合、照会側と同じ個数の出現があれば元の順序で対応付けます。
異なる pose の重複数が合わず、対応が曖昧な場合はエラーにします。同じ値の重複 pose は再利用できます。
required time とその重複は元の順に保持します。
source pose の不在は `None`、アレイ pose の不在や不一致はエラーです。

`time_bounds=(start, stop)` を指定すると、共通原点からの秒数で表した半開区間内の有効行を選びます。既定では切り出しません。
注釈が音声より先に始まる録音を音声の範囲で評価するには、`time_bounds=sample["metadata"]["time_bounds"]` を指定します。
この選択でも欠損 VAD を非活動には変えません。submission の書き出しには元の required time 表全体を渡します。

`align_vad(vad, time, sample_rate=...)` は 0、1、NaN を含む float64 `[T]` を返します。
VAD の実際の音声時刻で直前サンプルの値を保持し、サンプル境界では新しいサンプル側に含めます。
範囲は最後の時刻から実際の 1 サンプル周期後までで、その外側は NaN です。
時刻表に空白がある場合、直前サンプルの 1 周期を越えた区間は未知のままです。
境界の比較には 1 ps の許容差を使いますが、返す時刻は変えません。
`prepare_ground_truth` が使うのはアレイ時刻に対応した VAD だけです。
close-talking の VAD は時刻と伝搬の基準が異なるため、代わりに使いません。

`activity_periods(activity)` は、既知の活動区間の開始・終了 index を int64 `[K, 2]` で返します。終了 index は含みません。
未知の値が入ると既知の区間を分け、先頭・末尾の活動も保持します。

## 単一音源の MUSIC {#single-source-music}

`MusicConfig` の既定値は MATLAB baseline に従います。
対称な 30 ms の Hamming 窓、窓長の 1/4 の hop、要求 FFT サイズ 1024、ブロック長 100 フレーム、ブロック間隔 10、音速 340 m/s を使います。
周波数は 800 Hz より大きく、1400 Hz 未満の帯域を選びます。
探索間隔は方位角 5 度、傾斜角 10 度です。
DICIT はゼロ始まりのチャンネル `(5, 6, 8)`、MATLAB では `(6, 7, 9)` を使い、他のアレイはすべての WAV チャンネルを使います。
チャンネル、探索格子、フレーム分割は設定で変更できます。

`music_stft` は `STFTResult` を返します。
`spectrum` は complex128 `[frames, frequencies, channels]`、フレーム時刻は相対秒の float64、周波数は Hz の float64 です。
`stft.m` と同じ先頭・末尾のゼロ、2 のべき乗の FFT、中央を揃える FFT padding、`fft_size/2` に基づく時刻を使います。
FFT サイズが窓より短い場合も、MATLAB と同じ切り詰めを行います。
したがって 48 kHz の既定設定では、窓は 1440 サンプル、変換は 1024 点です。

`music_localize(sample, config=...)` は有効な required time とアレイ pose を使い、source pose と VAD は使いません。
音声時刻は等間隔で WAV のサンプリング周波数と一致する必要があり、欠落がある場合はエラーにします。
STFT 時刻は窓の開始位置と録音原点のずれを保持します。
ブロックの幾何情報には選択した pose の範囲内で最も近いアレイ pose を使います。
外挿や回転の補間は行わず、pose の範囲外のブロックは利用不能のままです。

周波数ごとの空間共分散は `X.T @ X.conj()` です。
最大固有値の固有ベクトルを 1 次元の信号部分空間、残りを雑音部分空間とします。
ステアリングベクトルは world 座標のマイク位置と、回転した LOCATA 方向から求めます。
雑音部分空間への射影の逆数を周波数について加算します。
処理は共分散ブロックと探索格子ごとに行い、周波数・格子・ブロックをすべて積んだ 4 次元 Tensor は保持しません。
エネルギーがゼロのブロックは任意の方向を選ばず NaN とし、同値の格子点があれば平坦化した順で最初を選びます。

`MusicResult` は `track`、ブロックの時刻・方位角・傾斜角、設定、実測の `elapsed_seconds` を持ちます。
`elapsed_seconds` はアルゴリズムの実測経過時間で、Dataset の読み込み時間は含みません。
推定値の補間は隣接する有限の 2 ブロック間だけで行い、方位角は短い弧に沿うよう unwrap します。
欠落区間や範囲外は NaN です。参照コードの、方位角の不連続点をまたぐ直接補間とは異なります。
波形の無音除去、リサンプリング、正規化は行いません。

## track と評価 {#tracks-and-evaluation}

`DOATrack` は `id: str`、`time_origin`、float64 の `time: [N]` と `azimuth: [N]`、任意の `inclination: [N]` を持ちます。
角度は rad で、方位角は `[-pi, pi)`、+z からの傾斜角は `[0, pi]` です。
NaN の方位角はその時刻の未推定、`inclination=None` は傾斜角の不在を表します。
ID は空でなく、track 間で一意である必要があります。
量子化された重複時刻は、正解と出現数が合えば順に照合します。
値が異なる重複の数が合わない場合はエラーとし、同じ推定値の繰り返しは再利用できます。
時刻原点は正解と一致する必要があります。track にない時刻は未検出とし、評価時には推定値を補間しません。

`evaluate_locata(truth, tracks, config=...)` には source DOA と、対象範囲をすべて覆う既知のアレイ VAD が必要です。
欠損ラベルや VAD の範囲外はエラーにします。活動と `valid_flag` は別の情報です。
対応付けは活動中の音源と有限の track だけを対象とし、wrap した方位角の距離と、既定では境界を含む 30 度のゲートを使います。
有効な組の数を最大にしてから、合計角度誤差を最小にする割り当てを選びます。
長方形行列の割り当ては独自実装で、SciPy には依存しません。
傾斜角の誤差は方位角で対応した組のうち、傾斜角がある組で求めます。

OSPA はゲートを適用しない方位角距離を度数で計算し、30 度で打ち切ります。
次数は `(1, 1.5, 2, 5)`、1 対 1 の最小コスト割り当てと、標準の要素数差の penalty を使います。
両集合が空ならゼロ、片方だけが空なら打ち切り値です。
フレームごとの角度誤差 Tensor は rad、スカラーの角度誤差と OSPA は度数です。対応のない index は `-1` です。

録音ごとの指標は `value`、`numerator`、`denominator`、`unit` を持ちます。
定義できない値は分母ゼロの `None` です。
検出確率は「対応した活動音源フレーム数 / 活動音源フレーム数」、誤警報率は「誤 track フレーム数 / 録音時間」で、単位は参照カウンタと同じ track-frames/s です。
音声活動中の誤警報率では、活動区間の合計時間で割ります。
角度誤差は有限で対応済みの観測を集約し、OSPA は両集合が空のゼロ距離も含めてフレーム平均します。

録音時間は評価時刻の最後と最初の差です。活動区間の長さも、その区間の最後と最初の時刻の差で、1 行だけの区間はゼロです。
検出遅延は最初の検出時刻から区間開始を引いて求めます。
完全に未検出の区間の遅延は利用不能とし、検出・未検出区間の数には残します。
track swap は MATLAB と同じく未検出や非活動をまたいで最後に割り当てた track と比較します。
fragmentation は遅れて検出した場合も含む未検出から検出への遷移数に swap を加え、`measures.m` に従って数えます。
率は活動音源の区間長を分母に集計し、`sources` と `periods` に対応する統計量を残します。

## MATLAB 評価との違い {#deliberate-changes-from-the-matlab-evaluator}

指標定義 `locata-torch-v1` には次の変更を加えてテストしています。過去の leaderboard との一致は確認していません。

- 独立した音声時刻、実際のサンプリング周波数、VAD の有効範囲を使います。固定の 48 kHz・ゼロ始まりの時刻や、最後の VAD の引き延ばしは使いません。
- pose は行番号でなく時刻で照合します。
- 対応付けと OSPA は活動中の音源だけを対象にします。`measures.m` には非活動の音源も距離行列に入る箇所があります。
- OSPA の長方形行列を保持します。参照コードには平坦化した行列を `Hungarian` に渡す分岐があります。
- 傾斜角の誤差を計算します。参照コードには `error_el_ss` に方位角誤差を代入する分岐があります。
- 検出遅延は最初の検出から求めます。参照コードの `this_miss` に対する探索は、この定義と一致しない場合があります。
- 先頭・末尾の活動、空の track、無音、同コスト時の割り当て、傾斜角の欠損、未定義の率を扱います。
- 参照コード独自の `MOTA` 変数を、標準的な MOTA としては公開しません。
- 発話・音源・録音の平均をさらに平均する処理を自動適用せず、フレームごとの統計量を残します。区間 CSV には角度誤差の合計と個数を保存し、重みを選んで再集計できます。

## 描画と保存 {#plotting-and-persistence}

`plot` extra は Matplotlib を追加します。`locata_torch` の import だけでは読み込みません。
描画関数は非対話の Figure API で Figure を作り、単位を付け、NaN の区間を保持します。保存・表示は行いません。
scene 図は音源とアレイの軌跡、番号付きマイクを示します。DOA 図の第 2 角度は inclination と表示します。
評価図には活動、方位角誤差、未検出、誤 track、swap、OSPA を表示します。

JSON / CSV / NPZ、重み付け、公式 submission の書き出しは[結果の保存と集計](results-design.md)を参照してください。

`write_submission` には無効行も含む raw の `RequiredTime` 表と、実測の `elapsed_seconds` が必要です。
`telapsed.txt` と source ごとの TSV を書きます。
数値の `timestamps` の原点は MATLAB `main.m` と同じく最初の raw required time です。
カレンダー列は音声の共通原点との対応を保持します。
録音全体の submission には required time 表全体と、すべての有効行を覆う track を渡してください。切り出した窓だけでは完全な Challenge submission になりません。
DOA の方位角、任意の傾斜角、一貫した文字列 ID に対応します。距離・Cartesian 推定値と参加者情報の spreadsheet には対応していません。
実行時間の manifest は出典情報で、Challenge の規定フィールドではありません。

## 一連の処理を実行する {#end-to-end-use}

解析 API には 0.2.0 以降が必要です。
リポジトリの例を実行するには、[ソースリポジトリ](https://github.com/taishi-n/torchlocata)を取得し、root で `plot` extra をインストールして[解析例](https://github.com/taishi-n/torchlocata/blob/main/examples/analyze_locata.py)を実行します。

```sh
git clone https://github.com/taishi-n/torchlocata.git
cd torchlocata
uv sync --extra download --extra plot --group docs
uv run python examples/analyze_locata.py --root /path/to/LOCATA \
  --split eval --task 1 --recording 1 --array benchmark2 \
  --output /path/to/experiment --evaluate --plot --coarse-grid
```

この例は録音全体を読み、粗い MUSIC 格子を指定して、結果 bundle、公式形式の source ファイル、診断用 PNG をデータ本体の外へ保存します。
参照格子を使うには `--coarse-grid` を外します。
評価には音源位置と既知のアレイ VAD が必要です。ない録音では `--evaluate` を外してください。
単一音源 baseline は複数音源 tracker ではありません。

窓単位では `music_localize(window)` と `prepare_ground_truth(window)` を直接呼びます。
窓の結果は別々に保存し、重なった窓を独立した録音として集計したり、録音 ID を上書きしたりしないでください。
実験ごとの trial / window ID を呼び出し側で指定します。

## 検証範囲 {#validation-limits}

合成テストは解析的な例、独立した NumPy の STFT / MUSIC 参照計算、小さな割り当ての全探索を使います。
実データの integration test は `LOCATA_ROOT` を指定した場合だけ実行します。
開発環境で MATLAB / Octave は実行していません。ソースに基づく比較はMATLAB を実行した数値一致の確認とは区別してください。
実行済みの検証は[検証記録](validation.md)に記載しています。
