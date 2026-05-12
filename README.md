# Scenario Master DB Auto

世界中でヒットしている映画・小説・漫画などから、シナリオ設計に使える公開メタデータを継続収集するマスターデータベースです。

GitHub Actionsで1日10回実行し、`data/master_scenario_elements.jsonl` を更新して自動pushします。

## 保存するもの

- タイトル
- 媒体: film / novel / manga
- 公開年
- 国
- ジャンル
- 人気指標
- 公開ソースURL
- 自動推定したシナリオ要素タグ

## 保存しないもの

- 著作権のある本文
- 長いあらすじ
- 台詞
- 漫画のコマ内容
- 小説本文

## 自動実行

`.github/workflows/collect.yml` がUTCで毎日10回実行されます。

```yaml
cron: '0 0,2,4,6,8,10,12,14,16,18 * * *'
```

日本時間では、おおむね 09:00 / 11:00 / 13:00 / 15:00 / 17:00 / 19:00 / 21:00 / 23:00 / 翌01:00 / 翌03:00 です。

## ローカル実行

```bash
pip install -r requirements.txt
python src/collector.py --batch-size 10
pytest
```
