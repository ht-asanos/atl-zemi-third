# Admin YouTube Quick Guide

`/admin/youtube` 画面で YouTube レシピを登録・一括アレンジするときの最短手順をまとめる。

このドキュメントは、実スクリーンショットを差し込む前提で読めるように、画面セクション名を UI と一致させている。

## 画面全体

画面は次の 4 セクションで構成される。

1. `YouTube URL からレシピ抽出`
2. `レシピプレビュー・編集`
3. `主食アレンジ一括登録`
4. `登録済み YouTube レシピ`

スクリーンショット差し込み位置:

- Screenshot 1: `/admin/youtube` 全体画面

## 1. 単一 URL から登録する

使う場所:

- `YouTube URL からレシピ抽出`
- `レシピプレビュー・編集`

手順:

1. `YouTube URL` に対象動画 URL を入力する
2. 必要なら `主食名（オプション）` に `冷凍うどん` などを入力する
3. `字幕取得・レシピ抽出` を押す
4. 抽出後、`レシピプレビュー・編集` に draft が表示される
5. `タイトル`、`人数`、`調理時間（分）` を必要に応じて修正する
6. `材料` と `手順` を見直し、不足や誤変換を直す
7. `DB に登録` を押す

確認ポイント:

- 抽出直後に `品質スコア` と `video_id` が表示される
- 登録成功時は上部に成功メッセージが出る
- 非食事レシピは backend 側の品質ゲートで `422` になる

スクリーンショット差し込み位置:

- Screenshot 2: `YouTube URL からレシピ抽出`
- Screenshot 3: `レシピプレビュー・編集`

## 2. チャンネルから一括アレンジ登録する

使う場所:

- `主食アレンジ一括登録`

推奨入力例:

- `チャンネルハンドル`: `@yugetube2020`
- `元動画の検索語`: `パスタ`
- `変換先主食`: `冷凍うどん`
- `処理件数`: `10`

手順:

1. 上記 4 項目を入力する
2. `一括アレンジ実行` を押す
3. 結果サマリーの `videos_found`、`processed`、`success`、`failed`、`skipped` を確認する
4. テーブルで各動画の `status` を確認する
5. `success` 行では `生成レシピ` から詳細を開いて内容を確認する

運用ルール:

- `filtered_source_mismatch` は検索ノイズ。再実行せず除外でよい
- `filtered_non_meal` は品質ゲート除外。再登録しない
- `filtered_accompaniment` は主食の付け合わせ判定。除外でよい
- `skipped_existing` は既存登録済み。何もしない
- `no_transcript` は字幕なし。基本はスキップ
- `registration_failed` は backend ログ確認対象

スクリーンショット差し込み位置:

- Screenshot 4: `主食アレンジ一括登録` の入力欄
- Screenshot 5: 実行後の結果テーブル

## 3. 登録済みレシピを確認する

使う場所:

- `登録済み YouTube レシピ`

見方:

- 一覧には `title`、`youtube_video_id`、`nutrition_status`、`steps_status`、`created_at` が並ぶ
- タイトルまたは詳細ボタンからレシピ詳細モーダルを開く
- 一括アレンジ直後は、ここで新規登録分が先頭に出る

スクリーンショット差し込み位置:

- Screenshot 6: `登録済み YouTube レシピ`

## 4. エラー時の見方

画面上部の赤いメッセージ領域は API エラー表示に使う。

典型例:

- `レシピ抽出に失敗しました`
- `レシピ登録に失敗しました`
- backend から返る `422` の詳細メッセージ

判断基準:

- 単発登録での `422` は、URL 不正・字幕取得失敗・品質ゲート拒否のどれか
- 一括アレンジでの個別失敗は結果テーブルの `error` 列を見る
- 画面の情報だけで足りない場合は backend ログを確認する

## 関連ドキュメント

- [YouTube Recipe Ops](./youtube_recipe_ops.md)
- [Backend README](../backend/README.md)
- [Frontend README](../frontend/README.md)
