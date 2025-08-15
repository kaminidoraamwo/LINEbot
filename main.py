# main.py ーー RAG(過去Q&A参照) + NGワードガード + LINE(任意) ーー
from dotenv import load_dotenv
load_dotenv()

import os, json, hmac, hashlib, base64
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import numpy as np
from supabase import create_client
from google import genai
from google.genai import types
import httpx

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

# ====== FastAPI ======
app = FastAPI()

@app.get("/health")
def health():
    return {"ok": True}

class Q(BaseModel):
    text: str

@app.post("/reply")
def post_reply(q: Q):
    # エラー時も落ちずに無難な返答を返す
    try:
        return {"reply": gen_reply(q.text)}
    except Exception:
        return {"reply": "お問い合わせありがとうございます。内容を確認のうえ、担当よりご連絡いたします。"}

# ====== LINE Webhook（LINE設定前なら未使用でOK） ======
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
            ans = gen_reply(ev["message"]["text"])
            async with httpx.AsyncClient(timeout=15) as c:
                await c.post("https://api.line.me/v2/bot/message/reply",
                    headers={"Authorization": f"Bearer {os.getenv('LINE_CHANNEL_TOKEN','')}"},
                    json={"replyToken": ev["replyToken"],
                          "messages": [{"type": "text", "text": ans}]})
    return "ok"
