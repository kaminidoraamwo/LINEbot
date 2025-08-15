# LINE Bot with RAG System

AI搭載のLINE自動返信ボット（RAG機能付き）

## 🚀 機能

- **自動返信**: LINEメッセージに自動で返答
- **RAG機能**: 過去のQ&Aデータを参照して精度の高い回答を生成
- **NGワードガード**: 不適切な表現を自動検出・フラグ付け
- **カスタマイズ可能**: 返答スタイルを環境変数で調整

## 🏗️ システム構成

```
ユーザー → LINE → Webhook → FastAPI Server
                              ↓
                          埋め込み生成
                              ↓
                    Supabase（類似Q&A検索）
                              ↓
                     Gemini AI（回答生成）
                              ↓
                        NGワードチェック
                              ↓
                          LINE返信
```

## 📋 必要な環境

- Python 3.9+
- Google Gemini API キー
- Supabase アカウント
- LINE Developersアカウント（LINE Bot利用時）

## 🔧 セットアップ

### 1. リポジトリのクローン
```bash
git clone https://github.com/kaminidoraamwo/LINEbot.git
cd LINEbot
```

### 2. 依存パッケージのインストール
```bash
pip install -r requirements.txt
pip install supabase google-genai numpy
```

### 3. 環境変数の設定
`.env.example`を`.env`にコピーして編集：
```bash
cp .env.example .env
nano .env
```

必要な設定：
- `GOOGLE_API_KEY`: [Google AI Studio](https://aistudio.google.com/apikey)から取得
- `SUPABASE_URL`: Supabaseプロジェクトから取得
- `SUPABASE_KEY`: Supabase service_roleキー
- `LINE_CHANNEL_SECRET`: LINE Developers から取得
- `LINE_CHANNEL_TOKEN`: LINE Developers から取得

### 4. Supabaseテーブル作成
Supabase SQL Editorで実行：
```sql
-- ベクター拡張を有効化
create extension if not exists vector;

-- テーブル作成
create table rag_data (
  id serial primary key,
  question text,
  answer text,
  content text not null,
  embedding vector(1536),
  created_at timestamp default now()
);

-- インデックス作成
create index on rag_data using ivfflat (embedding vector_cosine_ops);
```

### 5. FAQデータの投入
```bash
python3 ingest_csv.py faq.csv
```

## 🚀 起動方法

### ローカルテスト
```bash
# サーバー起動
python3 -m uvicorn main:app --reload --port 8000

# APIドキュメント確認
# http://localhost:8000/docs
```

### LINE Botとして運用
```bash
# ngrokで公開（開発用）
ngrok http 8000

# LINE DevelopersでWebhook URLを設定
# https://xxx.ngrok.io/line
```

## 📁 ファイル構成

```
line-bot/
├── main.py           # メインサーバー
├── ingest_csv.py     # データ投入スクリプト
├── faq.csv           # Q&Aデータ
├── requirements.txt  # 依存パッケージ
├── .env             # 環境変数（非公開）
└── .env.example     # 環境変数テンプレート
```

## 🔐 セキュリティ

- APIキーは`.env`ファイルに保存（`.gitignore`で除外）
- LINE署名検証でセキュアな通信を確保
- NGワードガードで不適切な回答を防止

## 📝 ライセンス

MIT

## 🤝 貢献

Issue・Pull Request歓迎です！

## 📧 お問い合わせ

[Issues](https://github.com/kaminidoraamwo/LINEbot/issues)からお願いします。