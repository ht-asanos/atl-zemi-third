# Roadmap: 一人暮らし向け自炊 x トレーニング最適化アプリ

本ロードマップはコードベースの実装状況を正確に反映し、今後の開発方針を示すものである。

差分メモ:
- [roadmap_delta_2026-03-12.md](/Users/hdymacuser/WorkSpace/260401dtzemi/atl-zemi-third/doc/roadmap_delta_2026-03-12.md)
- [roadmap_update_2026-03-22.md](/Users/hdymacuser/WorkSpace/260401dtzemi/atl-zemi-third/doc/roadmap_update_2026-03-22.md)

---

## 技術構成

| レイヤー | 技術 |
|---|---|
| Frontend | Next.js 15 (App Router, TypeScript, Tailwind CSS v4, shadcn/ui) |
| Backend | FastAPI (Python 3.11, uv) |
| DB / Auth / Storage | Supabase (PostgreSQL + Auth + Storage) |
| AI | OpenAI API (感想タグ抽出), Gemini (レシピ品質判定・食材処理補助) |
| 外部データ | MEXT 食品成分データベース (スクレイピング), 楽天レシピ API, YouTube |
| テスト / Lint | pytest, ruff, ty, pre-commit, ESLint |

---

## API 設計方針

| 方針 | 詳細 |
|---|---|
| 冪等性 | POST 系エンドポイントは `Idempotency-Key` ヘッダーに対応する。重複リクエストは 409 Conflict を返す |
| 所有権 | 全 API で `user_id` は JWT クレームから取得する。パスパラメータやリクエストボディでの指定は不可 |
| エラーコード | 重複送信: 409 Conflict / バリデーション違反: 422 Unprocessable Entity |

---

## 完了済みフェーズ（実績記録）

### Phase 1（完了）: データモデル + 計算エンジン

**目的:** アプリの基盤となるデータ構造と栄養計算ロジックを構築する。

- 栄養計算エンジン（BMR / TDEE / PFC 目標算出）
- 食材マスタ（主食 5 種 + タンパク源 4 種 + かさ増し 3 種） — `backend/src/app/data/food_master.py`
- トレーニングテンプレート（diet / strength / bouldering）
- 食事提案ロジック（主食選択 → 残枠計算 → 組み合わせ生成）
- ユニットテスト一式（177 tests passing）

---

### Phase 2（安定化中）: 週次プラン生成 API + UI

**目的:** ユーザーが初期設定を行い、1 週間分のメニューを確認できる状態にする。

- Profile / Goal API（`POST /profiles`, `GET /profiles/me`, `POST /goals`, `GET /goals/me`）
- 週次プラン生成（classic + recipe モード）— `POST /plans/weekly`, `GET /plans/weekly?start_date=`
- 主食変更 API — `PATCH /plans/{id}/meal`
- Supabase Auth 連携（cookie ベース SSR、`@supabase/ssr`）
- フロントエンド（ログイン → 設定 → 主食選択 → 週間プラン表示）
- Middleware による認証保護（`/setup`, `/staple`, `/plans` へのアクセス制御）

**現状メモ:**
- 実 DB 経路の `meal_plan` JSON 二重シリアライズ問題は修正済み
- 既存プランは `daily_plans.meal_plan` のスナップショット保持であり、後から `recipes` を更新しても自動反映されない
- 引き続き実 Supabase 経路での継続的な結合確認は必要

---

### Phase 3（完了）: ログ収集 + 感想解析 + 適応

**目的:** 日々の実行記録と感想から次回提案を自動調整する仕組みを構築する。

- 食事ログ / トレーニングログ API（`POST /logs/meal`, `POST /logs/workout`, `GET`）
- ChatGPT タグ抽出（5 タグ: `too_hard`, `cannot_complete_reps`, `forearm_sore`, `bored_staple`, `too_much_food`）
- ルールベース適応エンジン + 楽観ロック + リビジョン保存（`plan_revisions`）
- フロントエンド日次ページ（ログ記録 + フィードバック入力・結果表示）
- E2E シナリオテスト（設定 → 生成 → ログ → 感想 → 適応の全フロー）

**残課題:**
- 食事フィードバックは当日プラン変更が中心で、次回以降のレシピ選定学習には十分つながっていない
- `feedback_tags` / `plan_revisions` はあるが、「どの感想がどの recipe / workout の変更を起こしたか」の構造化履歴は弱い
- ユーザーが履歴を時系列で閲覧する UI は未実装

