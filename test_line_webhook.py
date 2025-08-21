#!/usr/bin/env python3
"""LINE Webhook テスト"""
import os
import json
import hmac
import hashlib
import base64
import requests
from dotenv import load_dotenv

load_dotenv()

# テスト用のLINEイベント
test_event = {
    "events": [{
        "type": "message",
        "replyToken": "test_reply_token",
        "message": {
            "type": "text",
            "text": "テストメッセージ"
        }
    }]
}

# 署名を生成
channel_secret = os.getenv("LINE_CHANNEL_SECRET", "").encode()
body = json.dumps(test_event).encode()
signature = base64.b64encode(
    hmac.new(channel_secret, body, hashlib.sha256).digest()
).decode()

print(f"Channel Secret exists: {bool(channel_secret)}")
print(f"Generated signature: {signature}")

# Webhookをテスト
response = requests.post(
    "http://localhost:8001/line",
    data=body,
    headers={
        "Content-Type": "application/json",
        "X-Line-Signature": signature
    }
)

print(f"Response status: {response.status_code}")
print(f"Response body: {response.text}")

if response.status_code == 200:
    print("✅ Webhook処理成功")
elif response.status_code == 403:
    print("❌ 署名検証失敗")
else:
    print(f"❌ エラー: {response.status_code}")