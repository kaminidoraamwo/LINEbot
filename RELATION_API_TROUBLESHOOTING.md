# Re:lation API トラブルシューティングガイド

## 概要

このドキュメントは、Re:lation API統合で発生する404エラーや其他の問題を解決するための包括的なガイドです。

## 404エラーの主要原因と解決策

### 1. 基本設定の確認

#### ✅ 必要な環境変数
```bash
# .envファイルに以下を設定
RELATION_ACCESS_TOKEN=your_access_token_here
RELATION_SUBDOMAIN=your_subdomain_here
RELATION_MESSAGE_BOX_ID=123
```

#### 🔍 設定値の確認方法

**サブドメインの確認:**
- ブラウザでRe:lationにアクセス
- URL: `https://[ここがサブドメイン].relationapp.jp`
- 例: `https://company-name.relationapp.jp` → `RELATION_SUBDOMAIN=company-name`

**メッセージボックスIDの確認:**
- Re:lation管理画面 → 受信箱設定
- URLの末尾の数値: `https://company.relationapp.jp/message_box/123` → `RELATION_MESSAGE_BOX_ID=123`

**アクセストークンの取得:**
- Re:lation管理画面 → 設定（歯車アイコン）→ システム設定 → APIトークン
- 「新規作成」でトークンを発行
- 必要な権限: 「チケット読み取り」「チケット作成」「チケット更新」

### 2. URLパターンの確認

#### ✅ 正しいAPIエンドポイント構造
```
ベースURL: https://{subdomain}.relationapp.jp/api/v2
メッセージボックス必須: https://{subdomain}.relationapp.jp/api/v2/{message_box_id}/{endpoint}
メッセージボックス不要: https://{subdomain}.relationapp.jp/api/v2/{endpoint}
```

#### ❌ よくある間違い
```
× https://{subdomain}.relationapp.jp/api/v1/...  (古いバージョン)
× https://{subdomain}.relationapp.jp/api/{endpoint}  (v2がない)
× https://relationapp.jp/api/v2/...  (サブドメインがない)
× https://{subdomain}.relationapp.jp/v2/...  (/apiがない)
```

### 3. HTTPヘッダーの確認

#### ✅ 必要なヘッダー
```python
headers = {
    "Authorization": f"Bearer {access_token}",  # 認証ヘッダー
    "Content-Type": "application/json",         # POST/PUT時
    "Accept": "application/json",               # レスポンス形式
    "User-Agent": "Your-App-Name/1.0"          # 推奨
}
```

#### ❌ よくある間違い
```python
# 間違い: Bearer がない
"Authorization": f"Token {access_token}"

# 間違い: 別のヘッダー名
"X-API-Token": access_token

# 間違い: 不正な形式
"Authorization": access_token
```

## HTTPステータスコード別対処法

### 400 Bad Request
**原因:** リクエストパラメータが無効
- JSONの構文エラー
- 必須パラメータの不足
- データ型の不一致

**対処法:**
```python
# リクエストデータの検証
import json
data = {"subject": "テスト", "message": "内容"}
json_str = json.dumps(data, ensure_ascii=False)  # JSON形式確認
```

### 401 Unauthorized  
**原因:** 認証失敗
- アクセストークンが無効または期限切れ
- 認証ヘッダーの形式が間違い

**対処法:**
1. Re:lation管理画面でトークンの有効性確認
2. 新しいトークンを発行
3. 認証ヘッダーの形式確認

### 403 Forbidden
**原因:** アクセス権限不足またはレート制限
- トークンにメッセージボックスへのアクセス権限がない
- レート制限（60回/分）を超過
- IP制限が設定されている

**対処法:**
```python
# レスポンスヘッダーでレート制限確認
response_headers = response.headers
print(f"制限: {response_headers.get('X-RateLimit-Limit')}")
print(f"残り: {response_headers.get('X-RateLimit-Remaining')}")
print(f"リセット: {response_headers.get('X-RateLimit-Reset')}")
```

### 404 Not Found
**原因:** エンドポイントまたはリソースが存在しない
- URL構造の間違い
- 存在しないメッセージボックスID
- 存在しないチケットID

**対処法:**
1. URL構造の再確認
2. メッセージボックスIDの確認
3. API仕様書との照合

### 415 Unsupported Media Type
**原因:** Content-Typeヘッダーが不正
**対処法:** `Content-Type: application/json` を設定

### 500 Internal Server Error
**原因:** サーバー側の問題
**対処法:** Re:lationサポートに連絡

