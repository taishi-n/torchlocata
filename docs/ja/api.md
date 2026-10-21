# API リファレンス

公開オブジェクトは `locata_torch` から import します。
以下のシグネチャ、型、docstring は共通の Python ソースから生成します。docstring は英語です。

コンストラクタの既定値と選択条件は[使い始める](getting-started.md)、shape と欠損値は[データ形式](data-model.md)、時刻は[時刻と窓](time-and-windows.md)、cache と worker は[読み込みと DataLoader](io-and-dataloader.md)を参照してください。

| 処理 | 関数・クラス | 内容 |
| --- | --- | --- |
| 録音を読む | `LocataDataset`、`LocataWindowDataset` | 録音全体、またはフレーム数で指定した窓を返す |
| バッチを作る | `collate_locata` | 波形を padding し、長さと音声 mask を返す |
| データを用意する | `download_locata` | 公式 split を検証して管理保存先に配置する |
| 座標と角度を求める | `world_to_array`、`locata_doa` | 同時刻の位置・姿勢からアレイ座標と DOA を計算する |
| 正解を選ぶ | `prepare_ground_truth` | required time と pose を時刻で対応付ける |
| 活動を扱う | `align_vad`、`activity_periods` | VAD を対象時刻へ対応付け、既知の活動区間を求める |
| MUSIC を使う | `music_stft`、`music_localize`、`MusicConfig` | STFT と単一音源の定位を実行する |
| track を評価する | `validate_tracks`、`evaluate_locata`、`EvaluationConfig` | track を検証し、検出・角度・追跡の指標を求める |
| 図を作る | `plot_scene`、`plot_doa`、`plot_evaluation` | scene、DOA、評価結果の Figure を返す |
| 結果を保存・集計する | `write_results`、`read_results`、`aggregate_results`、`ResultBundle` | JSON / CSV / NPZ を読み書きし、重みを指定して再集計する |
| submission を書く | `write_submission` | 公式形式の DOA source ファイルを書き出す |

`RecordingInfo`、`CalendarTime`、`RecordingMetadata`、`LocataSample`、`LocataBatch`、`RequiredTime`、`Pose`、`ArrayPose`、`Source`、`SourceAudio`、`SourceVAD`、`TimedVAD`、`DOA` は reader の型です。
解析では `GroundTruth`、`TruthSource`、`DOATrack`、`STFTResult`、`MusicResult`、`EvaluationResult`、`SourceResult`、`PeriodResult`、`Metric` を使います。
異常なファイルは `LocataError`、WAV のないアレイディレクトリは `MissingAudioWarning` で知らせます。

::: locata_torch
    options:
      members:
        - LocataDataset
        - download_locata
        - LocataWindowDataset
        - collate_locata
        - world_to_array
        - locata_doa
        - LocataError
        - MissingAudioWarning
        - RecordingInfo
        - CalendarTime
        - RecordingMetadata
        - LocataSample
        - LocataBatch
        - RequiredTime
        - Pose
        - ArrayPose
        - Source
        - SourceAudio
        - SourceVAD
        - TimedVAD
        - DOA
        - prepare_ground_truth
        - align_vad
        - activity_periods
        - music_stft
        - music_localize
        - MusicConfig
        - validate_tracks
        - evaluate_locata
        - EvaluationConfig
        - plot_scene
        - plot_doa
        - plot_evaluation
        - aggregate_results
        - write_results
        - read_results
        - write_submission
        - ResultBundle
        - GroundTruth
        - TruthSource
        - DOATrack
        - STFTResult
        - MusicResult
        - EvaluationResult
        - SourceResult
        - PeriodResult
        - Metric
