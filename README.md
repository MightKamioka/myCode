# Local VidIQ-like Analyzer

VidIQ風の分析機能を**ローカル環境だけ**で使えるミニサービスです。

## 機能
- **Sherlock風OSINT（単一ユーザー調査 / 登録ユーザー全体調査 / Bluesky / Threads対応）**
- **コメント調査（単一ユーザー注目 / 動画コメント一覧 / 返信UI / 全チャンネル共有ユーザーDB）**
- **キーワード監視 / カテゴリ監視 / 競合監視（頻度: daily/every2/weekly）とトレンド検知通知**
- **競合分析（ウォッチリスト比較 / views・subscribers・video count / 30日・60日・12か月比較 / 7・14・28日成長率 / 平均日次再生 / 競合の伸びた動画）**
- **キーワード調査（検索ボリューム推定/競合度/関連キーワード/トレンド推移/Rising keywords/Top opportunities/チャンネル規模に対する狙い目判定）**
- **Channel Audit（VPH/エンゲージメント率/登録者増減/総視聴時間・平均視聴時間/Retention上位動画/上位プレイリスト/流入元）**
- **チャンネル概要ダッシュボード（最新動画、伸び動画、失速動画、Scorecard、ライブ近似監視、日次/週次/月次比較）**
- SEOスコア算出（タイトル長・説明文長・タグ数・台本量・キーワード密度）
- キーワード密度の可視化
- タグ提案
- タイトル案生成
- 説明文ドラフト生成
- 離脱リスク（繰り返し過多）セグメント検出
- **ブラウザOAuthでYouTubeログイン**
- **YouTube Data API 連携（チャンネル/動画/監視チャンネルUID）**
- **YouTube Analytics API 連携（日次指標・検索語履歴）**
- **ログイン時（初回または前回取得から12時間経過）に自動フル取得し、差分を記録**
- **定期同期（`SYNC_INTERVAL_MINUTES`ごと）で差分更新**
- **複数チャンネル運営向けにチャンネル単位でデータ分離表示/保存**
- **類似チャンネルをUID登録して監視し、動画差分（タイトル/説明文/タグ文体変化含む）を記録**

## セットアップ
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## YouTube連携の準備
1. Google Cloud Console で YouTube Data API v3 と YouTube Analytics API を有効化
2. OAuth クライアント (Web application) を作成
3. `http://127.0.0.1:8000/oauth2callback` をリダイレクトURIに追加
4. クライアントシークレットJSONをプロジェクト直下に `client_secret.json` として配置

## 起動
```bash
SYNC_INTERVAL_MINUTES=60 uvicorn app.main:app --reload
```

ブラウザで `http://127.0.0.1:8000` を開き、
- 「YouTubeでログイン」→ Googleアカウント認証（初回 or 12時間経過時は自動フル同期）
- 「動画データを同期して保存」→ 自チャンネルを手動フル同期
- 「Analytics / 検索語を同期」→ YouTube Analytics API から履歴スナップショット保存
- 「キーワード調査を実行」→ ボリューム/競合/トレンド/機会スコアを算出して保存
- 「監視チャンネルUID」を登録 → 「監視チャンネルを一括同期」
- 監視ルールを追加（keyword/category/competitor + 頻度 + 閾値）
- 「トレンド検知を今すぐ実行」で通知を生成（`data/notifications/`）

## ローカルキャッシュ / スナップショット保存先
- 自チャンネル動画: `data/channels/<channel_id>/video_exports/`
- 自チャンネル動画差分: `data/channels/<channel_id>/performance_diffs/`
- 自チャンネルAnalytics履歴: `data/channels/<channel_id>/analytics_snapshots/`
- 自チャンネル検索語履歴: `data/channels/<channel_id>/search_terms_snapshots/`
- 監視チャンネル動画: `data/monitored/<channel_id>/video_exports/`
- 監視チャンネル差分: `data/monitored/<channel_id>/performance_diffs/`

## テスト
```bash
pytest -q
```

## browser_container をローカルで有効化
`browser_container`互換の実行環境として、`browserless/chromium`を使えます。

```bash
docker compose -f docker-compose.browser.yml up -d
python -m playwright install chromium
python scripts/browser_container_smoke.py --url http://127.0.0.1:8000 --out artifacts/home.png
```


## 自分のアカウントでテスト稼働
```bash
./scripts/test_with_your_account.sh
```

ログイン後の接続確認:
```bash
curl -X POST http://127.0.0.1:8000/self-test
```

`channel_api_ok: true` と `analytics_api_ok: true` が返れば、実運用テスト準備完了です。
