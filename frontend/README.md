# Frontend — Next.js

## セットアップ

```bash
npm install
cp .env.example .env.local
# .env.local を編集して Supabase / API 接続情報を設定
```

## 起動

```bash
npm run dev      # 開発サーバー (http://localhost:3000)
npm run build    # プロダクションビルド
npm run start    # プロダクションサーバー
npm run vibe     # Vibe Kanban 起動
```

## ページフロー

```
Login → Setup → Staple(プラン生成) → Plans(週間)
  ↑             │                    │
  └── Logout ───┴──── Settings ──────┘
                    ├─ /settings/profile
                    ├─ /settings/goal
                    └─ /staple?from=settings
```

1. **Login** (`/login`) — メール + パスワードでログイン
2. **Signup** (`/signup`) — 新規アカウント作成
3. **Setup** (`/setup`) — プロフィール + 目標設定
4. **Staple** (`/staple`) — モード選択（レシピ/主食）+ 週間プラン生成
5. **Plans** (`/plans`) — 週間メニュー表示（食事 + トレーニング + 買い物リスト）
6. **Daily** (`/daily`) — 当日の食事ログ・フィードバック
7. **Settings** (`/settings/profile`, `/settings/goal`) — プロフィール・目標の更新
8. **Admin YouTube** (`/admin/youtube`) — YouTube URL からのレシピ抽出・登録、一括アレンジ登録

未認証ユーザーは自動的に `/login` にリダイレクトされます。

## 管理画面 `/admin/youtube`

- YouTube URL を入力して字幕から recipe draft を抽出できる
- draft のタイトル、材料、手順をその場で編集して登録できる
- `channel_handle`、`source_query`、`target_staple`、`max_results` を指定してチャンネル動画を一括アレンジ登録できる
- 一括アレンジ結果は `success`、`skipped_existing`、`filtered_*`、`no_transcript` などの status ごとに確認できる
- 登録済み YouTube レシピ一覧から詳細モーダルを開ける

運用上の前提:

- この画面は backend の `/admin/youtube/*` API をそのまま使う
- `filtered_source_mismatch` と `filtered_non_meal` は正常系の除外であり、UI 上でエラー扱いしない
- `no_transcript` は字幕なし動画のため、基本はスキップでよい
- 詳細な運用手順と復旧コマンドは [doc/youtube_recipe_ops.md](../doc/youtube_recipe_ops.md) を参照
- 画面ベースの簡易ガイドは [doc/admin_youtube_quick_guide.md](../doc/admin_youtube_quick_guide.md) を参照

## 買い物リスト UI 仕様

- 週間買い物リストは `未購入` と `購入済み` の 2 セクションで表示
- チェック済み項目は消さずに `購入済み` に移動
- `購入済み` 側のチェックを外すと `未購入` に戻る（双方向トグル）
- 材料名はバックエンド正規化済み文字列（括弧・記号ノイズを削除）を表示

## コンポーネント構成

```
src/
├── app/
│   ├── layout.tsx              # AuthProvider + Toaster
│   ├── page.tsx                # リダイレクト
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── signup/page.tsx
│   └── (app)/
│       ├── layout.tsx          # 保護レイアウト + ナビ
│       ├── daily/page.tsx
│       ├── admin/youtube/page.tsx
│       ├── settings/
│       │   ├── profile/page.tsx
│       │   └── goal/page.tsx
│       ├── setup/page.tsx
│       ├── staple/page.tsx
│       └── plans/page.tsx
├── components/
│   ├── ui/                     # UI コンポーネント (shadcn 互換)
│   ├── auth/                   # ログイン / サインアップフォーム
│   ├── setup/                  # プロフィール / 目標設定
│   ├── staple/                 # 主食カード
│   └── plans/                  # 週間プラン表示
├── lib/
│   ├── supabase/               # Supabase クライアント
│   └── api/                    # Backend API クライアント
├── types/                      # TypeScript 型定義
├── providers/                  # AuthProvider
└── middleware.ts               # 認証ミドルウェア
```

## Lint

```bash
npm run lint
```
