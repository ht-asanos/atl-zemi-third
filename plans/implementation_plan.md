# テキサスホールデム確率計算Webアプリ 実装計画書

## 1. プロジェクト概要
本プロジェクトは、テキサスホールデムポーカーにおいて、プリフロップ（手札が配られた直後）時点での役成立確率と勝率をシミュレーションし、プレイヤーの意思決定を支援するWebアプリケーションを開発することを目的とします。

### 主な機能
1.  **役成立確率表示**: 自分の手札から、最終的（リバーまで）に成立する可能性が高い役TOP3とその確率を表示。
2.  **敗北確率表示**: 指定されたプレイヤー人数において、他プレイヤーが自分より強い役を成立させる可能性（脅威度）を表示。

## 2. システムアーキテクチャ

### 全体構成
```mermaid
graph TD
    User[ユーザー] -->|ブラウザ操作| Frontend[Frontend (Next.js)]
    Frontend -->|API Request (JSON)| Backend[Backend (FastAPI)]
    Backend -->|Monte Carlo Simulation| Logic[Poker Logic (Python)]
    Logic -->|Result| Backend
    Backend -->|Response (JSON)| Frontend
    Frontend -->|表示| User
```

### 技術スタック
*   **Frontend**:
    *   Framework: Next.js 14+ (App Router)
    *   Language: TypeScript
    *   Styling: Tailwind CSS
    *   State Management: React Hooks
    *   Conventions: `AGENTS.md` に従う (Single quotes, No semicolons)
*   **Backend**:
    *   Framework: FastAPI
    *   Language: Python 3.11 (`AGENTS.md` 準拠)
    *   Poker Library: `treys` (または同等の評価ライブラリ)
    *   Server: Uvicorn
    *   **Toolchain**: `uv` (Package Management), `ruff` (Lint/Format), `ty` (Type Check) - `AGENTS.md` 準拠

## 3. ディレクトリ構成詳細

```text
atl-zemi-third/
├── backend/                # Python FastAPI Backend
│   ├── main.py             # エントリーポイント & APIルート
│   ├── poker_logic.py      # シミュレーションと役判定ロジック
│   ├── pyproject.toml      # 依存定義 (uv管理)
│   └── .venv/              # 仮想環境 (uv syncで作成)
├── frontend/               # Next.js Frontend
│   ├── src/
│   │   ├── app/
│   │   │   └── page.tsx    # メインページ
│   │   ├── components/
│   │   │   ├── CardSelector.tsx  # カード選択UI
│   │   │   ├── ResultView.tsx    # 結果表示UI
│   │   │   └── PlayerSettings.tsx # 人数設定UI
│   │   └── utils/
│   │       └── api.ts      # APIクライアント
│   ├── package.json
│   └── ...
└── plans/
    └── implementation_plan.md # 本ドキュメント
```

## 4. データ構造とAPI仕様

### カード表現
カードは2文字の文字列で表現する。
*   ランク: `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9`, `T` (10), `J`, `Q`, `K`, `A`
*   スート: `s` (spades), `h` (hearts), `d` (diamonds), `c` (clubs)
*   例: `Ah` (ハートのエース), `Td` (ダイヤの10)

### API: シミュレーション実行

*   **Endpoint**: `POST /api/analyze`
*   **Request Body**:
    ```json
    {
      "my_cards": ["Ah", "Kd"],
      "num_players": 6,
      "num_simulations": 10000
    }
    ```
    *   `my_cards`: 自分の手札（2枚）。
    *   `num_players`: 自分を含めたプレイヤー総数（2〜10）。
    *   `num_simulations`: (Optional) シミュレーション回数。デフォルト10,000。

*   **Response Body**:
    ```json
    {
      "hand_potential": [
        { "rank_name": "Pair", "probability": 45.5 },
        { "rank_name": "Two Pair", "probability": 23.1 },
        { "rank_name": "High Card", "probability": 18.2 }
      ],
      "win_rate": 32.5,
      "tie_rate": 2.3,
      "loss_rate": 65.2
    }
    ```
    *   `hand_potential`: 自分が最終的に完成させた**最強役**の分布（降順TOP3）。
        *   ※ 重複カウントはしない（例：フルハウス完成時はスリーカードにはカウントしない）。
        *   ※ 役名はBackend側で正規化された英語表記（例: "Royal Flush", "Four of a Kind"）を返す。
    *   `win_rate`: 自分が**単独で**最も強い役を持っていた確率。
    *   `tie_rate`: 最も強い役を持つプレイヤーが複数いて、自分もその一人である確率（引き分け）。
    *   `loss_rate`: **自分より強い役を持つプレイヤーが少なくとも1人存在する確率**。
    *   `execution_count`: 実際に実行されたシミュレーション回数（リクエスト値と異なる場合がある）。
    *   ※ `win_rate + tie_rate + loss_rate` は 100% となる（浮動小数点誤差を除く）。

