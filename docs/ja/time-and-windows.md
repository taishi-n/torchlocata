# 時刻と窓

## 独立した時刻表と共通原点 {#independent-clocks-and-a-shared-origin}

アレイ音声、アレイの pose、`required_time`、source の pose、source 音声は、それぞれの時刻表を使います。
カレンダー列は `year`、`month`、`day`、`hour`、`minute`、`second` です。小数秒と日付の変化を保持します。

各時刻を、録音全体のアレイ音声の最初の時刻からの相対秒に変換します。
元のカレンダー時刻は `time_origin` に残り、窓や pose も同じ原点を使います。
変換にはカレンダー時刻の差を使い、大きな float の Unix 時刻を引き算する方法は使いません。
ファイルにタイムゾーンの情報がないため、UTC とは仮定しません。

確認した snapshot の `dev/task1/recording1/benchmark2` では、アレイ音声が `15:40:25.068`、pose と `required_time` が `15:40:25.064` から始まります。
最初の相対時刻はそれぞれ `0.0` 秒と `-0.004` 秒です。
この差はファイルから読み取り、他の録音に固定補正として適用しません。
WAV は 155072 フレーム、pose は 389 行で、両者は異なる時刻表を持ちます。

カレンダー値は有限で有効な値である必要があります。音声の時刻は狭義単調増加でなければなりません。
pose と required time の時刻は同値の繰り返しを許す単調非減少とし、snapshot 内で見つかった同一時刻の注釈を元の順序で保持します。
reader は並べ替え、重複排除、補間、無効行の削除をしません。うるう秒には対応していません。

## 窓を返す Dataset view {#construct-a-window-view}

`dataset.windows(num_samples=..., hop_samples=None, drop_last=True)` は map-style の `LocataWindowDataset` を返します。
窓の長さと hop は正の整数の WAV フレーム数です。hop の既定値は窓の長さと同じです。

開始位置は `0, hop, 2*hop, ...` です。区間は開始を含み終了を含まない `[start_frame, stop_frame)` で表します。

| 設定 | 含める開始位置 | 末尾の扱い |
| --- | --- | --- |
| `drop_last=True` | 録音内に完全な窓が収まる位置のみ | 窓より短い録音からは窓を作らない |
| `drop_last=False` | 録音の終端より前のすべての位置 | 短い末尾はバッチ化まで短いまま保持 |

窓が重なる場合、短い末尾が複数できることがあります。hop が窓の長さより大きいと、読み込まない区間ができます。
10 フレームの録音を長さ 6、hop 4 で切ると、末尾を除く場合は `[0,6)` と `[4,10)` です。
末尾も含める場合は `[8,10)` が加わります。

すべての窓を列挙して保持する代わりに、録音ごとの窓数を累積して保持します。
録音の選択、dtype、source 音声の読み込み、cache の設定は親 Dataset から引き継ぎます。

## 時刻範囲と注釈の切り出し {#determine-time-boundaries}

`metadata["time_bounds"] = (a, b)` は、`start_frame` と `stop_frame` の実際の timestamp を使います。
`stop_frame` が WAV のフレーム数と一致する場合、終了時刻は最後の timestamp に `1 / sample_rate` を加えた値です。
非等間隔の時刻表はそのまま保持し、名目上のサンプル周期を使うのはこの最終端だけです。

pose、required time、source 音声、VAD は、それぞれの時刻表で `a <= time < b` に当たる部分を選びます。
窓の外側の pose 行は追加しません。録音全体の原点を保持するため、窓内の最初の時刻はゼロとは限りません。
ファイルはあっても該当する行がなければ、定義された shape の空の Tensor を返します。

区間の境界比較には `1e-12` 秒の許容差を使います。この範囲の値は境界上とみなし、開始の行は含め、終了の行は除きます。
返す時刻を丸めたり補正したりする処理ではなく、4 ms の開始差も保持します。

録音単位の item はアレイ音声の範囲外も含め、存在する注釈表と source 音声のすべてを返します。
異なる pose 表の同じ行が同時刻とは限りません。
[DOA helper](geometry.md#time-alignment) は時刻を揃えた pose を要求します。
