# データの保存先

## 既存データを複数プロジェクトで使う {#existing-data-across-projects}

アプリケーションの環境変数に `LOCATA_ROOT=/path/to/LOCATA` を設定するか、引数 `root` を指定します。
`dev/` または `eval/` が入った展開済みディレクトリを指し、manifest は不要です。
検索順は引数 `root`、`LOCATA_ROOT`、管理保存先です。無効なパスを設定した場合はエラーとし、次の候補へは進みません。
選択した絶対パスは Dataset が保持し、spawn 後も同じ場所を参照します。

reader の構築時にはネットワークアクセスやディレクトリ作成を行わず、データ本体の下に index や cache を書きません。
環境変数とは別のインストールを使う場合は、`root` を指定してください。

## ダウンロードと管理保存先 {#download-and-manage-storage}

`locata-torch[download]` をインストールし、DataLoader の worker を作る前に `download_locata` を呼ぶか、`locata-torch download --split dev` を実行します。
API は `dev`、`eval`、または空でない列を受け取り、重複を除いて決定的な順に配置します。CLI では `--split` を繰り返して両方を選べます。
進捗とエラーは stderr、成功時の展開済み root は stdout に出力します。
`locata-torch path` は既定で dev を確認します。eval だけの管理保存先では `locata-torch path --split eval`、両方を要求する場合は `--split` を繰り返します。

保存先は引数 `data_dir` / `--data-dir`、`LOCATA_DATA_DIR`、`platformdirs.user_data_path("locata-torch", appauthor=False, ensure_exists=False)` の順に探します。
Python 環境を越えて共有できる、永続的な保存先です。
`LOCATA_ROOT` はダウンロード先を変更しません。既存の展開済み root は `data_dir` に使わず、別の管理保存先を用意してください。
reader が設定から管理保存先を探す場合は、準備が完了した split だけを受け付けます。

```text
<data_dir>/
├── archives/zenodo-3630471/    # ZIPs, .part files, and partial identity records
├── datasets/zenodo-3630471/   # Returned root with completed dev/ and/or eval/
├── state/zenodo-3630471/      # Installation inventory and attribution records
├── staging/                  # Owned temporary extraction directories
└── locks/                    # Per-split process locks
```

データ release のキーは Python パッケージのバージョンから独立しています。
ライブラリの更新時も同じデータを再利用できます。
各 split は公式アーカイブ全体を含み、task / array の選択が変えるのは読み込み対象だけです。

## 配布版と必要容量 {#release-and-disk-space}

対応するデータは [公式の最終配布版](https://zenodo.org/records/3630471)、v1、2020-01-31、DOI `10.5281/zenodo.3630471` です。
アーカイブのサイズと MD5 は[公式 metadata API](https://zenodo.org/api/records/3630471)に固定し、展開サイズは ZIP64 の directory 情報から確認しています。

| split | ZIP の byte 数 | 展開後の byte 数 | 公式 MD5 |
| --- | ---: | ---: | --- |
| dev | 6,207,354,195 | 27,136,519,350 | `d5a5417c3f6b2ed0e43581dd06f504e6` |
| eval | 13,045,105,034 | 57,426,914,435 | `46709713350bc16c106e788920d30a8b` |

両 split の ZIP と展開済みデータを保持すると、ファイルシステムの付加容量を除いて約 103.8 GB です。
新規導入時は少なくとも 120 GB の空きを用意してください。
これらはアーカイブの metadata に基づく見積もりで、全インストールの実測容量ではありません。
downloader は転送前と展開前に空き容量を確認します。

## 検証、再開、復旧 {#integrity-resume-and-recovery}

[Zenodo v1](https://zenodo.org/records/3630471)、DOI `10.5281/zenodo.3630471` の公式 HTTPS URL に対応します。
転送はメモリ上限のある chunk で逐次処理し、identity encoding を要求し、応答サイズと HTTP Range を毎回確認します。
socket timeout は 30 秒、試行は最大 3 回です。
一時的な HTTP エラーや短い応答では、識別済みの途中ファイルを保持します。
サーバーが Range を無視した場合は、その途中ファイルの転送を最初から再開します。
不正な Range、想定外の encoding、HTTP 416 はエラーにします。source URL の変更用 API はありません。

保存済みの全 byte を hash 計算し、正確なサイズと配布元の MD5 が一致してから展開します。
MD5 は配布元 metadata に対する整合性の確認に使い、source は公式 HTTPS URL に固定します。
完了した ZIP は保持し、ネットワークなしでの再展開に使えます。

空き容量と元の ZIP64 member 名を確認し、Python が OS ごとの正規化で変える名前も検証します。
危険なパス、型、名前の衝突、symlink、Windows に持ち運べないファイル名を拒否し、ZIP CRC を確認しながら展開します。
保存先と同じファイルシステム内の新しい作業用ディレクトリを使います。
配置の前に prepared manifest、split の atomic な配置後に complete manifest を書きます。
その間に中断した場合は、記録したファイル一覧を検証して復旧します。途中の展開先は reader が読む root の外です。
split ごとの process lock で準備処理を直列化し、待ち時間は 60 秒に制限します。

再度要求すると、ファイル一覧、サイズ、CRC をすべて検証し、ネットワークアクセスやデータ本体への書き込みなしで再利用します。
全ファイルを読むため、大きなデータでは時間がかかります。
未知の保存先、互換性のない記録、変更されたファイルはエラーとし、自動修復、merge、削除、上書きは行いません。
後続 split の処理が失敗しても、完了済み split は利用できます。
新規展開に失敗した場合は、その処理の作業用ディレクトリだけを片付けます。prepared manifest のない crash 残骸は自動削除しません。

## 帰属表示と検証の根拠 {#attribution-and-evidence}

管理 manifest は正確な source URL、サイズ、MD5、観測した hash、ファイル一覧、DOI、引用、データの [ODC-BY 1.0](https://opendatacommons.org/licenses/by/1-0/) 表示を記録します。
ライブラリのコードは Apache-2.0 です。LOCATA データ本体はパッケージに同梱・再配布しません。
研究や他のツールで利用する場合は、データの帰属表示条件に従ってください。

転送と展開のテストには local HTTP server と小さな合成 ZIP64 を使います。
reader は Challenge 時代の snapshot と、source pose / VAD を含む最終配布版 eval の代表的な録音で確認しています。
確認したケースと残る制約は[検証記録](validation.md)を参照してください。
