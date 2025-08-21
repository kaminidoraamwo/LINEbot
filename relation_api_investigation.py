"""
Re:lation API 調査・テスト用スクリプト

404エラーの原因を特定し、正しいAPI呼び出し方法を確立する
"""

import os
import json
import requests
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

class RelationAPIInvestigator:
    """Re:lation API の調査・テスト用クラス"""
    
    def __init__(self):
        self.access_token = os.getenv("RELATION_ACCESS_TOKEN")
        self.subdomain = os.getenv("RELATION_SUBDOMAIN") 
        self.message_box_id = os.getenv("RELATION_MESSAGE_BOX_ID")
        
        # 必要な設定値の確認
        self._validate_config()
        
        # 正しいベースURL
        self.base_url = f"https://{self.subdomain}.relationapp.jp/api/v2"
        
        # 共通ヘッダー
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "User-Agent": "Re:lation-API-Investigation/1.0"
        }
    
    def _validate_config(self):
        """必要な設定値の確認"""
        missing_vars = []
        
        if not self.access_token:
            missing_vars.append("RELATION_ACCESS_TOKEN")
        if not self.subdomain:
            missing_vars.append("RELATION_SUBDOMAIN")
        if not self.message_box_id:
            missing_vars.append("RELATION_MESSAGE_BOX_ID")
            
        if missing_vars:
            raise ValueError(f"以下の環境変数が未設定です: {', '.join(missing_vars)}")
    
    def test_api_connectivity(self) -> Dict[str, Any]:
        """API接続テスト - 最も基本的なエンドポイントをテスト"""
        results = {}
        
        # 1. 受信箱一覧取得 (message_box_id不要)
        results['inbox_list'] = self._test_endpoint(
            "GET", 
            f"{self.base_url}/message_boxes",
            description="受信箱一覧取得"
        )
        
        # 2. ユーザー一覧取得 (message_box_id必要)
        results['user_list'] = self._test_endpoint(
            "GET",
            f"{self.base_url}/{self.message_box_id}/users", 
            description="ユーザー一覧取得"
        )
        
        # 3. チケット分類一覧取得
        results['case_categories'] = self._test_endpoint(
            "GET",
            f"{self.base_url}/{self.message_box_id}/case_categories",
            description="チケット分類一覧取得"
        )
        
        # 4. ラベル一覧取得
        results['labels'] = self._test_endpoint(
            "GET", 
            f"{self.base_url}/{self.message_box_id}/labels",
            description="ラベル一覧取得"
        )
        
        return results
    
    def _test_endpoint(self, method: str, url: str, description: str, data: Optional[Dict] = None) -> Dict[str, Any]:
        """個別エンドポイントのテスト"""
        try:
            print(f"\n🔍 テスト中: {description}")
            print(f"   Method: {method}")
            print(f"   URL: {url}")
            print(f"   Headers: {json.dumps(self.headers, indent=2, ensure_ascii=False)}")
            
            if method.upper() == "GET":
                response = requests.get(url, headers=self.headers, timeout=30)
            elif method.upper() == "POST":
                response = requests.post(url, headers=self.headers, json=data, timeout=30)
            elif method.upper() == "PUT":
                response = requests.put(url, headers=self.headers, json=data, timeout=30)
            else:
                return {"error": f"未対応のHTTPメソッド: {method}"}
            
            result = {
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "headers": dict(response.headers),
                "url": response.url,
                "description": description
            }
            
            # レスポンス本文の処理
            try:
                result["response"] = response.json()
            except json.JSONDecodeError:
                result["response_text"] = response.text
            
            # レート制限情報
            rate_limit_info = {}
            for header in ['X-RateLimit-Limit', 'X-RateLimit-Remaining', 'X-RateLimit-Reset']:
                if header in response.headers:
                    rate_limit_info[header] = response.headers[header]
            
            if rate_limit_info:
                result["rate_limit"] = rate_limit_info
            
            # 結果の表示
            if result["success"]:
                print(f"   ✅ 成功: HTTP {response.status_code}")
                if "response" in result:
                    print(f"   データ件数: {len(result['response']) if isinstance(result['response'], list) else '1件'}")
            else:
                print(f"   ❌ 失敗: HTTP {response.status_code}")
                print(f"   エラー内容: {result.get('response', result.get('response_text', 'No response'))}")
            
            return result
            
        except requests.exceptions.RequestException as e:
            error_result = {
                "error": str(e),
                "success": False,
                "description": description,
                "url": url
            }
            print(f"   ❌ 接続エラー: {e}")
            return error_result
    
    def diagnose_404_causes(self) -> Dict[str, Any]:
        """404エラーの原因診断"""
        print("\n" + "="*60)
        print("🔍 Re:lation API 404エラー原因診断")
        print("="*60)
        
        diagnoses = {}
        
        # 1. 基本的な設定値確認
        print("\n📋 設定値確認:")
        print(f"   Subdomain: {self.subdomain}")
        print(f"   Message Box ID: {self.message_box_id}")
        print(f"   Access Token: {'設定済み' if self.access_token else '未設定'}")
        print(f"   Base URL: {self.base_url}")
        
        # 2. 様々なURLパターンでのテスト
        url_patterns = {
            "v1_api": f"https://{self.subdomain}.relationapp.jp/api/v1/message_boxes",
            "v2_api": f"https://{self.subdomain}.relationapp.jp/api/v2/message_boxes", 
            "with_message_box": f"https://{self.subdomain}.relationapp.jp/api/v2/{self.message_box_id}/users",
            "root_check": f"https://{self.subdomain}.relationapp.jp/",
        }
        
        print("\n🌐 URLパターン検証:")
        for pattern_name, url in url_patterns.items():
            diagnoses[pattern_name] = self._test_endpoint("GET", url, f"URLパターン: {pattern_name}")
        
        # 3. 認証ヘッダーのバリエーションテスト
        print("\n🔐 認証ヘッダー検証:")
        auth_variations = [
            {"Authorization": f"Bearer {self.access_token}"},
            {"Authorization": f"Token {self.access_token}"},
            {"X-API-Token": self.access_token},
            {"Authorization": self.access_token},
        ]
        
        test_url = f"{self.base_url}/message_boxes"
        for i, headers_variant in enumerate(auth_variations):
            test_headers = {**self.headers, **headers_variant}
            try:
                response = requests.get(test_url, headers=test_headers, timeout=30)
                diagnoses[f"auth_variant_{i}"] = {
                    "status_code": response.status_code,
                    "success": response.status_code < 400,
                    "headers_used": headers_variant,
                    "description": f"認証ヘッダー変更パターン {i+1}"
                }
                print(f"   パターン {i+1}: HTTP {response.status_code} - {headers_variant}")
            except Exception as e:
                diagnoses[f"auth_variant_{i}"] = {
                    "error": str(e),
                    "headers_used": headers_variant,
                    "description": f"認証ヘッダー変更パターン {i+1}"
                }
        
        return diagnoses
    
    def generate_debug_report(self) -> str:
        """デバッグレポートの生成"""
        print("\n" + "="*60)
        print("📊 Re:lation API 詳細調査開始")
        print("="*60)
        
        # 基本接続テスト
        connectivity_results = self.test_api_connectivity()
        
        # 404エラー原因診断
        diagnostic_results = self.diagnose_404_causes()
        
        # レポート生成
        report_lines = []
        report_lines.append("# Re:lation API 調査レポート")
        report_lines.append(f"調査日時: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # 設定確認
        report_lines.append("## 設定確認")
        report_lines.append(f"- Subdomain: {self.subdomain}")
        report_lines.append(f"- Message Box ID: {self.message_box_id}")  
        report_lines.append(f"- Access Token: {'✅ 設定済み' if self.access_token else '❌ 未設定'}")
        report_lines.append(f"- Base URL: {self.base_url}")
        report_lines.append("")
        
        # 接続テスト結果
        report_lines.append("## API接続テスト結果")
        for endpoint_name, result in connectivity_results.items():
            status = "✅ 成功" if result.get("success") else "❌ 失敗"
            status_code = result.get("status_code", "N/A")
            report_lines.append(f"- {result.get('description', endpoint_name)}: {status} (HTTP {status_code})")
            
            if not result.get("success") and "response" in result:
                error_msg = result["response"]
                if isinstance(error_msg, dict):
                    error_msg = json.dumps(error_msg, ensure_ascii=False)
                report_lines.append(f"  エラー詳細: {error_msg}")
        
        report_lines.append("")
        
        # 診断結果
        report_lines.append("## 404エラー原因診断")
        successful_patterns = []
        failed_patterns = []
        
        for pattern_name, result in diagnostic_results.items():
            if result.get("success"):
                successful_patterns.append(f"- {result.get('description', pattern_name)}: ✅ HTTP {result['status_code']}")
            else:
                status_code = result.get("status_code", "接続エラー")
                failed_patterns.append(f"- {result.get('description', pattern_name)}: ❌ {status_code}")
        
        if successful_patterns:
            report_lines.append("### 成功したパターン")
            report_lines.extend(successful_patterns)
            report_lines.append("")
        
        if failed_patterns:
            report_lines.append("### 失敗したパターン")
            report_lines.extend(failed_patterns)
            report_lines.append("")
        
        # 推奨解決策
        report_lines.append("## 推奨解決策")
        
        # 成功パターンがある場合
        if any(r.get("success") for r in {**connectivity_results, **diagnostic_results}.values()):
            report_lines.append("### ✅ API接続が一部成功しています")
            report_lines.append("1. 成功したエンドポイントのパターンを参考に実装を修正")
            report_lines.append("2. message_box_idが必要なエンドポイントと不要なエンドポイントを確認")
            report_lines.append("3. 正しいベースURL形式を使用")
        else:
            report_lines.append("### ❌ 全てのAPIコールが失敗しています")
            report_lines.append("以下の点を確認してください:")
            report_lines.append("1. **アクセストークンの確認**")
            report_lines.append("   - Re:lation管理画面で「APIトークン」が正しく発行されているか")
            report_lines.append("   - トークンの有効期限が切れていないか")
            report_lines.append("   - トークンにメッセージボックスへのアクセス権限があるか")
            report_lines.append("")
            report_lines.append("2. **サブドメインの確認**")
            report_lines.append("   - Re:lationの実際のサブドメインと環境変数の値が一致しているか")
            report_lines.append("   - 例: https://your-company.relationapp.jp の場合、RELATION_SUBDOMAIN=your-company")
            report_lines.append("")
            report_lines.append("3. **メッセージボックスIDの確認**") 
            report_lines.append("   - Re:lation管理画面でメッセージボックスの数値IDを確認")
            report_lines.append("   - URLやAPI レスポンスから正しいIDを取得")
            report_lines.append("")
            report_lines.append("4. **ネットワーク設定の確認**")
            report_lines.append("   - ファイアウォールやプロキシの設定")
            report_lines.append("   - IP制限の設定（Re:lation側での制限）")
        
        report_lines.append("")
        report_lines.append("## 実装推奨事項")
        report_lines.append("1. **正しいベースURL**: `https://{subdomain}.relationapp.jp/api/v2`")
        report_lines.append("2. **認証ヘッダー**: `Authorization: Bearer {access_token}`")
        report_lines.append("3. **Content-Type**: `application/json` (POST/PUT時)")
        report_lines.append("4. **レート制限**: 60回/分を遵守")
        report_lines.append("5. **タイムアウト設定**: 30秒程度を推奨")
        report_lines.append("6. **エラーハンドリング**: HTTPステータスコードに応じた適切な処理")
        
        report = "\n".join(report_lines)
        print("\n" + "="*60)
        print("📋 調査完了 - 詳細レポート")
        print("="*60)
        print(report)
        
        return report


def main():
    """メイン実行関数"""
    try:
        investigator = RelationAPIInvestigator()
        report = investigator.generate_debug_report()
        
        # レポートをファイルに保存
        report_file = "/Users/okunoren/Downloads/LINE/line-bot/relation_api_debug_report.md"
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(report)
        
        print(f"\n📄 詳細レポートを保存しました: {report_file}")
        
    except ValueError as e:
        print(f"❌ 設定エラー: {e}")
        print("\n必要な環境変数を .env ファイルに設定してください:")
        print("RELATION_ACCESS_TOKEN=your_access_token_here")
        print("RELATION_SUBDOMAIN=your_subdomain_here") 
        print("RELATION_MESSAGE_BOX_ID=your_message_box_id_here")
    
    except Exception as e:
        print(f"❌ 予期しないエラーが発生しました: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()