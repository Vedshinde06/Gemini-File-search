from google.genai import types
from gemini_client import client
import os

MODEL_NAME = os.getenv("MODEL_NAME")

REWRITE_PROMPT = """
You are a query rewriting assistant for a Retrieval-Augmented Generation (RAG) system.

You will receive:
1. The user's current message
2. A short conversation history

Your job is to determine whether the message is a **real question that needs document retrieval**.

Step 1 — Detect message type

Classify the message as one of these:

1. QUESTION
   - The user is asking a new question
   - Example: "How many leaves do employees get?"

2. FOLLOWUP QUESTION
   - The user refers to earlier context
   - Example: "what about interns?"
   - Example: "can probation employees do that?"

3. ACKNOWLEDGEMENT / NON-QUESTION
   - Messages like:
     ok
     okay
     thanks
     got it
     cool
     yes
     no
     understood
     👍

Step 2 — Rewrite logic

If the message is:

QUESTION
→ Rewrite it slightly for clarity.

FOLLOWUP QUESTION
→ Use chat history to resolve references and rewrite it as a standalone question.

ACKNOWLEDGEMENT / NON-QUESTION
→ Return the message EXACTLY as it is.

Rules:
- Never invent policy information
- Never expand the question with assumptions
- Do not answer the question
- Return ONLY the rewritten text
"""

def rewrite_query(question: str, history: list):

    history_text = ""

    for msg in history[-6:]:
        role = msg["role"].capitalize()
        history_text += f"{role}: {msg['content']}\n"

    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=f"""
{REWRITE_PROMPT}

Conversation history:
{history_text}

User question:
{question}

Standalone question:
""",
        config=types.GenerateContentConfig(
            temperature=0.0
        )
    )

    return response.text.strip()