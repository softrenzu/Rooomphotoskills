# RooomPhotoSkills

Google Drive の写真フォルダを指定すると、宿泊・レンタルスペース掲載に必要な写真だけを自動選定し、類似写真や不要写真を除外したうえで、Airbnb / Booking.com / スペースマーケット / インスタベース向けに補正・書き出しするツールです。

## 主な機能

- Google Drive フォルダ URL / ID を直接指定
- 元写真は削除・移動・上書きしない
- pHash + CLIP 埋め込みで近似・重複写真を除外
- ブレ、露出、解像度、縦横、構図の品質スコアリング
- CLIP による写真カテゴリ推定（リビング、寝室、キッチン、浴室、外観、入口、設備、眺望など）
- 各カテゴリをバランスよく残すカバレッジ選定
- スクリーンショット、書類、QR/文字主体画像、極端に暗い・ぼけた写真を原則除外
- 掲載用の自然な明るさ、ホワイトバランス、局所コントラスト、軽いシャープ補正
- プラットフォーム別サイズで出力
- 元フォルダ配下に `リスティング用_加工済み` を新規作成
- 選定理由・除外理由を CSV / JSON で保存
- `--dry-run` でアップロードせず選定結果だけ確認可能

## 出力フォルダ

```text
元写真フォルダ/
└─ リスティング用_加工済み/
   ├─ 共通_マスター/
   ├─ Airbnb/
   ├─ Booking/
   ├─ スペースマーケット/
   ├─ インスタベース/
   ├─ 選定レポート.csv
   └─ 選定レポート.json
```

## 掲載写真の方針

- Airbnb: 横長を優先。最低 1024 x 683 を満たす。出力は 2048 x 1365 を標準。
- Booking.com: 重複を避け、JPEG/PNG、十分な解像度を維持。出力は最大 2400px を標準。
- スペースマーケット: 検索・一覧で見やすい横長 16:9 を標準出力。
- インスタベース: 公式推奨 1570 x 880 を標準出力。15枚以上を目標に選定。

プラットフォーム要件は変更される場合があるため、`rooomphotos/config.py` のプリセットで調整できます。

## インストール

Python 3.11 以上を推奨します。

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -e .
```

初回は CLIP モデルをダウンロードするためインターネット接続が必要です。

## Google Drive 認証

Google Cloud Console で OAuth 2.0 Desktop App の `credentials.json` を作成し、次のどちらかで指定します。

```bash
set GOOGLE_OAUTH_CLIENT_FILE=C:\path\to\credentials.json
```

または

```bash
rooomphotos drive "DRIVE_FOLDER_URL" --credentials credentials.json
```

初回実行時にブラウザ認証され、トークンはユーザーディレクトリに保存されます。必要権限は Drive ファイルの読み書きです。

## 実行例

```bash
rooomphotos drive "https://drive.google.com/drive/folders/1d80JZ33vLArjdSsXpnu0Xi9KN1dzeCl6"
```

選定だけ確認:

```bash
rooomphotos drive "DRIVE_FOLDER_URL" --dry-run
```

枚数を指定:

```bash
rooomphotos drive "DRIVE_FOLDER_URL" --min-selected 15 --max-selected 28
```

出力フォルダ名を変更:

```bash
rooomphotos drive "DRIVE_FOLDER_URL" --output-folder-name "掲載用写真_加工済み"
```

## 選定アルゴリズム

1. Drive から JPEG / PNG / WebP を列挙
2. EXIF の向きを補正し、解析用サムネイルを作成
3. 解像度、ブレ、明るさ、白飛び・黒つぶれ、色、横長度を評価
4. CLIP で写真カテゴリと不要画像候補を分類
5. pHash と CLIP 類似度で連写・近似構図をグルーピング
6. 各グループから最良の1枚を優先
7. 部屋・設備カテゴリのカバレッジを満たしながら総合得点順に追加
8. 採用画像だけ自然な補正を実施
9. プラットフォーム別バリアントを作成
10. 新規 Drive フォルダへアップロードし、元写真はそのまま保持

## 重要な設計方針

本ツールは物件を実態以上に見せる生成加工はしません。家具の追加、窓の外の景色の置換、不要物の生成消去、部屋の拡張などは行わず、露出・色・傾き・トリミング・解像度調整など写真編集の範囲に限定します。

## License

Copyright (c) 2026 ROOOMTECH Inc. See `LICENSE`.
Commercial / production / corporate use requires a commercial license. Contact: support@rooomtech.com
