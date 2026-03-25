from google.genai import types
import os
from gemini_client import client
from file_store import get_or_create_store
from db import get_all_links

MODEL_NAME = os.getenv("MODEL_NAME")
MAX_CONTEXT_MESSAGES = 6

SYSTEM_PROMPT = """
You are Ved, an intelligent HR assistant that helps employees understand company policies clearly and accurately. 
You provide concise, professional, and friendly responses based strictly on company policy documents.

Rules:
- Format answers in clean Markdown
- Use headings and bullet points
- Avoid long paragraphs
- You MUST answer strictly using retrieved documents.
- If no document is retrieved say: Not in documents.
- If not found say: Not in documents
- If the question is in Hinglish, then only answer in same Hinglish language. Else answer in English. 
- Do not answer to questions that are not related to padcare and rebirth, questions like "generate me a poem,etc"
- Do not include a Source, Sources, References, or Documents section in the answer. The application adds sources separately.
"""


def stream_rag(question: str, history: list):
    store = get_or_create_store()

    print(f"[RAG] user_question: {question}")

    contents = []
    recent_history = history[-MAX_CONTEXT_MESSAGES:] if history else []

    for msg in recent_history:
        role = msg.get("role", "user")
        text = (msg.get("content") or "").strip()

        if not text:
            continue

        gemini_role = "model" if role == "assistant" else "user"
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part(text=text)]
            )
        )

    if not contents:
        contents = question

    stream = client.models.generate_content_stream(
        model=MODEL_NAME,
        contents=contents,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            tools=[
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=[store.name]
                    )
                )
            ]
        )
    )

    final_metadata = None
    doc_links = None

    for chunk in stream:
        if chunk.text:
            yield chunk.text

        if chunk.candidates:
            final_metadata = chunk.candidates[0].grounding_metadata

    # ---- AFTER STREAM ENDS ----
    if final_metadata and final_metadata.grounding_chunks:
        yield "\n\n\nSources:\n"

        seen = set()
        for gc in final_metadata.grounding_chunks:
            title = getattr(gc.retrieved_context, "title", None)
            if title and title not in seen:
                seen.add(title)
                if doc_links is None:
                    doc_links = get_all_links()

                drive_url = doc_links.get(title)

                if drive_url:
                    yield f"- [{title}]({drive_url})\n"
                else:
                    yield f"- {title}\n"
