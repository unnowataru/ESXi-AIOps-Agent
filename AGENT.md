# AGENT.md

## 目的

このリポジトリで動くエージェントに対し、案件固有差分と共通 SoT の関係を明示する。

## 共通前提

- 共通方針は `work-env` を優先する
- `work-env` は `C:\dev\work-env` にある前提で扱う
- 操作 UI は VS Code
- 実行オーケストレーターは Codex
- Claude は設計 / レビュー sidecar
- xAI は調査 sidecar
- `x-search` は blog / slide 向けの X 調査に使う

## 案件固有差分

- この repo は Gemini, SSH, Playwright を使う ESXi AIOps agent を扱う
- 主な実装対象は `esxi_aiops.py`
- 自然言語操作の安全境界が重要

## 禁止

- 共通方針をこの repo 単独で上書きしない
- secrets をコミットしない
- `x-search` を ESXi 操作の制御経路に使わない
