# 参考資料と設計方針

## 一次資料 {#primary-sources-reviewed}

reader の資料は 2026-10-07 に確認しました。研究用 reader は仕様比較に参照し、コードのコピー、翻訳、機能移設は行っていません。
2026-10-21 に追加した解析処理は、主催者の MATLAB コードに基づくアルゴリズムの再実装です。
対応するソースと変更点は[MATLAB に基づく定位と評価](analysis.md)に記載しています。
Python は独自に書いたもので、機械的な翻訳ではありません。
[NOTICE](https://github.com/taishi-n/torchlocata/blob/main/NOTICE) に MATLAB の帰属を記載し、[Apache-2.0 LICENSE](https://github.com/taishi-n/torchlocata/blob/main/LICENSE) とともに wheel / sdist に含めます。
LOCATA データの ODC-BY 1.0 は別のライセンスです。データ本体と MATLAB ソースは再配布しません。

| 出典 | 確認したバージョン | ライセンスと利用内容 |
| --- | --- | --- |
| [LOCATA Datasets](https://www.locata.lms.tf.fau.de/datasets/) | 内容の確認日 2026-10-07 | 最終配布版と dev の修正告知を確認。ページ自体の再利用条件は未確認。 |
| [LOCATA final release](https://zenodo.org/records/3630471) | v1, 2020-01-31, DOI 10.5281/zenodo.3630471 | [metadata API](https://zenodo.org/api/records/3630471) の license ID は `odc-by`。データの条件と Python 実装のライセンスは別です。 |
| [Final Release Documentation](https://www.locata.lms.tf.fau.de/files/2020/01/Documentation_LOCATA_final_release_V1.pdf) | Version 1.0, 2020-01-31 | 最終 dev/eval の source 正解、VAD 名、world / local 座標を確認。PDF 自体の再利用条件は未確認。 |
| [cevers/sap_locata_io](https://github.com/cevers/sap_locata_io/tree/632468f49b13ca5a9f2f51c064d91183c06622fa) | commit `632468f49b13ca5a9f2f51c064d91183c06622fa` | MATLAB ヘッダーは ODC-BY 1.0。仕様と式を参照し、コードは再利用していません。 |
| [cevers/sap_locata_eval](https://github.com/cevers/sap_locata_eval/tree/2787cdabf21bc96453c0d4f3c66db9c9c9f40434) | commit `2787cdabf21bc96453c0d4f3c66db9c9c9f40434`、確認日 2026-10-21 | 主催者の評価・VAD 処理を Python 解析の基にしています。ヘッダーは ODC-BY 1.0。同梱の第三者製割り当て solver は再利用していません。 |
| [Cross3D reader](https://github.com/DavidDiazGuerra/Cross3D/blob/2532cf57160aef67f7fdedccc7452aa422ea7a24/acousticTrackingDataset.py) | commit `2532cf57160aef67f7fdedccc7452aa422ea7a24` | AGPL-3.0。task 1/3/5 の制限、pandas / webrtcvad / gpuRIR 依存、リサンプリング、無音除去、補間を確認。コードは再利用していません。 |
| [SRP-DNN reader](https://github.com/BingYang-20/SRP-DNN/blob/e67c2a9d24d8707048f38e09146fb2d3cbc9be8d/code/Dataset.py) | commit `e67c2a9d24d8707048f38e09146fb2d3cbc9be8d` | MIT、Copyright 2023 BingYang。複数音源の列挙と `VAD` 列を参照。前処理、必須 VAD、追加依存は採用せず、コードも再利用していません。 |
| [PyTorch torch.utils.data](https://docs.pytorch.org/docs/2.9/data.html) | 2.9 のバージョン固定文書 | map-style Dataset、Sampler、collate、spawn、pickle の仕様を確認。PyTorch は BSD 系ライセンス。文書のコード例はコピーしていません。 |

確認した MATLAB reader は `utils/load_data.m`、`struct2time.m`、`struct2position.m`、`get_truth.m`、`mycart2sph.m` です。
最終配布版のリポジトリにも古い `is_dev` による source 読み込み制限が残っていますが、この reader はファイルの存在で判断します。
座標変換には `get_truth.m` の `R'*(h-p)`、角度には `mycart2sph.m` の方位角と傾斜角を使います。MATLAB を実行した比較はしていません。

2026-10-21 には、I/O framework の `MUSIC.m`、`stft.m`、`check_results.m`、`results2csv.m`、`plot_results.m`、`struct2csv.m`、`csv2struct.m`、`init.m` も確認しました。
evaluation framework では `read_ground_truth.m`、`measures.m`、`measures_statistics.m`、`main_evaluation.m`、`figures_for_paper.m`、`stats_for_paper.m` を確認しました。
`matlab_v2` として配布された Challenge 時代の snapshot には、同じ主要アルゴリズム、STFT、座標、描画処理がありました。参照コードは上記の commit 固定 URL から辿れます。
snapshot の音源名一覧は匿名化前のものです。解析 API には旧名の固定一覧や `is_dev` による正解の読み込み制限を組み込んでいません。
公開評価スクリプトには、外部 MAT ファイルやリポジトリ内にない関数への参照があるため、元の workflow 全体がそのまま動くと確認したものではありません。

結果保存は数値配列に [NumPy NPZ](https://numpy.org/doc/stable/reference/generated/numpy.savez_compressed.html)、metadata と表に標準の JSON / CSV を使います。
これらは設計上の参照で、コードの再利用ではありません。
描画は任意の [Matplotlib Figure API](https://matplotlib.org/stable/api/_as_gen/matplotlib.figure.Figure.html) と Agg canvas を使い、表示・保存せず Figure を返します。

## 保存先とダウンロードの参考資料 {#storage-and-download-design-references}

次のツールを、パス設定とデータ準備の設計に参照しました。コードは再利用していません。
rolling documentation と上流の license ファイルの確認日は 2026-10-07 です。

| 出典 | 確認したバージョン | 参考にした設計と上流ライセンス |
| --- | --- | --- |
| [Torchvision CIFAR10](https://docs.pytorch.org/vision/stable/generated/torchvision.datasets.CIFAR10.html) | 0.29 文書 | root の指定と、要求した場合だけダウンロードする設計。 [BSD-3-Clause](https://raw.githubusercontent.com/pytorch/vision/main/LICENSE) |
| [TensorFlow Datasets](https://www.tensorflow.org/datasets/api_docs/python/tfds/load) | API ページ更新日 2024-04-26 | 環境変数による保存先、バージョン別データ、準備と利用の分離。 [Apache-2.0](https://raw.githubusercontent.com/tensorflow/datasets/master/LICENSE) |
| [Hugging Face Hub](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache) | 確認日時点の cache ガイド | revision ごとの snapshot を共通の保存先で管理する設計。 [Apache-2.0](https://raw.githubusercontent.com/huggingface/huggingface_hub/main/LICENSE) |
| [Pooch](https://www.fatiando.org/pooch/latest/api/generated/pooch.create.html) | 1.9.0 | 既知 hash の registry と、変更できる保存先。 [BSD-3-Clause](https://raw.githubusercontent.com/fatiando/pooch/v1.9.0/LICENSE.txt) |

locata-torch はデータの準備と読み取り専用の Dataset 構築を分けます。
保存先は Python パッケージのバージョンとは別のデータ release ID を使い、複数のプロジェクトや仮想環境で 1 つのインストールを共有します。
再開と作業用ディレクトリを使う配置処理は、標準ライブラリの HTTP、hash、ZIP64 処理で実装しています。

[platformdirs](https://platformdirs.readthedocs.io/en/latest/api.html#platformdirs.user_data_path) で OS 標準の永続保存先を選びます。
最小バージョン 4.3.8 と解決済みの 4.12.3 は MIT です。
任意の [filelock](https://py-filelock.readthedocs.io/en/latest/) は process lock に使い、最小 3.20.0 は Unlicense、解決済みの 4.0.12 は MIT です。
filelock は downloader だけが import します。上流 branch の license 記録を、このライブラリのライセンスとして扱うことはありません。
実装した仕様と固定 archive metadata は[データの保存先](storage.md)、packaging と Trusted Publishing は[公開手順](release-plan.md)を参照してください。

## Challenge 時代の snapshot {#challenge-era-snapshot}

既存の Challenge 時代の snapshot を読み取り専用で確認しました。
資料は documentation v2（2018-04-05）、v3（2018-04-17）、5 つの MATLAB reader 関数です。
公開資料は [documentation v3](https://www.locata.lms.tf.fau.de/files/2018/06/documentation_v3.pdf) と下表の commit 固定ソースを参照してください。
現在のデータ準備には[最終配布版の文書](https://www.locata.lms.tf.fau.de/files/2020/01/Documentation_LOCATA_final_release_V1.pdf)を使います。

checksum は確認したコピーを識別するもので、このリポジトリの同梱ファイルや利用者の必須ファイルを表しません。
v2 のファイル名は履歴上の識別子です。そのコピーの公開 URL は未確認です。

| 確認資料 | 確認したコピーの SHA-256 |
| --- | --- |
| 最終配布版 documentation v1 | `05c2b6948b5783ffcf59126a238ce14b4c29b072d3472189f5d5ffd320654c25` |
| `documentation_v2.pdf` | `84747303cb4a4dac0d7e850f12c105c8cca5f73ca7d6b21bf1aef3caf9811f31` |
| `documentation_v3.pdf` | `0679e408963c529d61e83a19c6f0a32133df67da07fb9e3581689670f00c698b` |
| [`load_data.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/load_data.m), Challenge 時代のコピー | `6636167192bd2f21079b9d55241815cea49f6c54cc00f2eda447dd90aa3f9e9d` |
| [`struct2time.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/struct2time.m) | `703242dec2087f78c7465e2bbb84744709ef13594c57bd720e1cde690954c1d0` |
| [`struct2position.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/struct2position.m) | `b7f78cdaa3336d85e53e6372e9da4eb741fb75c3ee2464086af99f8b9185657c` |
| [`get_truth.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/get_truth.m) | `ed77f68076e316b673e7a1dac26bdcc96f62ab65cc901c1facf28fa7d3a2e8f1` |
| [`mycart2sph.m`](https://github.com/cevers/sap_locata_io/blob/632468f49b13ca5a9f2f51c064d91183c06622fa/utils/mycart2sph.m) | `0625681763e3303490a716562dd8ea182ce83782c49b583f7947411af5d789ea` |


`load_data.m` 以外の 4 関数は参照 GitHub commit と byte 単位で一致しました。
snapshot のアレイ WAV は dev 72、eval 154 件でした。次の既存ディレクトリには WAV がありませんでした。

- `eval/task4/recording4/dicit`
- `eval/task6/recording5/dicit`

この snapshot の dev には source 音声と pose があり、eval には source ファイルがなく、両 split とも VAD はありませんでした。
件数や欠損パスは実装に固定していません。これらは最終配布版の integration 検証とは区別しています。

## 設計方針と制約 {#design-decisions-and-constraints}

- 録音と窓を返す Dataset を分けます。録音 index はヘッダーだけを読み、窓は録音ごとの累積個数を保持します。
- 検証済みの疎な TXT index で元の時刻を保持します。各 worker の初回は全体を逐次読み、index は上限付きメモリ内だけに置きます。worker 間で共有せず、データ本体には書きません。
- 窓の注釈には実際の半開の時刻区間を使います。アレイと source の音声はサンプリング周波数や開始時刻が異なっていても構いません。
- 欠損は `None`、存在する空の区間は空の Tensor です。有効性フラグは VAD と区別します。
- DOA には同じ時刻を要求し、raw reader は注釈の時刻や回転を補間しません。
- 非等間隔の時刻も保持します。最後の音声サンプルの次の終端だけに名目上の `1/fs` を使います。
- 境界の比較だけに `1e-12` 秒の許容差を使います。元の時刻と 4 ms のずれは保持します。
- raw reader は有限でない world 座標と無効行も保持し、DOA helper は有限の幾何情報だけを受け付けます。
- snapshot には、hendrik の `dev/task3/recording2/dummy` に 53 組、christine の `dev/task5/recording1/eigenmike` に 210 組、christine の `dev/task6/recording3/benchmark2` に 115 組の source pose 重複時刻がありました。注釈は単調非減少、音声は狭義単調増加とし、注釈行はすべて保持します。
- Challenge 時代の snapshot に VAD はなく、初期の名前・値のテストには公式資料、SRP-DNN の `VAD` 列、合成 fixture を使いました。その後の最終 eval の VAD 検証は[検証記録](validation.md#unreleased-matlab-based-analysis-update-2026-10-21)に分けて記載しています。
- dense なラベルへの変換、学習変換 framework、汎用 plugin、互換性の別名は提供していません。
- 開発には pytest、Ruff、ty、文書には `docs` group の Zensical と mkdocstrings を使います。ガイドは英語と日本語で提供し、生成 HTML は追跡しません。GitHub Actions は配布物と文書を検証してから OIDC で公開します。

source 音声が完全な clean な学習 target であることは保証していません。また、公式評価ツールの代替としての一致も確認していません。

## 文書ツールの資料 {#documentation-tooling}

[Zensical の設定](https://zensical.org/docs/setup/basics/)、[言語設定](https://zensical.org/docs/setup/language/)、[offline 利用](https://zensical.org/docs/setup/offline/)、[mkdocstrings 互換性](https://zensical.org/docs/compatibility/mkdocs/plugins/)、[mkdocstrings-python](https://mkdocstrings.github.io/python/usage/) に従います。
実行したチェックは[検証記録](validation.md)に記載しています。これらは文書のビルド用で、ライブラリの import 時には使いません。
