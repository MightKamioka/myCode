#!/usr/bin/env bash
set -euo pipefail

if [ ! -f client_secret.json ]; then
  echo "[ERROR] client_secret.json が見つかりません。READMEの手順で配置してください。"
  exit 1
fi

echo "[1/5] 依存関係をインストール"
pip install -r requirements.txt >/dev/null

echo "[2/5] サーバー起動"
echo "  別ターミナルで実行: uvicorn app.main:app --reload"

echo "[3/5] ブラウザで開く"
echo "  http://127.0.0.1:8000"

echo "[4/5] UIで実行"
echo "  - YouTubeでログイン"
echo "  - 動画データを同期して保存"
echo "  - Analytics / 検索語を同期"
echo "  - コメントを同期"
echo "  - キーワード調査を実行"

echo "[5/5] API健全性確認 (ログイン後)"
echo "  curl -X POST http://127.0.0.1:8000/self-test"

echo "完了: data/ 配下にスナップショットが出力されることを確認してください。"
