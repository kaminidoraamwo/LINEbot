# main_with_relation.py ーー RAG(過去Q&A参照) + NGワードガード + LINE + Re:lation統合 ーー
from dotenv import load_dotenv
load_dotenv()

import os, json, hmac, hashlib, base64, logging
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import numpy as np
from supabase import create_client
from google import genai
from google.genai import types
import httpx
from typing import Optional, Dict, Any

# Re:lation統合のインポート
from relation_integration_fixed import create_relation_service_from_env, RelationAPIError

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ====== 外部サービスのクライアント ======
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY が未設定です。.env を確認してください。")
gclient = genai.Client(api_key=API_KEY)

SB_URL = os.getenv("SUPABASE_URL")
SB_KEY = os.getenv("SUPABASE_KEY")
if not SB_URL or not SB_KEY:
    raise RuntimeError("SUPABASE_URL / SUPABASE_KEY が未設定です。.env を確認してください。")
sb = create_client(SB_URL, SB_KEY)

# Re:lation サービス初期化（オプション）
relation_service = None
try:
    relation_service = create_relation_service_from_env()
    logger.info("✅ Re:lation API統合が有効になりました")
except Exception as e:
    logger.warning(f"⚠️ Re:lation API統合を無効にしました: {e}")

# ====== 返答スタイル（必要に応じて編集OK） ======
STYLE = os.getenv("REPLY_STYLE", """
- あなたは丁寧で親切なカスタマーサポート担当。
- 事実を優先し、断定しすぎない。3〜5文で簡潔に。
- 不明点は「確認のうえご連絡します」と案内。
- 過度な確約や誤解を招く表現は避ける。
""").strip()

# ====== NGワードガード（任意） ======
RAW_NG = os.getenv("NG_WORDS", "返金,100%,永久無料,必ず,保証").strip()
NG_WORDS = [w.strip() for w in RAW_NG.split(",") if w.strip()]
FLAG_PREFIX = os.getenv("FLAG_PREFIX", "【確認が必要です】")

def guard(user_text: str, reply_text: str) -> str:
    combined = f"{user_text}\n{reply_text}"
    if any(ng in combined for ng in NG_WORDS):
        return f"{FLAG_PREFIX}\n{reply_text}"
    return reply_text

# ====== Embedding（1536次元でDBに合わせる） ======
def embed(text: str) -> list[float]:
    res = gclient.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=types.EmbedContentConfig(
            task_type="SEMANTIC_SIMILARITY",
            output_dimensionality=1536
        )
    )
    return res.embeddings[0].values

# ====== 類似検索（Supabaseからの戻りが list でも str でもOKにする） ======
def search_similar(vec: list[float], k: int = 5) -> list[str]:
    """
    rag_data の content/embedding からコサイン類似度で上位k件を返す。
    embedding が list でも "[...]" の文字列でも正しく処理する。
    """
    rows = sb.table("rag_data").select("content, embedding").limit(2000).execute().data
    if not rows:
        return []

    q = np.array(vec, dtype=np.float32)

    def to_vec(x):
        # そのまま配列で来るケース
        if isinstance(x, list):
            try:
                return np.array(x, dtype=np.float32)
            except Exception:
                return None
        # 文字列 "[0.12, -0.34, ...]" で来るケース
        if isinstance(x, str):
            s = x.strip()
            if s.startswith('[') and s.endswith(']'):
                try:
                    return np.fromstring(s[1:-1], sep=',', dtype=np.float32)
                except Exception:
                    return None
        return None

    scored = []
    for r in rows:
        v = to_vec(r.get("embedding"))
        if v is None or v.size == 0:
            continue
        denom = (np.linalg.norm(q) + 1e-9) * (np.linalg.norm(v) + 1e-9)
        score = float(np.dot(q, v) / denom)
        scored.append((score, r["content"]))

    if not scored:
        return []
    scored.sort(reverse=True, key=lambda t: t[0])
    return [content for _, content in scored[:k]]

