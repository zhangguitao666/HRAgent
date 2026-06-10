"""
知识库管理 API — 文件上传、源管理、分块操作
"""
import os
import uuid
import shutil
import tempfile
from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.hr_assistant.utils.chroma_utils import (
    list_sources, list_chunks, get_chunk_detail,
    add_text, add_file_content, delete_source, delete_chunk,
    rechunk_source, get_doc_count,
)

router = APIRouter()

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)


class RechunkRequest(BaseModel):
    source: str
    chunk_size: int = 500
    overlap: int = 80

class AddTextRequest(BaseModel):
    text: str
    source: str = "manual"


# ──── 文件上传 ────

@router.post("/upload-file")
async def upload_file(file: UploadFile = File(...)):
    """上传文件（支持 txt, md, pdf, docx），自动分块嵌入"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in (".txt", ".md", ".pdf", ".docx"):
        return JSONResponse({"ok": False, "error": f"不支持的文件类型: {ext}"}, 400)

    content = await file.read()
    text = ""

    try:
        if ext in (".txt", ".md"):
            # 尝试多种编码解码
            for enc in ("utf-8", "gbk", "gb2312", "latin-1"):
                try:
                    text = content.decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
        elif ext == ".docx":
            # 保存临时文件后解析
            tmp = os.path.join(tempfile.gettempdir(), f"kb_{uuid.uuid4().hex}.docx")
            with open(tmp, "wb") as f:
                f.write(content)
            try:
                from docx import Document
                doc = Document(tmp)
                text = "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
            finally:
                os.remove(tmp)
        elif ext == ".pdf":
            # 保存临时文件后用 PyPDFLoader 解析
            tmp = os.path.join(tempfile.gettempdir(), f"kb_{uuid.uuid4().hex}.pdf")
            with open(tmp, "wb") as f:
                f.write(content)
            try:
                from langchain_community.document_loaders import PyPDFLoader
                pages = PyPDFLoader(tmp).load()
                text = "\n\n".join(p.page_content.strip() for p in pages if p.page_content.strip())
            finally:
                os.remove(tmp)
    except Exception as e:
        return JSONResponse({"ok": False, "error": f"解析失败: {str(e)[:200]}"}, 500)

    if not text.strip():
        return JSONResponse({"ok": False, "error": "文件内容为空"}, 400)

    count = add_file_content(file.filename, text)
    return {"ok": True, "source": file.filename, "chunks_added": count, "total": get_doc_count()}


@router.post("/add-text")
def add_text_api(req: AddTextRequest):
    count = add_text(req.text, source=req.source)
    return {"ok": True, "chunks_added": count, "total": get_doc_count()}


# ──── 源管理 ────

@router.get("/sources")
def get_sources():
    return {"total_docs": get_doc_count(), "sources": list_sources()}


@router.get("/chunks/{source:path}")
def get_chunks(source: str):
    return {"source": source, "chunks": list_chunks(source)}


@router.get("/chunk/{chunk_id}")
def chunk_detail(chunk_id: str):
    chunk = get_chunk_detail(chunk_id)
    if not chunk:
        return JSONResponse({"ok": False, "error": "未找到该文档块"}, 404)
    return {"ok": True, "chunk": chunk}


@router.delete("/source/{source:path}")
def remove_source(source: str):
    count = delete_source(source)
    return {"ok": True, "deleted": count, "total": get_doc_count()}


@router.delete("/chunk/{chunk_id}")
def remove_chunk(chunk_id: str):
    ok = delete_chunk(chunk_id)
    return {"ok": ok, "total": get_doc_count()}


# ──── 重新分块 ────

@router.post("/rechunk")
def rechunk(req: RechunkRequest):
    count = rechunk_source(req.source, chunk_size=req.chunk_size, overlap=req.overlap)
    return {"ok": True, "chunks": count, "source": req.source, "total": get_doc_count()}