## 5. アルゴリズム詳細 (モンテカルロシミュレーション)

### 制約事項
*   **シミュレーション回数上限**: 最大 100,000 回。これを超えるリクエストは**上限値（100,000）に丸めて**実行し、レスポンスの `execution_count` で通知する。
*   **タイムアウト**: 計算処理が 10秒 を超える場合は処理を中断し、504 Gateway Timeout エラーを返す。
    *   ※ CPUバウンド処理のため、`ProcessPoolExecutor` 等を用いて別プロセスで実行し、キャンセル可能な構成とする。
*   **CORS**: 開発環境では `http://localhost:3000` からのアクセスを許可する。

### 処理フロー
1.  **初期化**: デッキ（52枚）から自分のカード（2枚）を除外。
2.  **ループ実行** (`num_simulations` 回):
    a.  残りのデッキをシャッフル。
    b.  **ボード生成**: 共通カード5枚をドロー。
    c.  **相手ハンド生成**: (`num_players` - 1) 人分の手札（各2枚）をドロー。
    d.  **役判定**:
        *   自分の手札 + ボード から構成される**最強役**を判定し、ランク（スコア）を取得。
        *   各相手の手札 + ボード の最強役を判定し、ランクを取得。
    e.  **集計**:
        *   自分の最強役の種類（Straight, Flush等）のカウンタをインクリメント。役名は `treys` ライブラリの出力（例: "Royal Flush", "Pair"）に準拠。
        *   **勝敗判定**:
            *   相手全員のランクの**最小値**（=最強の敵）を算出 => `min_opp_rank`
            *   `my_rank` < `min_opp_rank` => **Win** (自分が最強)
            *   `my_rank` == `min_opp_rank` => **Tie** (引き分け)
            *   `my_rank` > `min_opp_rank` => **Loss** (自分より強い相手がいる)
3.  **結果算出**:
    *   各役のカウント / 試行回数 * 100 = 役確率 (%)。
    *   Win/Tie/Loss カウント / 試行回数 * 100 = 勝率/引き分け率/敗北率 (%)。

## 6. テスト戦略

モンテカルロシミュレーションは確率的な結果を含むため、以下の戦略でテストを行う。

1.  **ロジックの正当性検証 (Unit Test)**:
    *   `random.seed` を固定し、常に同じカードが配られる状態でシミュレーションを実行。期待結果との完全一致を確認する。
    *   統計的テスト: シードを固定せず複数回実行し、結果が理論値の許容誤差範囲内（例: ±1-2%）に収まることを確認する。
2.  **エッジケース検証**:
    *   プレイヤー人数最小(2)・最大(10)での動作確認。
    *   不正なカード入力（存在しないカード、重複カード）に対するエラーハンドリング。
3.  **役判定ライブラリの検証**:
    *   既知のハンドとボードに対して、正しい役が判定されているか確認するテストケースを含める。

## 7. UI/UX設計

*   **役名表示**: Backendからは英語名（例: "High Card", "Royal Flush"）が返るため、Frontendで日本語変換マップを持つ。
    *   例: `{ "Royal Flush": "ロイヤルフラッシュ", "Straight Flush": "ストレートフラッシュ", ... }`
*   **Input Area**:
    *   トランプのカード画像またはテキストボタンを配置し、2枚を選択させる。選択済みカードはハイライト。
    *   プレイヤー人数をスライダーまたはプルダウンで選択（デフォルト6人）。
    *   「計算する」ボタン。
*   **Output Area**:
    *   計算中はローディングインジケータを表示。
    *   **役確率**: 棒グラフまたはパーセンテージリストでTOP3を表示。
    *   **勝敗予測**: 円グラフ等で「勝率」「敗北確率」を視覚的に表示。「敗北確率」を強調（リスク警告）。

## 8. 開発ステップ

1.  **Backend Setup**:
    *   `backend` ディレクトリで `uv init`。
    *   `uv add fastapi uvicorn treys`。
    *   `AGENTS.md` に従い `ruff`, `ty`, `pre-commit` を設定。
2.  **Logic Implementation**: `poker_logic.py` でシミュレーション関数を実装し、テスト実行。
3.  **API Implementation**: `/analyze` エンドポイントの実装。
4.  **Frontend Setup**: Next.js 初期化。
5.  **UI Component**: カード選択UIの実装。
6.  **Integration**: FrontendからBackend APIを呼び出し、結果を表示。
7.  **Refinement**: デザイン調整。
