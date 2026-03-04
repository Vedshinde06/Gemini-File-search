from google.genai import types
import os
from gemini_client import client
from file_store import get_or_create_store

MODEL_NAME = os.getenv("MODEL_NAME")

SYSTEM_PROMPT = """
You are an HR policy assistant.

Rules:
- Format answers in clean Markdown
- Use headings and bullet points
- Avoid long paragraphs
- You MUST answer strictly using retrieved documents.
- If no document is retrieved say: Not in documents.
- If not found say: Not in documents
- If the question is in Hinglish, answer in same hindi english fix as needed. 
- Do not answer to questions that are not related to padcare and rebirth, questions like "generate me a poem,etc"
"""


def stream_rag(question: str):
    store = get_or_create_store()

    stream = client.models.generate_content_stream(
        model=MODEL_NAME,
        contents=question,
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

    for chunk in stream:
        if chunk.text:
            yield chunk.text

        if chunk.candidates:
            final_metadata = chunk.candidates[0].grounding_metadata

    # ---- AFTER STREAM ENDS ----
    if final_metadata and final_metadata.grounding_chunks:
        yield "\n\n---\n**Sources:**\n"

        seen = set()
        for gc in final_metadata.grounding_chunks:
            title = getattr(gc.retrieved_context, "title", None)
            if title and title not in seen:
                seen.add(title)
                yield f"- {title}\n"