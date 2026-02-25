import os
from google import genai
from google.genai import types

# ---------- CONFIG ----------
API_KEY = os.getenv("GEMINI_API_KEY") or "AIzaSyA3qk6O6Q_dHlP7kPfGgUkCEPWthyXLtdw"
MODEL_NAME = os.getenv("MODEL_NAME", "gemini-3-flash-preview")
STORE_DISPLAY_NAME = os.getenv("FILE_SEARCH_STORE_NAME", "padcare-doc-store")


# ---------- INIT ----------
client = genai.Client(api_key=API_KEY)


def get_store():
    for store in client.file_search_stores.list():
        if STORE_DISPLAY_NAME in store.display_name:
            return store
    raise Exception("File Search store not found")


def debug_grounding(question: str):
    store = get_store()

    print("\n===== QUESTION =====\n")
    print(question)

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=question,
        config=types.GenerateContentConfig(
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store.name]
                    )
                )
            ]
        )
    )

    print("\n===== ANSWER =====\n")
    print(response.text)

    print("\n===== RAW GROUNDING METADATA =====\n")
    meta = response.candidates[0].grounding_metadata
    print(meta)

    print("\n===== GROUNDING STATUS =====\n")

    if meta is None:
        print("❌ Grounding NOT happening (model answered from its own knowledge)")
    else:
        try:
            chunks = getattr(meta, "grounding_chunks", None)
            if chunks:
                print("✅ Grounding WORKING (documents retrieved)")
                print(f"Chunks retrieved: {len(chunks)}")

                print("\nPossible citation sources:")
                for gc in chunks:
                    try:
                        src = getattr(gc, "source", None)
                        if src and hasattr(src, "file") and src.file:
                            print("-", src.file.display_name)
                    except:
                        pass
            else:
                print("⚠️ Metadata present but no chunks found")
        except Exception as e:
            print("⚠️ Could not parse metadata:", str(e))


if __name__ == "__main__":
    print("\n=== Gemini File Search Grounding Debugger ===\n")

    q = input("Enter a question from your document:\n> ").strip()

    if not q:
        q = "How many earned leaves are allowed?"

    debug_grounding(q)