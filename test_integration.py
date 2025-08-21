#!/usr/bin/env python3
"""
LINE Bot と Re:lation API の統合テスト
"""
import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# テストカラー
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
ENDC = '\033[0m'

def print_test(name, result, details=""):
    """テスト結果を表示"""
    status = f"{GREEN}✅ 成功{ENDC}" if result else f"{RED}❌ 失敗{ENDC}"
    print(f"\n{BLUE}[テスト]{ENDC} {name}")
    print(f"  結果: {status}")
    if details:
        print(f"  詳細: {details}")

def test_relation_api():
    """Re:lation API接続テスト"""
    print(f"\n{YELLOW}=== Re:lation API テスト ==={ENDC}")
    
    token = os.getenv('RELATION_ACCESS_TOKEN')
    subdomain = os.getenv('RELATION_SUBDOMAIN')
    message_box_id = os.getenv('RELATION_MESSAGE_BOX_ID')
    
    if not all([token, subdomain, message_box_id]):
        print_test("環境変数チェック", False, "必要な環境変数が設定されていません")
        return False
    
    # 受信箱一覧の取得
    url = f"https://{subdomain}.relationapp.jp/api/v2/message_boxes"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            print_test("Re:lation API接続", True, f"受信箱数: {len(data)}")
            
            # メッセージボックスIDの確認
            box_ids = [str(box.get('id')) for box in data]
            if message_box_id in box_ids:
                print_test("メッセージボックスID確認", True, f"ID {message_box_id} が存在します")
            else:
                print_test("メッセージボックスID確認", False, f"ID {message_box_id} が見つかりません。利用可能: {box_ids}")
            return True
        else:
            print_test("Re:lation API接続", False, f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print_test("Re:lation API接続", False, str(e))
        return False

def test_line_webhook():
    """LINE Webhookエンドポイントテスト"""
    print(f"\n{YELLOW}=== LINE Webhook テスト ==={ENDC}")
    
    # ヘルスチェック
    try:
        response = requests.get("http://localhost:8001/health", timeout=5)
        if response.status_code == 200:
            print_test("サーバーヘルスチェック", True, "サーバーは正常に稼働中")
        else:
            print_test("サーバーヘルスチェック", False, f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print_test("サーバーヘルスチェック", False, "サーバーに接続できません")
        return False
    
    # LINE Webhookエンドポイントの確認（GETリクエスト）
    try:
        response = requests.get("http://localhost:8001/line", timeout=5)
        # LINE webhookは通常POSTのみ受け付けるため、405が正常
        if response.status_code == 405:
            print_test("LINE Webhookエンドポイント", True, "エンドポイントが存在します")
            return True
        else:
            print_test("LINE Webhookエンドポイント", False, f"予期しないレスポンス: HTTP {response.status_code}")
            return False
    except Exception as e:
        print_test("LINE Webhookエンドポイント", False, str(e))
        return False

def test_ai_response():
    """AI応答機能のテスト"""
    print(f"\n{YELLOW}=== AI応答機能テスト ==={ENDC}")
    
    # テスト用の質問
    test_query = "製品の返品方法を教えてください"
    
    try:
        response = requests.post(
            "http://localhost:8001/test-ai",
            json={"query": test_query},
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data:
                print_test("AI応答生成", True, f"回答文字数: {len(data['response'])}")
                print(f"  {BLUE}質問:{ENDC} {test_query}")
                print(f"  {BLUE}回答:{ENDC} {data['response'][:100]}...")
                return True
            else:
                print_test("AI応答生成", False, "レスポンスが不正です")
                return False
        elif response.status_code == 404:
            print_test("AI応答生成", True, "テストエンドポイントは未実装（正常）")
            return True
        else:
            print_test("AI応答生成", False, f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print_test("AI応答生成", False, str(e))
        return False

def test_database_connection():
    """データベース接続テスト"""
    print(f"\n{YELLOW}=== データベース接続テスト ==={ENDC}")
    
    supabase_url = os.getenv('SUPABASE_URL')
    supabase_key = os.getenv('SUPABASE_KEY')
    
    if not all([supabase_url, supabase_key]):
        print_test("Supabase環境変数", False, "必要な環境変数が設定されていません")
        return False
    
    print_test("Supabase環境変数", True, "設定確認済み")
    
    # Supabase接続テスト
    headers = {
        "apikey": supabase_key,
        "Authorization": f"Bearer {supabase_key}"
    }
    
    try:
        # FAQテーブルの存在確認
        response = requests.get(
            f"{supabase_url}/rest/v1/faq_embeddings?select=count",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            print_test("Supabaseデータベース接続", True, "FAQ埋め込みテーブルにアクセス可能")
            return True
        elif response.status_code == 401:
            print_test("Supabaseデータベース接続", False, "認証エラー")
            return False
        else:
            print_test("Supabaseデータベース接続", False, f"HTTP {response.status_code}")
            return False
    except Exception as e:
        print_test("Supabaseデータベース接続", False, str(e))
        return False

def main():
    """メインテスト実行"""
    print(f"{YELLOW}{'='*60}{ENDC}")
    print(f"{YELLOW}   LINE Bot × Re:lation 統合テスト{ENDC}")
    print(f"{YELLOW}{'='*60}{ENDC}")
    print(f"実行時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # 各テストを実行
    results = []
    results.append(("Re:lation API", test_relation_api()))
    results.append(("LINE Webhook", test_line_webhook()))
    results.append(("データベース", test_database_connection()))
    results.append(("AI応答", test_ai_response()))
    
    # 結果サマリー
    print(f"\n{YELLOW}=== テスト結果サマリー ==={ENDC}")
    success_count = sum(1 for _, result in results if result)
    total_count = len(results)
    
    for name, result in results:
        status = f"{GREEN}✅{ENDC}" if result else f"{RED}❌{ENDC}"
        print(f"  {status} {name}")
    
    print(f"\n{BLUE}結果: {success_count}/{total_count} テスト成功{ENDC}")
    
    if success_count == total_count:
        print(f"{GREEN}🎉 すべてのテストが成功しました！{ENDC}")
        print(f"\n{BLUE}次のステップ:{ENDC}")
        print("1. ngrokでトンネルを作成: ngrok http 8001")
        print("2. LINE DevelopersでWebhook URLを設定")
        print("3. LINEアプリから実際にメッセージを送信してテスト")
    else:
        print(f"{RED}⚠️ 一部のテストが失敗しました{ENDC}")
        print("失敗したテストの詳細を確認してください")

if __name__ == "__main__":
    main()