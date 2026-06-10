"""
FastAPI 主入口 - HR 智能助手 API
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.api import faq, resume, lifecycle, query, chat, knowledge, resume_lookup

app = FastAPI(title="HR 智能助手 API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(faq.router, prefix="/api/faq", tags=["FAQ"])
app.include_router(resume.router, prefix="/api/resume", tags=["简历"])
app.include_router(lifecycle.router, prefix="/api/lifecycle", tags=["入转调离"])
app.include_router(query.router, prefix="/api/query", tags=["数据查询"])
app.include_router(chat.router, prefix="/api/chat", tags=["统一对话"])
app.include_router(knowledge.router, prefix="/api/knowledge", tags=["知识库"])
app.include_router(resume_lookup.router, prefix="/api/resume-lookup", tags=["干部简历"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
