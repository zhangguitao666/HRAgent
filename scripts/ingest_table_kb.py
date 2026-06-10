"""
知识库构建：将预发人事库简历表说明文档 向量化后存入 ChromaDB
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_core.documents import Document
from langchain_chroma import Chroma

from src.hr_assistant.config import EMBEDDING_CONFIG

MD_PATH = "预发人事库简历相关表说明.md"
COLLECTION_NAME = "hr_table_kb"
PERSIST_DIR = "./chroma_db"

embeddings = OpenAIEmbeddings(
    model=EMBEDDING_CONFIG["model"],
    api_key=EMBEDDING_CONFIG["api_key"],
    base_url=EMBEDDING_CONFIG["base_url"],
)

with open(MD_PATH, "r", encoding="utf-8") as f:
    md_text = f.read()

splitter = MarkdownHeaderTextSplitter(headers_to_split_on=[("##", "章节")])
sections = splitter.split_text(md_text)

merged = []
for sec in sections:
    chapter = sec.metadata.get("章节", "概述")
    if merged and len(merged[-1].page_content) < 600:
        merged[-1].page_content += "\n\n" + sec.page_content
        merged[-1].metadata["章节"] += ", " + chapter
    else:
        merged.append(Document(page_content=sec.page_content, metadata={"章节": chapter}))

print(f"合并后共 {len(merged)} 个块:")
for i, m in enumerate(merged):
    print(f"  [{i+1}] {len(m.page_content)} chars - {m.metadata['章节']}")

vector_store = Chroma.from_documents(
    documents=merged,
    embedding=embeddings,
    persist_directory=PERSIST_DIR,
    collection_name=COLLECTION_NAME,
)
print(f"已存入 ChromaDB collection '{COLLECTION_NAME}'，共 {vector_store._collection.count()} 条")