### 503 Service Unavailable  
**原因:** メンテナンス中
**対処法:** 時間を空けて再試行

## 診断スクリプトの実行

### 1. 基本診断の実行
```bash
python3 relation_api_investigation.py
```

### 2. 結果の確認
生成されるレポートファイル: `relation_api_debug_report.md`

### 3. 統合テストの実行  
```bash
python3 relation_integration_fixed.py
```

## 段階的デバッグ手順

### Step 1: 設定値検証
```python
import os
from dotenv import load_dotenv
load_dotenv()

# 必要な値が設定されているか確認
token = os.getenv("RELATION_ACCESS_TOKEN")
subdomain = os.getenv("RELATION_SUBDOMAIN") 
message_box_id = os.getenv("RELATION_MESSAGE_BOX_ID")

print(f"Token: {'設定済み' if token else '未設定'}")
print(f"Subdomain: {subdomain}")
print(f"Message Box ID: {message_box_id}")
```

### Step 2: 接続テスト
```python
import requests

# 最もシンプルなエンドポイントでテスト
url = f"https://{subdomain}.relationapp.jp/api/v2/message_boxes"
headers = {"Authorization": f"Bearer {token}"}

response = requests.get(url, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")
```

### Step 3: エラー詳細確認
```python
if response.status_code != 200:
    print("=== エラー詳細 ===")
    print(f"Status Code: {response.status_code}")
    print(f"Headers: {dict(response.headers)}")
    print(f"Response: {response.text}")
    print(f"URL: {response.url}")
```

## API仕様の確認事項

### 利用可能なエンドポイント（2024年版）

#### メッセージボックス不要
- `GET /message_boxes` - 受信箱一覧

#### メッセージボックス必要
- `GET /{message_box_id}/users` - ユーザー一覧
- `GET /{message_box_id}/case_categories` - チケット分類一覧  
- `GET /{message_box_id}/labels` - ラベル一覧
- `GET /{message_box_id}/tickets/search` - チケット検索
- `GET /{message_box_id}/tickets/{ticket_id}` - チケット詳細
- `PUT /{message_box_id}/tickets/{ticket_id}` - チケット更新
- `POST /{message_box_id}/comments` - コメント作成（2024年4月追加）
- `POST /{message_box_id}/templates/search` - テンプレート検索（2024年4月追加）

### レート制限
- **制限:** 60回/分
- **ヘッダー:** `X-RateLimit-*` で状況確認可能
- **超過時:** HTTP 403エラー

### 文字エンコーディング
- **要求:** UTF-8
- **レスポンス:** UTF-8

## よくある問題と解決例

### 問題1: 「メッセージボックスが見つからない」
```python
# 原因: message_box_idが間違っている
# 解決: 正しいIDを確認
response = requests.get(f"https://{subdomain}.relationapp.jp/api/v2/message_boxes", 
                       headers={"Authorization": f"Bearer {token}"})
message_boxes = response.json()
for mb in message_boxes:
    print(f"ID: {mb['id']}, Name: {mb['name']}")
```

### 問題2: 「アクセストークンが無効」  
```python
# 原因: トークンの期限切れまたは権限不足
# 解決: 新しいトークンの発行
# Re:lation管理画面 → システム設定 → APIトークン → 新規作成
```

### 問題3: 「レート制限エラー」
```python
import time

# 解決: リクエスト間隔の調整
def safe_api_call(url, headers, max_retries=3):
    for attempt in range(max_retries):
        response = requests.get(url, headers=headers)
        if response.status_code != 403:
            return response
        print(f"レート制限中、{60}秒待機...")
        time.sleep(60)
    raise Exception("レート制限を超過しました")
```

## サポート連絡先

### Re:lation サポート
- **サポートチャット:** Re:lation管理画面内
- **メール:** support@ingage.jp
- **公式ドキュメント:** https://developer.ingage.jp/

### 連絡時に準備する情報
1. 使用しているサブドメイン
2. エラーの詳細（HTTPステータスコード、エラーメッセージ）
3. 実行したAPIリクエストの詳細
4. 診断スクリプトの実行結果

## まとめ

Re:lation API統合の404エラーは主に以下の原因で発生します：

1. **設定値の誤り** （最も多い原因）
2. **URL構造の間違い**
3. **認証情報の問題**
4. **権限設定の不備**

このガイドに従って段階的に確認することで、多くの問題を解決できます。

解決しない場合は、診断スクリプトの実行結果とともにRe:lationサポートにお問い合わせください。