# ====== 回答生成（RAG + スタイル + ガード） ======
def gen_reply(user_text: str) -> str:
    try:
        qvec = embed(user_text)
        examples = search_similar(qvec)
    except Exception:
        # 何かあっても落ちないように
        examples = []

    context = "\n\n".join(examples) if examples else "(参考データなし)"
    prompt = [
        {"role": "user", "parts": [
            {"text": STYLE},
            {"text": f"【参考Q&A】\n{context}"},
            {"text": f"【質問】\n{user_text}\n\n【お願い】上記のルールに従って、丁寧で簡潔に回答してください。"}
        ]}
    ]
    try:
        res = gclient.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.6)
        )
        reply = (res.text or "").strip()
    except Exception:
        reply = ""

    if not reply:
        reply = "お問い合わせありがとうございます。内容を確認のうえ、担当よりご連絡いたします。"
    return guard(user_text, reply)

# ====== Re:lation統合処理 ======
def process_with_relation(user_id: str, message: str, display_name: Optional[str] = None) -> Dict[str, Any]:
    """Re:lation APIとの統合処理"""
    if not relation_service:
        return {"relation_enabled": False, "message": "Re:lation統合が無効です"}
    
    try:
        # 特定のキーワードでRe:lationチケット作成を判定
        create_ticket_keywords = ["問い合わせ", "質問", "要望", "不具合", "エラー", "困って", "助けて"]
        should_create_ticket = any(keyword in message for keyword in create_ticket_keywords)
        
        if should_create_ticket:
            # Re:lationにチケット作成
            result = relation_service.process_line_message(
                user_id=user_id,
                message=message,
                display_name=display_name
            )
            
            if result["success"]:
                logger.info(f"Re:lationチケット作成成功: {result.get('ticket_id')}")
                return {
                    "relation_enabled": True,
                    "ticket_created": True,
                    "ticket_id": result.get("ticket_id"),
                    "message": result["message"]
                }
            else:
                logger.error(f"Re:lationチケット作成失敗: {result.get('error')}")
                return {
                    "relation_enabled": True,
                    "ticket_created": False,
                    "error": result.get("error"),
                    "message": "システムエラーが発生しました。後ほど再度お試しください。"
                }
        else:
            return {"relation_enabled": True, "ticket_created": False, "message": "通常の回答を返します"}
            
    except RelationAPIError as e:
        logger.error(f"Re:lation API エラー: {e}")
        return {
            "relation_enabled": True, 
            "ticket_created": False, 
            "error": str(e),
            "message": "申し訳ございません。サポートシステムで一時的な問題が発生しています。"
        }

# ====== FastAPI ======
app = FastAPI(title="LINE Bot with Re:lation Integration")

@app.get("/health")
def health():
    health_status = {"ok": True, "services": {}}
    
    # Supabase接続確認
    try:
        sb.table("rag_data").select("id").limit(1).execute()
        health_status["services"]["supabase"] = "ok"
    except Exception as e:
        health_status["services"]["supabase"] = f"error: {str(e)}"
    
    # Re:lation接続確認
    if relation_service:
        try:
            if relation_service.client.health_check():
                health_status["services"]["relation"] = "ok"
            else:
                health_status["services"]["relation"] = "connection_failed"
        except Exception as e:
            health_status["services"]["relation"] = f"error: {str(e)}"
    else:
        health_status["services"]["relation"] = "disabled"
    
    return health_status

@app.get("/relation/status")
def relation_status():
    """Re:lation API ステータス確認"""
    if not relation_service:
        return {"enabled": False, "message": "Re:lation統合が無効です"}
    
    try:
        # 基本情報取得テスト
        message_boxes = relation_service.client.get_message_boxes()
        users = relation_service.client.get_users()
        categories = relation_service.client.get_case_categories()
        
        return {
            "enabled": True,
            "connection": "ok",
            "message_boxes": len(message_boxes),
            "users": len(users),
            "categories": len(categories),
            "subdomain": relation_service.client.config.subdomain,
            "message_box_id": relation_service.client.config.message_box_id
        }
    except Exception as e:
        return {
            "enabled": True,
            "connection": "error",
            "error": str(e)
        }

class Q(BaseModel):
    text: str
    user_id: Optional[str] = None
    display_name: Optional[str] = None

