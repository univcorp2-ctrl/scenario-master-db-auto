# Scenario Master DB Auto

世界中でヒットしている映画・小説・漫画などから、シナリオ設計に使える公開メタデータを継続収集し、そのDBを使ってオリジナル作品案を自動生成するリポジトリです。

GitHub Actionsで1日10回実行し、以下を自動で行います。

1. 公開メタデータを収集
2. `data/master_scenario_elements.jsonl` を更新
3. DBのシナリオ要素タグを使ってオリジナル作品案を生成
4. ヘルスチェックで「回っているか」を検査
5. `generated/latest_output.md` に最新アウトプットを保存
6. GitHubへ自動push

## 自動実行

`.github/workflows/collect.yml` がUTCで毎日10回実行されます。

```yaml
cron: '0 0,2,4,6,8,10,12,14,16,18 * * *'
```

日本時間では、おおむね 09:00 / 11:00 / 13:00 / 15:00 / 17:00 / 19:00 / 21:00 / 23:00 / 翌01:00 / 翌03:00 です。

さらに、`src/**`, `tests/**`, workflow, requirements変更時はpush直後にもテスト実行されます。

## 確認する場所

- 実行履歴: `Actions` → `Collect scenario master data`
- 回っているか: `health/latest_healthcheck.md`
- 最新アウトプット: `generated/latest_output.md`
- 生成作品DB: `generated/original_works.jsonl`
- 収集DB: `data/master_scenario_elements.jsonl`

## 保存しないもの

- 著作権のある本文
- 長いあらすじ
- 台詞
- 漫画のコマ内容
- 小説本文
- 既存作品のキャラクター名、固有設定、固有世界観のコピー

## ローカル実行

```bash
pip install -r requirements.txt
pytest
python src/collector.py --batch-size 10
python src/generator.py --count 3
python src/healthcheck.py --max-age-hours 36
```

## 注意

GitHub ActionsのcronはGitHub側のサービスなので、実行時刻の秒単位保証や100%の永久稼働保証はできません。その代わり、このリポジトリでは1日10回の多重スケジュールとヘルスチェックで停止・遅延を検知できるようにしています。
