"""
知识库测试：查询人事库简历表说明
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

test_questions = [
    "员工基本信息存在哪张表里？",
    "教育背景用哪张表存储？",
    "工作经历存在哪张表？",
    "家庭成员信息在哪张表？",
    "应聘简历数据存在哪些表中？",
    "技能证书和职称信息分别用什么表？",
]

for q in test_questions:
    print(f"\n{'='*60}")
    print(f"Q: {q}")
    sys.stdout.flush()
    docs = retriever.invoke(q)
    print(f"\n检索到 {len(docs)} 个相关片段:")
    for i, d in enumerate(docs):
        print(f"  [{i+1}] ({len(d.page_content)} chars) {d.page_content[:80]}...")
    sys.stdout.flush()
    answer = rag_chain.invoke(q)
    print(f"\nA: {answer}")
    sys.stdout.flush()
