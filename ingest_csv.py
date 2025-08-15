import os, csv, sys, time
from argparse import ArgumentParser
from dotenv import load_dotenv
load_dotenv()

from supabase import create_client
from google import genai
from google.genai import types

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

if not (SUPABASE_URL and SUPABASE_KEY and API_KEY):
    raise SystemExit("環境変数(SUPABASE_URL/SUPABASE_KEY/GEMINI_API_KEY)が未設定です。 .env を確認してください。")

sb = create_client(SUPABASE_URL, SUPABASE_KEY)
gclient = genai.Client(api_key=API_KEY)

Q_KEYS = ["question","Question","質問","問い合わせ","お問い合わせ","問合せ","件名","タイトル","subject","Subject"]
A_KEYS = ["answer","Answer","回答","返信","返答","response","reply","本文","メッセージ","ボディ"]

def pick(row, keys):
    for k in keys:
        if k in row and str(row[k]).strip():
            return str(row[k]).replace("\u3000"," ").strip()  # 全角スペース除去
    return ""

def embed(text: str, backoffs=(2,5,10,20,40)) -> list[float]:
    for i, wait_s in enumerate((0,)+backoffs):
        if wait_s: time.sleep(wait_s)
        try:
            res = gclient.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
                config=types.EmbedContentConfig(
                    task_type="SEMANTIC_SIMILARITY",
                    output_dimensionality=1536
                )
            )
            return res.embeddings[0].values
        except Exception as e:
            msg = str(e)
            if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "temporarily" in msg.lower():
                if i < len(backoffs):
                    print(f"[embed] 429等で待機 {wait_s}s → 再試行 ({i}/{len(backoffs)})")
                    continue
            raise
    raise RuntimeError("埋め込みに失敗（再試行上限）")

def load_existing_contents() -> set[str]:
    existing = set()
    # 必要ならページングする。まずは最大2万件分取得
    data = sb.table("rag_data").select("content").limit(20000).execute().data
    for r in data:
        c = r.get("content")
        if isinstance(c, str):
            existing.add(c)
    print(f"[dedup] 既存: {len(existing)} 件")
    return existing

def upsert_row(q: str, a: str):
    content = f"Q: {q}\nA: {a}"
    emb = embed(content)
    sb.table("rag_data").insert({
        "question": q, "answer": a, "content": content, "embedding": emb
    }).execute()
    return content

def main():
    ap = ArgumentParser()
    ap.add_argument("path", nargs="?", default="faq.csv")
    ap.add_argument("--limit", type=int, default=0, help="この件数まで取り込む（0=無制限）")
    ap.add_argument("--skip-valid", type=int, default=0, help="先頭からこの件数の“有効行”を読み飛ばす")
    ap.add_argument("--sleep-ms", type=int, default=300, help="行ごとの待機(ミリ秒)でレート制限回避")
    ap.add_argument("--dry-run", action="store_true", help="DBへ挿入せず検証のみ")
    args = ap.parse_args()

    existing = set()
    if not args.dry_run:
        existing = load_existing_contents()

    valid = skipped = inserted = dedup = 0
    skipped_examples = 0

    with open(args.path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise SystemExit("CSVのヘッダ行がありません。1行目を '質問,回答' または 'question,answer' にしてください。")
        print("columns:", reader.fieldnames)

        for i, row in enumerate(reader, start=1):
            q = pick(row, Q_KEYS)
            a = pick(row, A_KEYS)
            if not q or not a:
                if skipped_examples < 20:
                    print(f"skip: 行{i} 必須列不足（Q/A） q='{q[:20]}' a='{a[:20]}'")
                    skipped_examples += 1
                skipped += 1
                continue

            # 有効行カウントに基づく読み飛ばし
            if valid < args.skip_valid:
                valid += 1
                continue

            valid += 1

            content = f"Q: {q}\nA: {a}"
            if not args.dry_run and content in existing:
                dedup += 1
                continue

            if not args.dry_run:
                upsert_row(q, a)
                existing.add(content)
                inserted += 1
                if inserted % 5 == 0:
                    print(f"...{inserted} inserted")

                if args.sleep_ms > 0:
                    time.sleep(args.sleep_ms / 1000.0)

                if args.limit and inserted >= args.limit:
                    break

    print(f"result: valid(after-skip)={max(valid - args.skip_valid, 0)}, "
          f"skipped(blank)={skipped}, dedup={dedup}, inserted={inserted}")

if __name__ == "__main__":
    main()
