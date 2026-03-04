import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

from gemini_client import client
from file_store import upload_file_to_store, get_or_create_store
from rag_chat import stream_rag

import uvicorn

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Warmup ----------

@app.on_event("startup")
async def warmup():
    try:
        for _ in stream_rag("ping"):
            break
    except:
        pass


# ---------- ADMIN: Upload ----------

@app.post("/admin/upload")
async def upload_doc(file: UploadFile = File(...)):
    file_path = os.path.join(UPLOAD_DIR, file.filename)

    with open(file_path, "wb") as f:
        f.write(await file.read())

    return upload_file_to_store(file_path)


# ---------- CHAT STREAM ----------

@app.post("/chat-stream")
async def chat_stream(question: str = Form(...)):
    def generator():
        try:
            for token in stream_rag(question):
                yield token
        except Exception as e:
            yield f"\n[ERROR] {str(e)}"

    return StreamingResponse(generator(), media_type="text/plain")


# ---------- ADMIN: LIST DOCS ----------

@app.get("/admin/docs")
async def list_docs():
    store = get_or_create_store()

    docs = []
    for d in client.file_search_stores.documents.list(parent=store.name):
        docs.append({
            "name": d.name.split("/")[-1],
            "display_name": getattr(d, "display_name", "unknown")
        })

    return {"documents": docs}


# ---------- ADMIN: DELETE DOC ----------

@app.delete("/admin/docs/{doc_id}")
async def delete_doc(doc_id: str):
    try:
        store = get_or_create_store()
        full_doc_name = f"{store.name}/documents/{doc_id}"

        client.file_search_stores.documents.delete(
            name=full_doc_name,
            config={"force": True}
        )

        return {"status": "deleted", "doc": doc_id}

    except Exception as e:
        return {"status": "error", "message": str(e)}
    

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app.mount("/static", StaticFiles(directory="."), name="static")

@app.get("/")
def serve_ui():
    return FileResponse(os.path.join(BASE_DIR, "index.html"))
    

@app.get("/admin")
def serve_admin():
    return FileResponse(os.path.join(BASE_DIR, "admin.html"))

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)

