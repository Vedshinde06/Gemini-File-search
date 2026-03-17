import os
from fastapi import FastAPI, UploadFile, File, Form, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from gemini_client import client
from file_store import upload_file_to_store, get_or_create_store
from rag_chat import stream_rag
from typing import List
from starlette.middleware.sessions import SessionMiddleware
import uvicorn
from fastapi.responses import RedirectResponse
from auth import require_login, require_admin

from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    https_only=True,
    same_site="none",
    session_cookie="session",
    max_age=86400
)

from authlib.integrations.starlette_client import OAuth

oauth = OAuth()

oauth.register(
    name="google",
    client_id=os.getenv("GOOGLE_CLIENT_ID"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={
        "scope": "openid email profile",
        "hd": "padcarelabs.com"
    },
)

# ---------- Warmup ----------

@app.on_event("startup")
async def warmup():
    try:
        for _ in stream_rag("ping", []):
            break
    except:
        pass


# ---------- CHAT STREAM ----------
chat_sessions = {}

@app.post("/chat-stream")
async def chat_stream(request: Request, session_id: str = Form(...), question: str = Form(...)):

    require_login(request)

    history = chat_sessions.get(session_id, [])

    history.append({
        "role": "user",
        "content": question
    })

    chat_sessions[session_id] = history

    def generator():
        try:
            for token in stream_rag(question, history):
                yield token
        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    return StreamingResponse(generator(), media_type="text/plain")

# ---------- ADMIN: LIST DOCS ----------


@app.get("/admin/docs")
async def list_docs(request: Request):

    require_admin(request)

    store = get_or_create_store()

    docs = []
    for d in client.file_search_stores.documents.list(parent=store.name):
        docs.append({
            "name": d.name.split("/")[-1],
            "display_name": getattr(d, "display_name", "unknown")
        })

    return {"documents": docs}

# ---------- ADMIN: Upload ----------

@app.post("/admin/upload")
async def upload_docs(request: Request, files: List[UploadFile] = File(...)):

    require_admin(request)

    results = []

    for file in files:
        file_path = os.path.join(UPLOAD_DIR, file.filename)

        with open(file_path, "wb") as f:
            f.write(await file.read())

        res = upload_file_to_store(file_path)
        results.append(res)

    return {"uploaded": results}

# ---------- ADMIN: DELETE DOC ----------

@app.delete("/admin/docs/{doc_id}")
async def delete_doc(request: Request, doc_id: str):

    require_admin(request)

    store = get_or_create_store()

    full_doc_name = f"{store.name}/documents/{doc_id}"

    client.file_search_stores.documents.delete(
        name=full_doc_name,
        config={"force": True}
    )

    return {"status": "deleted", "doc": doc_id}
    

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_ui(request: Request):

    try:
        require_login(request)
    except:
        return RedirectResponse("/login-page")

    return FileResponse(os.path.join(BASE_DIR, "index.html"))
    

@app.get("/admin")
def serve_admin(request: Request):

    try:
        require_admin(request)
    except:
        return RedirectResponse("/login-page")

    return FileResponse(os.path.join(BASE_DIR, "admin.html"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


@app.get("/login")
async def login(request: Request):

    redirect_uri = request.url_for("auth").replace(scheme="https")

    return await oauth.google.authorize_redirect(request, redirect_uri)


from fastapi.responses import RedirectResponse

import httpx
from fastapi.responses import RedirectResponse

@app.get("/auth")
async def auth(request: Request):

    try:
        token = await oauth.google.authorize_access_token(request)
    except Exception:
        request.session.clear()
        return RedirectResponse("/login-page")

    #  Instead of parse_id_token → fetch user manually
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {token['access_token']}"}
            )
            user = resp.json()
    except Exception:
        request.session.clear()
        return RedirectResponse("/login-page")

    email = user.get("email")

    if not email or not email.endswith("@padcarelabs.com"):
        request.session.clear()
        return RedirectResponse("/login-page")

    #  set session
    response = RedirectResponse("/")
    request.session["user"] = {
        "email": email,
        "name": user.get("name", "")
    }

    return response

@app.get("/login-page")
def login_page():
    return FileResponse(os.path.join(BASE_DIR, "login.html"))

@app.get("/logout")
def logout(request: Request):

    request.session.clear()

    return RedirectResponse("/login-page")