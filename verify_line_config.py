#!/usr/bin/env python3
"""LINE設定確認スクリプト"""
import os
import requests
from dotenv import load_dotenv

load_dotenv()

print("=" * 60)
print("LINE Bot 設定確認")
print("=" * 60)

# 環境変数チェック
channel_secret = os.getenv("LINE_CHANNEL_SECRET")
channel_token = os.getenv("LINE_CHANNEL_TOKEN")

print(f"✅ Channel Secret: {'設定済み' if channel_secret else '❌ 未設定'}")
print(f"✅ Channel Token: {'設定済み' if channel_token else '❌ 未設定'}")

if channel_token:
    # LINE APIで設定を確認
    headers = {"Authorization": f"Bearer {channel_token}"}
    
    # Webhook エンドポイント情報を取得
    response = requests.get(
        "https://api.line.me/v2/bot/channel/webhook/endpoint",
        headers=headers
    )
    
    print(f"\n📡 Webhook設定状態:")
    if response.status_code == 200:
        data = response.json()
        print(f"  - エンドポイント: {data.get('endpoint', '未設定')}")
        print(f"  - アクティブ: {data.get('active', False)}")
    else:
        print(f"  ❌ 取得失敗: {response.status_code}")
    
    # Bot情報を取得
    response = requests.get(
        "https://api.line.me/v2/bot/info",
        headers=headers
    )
    
    print(f"\n🤖 Bot情報:")
    if response.status_code == 200:
        data = response.json()
        print(f"  - 表示名: {data.get('displayName', '不明')}")
        print(f"  - Bot ID: {data.get('userId', '不明')}")
        print(f"  - 画像URL: {data.get('pictureUrl', '未設定')}")
    else:
        print(f"  ❌ 取得失敗: {response.status_code} - {response.text}")

print("\n" + "=" * 60)
print("ngrok URL: https://86f51d09e845.ngrok-free.app/line")
print("この URL を LINE Developers Console に設定してください")
print("=" * 60)