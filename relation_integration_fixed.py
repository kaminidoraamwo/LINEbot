"""
Re:lation API 正しい統合実装

404エラーを解消し、適切なRe:lation API統合を実現するためのクラス
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from dataclasses import dataclass
from enum import Enum


# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RelationAPIError(Exception):
    """Re:lation API エラー"""
    pass


class TicketStatus(Enum):
    """チケット状態"""
    OPEN = "open"
    CLOSED = "closed"
    PENDING = "pending"


@dataclass
class RelationConfig:
    """Re:lation API 設定"""
    access_token: str
    subdomain: str
    message_box_id: str
    timeout: int = 30
    max_retries: int = 3


@dataclass
class TicketInfo:
    """チケット情報"""
    id: str
    subject: str
    status: str
    assignee_id: Optional[str] = None
    case_category_id: Optional[str] = None
    labels: Optional[List[str]] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class RelationAPIClient:
    """Re:lation API クライアント（修正版）"""
    
    def __init__(self, config: RelationConfig):
        self.config = config
        self.base_url = f"https://{config.subdomain}.relationapp.jp/api/v2"
        self.session = self._create_session()
        
        # 設定検証
        self._validate_config()
    
    def _create_session(self) -> requests.Session:
        """HTTPセッションの作成"""
        session = requests.Session()
        session.headers.update({
            "Authorization": f"Bearer {self.config.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Re:lation-LINE-Bot-Integration/1.0"
        })
        return session
    
    def _validate_config(self):
        """設定値の検証"""
        if not self.config.access_token:
            raise RelationAPIError("アクセストークンが設定されていません")
        
        if not self.config.subdomain:
            raise RelationAPIError("サブドメインが設定されていません")
        
        if not self.config.message_box_id:
            raise RelationAPIError("メッセージボックスIDが設定されていません")
        
        # メッセージボックスIDが数値であることを確認
        try:
            int(self.config.message_box_id)
        except ValueError:
            raise RelationAPIError("メッセージボックスIDは数値である必要があります")
    
    def _make_request(
        self, 
        method: str, 
        endpoint: str, 
        data: Optional[Dict] = None,
        require_message_box: bool = True
    ) -> requests.Response:
        """API リクエストの実行"""
        
        # エンドポイントURL構築
        if require_message_box:
            url = f"{self.base_url}/{self.config.message_box_id}{endpoint}"
        else:
            url = f"{self.base_url}{endpoint}"
        
        logger.info(f"API Request: {method} {url}")
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=self.config.timeout)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=self.config.timeout)
            elif method.upper() == "PUT":
                response = self.session.put(url, json=data, timeout=self.config.timeout)
            elif method.upper() == "DELETE":
                response = self.session.delete(url, timeout=self.config.timeout)
            else:
                raise RelationAPIError(f"未対応のHTTPメソッド: {method}")
            
            # レート制限チェック
            self._check_rate_limit(response)
            
            # エラーレスポンスの処理
            if not response.ok:
                self._handle_error_response(response)
            
            logger.info(f"API Response: {response.status_code}")
            return response
            
        except requests.exceptions.Timeout:
            raise RelationAPIError("APIリクエストがタイムアウトしました")
        except requests.exceptions.ConnectionError:
            raise RelationAPIError("API サーバーに接続できません")
        except requests.exceptions.RequestException as e:
            raise RelationAPIError(f"API リクエストエラー: {str(e)}")
    
    def _check_rate_limit(self, response: requests.Response):
        """レート制限チェック"""
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) < 5:
            logger.warning(f"レート制限に近づいています。残り: {remaining}")
        
        if response.status_code == 403:
            reset_time = response.headers.get("X-RateLimit-Reset", "不明")
            raise RelationAPIError(f"レート制限を超過しました。リセット時刻: {reset_time}")
    
    def _handle_error_response(self, response: requests.Response):
        """エラーレスポンスの処理"""
        try:
            error_data = response.json()
            error_message = error_data.get("message", "不明なエラー")
        except json.JSONDecodeError:
            error_message = response.text or "エラー詳細なし"
        
        status_messages = {
            400: "リクエストパラメータが無効です",
            401: "認証に失敗しました。アクセストークンを確認してください",
            403: "アクセス権限がありません。またはレート制限を超過しました",
            404: "指定されたリソースが見つかりません",
            415: "サポートされていない形式です",
            500: "サーバー内部エラーが発生しました",
            503: "サービスがメンテナンス中です"
        }
        
        base_message = status_messages.get(response.status_code, "API エラーが発生しました")
        raise RelationAPIError(f"{base_message} (HTTP {response.status_code}): {error_message}")
    
    # ========== 基本的なAPI メソッド ==========
    
    def get_message_boxes(self) -> List[Dict[str, Any]]:
        """受信箱一覧の取得"""
        response = self._make_request("GET", "/message_boxes", require_message_box=False)
        return response.json()
    
    def get_users(self) -> List[Dict[str, Any]]:
        """ユーザー一覧の取得"""
        response = self._make_request("GET", "/users")
        return response.json()
    
    def get_case_categories(self) -> List[Dict[str, Any]]:
        """チケット分類一覧の取得"""
        response = self._make_request("GET", "/case_categories")
        return response.json()
    
    def get_labels(self) -> List[Dict[str, Any]]:
        """ラベル一覧の取得"""
        response = self._make_request("GET", "/labels")
        return response.json()
    
    def search_tickets(
        self, 
        query: Optional[str] = None,
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """チケット検索"""
        params = {"limit": limit}
        if query:
            params["query"] = query
        if status:
            params["status"] = status
        if assignee_id:
            params["assignee_id"] = assignee_id
        
        # パラメータをクエリ文字列に変換
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        endpoint = f"/tickets/search?{query_string}"
        
        response = self._make_request("GET", endpoint)
        return response.json()
    
    def get_ticket(self, ticket_id: str) -> Dict[str, Any]:
        """特定チケットの詳細取得"""
        response = self._make_request("GET", f"/tickets/{ticket_id}")
        return response.json()
    
    def update_ticket(
        self, 
        ticket_id: str, 
        status: Optional[str] = None,
        assignee_id: Optional[str] = None,
        case_category_id: Optional[str] = None,
        label_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """チケット更新"""
        data = {}
        if status:
            data["status"] = status
        if assignee_id:
            data["assignee_id"] = assignee_id
        if case_category_id:
            data["case_category_id"] = case_category_id
        if label_ids:
            data["label_ids"] = label_ids
        
        response = self._make_request("PUT", f"/tickets/{ticket_id}", data)
        return response.json()
    
    def create_comment(
        self, 
        ticket_id: str, 
        comment: str,
        is_private: bool = False
    ) -> Dict[str, Any]:
        """コメント作成（2024年4月追加）"""
        data = {
            "ticket_id": ticket_id,
            "comment": comment,
            "is_private": is_private
        }
        response = self._make_request("POST", "/comments", data)
        return response.json()
    
    def search_templates(self, query: str) -> List[Dict[str, Any]]:
        """テンプレート検索（2024年4月追加）"""
        data = {"query": query}
        response = self._make_request("POST", "/templates/search", data)
        return response.json()
    
    # ========== 高レベルな統合メソッド ==========
    
    def create_ticket_from_line_message(
        self, 
        user_id: str, 
        message: str, 
        line_display_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """LINE メッセージからチケット作成"""
        
        # 件名を生成（メッセージの最初の30文字 + LINEユーザー情報）
        subject_base = message[:30] + ("..." if len(message) > 30 else "")
        subject = f"[LINE] {subject_base}"
        if line_display_name:
            subject += f" - {line_display_name}"
        
        # チケット作成用データ
        ticket_data = {
            "subject": subject,
            "message": f"LINE User ID: {user_id}\n"
                      f"Display Name: {line_display_name or '不明'}\n"
                      f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                      f"Message:\n{message}",
            "source": "line_bot"
        }
        
        # チケット作成（実際のエンドポイントは仕様書で確認必要）
        try:
            response = self._make_request("POST", "/tickets", ticket_data)
            return response.json()
        except RelationAPIError as e:
            logger.error(f"チケット作成に失敗: {e}")
            raise
    
    def get_ticket_summary(self, ticket_id: str) -> TicketInfo:
        """チケットサマリー取得"""
        ticket_data = self.get_ticket(ticket_id)
        
        return TicketInfo(
            id=ticket_data.get("id"),
            subject=ticket_data.get("subject"),
            status=ticket_data.get("status"),
            assignee_id=ticket_data.get("assignee_id"),
            case_category_id=ticket_data.get("case_category_id"),
            labels=ticket_data.get("labels", []),
            created_at=ticket_data.get("created_at"),
            updated_at=ticket_data.get("updated_at")
        )
    
    def health_check(self) -> bool:
        """API 接続確認"""
        try:
            # 最もシンプルなエンドポイントで接続確認
            self.get_message_boxes()
            return True
        except RelationAPIError:
            return False


class RelationService:
    """Re:lation サービス統合クラス"""
    
    def __init__(self, config: RelationConfig):
        self.client = RelationAPIClient(config)
        self._cache = {}  # 簡易キャッシュ
    
    def process_line_message(
        self, 
        user_id: str, 
        message: str,
        display_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """LINE メッセージの処理"""
        try:
            # チケット作成
            ticket = self.client.create_ticket_from_line_message(
                user_id=user_id,
                message=message,
                line_display_name=display_name
            )
            
            logger.info(f"チケット作成成功: {ticket.get('id')}")
            
            return {
                "success": True,
                "ticket_id": ticket.get("id"),
                "message": "お問い合わせを受け付けました。担当者が確認後、ご連絡いたします。"
            }
            
        except RelationAPIError as e:
            logger.error(f"チケット作成失敗: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": "申し訳ございません。システムエラーが発生しました。後ほど再度お試しください。"
            }
    
    def get_user_tickets(
        self, 
        user_id: str, 
        limit: int = 5
    ) -> List[TicketInfo]:
        """ユーザーのチケット一覧取得"""
        try:
            # LINE User IDでチケット検索
            tickets = self.client.search_tickets(
                query=user_id,
                limit=limit
            )
            
            return [
                self.client.get_ticket_summary(ticket["id"]) 
                for ticket in tickets
            ]
        except RelationAPIError as e:
            logger.error(f"チケット取得失敗: {e}")
            return []


def create_relation_service_from_env() -> RelationService:
    """環境変数からRe:lationサービスを作成"""
    config = RelationConfig(
        access_token=os.getenv("RELATION_ACCESS_TOKEN", ""),
        subdomain=os.getenv("RELATION_SUBDOMAIN", ""),
        message_box_id=os.getenv("RELATION_MESSAGE_BOX_ID", ""),
        timeout=int(os.getenv("RELATION_TIMEOUT", "30"))
    )
    
    return RelationService(config)


# ========== テスト実行例 ==========

def test_relation_integration():
    """統合テスト"""
    try:
        service = create_relation_service_from_env()
        
        # 接続確認
        if service.client.health_check():
            print("✅ Re:lation API 接続成功")
            
            # 基本情報取得テスト
            message_boxes = service.client.get_message_boxes()
            print(f"📨 メッセージボックス数: {len(message_boxes)}")
            
            users = service.client.get_users()
            print(f"👥 ユーザー数: {len(users)}")
            
            categories = service.client.get_case_categories()
            print(f"📂 チケット分類数: {len(categories)}")
            
        else:
            print("❌ Re:lation API 接続失敗")
            
    except Exception as e:
        print(f"❌ テストエラー: {e}")


if __name__ == "__main__":
    test_relation_integration()