@app.post("/reply")
def post_reply(q: Q):
    """通常の回答API（Re:lation統合対応）"""
    try:
        # Re:lation統合処理
        relation_result = process_with_relation(
            user_id=q.user_id or "anonymous",
            message=q.text,
            display_name=q.display_name
        )
        
        # 基本的な回答生成
        basic_reply = gen_reply(q.text)
        
        # Re:lationでチケットが作成された場合は、その旨を回答に含める
        if relation_result.get("ticket_created"):
            reply = f"{basic_reply}\n\n{relation_result['message']}"
            return {
                "reply": reply,
                "relation": relation_result
            }
        else:
            return {
                "reply": basic_reply,
                "relation": relation_result
            }
            
    except Exception as e:
        logger.error(f"回答生成エラー: {e}")
        return {
            "reply": "お問い合わせありがとうございます。内容を確認のうえ、担当よりご連絡いたします。",
            "relation": {"enabled": False, "error": "システムエラー"}
        }

# ====== LINE Webhook（Re:lation統合対応） ======
def verify_line(body: bytes, sig: str) -> bool:
    secret = os.getenv("LINE_CHANNEL_SECRET", "").encode()
    if not secret or not sig:
        return False
    mac = hmac.new(secret, body, hashlib.sha256).digest()
    return base64.b64encode(mac).decode() == sig

@app.post("/line")
async def line_webhook(req: Request):
    body = await req.body()
    if not verify_line(body, req.headers.get("X-Line-Signature", "")):
        raise HTTPException(403, "bad signature")

    data = json.loads(body.decode())
    for ev in data.get("events", []):
        if ev.get("type") == "message" and ev["message"]["type"] == "text":
            user_id = ev["source"]["userId"]
            message_text = ev["message"]["text"]
            
            # ユーザー情報取得（可能であれば）
            display_name = None
            try:
                async with httpx.AsyncClient(timeout=15) as c:
                    profile_response = await c.get(
                        f"https://api.line.me/v2/bot/profile/{user_id}",
                        headers={"Authorization": f"Bearer {os.getenv('LINE_CHANNEL_TOKEN','')}"}
                    )
                    if profile_response.status_code == 200:
                        profile_data = profile_response.json()
                        display_name = profile_data.get("displayName")
            except Exception:
                logger.warning("LINEユーザープロファイル取得に失敗")
            
            # Re:lation統合処理
            relation_result = process_with_relation(
                user_id=user_id,
                message=message_text,
                display_name=display_name
            )
            
            # 基本回答生成
            basic_answer = gen_reply(message_text)
            
            # 最終回答の決定
            if relation_result.get("ticket_created"):
                # チケットが作成された場合
                final_answer = f"{basic_answer}\n\n{relation_result['message']}"
                logger.info(f"LINEユーザー {user_id} のチケットを作成: {relation_result.get('ticket_id')}")
            elif relation_result.get("error"):
                # Re:lationでエラーが発生した場合
                final_answer = f"{basic_answer}\n\n※サポートシステムで一時的な問題が発生していますが、お問い合わせは確認させていただきます。"
                logger.warning(f"Re:lationエラーが発生: {relation_result['error']}")
            else:
                # 通常回答
                final_answer = basic_answer
            
            # LINE返信
            async with httpx.AsyncClient(timeout=15) as c:
                await c.post("https://api.line.me/v2/bot/message/reply",
                    headers={"Authorization": f"Bearer {os.getenv('LINE_CHANNEL_TOKEN','')}"},
                    json={"replyToken": ev["replyToken"],
                          "messages": [{"type": "text", "text": final_answer}]})
    
    return "ok"

# ========== デバッグ用エンドポイント ==========

@app.post("/debug/relation")
async def debug_relation(q: Q):
    """Re:lation統合のデバッグ用エンドポイント"""
    if not relation_service:
        return {"error": "Re:lation統合が無効です"}
    
    try:
        result = relation_service.process_line_message(
            user_id=q.user_id or "debug_user",
            message=q.text,
            display_name=q.display_name or "Debug User"
        )
        return result
    except Exception as e:
        return {"error": str(e), "type": type(e).__name__}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)