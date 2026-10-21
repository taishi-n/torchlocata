# 座標と到来方向

## world からアレイへの変換 {#world-to-array-coordinates}

[公式 MATLAB 実装](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/get_truth.m)では world 座標の音源位置 `h`、アレイ原点 `p`、local から world への回転 `R` から、アレイ座標のベクトルを求めます。

```text
v = R.T @ (h - p)
```

`world_to_array(source_position, array_position, array_rotation)` は、同時刻の値として渡された Tensor にこの式を適用します。
位置の末尾次元は `3`、回転は `[3, 3]` で、先行する次元は broadcast できる必要があります。出力は float64 です。
幾何情報が有限であること、回転の直交性、行列式が `+1` であることを、絶対・相対許容差 `1e-5` で検証します。

raw Dataset は有限でない幾何情報も保持しますが、この helper はエラーにします。

## 角度の定義 {#angle-convention}

`locata_doa(array_pose, source_pose)` は `DOA` 型の dict を返します。

| フィールド | shape | 単位と定義 |
| --- | --- | --- |
| `vector` | `[P, 3]` | アレイ座標の xyz、m |
| `azimuth` | `[P]` | +y をゼロとする方位角、`[-pi, pi)` rad |
| `inclination` | `[P]` | +z から測る傾斜角、`[0, pi]` rad |
| `range` | `[P]` | アレイから音源までの距離、m |

[公式の球座標変換](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/mycart2sph.m)は方位角を `atan2(v_y, v_x) - pi/2` として wrap し、elevation と呼ぶ角度を `acos(v_z / norm(v))` で計算します。
このライブラリでは水平面からの仰角と区別するため、後者を `inclination` と呼びます。

| アレイ座標の方向 | 方位角 | 傾斜角 |
| --- | --- | --- |
| +y | `0` | `pi/2` |
| +x | `-pi/2` | `pi/2` |
| -x | `pi/2` | `pi/2` |
| -y | `-pi` | `pi/2` |
| +z | `-pi/2` | `0` |
| -z | `-pi/2` | `pi` |

-y の境界は `-pi` で表します。MATLAB が返すことのある `+pi` と同じ方向です。
z 軸上の方位角は `atan2(0, 0)` に従い、`-pi/2` と表します。
距離がゼロの場合は方向を定義できないためエラーにします。

## 時刻の一致 {#time-alignment}

`locata_doa` には、pose の時刻表とカレンダー原点が完全に一致する必要があります。
pose 配列の行の shape も一致しなければなりません。
一致しない場合は `ValueError` とし、異なる時刻の注釈行を対応付けません。

reader に補間機能はありません。到来方向を求める前に、呼び出し側で時刻を揃え、有効な pose を用意してください。
回転行列を要素ごとに線形補間する操作には対応していません。
時刻と切り出しの定義は[時刻と窓](time-and-windows.md)、シグネチャは [API リファレンス](api.md)を参照してください。
