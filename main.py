import os
from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
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
from db import save_doc
from authlib.integrations.starlette_client import OAuth
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from dotenv import load_dotenv

load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()


app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("SESSION_SECRET"),
    https_only=True,
    same_site="none",
    session_cookie="session",
    max_age=86400
)


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
async def upload_docs(
    request: Request,
    files: List[UploadFile] = File(...),
    drive_links: List[str] = Form(...)
):
    require_admin(request)

    if len(files) != len(drive_links):
        raise HTTPException(status_code=400, detail="Each file must have exactly one Drive link.")

    results = []

    for file, link in zip(files, drive_links):
        clean_link = link.strip()

        if not clean_link:
            raise HTTPException(status_code=400, detail=f"Drive link missing for {file.filename}.")

        file_path = os.path.join(UPLOAD_DIR, file.filename)

        with open(file_path, "wb") as f:
            f.write(await file.read())

        # Upload to Gemini
        res = upload_file_to_store(file_path)

        # Save Drive link in Firestore
        save_doc(file.filename, clean_link)

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
    


app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_ui(request: Request):

    try:
        require_login(request)
    except:
        return RedirectResponse("/login-page")

    return FileResponse(os.path.join(BASE_DIR, "index.html"))
    

from fastapi.responses import HTMLResponse

@app.get("/admin")
def serve_admin(request: Request):
    try:
        require_admin(request)
    except:
        # Check if logged in at all
        user = request.session.get("user")
        if not user:
            return RedirectResponse("/login-page")
        # Logged in but not admin → friendly page
        return HTMLResponse("""
        <!DOCTYPE html>
        <html lang="en">
        <head>
          <meta charset="UTF-8"/>
          <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
          <title>Access Denied — PadCare Labs</title>
          <link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600&display=swap" rel="stylesheet">
          <style>
            body { margin:0; font-family:'Sora',sans-serif; background:#FFF6EA;
                   display:flex; align-items:center; justify-content:center; min-height:100vh; }
            .card { text-align:center; padding:48px 40px; background:#FCF8E6;
                    border:1px solid #CFCFCF; border-radius:18px; max-width:400px; width:90%; }
            .icon { width:64px; height:64px; border-radius:50%; background:rgba(201,22,26,0.09);
                    border:1px solid rgba(201,22,26,0.2); display:flex; align-items:center;
                    justify-content:center; margin:0 auto 20px; }
            .icon svg { width:28px; height:28px; stroke:#C9161A; }
            h1 { font-size:20px; font-weight:600; color:#AB0106; margin:0 0 8px; }
            p  { font-size:13.5px; color:#666666; line-height:1.65; margin:0 0 28px; }
            a  { display:inline-block; padding:11px 28px; background:#C9161A; color:#FFF6EA;
                 border-radius:10px; font-size:13px; font-weight:600; text-decoration:none;
                 transition:background 0.18s; }
            a:hover { background:#AB0106; }
          </style>
        </head>
        <body>
          <div class="card">
            <div class="icon">
              <svg viewBox="0 0 24 24" fill="none" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0 1 10 0v4"/>
              </svg>
            </div>
            <h1>Access Not Allowed</h1>
            <p>You don't have permission to view the admin panel.<br>Please contact your HR administrator if you think this is a mistake.</p>
            <a href="/">← Back to Assistant</a>
          </div>
        </body>
        </html>
        """, status_code=403)
    return FileResponse(os.path.join(BASE_DIR, "admin.html"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)


@app.get("/login")
async def login(request: Request):

    redirect_uri = request.url_for("auth").replace(scheme="https")

    return await oauth.google.authorize_redirect(request, redirect_uri)


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

@app.get("/me")
def get_user(request: Request):
    user = request.session.get("user")

    if not user:
        return {}

    from auth import ADMIN_EMAILS

    return {
        "name": user.get("name", ""),
        "email": user.get("email", ""),
        "is_admin": user.get("email") in ADMIN_EMAILS
    }
