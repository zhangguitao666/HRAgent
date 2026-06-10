"""
知识库批量导入 — 清空旧数据，按章节分块导入 10 个 PDF 制度文档
"""
import os
import re
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from src.hr_assistant.config import EMBEDDING_CONFIG

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(PROJECT_ROOT, "data", "knowledge")
PERSIST_DIR = os.path.join(PROJECT_ROOT, "chroma_db")
COLLECTION = "faq_knowledge"

# 中文制度文档的章节划分正则
CHAPTER_PATTERNS = [
    (r'(第[一二三四五六七八九十百]+编\s+.*?)(?=\n第[一二三四五六七八九十百]+编|\n第[一二三四五六七八九十百]+章|\Z)', '编'),
    (r'(第[一二三四五六七八九十百]+章\s+[^\n]+)', '章'),
    (r'(第[一二三四五六七八九十百]+节\s+[^\n]+)', '节'),
]

def split_by_chapters(text: str, filename: str) -> list[Document]:
    """按章节标题拆分文档，如果太短则合并"""
    # 先按"第X章"拆分
    chapters = []
    
    # 尝试匹配第X章
    pattern = r'(第[一二三四五六七八九十百\d]+章[^\n]*)'
    parts = re.split(pattern, text)
    
    if len(parts) <= 1:
        # 没有章标题，尝试用第X条或直接按段落拆
        pattern2 = r'(第[一二三四五六七八九十百\d]+条[^\n]*)'
        parts = re.split(pattern2, text)
    
    if len(parts) <= 1:
        # 完全无结构，整篇作为一个文档
        return [Document(page_content=text[:2000], metadata={"source": filename})]
    
    # 组装：第一个元素可能是序言，后续是 [标题, 内容] 交替
    chunks = []
    i = 0
    if not re.match(pattern, parts[0]):
        pre = parts[0].strip()
        if len(pre) > 50:
            chunks.append(Document(
                page_content=pre[:1500],
                metadata={"source": filename, "section": "前言"}
            ))
        i = 1
    
    while i < len(parts) - 1:
        title = parts[i].strip()
        content = parts[i + 1].strip() if i + 1 < len(parts) else ""
        full = title + "\n" + content
        
        # 如果内容太长（>2000 字），再按段细分
        if len(full) > 2000:
            sub_docs = split_long_chapter(full, filename, title)
            chunks.extend(sub_docs)
        else:
            chunks.append(Document(
                page_content=full,
                metadata={"source": filename, "section": title[:80]}
            ))
        i += 2
    
    return chunks


def split_long_chapter(text: str, filename: str, section: str) -> list[Document]:
    """对超长章节进一步拆分"""
    # 先尝试按"X、"/"（X）"等子标题拆分
    pattern = r'(\n[（(]?[一二三四五六七八九十\d]+[）)]\s*)'
    parts = re.split(pattern, text)
    
    if len(parts) <= 1:
        # 按段落拆分
        paras = text.split("\n")
        docs = []
        buf = ""
        for p in paras:
            if len(buf) + len(p) > 1500 and buf.strip():
                docs.append(Document(page_content=buf, metadata={"source": filename, "section": section[:80]}))
                buf = p
            else:
                buf += ("\n" + p) if buf else p
        if buf.strip():
            docs.append(Document(page_content=buf, metadata={"source": filename, "section": section[:80]}))
        return docs
    
    # 组装子标题块
    docs = []
    for i in range(0, len(parts), 2):
        sub_title = parts[i].strip()
        sub_content = parts[i+1].strip() if i+1 < len(parts) else ""
        full = sub_title + sub_content
        if len(full) > 50:
            docs.append(Document(
                page_content=full[:2000],
                metadata={"source": filename, "section": f"{section[:60]} > {sub_title[:30]}"}
            ))
    return docs


def process_all():
    print("=" * 60)
    print("知识库批量导入")
    print("=" * 60)
    
    embeddings = OpenAIEmbeddings(
        model=EMBEDDING_CONFIG["model"],
        api_key=EMBEDDING_CONFIG["api_key"],
        base_url=EMBEDDING_CONFIG["base_url"],
    )
    
    # 清空旧集合
    print("\n[1/3] 清空旧知识库...")
    os.makedirs(PERSIST_DIR, exist_ok=True)
    store = Chroma(embedding_function=embeddings, persist_directory=PERSIST_DIR, collection_name=COLLECTION)
    try:
        ids = store.get().get("ids", [])
        if ids:
            store.delete(ids=ids)
            print(f"  已删除 {len(ids)} 条旧记录")
    except Exception as e:
        print(f"  清空跳过: {e}")
    
    # 处理所有 PDF
    print(f"\n[2/3] 处理 PDF 文档...")
    pdf_files = sorted([f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")])
    
    all_docs = []
    for i, pdf_file in enumerate(pdf_files):
        path = os.path.join(PDF_DIR, pdf_file)
        print(f"  [{i+1}/{len(pdf_files)}] {pdf_file[:50]}...", end=" ", flush=True)
        try:
            loader = PyPDFLoader(path)
            pages = loader.load()
            text = "\n".join(p.page_content for p in pages if p.page_content.strip())
            
            docs = split_by_chapters(text, pdf_file)
            all_docs.extend(docs)
            total_chars = sum(len(d.page_content) for d in docs)
            print(f"OK → {len(docs)} 块, {total_chars} 字")
        except Exception as e:
            print(f"FAIL: {e}")
    
    # 存入 ChromaDB
    print(f"\n[3/3] 存入 ChromaDB ({len(all_docs)} 个文档块)...")
    batch_size = 20
    for i in range(0, len(all_docs), batch_size):
        batch = all_docs[i:i + batch_size]
        store.add_documents(batch)
        print(f"  已存入 {min(i + batch_size, len(all_docs))}/{len(all_docs)}")
    
    print(f"\n✓ 完成！共 {len(all_docs)} 个文档块导入到集合 '{COLLECTION}'")
    print(f"  来自 {len(pdf_files)} 个 PDF 文件")


if __name__ == "__main__":
    process_all()
