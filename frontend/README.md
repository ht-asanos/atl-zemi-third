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
```

## ページフロー

```
Login → Setup → Staple → Plans
  ↑                         │
  └────── Logout ───────────┘
```

1. **Login** (`/login`) — メール + パスワードでログイン
2. **Signup** (`/signup`) — 新規アカウント作成
3. **Setup** (`/setup`) — プロフィール + 目標設定
4. **Staple** (`/staple`) — 主食選択 + 週間プラン生成
5. **Plans** (`/plans`) — 週間メニュー表示（食事 + トレーニング）

未認証ユーザーは自動的に `/login` にリダイレクトされます。

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
