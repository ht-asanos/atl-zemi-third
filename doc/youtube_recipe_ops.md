# YouTube Recipe Ops

YouTube レシピの単発登録、一括アレンジ登録、DB 修復に必要な運用知識をまとめる。

## 基本フロー

1. 管理画面 `/admin/youtube` または `POST /admin/youtube/extract` で字幕から recipe draft を作る。
2. draft のタイトル、材料、手順を確認する。
3. 単発なら `POST /admin/youtube/register`、まとめて処理するなら `POST /admin/youtube/batch-adapt` を使う。
4. 登録後に栄養や材料行の不整合が疑われる場合は修復コマンドを実行する。

## 単発登録

- `extract` は YouTube URL から字幕を取得し、Gemini で recipe draft を作る。
- 自動字幕は自然化を試みる。自然化に失敗しても raw transcript で抽出を続ける。
- `register` は DB 登録前に Gemini 品質ゲートを通す。
- 非食事レシピと判定された場合は `422` で拒否される。

## 一括アレンジ登録

推奨例:

```bash
cd backend
curl -sS -X POST 'http://localhost:8000/admin/youtube/batch-adapt' \
  -H "Authorization: Bearer ${ADMIN_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d '{"channel_handle":"@yugetube2020","source_query":"パスタ","target_staple":"冷凍うどん","max_results":10}'
```

この処理は次の順でフィルタする。

1. YouTube 検索結果から、非食事キーワードを含む動画を事前除外する。
2. `source_query='パスタ'` の場合、動画タイトルが本当にパスタ動画かを厳格に確認する。
3. 字幕を取得し、レシピ抽出を行う。
4. 抽出した元レシピを Gemini 品質ゲートに通す。
5. 主食アレンジ後に付け合わせ判定を行う。
6. 最終的なアレンジ結果を再度 Gemini 品質ゲートに通す。
7. 通過したものだけ DB に登録し、食材マッチングと栄養計算を行う。

`no_transcript` は失敗ではあるが、運用ではスキップ扱いでよい。字幕がない動画を無理に救済しない。

## status の意味

| status | 意味 | 運用判断 |
|---|---|---|
| `success` | 登録完了 | そのまま採用 |
| `skipped_existing` | 既存動画と重複 | 何もしない |
| `filtered_source_mismatch` | 検索結果に出たが source query の意図と一致しない | 何もしない |
| `filtered_non_meal` | Gemini 品質ゲートで非食事判定 | 何もしない |
| `filtered_accompaniment` | 主食の付け合わせと判定 | 何もしない |
| `no_transcript` | 字幕なし、または字幕取得失敗 | スキップ |
| `extraction_failed` | 字幕からレシピ抽出できない | 必要なら単発で再確認 |
| `adaptation_failed` | 主食アレンジ失敗 | 必要なら単発で再確認 |
| `registration_failed` | DB 登録または後続処理失敗 | ログを見て原因調査 |

## 修復・保守コマンド

```bash
cd backend

# 既存 YouTube レシピの食材マッチングと栄養計算をやり直す
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  repair-youtube-nutrition

# recipe_ingredients をレシピ単位で再構築する
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  rebuild-recipe-ingredients

# 非食事レシピの棚卸し（dry-run）
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  prune-non-meal-recipes

# 非食事レシピを実削除
PYTHONUNBUFFERED=1 PYTHONPATH=src uv run python -m app.services.data_loader \
  prune-non-meal-recipes --execute
```

使い分け:

- 栄養値が入っていない、または古い判定で止まっているときは `repair-youtube-nutrition`
- `recipe_ingredients` の重複や raw 行混入が疑われるときは `rebuild-recipe-ingredients`
- つけ汁・たれ・ソース系の混入を棚卸ししたいときは `prune-non-meal-recipes`

## recipe_ingredients の正

- `upsert_recipe()` は `recipes` テーブルだけを更新する。`ingredients` はそこで保存しない。
- `match_recipe_ingredients()` が `recipe_ingredients` の正規な更新経路。
- `match_recipe_ingredients()` は対象レシピの既存材料行を削除してから再 insert するため、raw 材料行とマッチ済み材料行の二重登録を防ぐ。

## トラブルシュート

- `no_transcript` はそのままスキップする。字幕なし動画を一括処理の対象に含め続けない。
- 自動字幕自然化に失敗しても即ブロッカーではない。raw transcript fallback がある。
- `registration_failed` は DB 制約や後続の食材処理で失敗している可能性がある。API レスポンスの `error` と backend ログを確認する。
- `rebuild-recipe-ingredients` 実行後も失敗するレシピが残る場合は、タイトルと `recipe_id` を記録して個別に材料表記を確認する。
