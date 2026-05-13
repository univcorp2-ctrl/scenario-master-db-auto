# Cloud-only operation

このリポジトリは、ローカルPCを使わずGitHub上だけで運用できます。

## 現在の構成

- 実行環境: GitHub Actions
- 実行回数: 1日10回
- DB保存先: `data/master_scenario_elements.jsonl`
- 集計インデックス: `data/index.json`
- 実行ログ: `data/run_log.jsonl`
- 権限: `.github/workflows/collect.yml` の `permissions: contents: write` により、ActionsからDB更新をpush

## 確認する場所

- 実行履歴: `Actions` → `Collect scenario master data`
- DB件数: `data/index.json` の `total_records`
- 本体DB: `data/master_scenario_elements.jsonl`

## 手動で今すぐ回す方法

1. GitHubでこのリポジトリを開く
2. `Actions` を開く
3. `Collect scenario master data` を開く
4. `Run workflow` を押す

## 注意

GitHub ActionsのcronはGitHub側の負荷状況により数分遅れることがあります。APIの一時障害で候補取得が少ない回もありますが、次回以降の定期実行で継続されます。
