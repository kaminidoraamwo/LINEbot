#!/usr/bin/env python3
"""Supabaseなしでボットの基本機能をテスト"""

from dotenv import load_dotenv
load_dotenv()

import os
from google import genai
from google.genai import types

# Gemini APIのみ使用
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    print("GOOGLE_API_KEY を .env に設定してください")
    exit(1)

gclient = genai.Client(api_key=API_KEY)

def test_reply(user_text: str) -> str:
    """Gemini APIで返答生成（RAGなし）"""
    prompt = [{
        "role": "user",
        "parts": [{"text": f"カスタマーサポートとして、以下の質問に丁寧に答えてください：\n\n{user_text}"}]
    }]
    
    try:
        res = gclient.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.6)
        )
        return res.text.strip()
    except Exception as e:
        return f"エラー: {e}"

if __name__ == "__main__":
    print("テストモード（Ctrl+Cで終了）")
    while True:
        try:
            q = input("\n質問: ")
            if q.lower() in ('exit', 'quit', 'q'):
                break
            answer = test_reply(q)
            print(f"回答: {answer}")
        except KeyboardInterrupt:
            break
    print("\n終了しました")