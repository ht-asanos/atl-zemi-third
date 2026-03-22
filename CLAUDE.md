# CLAUDE.md

This project uses `AGENTS.md` as the source of truth for agent instructions.

- **Instructions:** Refer to [AGENTS.md](./AGENTS.md).
- **Local Overrides:** Use `CLAUDE.local.md` for personal environment settings (ignored by git).

Please read `AGENTS.md` before performing any tasks to ensure alignment with team standards.

ただし、プラニングのときには以下を行うこと。
## Planning Instructions
ユーザーに計画を提示する前に、`codex`コマンドで計画のレビューを行うこと。具体的な使い方は以下の通り。
レビュー指示の文章は適宜調整すること。ただし`codex`コマンドは本質的ではない指摘をすることもあるので「細かな点の指摘はしないで致命的な点のみ指摘して。」という指示は必ず入れること。

```
# initial plan review request
# 必ず -mでモデルを指定すること（gpt-5.4 が最適）
codex exec -m gpt-5.4 "このプランをレビューして。細かな点の指摘はしないで致命的な点のみ指摘して。: {plan_full_path} (ref:{CLAUDE.md full_path})"

# updated plan review request
# resume --last をつけないと最初のレビューの文脈が失われるので注意
codex exec resume --last -m gpt-5.4 "プランを更新したからレビューして。細かな点の指摘はしないで致命的な点のみ指摘して。: {plan_full_path} (ref:{CLAUDE.md full_path})"
```
