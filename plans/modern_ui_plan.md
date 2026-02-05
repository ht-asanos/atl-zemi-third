# Modern UI Refresh Plan for Texas Holdem Pre-flop Analyzer

## 1. 概要
本ドキュメントは、`feature/modern-ui` ブランチにおけるUI刷新の詳細な実装計画です。
既存の無機質なUIを、カードのビジュアル化とモダンなデザイン適用によって、視覚的に魅力的かつ直感的なものへ昇華させることを目的とします。

## 2. デザインコンセプト
- **Visual Richness**: テキストベースのカード表現から、トランプの実物を模したリッチなビジュアルへ変更します。
- **Clean & Accessible**: Glassmorphism（ブラー効果）への依存を減らし、**ドロップシャドウとボーダー**による明確な領域分離を採用します。背景とコンテンツの分離を明確にし、可読性とパフォーマンスを両立させます。
- **Interactive Feedback**: ユーザー操作に対するフィードバック（ホバー効果、選択状態、結果表示のアニメーション）を強化します。
- **Responsive**: モバイルからデスクトップまで、あらゆるデバイスで美しく表示されるレイアウトを維持します。

## 3. 技術アプローチ
- **CSS Framework**: Tailwind CSS v4（既存）を最大限活用します。
- **Icons**: Unicode文字（♠♥♦♣）を引き続き使用しますが、タイポグラフィと配置の工夫でグラフィカルに見せます。
- **Animation**: CSS Transitions / Animations を使用し、外部ライブラリ（Framer Motion等）への依存を増やさずに軽量に実装します。

## 4. コンポーネント設計

### 4.1 新規コンポーネント: `Card`
`src/components/ui/Card.tsx` を新規作成し、カードの表示ロジックをカプセル化します。

**Props:**
```typescript
interface CardProps {
  rank: string;       // 'A', 'K', 'Q', etc.
  suit: 's' | 'h' | 'd' | 'c'; // spades, hearts, diamonds, clubs
  isSelected?: boolean;
  isDisabled?: boolean;
  onClick?: () => void;
  size?: 'sm' | 'md' | 'lg'; // サイズバリエーション（今回はmd/smを使用）
}
```

**デザイン仕様:**
- **背景/形状**: 白背景、角丸 (`rounded-xl`)、ドロップシャドウで物理的なカード感を演出。
- **レイアウト**: 左上と右下にランクとスートを配置。中央に大きなスートを表示。
- **インタラクション**: 選択時は枠線 (`ring`) と若干の「浮き上がり」効果 (`translate-y`)。
- **配色方針**: 既存実装（4色デッキ：♠黒, ♥赤, ♦青, ♣緑）を維持します。これはオンラインポーカーで一般的な仕様であり、視認性を高めるためです。
- **凡例の追加**: ユーザーの混乱を防ぐため、CardSelectorのスート見出し部分に「♠ Spades」「♥ Hearts」「♦ Diamonds」「♣ Clubs」のようなラベルを明記し、色とスートの対応関係を直感的に伝えます。

### 4.2 改修: `CardSelector`
- 既存のボタングリッドを廃止し、新しい `Card` コンポーネントを使用。
- スートヘッダー部分のデザインを強化し、上記の凡例（ラベル）を追加。
- スートごとに行を分けるレイアウトは維持しつつ、カード間の余白（gap）を調整。
- コンテナ自体のデザインをシンプルにし、カードを目立たせる。

### 4.3 改修: `ResultView`
- **プログレスバー**: 結果表示時に0%からスムーズに伸びるCSSアニメーションを追加。
- **カード表示**: 「My Top 3 Likely Hands」のリストもテキストだけでなく、小さなカードアイコンを添えて視認性を向上。
- **レイアウト**: 結果全体をカード状のパネルに収める。背景とのコントラストを意識し、不透明度を高めに設定します。

### 4.4 改修: `PlayerSettings`
- **Input/Select**: デフォルトのブラウザスタイルを排除し、Tailwindでカスタムスタイルを適用。
- **統一感**: カードセレクターや結果表示とトーン＆マナーを合わせる。

### 4.5 全体レイアウト (`page.tsx` / `globals.css`)
- **背景**: **Slate Gradient** (例: `bg-gradient-to-br from-slate-100 to-slate-300`) を採用。紫系を避け、カードの色（赤・青・緑・黒）と干渉しないニュートラルでプロフェッショナルな配色とします。
- **コンテナ**: メインコンテンツエリアに白背景 (`bg-white/95`) を適用。Blur効果（backdrop-blur）は視覚効果が薄いため廃止し、代わりに `shadow-xl` と微細なボーダー (`border-slate-200`) で背景との分離を明確にします。
- **フォント**: `layout.tsx` で設定済みの `Geist` フォントを使用します（確認済み）。万が一適用に問題がある場合は、Next.js標準の `Inter` フォントへの切り替えをフォールバックとして用意します。

## 5. 実装ステップ

1.  **Gitブランチ作成**
    - `feature/modern-ui` を作成。

2.  **Cardコンポーネント実装**
    - `src/components/ui/Card.tsx` 作成。
    - Storybook等はないため、一時的に画面に表示してデザイン調整。

3.  **コンポーネント刷新**
    - `CardSelector.tsx` の書き換え。
    - `ResultView.tsx` の書き換え（アニメーション追加）。
    - `PlayerSettings.tsx` のスタイル調整。

4.  **全体テーマ適用**
    - `globals.css` で背景設定。
    - `page.tsx` でレイアウトコンテナのクラス調整。

5.  **動作確認・微調整**
    - レスポンシブ挙動の確認。
    - アニメーションのタイミング調整。

## 6. ファイル構成の変更
```diff
 atl-zemi-third/frontend/src/
 ├── app/
 │   ├── globals.css      (Updated: テーマ適用)
 │   └── page.tsx         (Updated: レイアウト調整)
 ├── components/
 │   ├── ui/              (New Directory)
 │   │   └── Card.tsx     (New File)
 │   ├── CardSelector.tsx (Updated)
 │   ├── PlayerSettings.tsx (Updated)
 │   └── ResultView.tsx   (Updated)
```