---

### Phase 2.5（部分完了 — ロードマップ外で実装）: レシピ統合

**目的:** 外部レシピデータを取り込み、具体的なレシピ名で献立を提案する。

**実装済み:**
- MEXT 食品 DB スクレイパー（9 カテゴリ対応）+ 食材マッチング（fuzzy match + 信頼度スコア）
- 楽天レシピ API クライアント（現行認証方式対応）+ DB キャッシュ（`recipes` / `recipe_ingredients` テーブル）
- レシピ更新 API / 補完 API（`POST /recipes/refresh`, `POST /recipes/backfill`）
- YouTube レシピ取込と管理画面運用（抽出、単体登録、チャンネル一括アレンジ登録、品質ゲート）
- 食材手動レビュー UI / API（`manual_review_needed` の運用導線あり）
- レシピモード v3（朝食固定 + 昼食固定 + 夕食日替わりレシピ、PFC フィルタ付き）
- フロントエンドでモード切替（classic / recipe）

**残タスク:**
- レシピ更新の定期自動実行基盤は未実装。現状は手動 API / CLI 運用
- MEXT / レシピ補完の対象拡大は継続課題
- レシピ取り込み品質の運用監視とバックフィルの定例化が必要

---

### Phase 3.5（完了 — 2026-03-29）: UX心理学に基づくフロントエンドUIリファクタリング

**目的:** UX心理学の知見を適用し、認知負荷を下げてユーザーの行動継続率を高める。

| # | タスク | 状態 |
|---|---|---|
| 3.5-1 | デザイントークン基盤（セマンティックカラー・トランジション・アニメーション） | 完了 |
| 3.5-2 | アクティブナビ状態（下線インジケータ、aria-current）、ヘッダー幅統一 | 完了 |
| 3.5-3 | モバイルボトムナビゲーション（メニューボトムシート） | 完了 |
| 3.5-4 | デイリー進捗バー（ツァイガルニク効果）+ 全完了セレブレーション（ピーク・エンドの法則） | 完了 |
| 3.5-5 | Dailyページ折り畳みセクション + スティッキー保存ボタン（フィッツの法則） | 完了 |
| 3.5-6 | 「今日」カードハイライト（フォン・レストルフ効果）| 完了 |
| 3.5-7 | スケルトンローディング（Plansページ）、EmptyStateコンポーネント | 完了 |
| 3.5-8 | Checkbox・星レーティングにマイクロインタラクション追加 | 完了 |
| 3.5-9 | ハードコードカラー全箇所をセマンティックトークンに置換 | 完了 |

---

## 今後のフェーズ

### Phase 4: 日常使いの実用性強化（一部完了、次の主対象は 4.5）

**目的:** 買い物・レシピ差し替え・データ安定性など、日常利用に必要な機能を整備する。

| # | タスク | 状態 | レイヤー | 優先度 | 備考 |
|---|---|---|---|---|---|
| 4-1 | 買い物リスト自動生成 | 完了 | Backend + Frontend | 高 | `GET /plans/weekly/shopping-list` とチェック状態 API まで実装済み |
| 4-2 | レシピモードの夕食再抽選 | 完了 | Backend + Frontend | 高 | `PATCH /plans/{id}/recipe` 実装済み。`plan_meta` に `recipe_filters` を保持 |
| 4-3 | レシピプール定期自動更新 | 最小運用版完了 | Backend + Infra | 高 | `job_logs`、`run-recipe-maintenance`、GitHub Actions 週次実行を導入済み。外部通知と運用可視化は継続課題 |
| 4-4 | Phase 2 実 DB 経路のバグ修正 | 完了 | Backend | 高 | `meal_plan` の JSON シリアライズ問題は修正済み |
| 4-5 | 食事写真アップロード | 未着手 | Backend + Frontend | 中 | Supabase Storage（private バケット）、署名 URL（TTL 15分）、ログ画面にカメラ UI |
| 4-6 | レシピお気に入り機能 | 完了 | Backend + Frontend | 中 | `user_recipe_favorites` と API / UI / 優先選出を実装済み |

**Exit Criteria（機能）:**
- DB 内レシピが週1回自動更新される
- refresh / backfill / 非食事クリーンアップの定期実行結果が追跡できる
- 写真付き食事ログが保存・参照できる

