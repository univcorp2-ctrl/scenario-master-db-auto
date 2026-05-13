# Scenario Master DB Auto

世界中でヒットしている映画・小説・漫画などから、シナリオ設計に使える公開メタデータを継続収集し、そのDBを使ってオリジナル作品案を自動生成するリポジトリです。

GitHub Actionsで1日10回実行し、以下を自動で行います。

1. 公開メタデータを収集
2. `data/master_scenario_elements.jsonl` を更新
3. DBのシナリオ要素タグを使ってオリジナル作品案を生成
4. `generated/original_works.jsonl` と日別Markdownへ保存
5. GitHubへ自動push

## 保存するもの

### マスターDB

- タイトル
- 媒体: film / novel / manga
- 公開年
- 国
- ジャンル
- 人気指標
- 公開ソースURL
- 自動推定したシナリオ要素タグ

### オリジナル作品案

- 日本語タイトル案
- ログライン
- コア対立
- 主人公アーキタイプ
- 敵対圧力
- 世界観
- 三幕構成
- モチーフ
- 続編フック
- 参照したパターンID

## 保存しないもの

- 著作権のある本文
- 長いあらすじ
- 台詞
- 漫画のコマ内容
- 小説本文
- 既存作品のキャラクター名、固有設定、固有世界観のコピー

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
python src/generator.py --count 3
pytest
```

## 主なファイル

- `src/collector.py`: 作品メタデータ収集
- `src/generator.py`: DBからオリジナル作品案を生成
- `data/master_scenario_elements.jsonl`: シナリオ要素DB
- `generated/original_works.jsonl`: 自動生成された作品案DB
- `generated/index.json`: 生成作品の集計

## 生成方針

生成器は既存作品の本文や具体的設定を使いません。ジャンル、対立軸、感情エンジン、テーマ、舞台タグなどの抽象パターンを組み替えて、別物の企画として出力します。
