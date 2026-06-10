"""
交互式查询：人事库简历表知识库（用于快速调试）
用法: python scripts/query_table_kb.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser

from src.hr_assistant.config import EMBEDDING_CONFIG, LLM_CONFIG

PERSIST_DIR = "./chroma_db"
COLLECTION_NAME = "hr_table_kb"

embeddings = OpenAIEmbeddings(
    model=EMBEDDING_CONFIG["model"],
    api_key=EMBEDDING_CONFIG["api_key"],
    base_url=EMBEDDING_CONFIG["base_url"],
)

vector_store = Chroma(
    embedding_function=embeddings,
    persist_directory=PERSIST_DIR,
    collection_name=COLLECTION_NAME,
)

retriever = vector_store.as_retriever(search_kwargs={"k": 3})

llm = ChatOpenAI(
    model=LLM_CONFIG["model"],
    api_key=LLM_CONFIG["api_key"],
    base_url=LLM_CONFIG["base_url"],
    temperature=0.1,
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个HR数据库专家。根据提供的知识库材料回答关于数据库表结构的问题。如果材料中没有相关信息，请如实告知。\n\n材料：\n{context}"),
    ("human", "{question}"),
])

rag_chain = (
    {"context": retriever, "question": RunnablePassthrough()}
    | prompt | llm | StrOutputParser()
)

print("=" * 60)
print("人事库简历表知识库查询 (输入 exit 退出)")
print("=" * 60)

while True:
    q = input("\nQ: ").strip()
    if q.lower() in ("exit", "quit", "q"):
        break
    if not q:
        continue
    answer = rag_chain.invoke(q)
    print(f"A: {answer}")