**Exit Criteria（KPI）:**
- レシピ更新ジョブ成功率 > 99%
- 生成失敗率 < 1%（実 DB 経路での 5xx エラー率）
- 夕食レシピ重複率 = 0%（7日間で同一レシピなし）

---

### Phase 4.5: フィードバック適応の高度化（4-3 の次に最優先）

**目的:** 食事とトレーニングのフィードバックを、単発の当日変更ではなく中長期の選好学習と説明可能な履歴に発展させる。

| # | タスク | 状態 | レイヤー | 優先度 | 備考 |
|---|---|---|---|---|---|
| 4.5-1 | フィードバック台帳の標準化 | 未着手 | Backend + DB | 最優先 | `feedback_events` / `feedback_event_tags` / `adaptation_events` を追加し、元入力・タグ・変更前後・変更理由を構造化保存 |
| 4.5-2 | 食事フィードバックによる次回レシピ選定 | 未着手 | Backend | 最優先 | 味・満足度・自由文を次回以降の再生成と週次プランに反映。主対象は「次回以降のレシピ優先度変更」 |
| 4.5-3 | トレーニング適応の履歴化と段階制御 | 未着手 | Backend | 高 | できなかったら優しめ、余裕なら1段階上へ。変更理由を event として保存 |
| 4.5-4 | フィードバック履歴 UI | 未着手 | Frontend + Backend | 最優先 | `/feedback/history` の専用画面で食事・トレーニング履歴、before/after、適応理由を時系列表示 |

**Exit Criteria（機能）:**
- ユーザーが「どの感想がどの変更を起こしたか」を UI で追える
- 食事フィードバックが次回以降のレシピ選定理由として表示される
- トレーニングの負荷調整理由と難度推移が履歴で見える

**Exit Criteria（KPI）:**
- 低評価レシピの再提示率が継続的に低下する
- 嗜好反映後のレシピ満足度が反映前より向上する
- トレーニング完遂率が調整前後で改善する

---

### Phase 5: パーソナライズ + データ蓄積

**目的:** ユーザーの身体データと嗜好を蓄積し、提案の精度を高める。

| # | タスク | レイヤー | 優先度 |
|---|---|---|---|
| 5-1 | 体重・体組成の記録 API + 進捗グラフ UI | Backend + Frontend | 高 |
| 5-2 | 食事嗜好学習（過去ログの好み傾向 → プラン生成に反映） | Backend | 中 |
| 5-3 | 食材マスタ拡充（MEXT 全カテゴリ + backfill スクレイピング補完の実装） | Backend | 中 |
| 5-4 | 週次サマリー通知（実行率・PFC 達成率のメール or Push） | Backend | 低 |

**Exit Criteria（機能）:**
- 体重推移グラフが表示され、目標との差分が可視化される
- ログ蓄積に応じて提案レシピのパーソナライズが体感できる

**Exit Criteria（KPI）:**
- 週間実行率（ログ記録日数 / 7）の可視化が機能すること
- 嗜好反映後のレシピ満足度（ログの satisfaction スコア平均）が反映前より向上

---

### Phase 6: 運用安定 + 高度な機能

**目的:** 運用品質の確保と将来の拡張基盤を整備する。

| # | タスク | レイヤー | 優先度 |
|---|---|---|---|
| 6-1 | アカウント削除フロー（データ + Storage 物理削除、72h 以内） | Backend + Supabase | 高 |
| 6-2 | API レスポンスタイム監視（P95 閾値: `/plans/weekly` < 5s, `/feedback` < 3s, その他 < 2s） | Backend | 中 |
| 6-3 | 週次実行率・継続率ダッシュボード（管理用） | Frontend | 中 |
| 6-4 | PWA 対応（モバイル通知 + オフラインキャッシュ） | Frontend | 低 |
| 6-5 | 適応エンジンの ML 化（ルールベース → 学習ベース） | Backend | 低 |

**Exit Criteria（KPI）:**
- 全エンドポイントで P95 応答時間が上記基準を達成
- 退会後 72h 以内にデータ + Storage が物理削除されること

---

## フェーズ進行まとめ

```
Phase 1 (基盤) ✅ → Phase 2 (MVP コア) 🔧安定化中 → Phase 3 (適応) ✅
                          ↓
                   Phase 2.5 (レシピ統合) ✅運用段階
                          ↓
        Phase 4 (一部完了 / 4-3 最小運用版完了)
                          ↓
      Phase 4.5 (フィードバック適応高度化) → Phase 5 (パーソナライズ) → Phase 6 (運用・拡張)
```
