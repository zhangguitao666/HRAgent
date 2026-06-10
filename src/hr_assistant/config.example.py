"""
HR 助手项目 - 配置模板（复制为 config.py 后填入真实凭证）
"""
import os

LLM_CONFIG = {
    "model": "<模型名称>",
    "api_key": "<LLM API Key>",
    "base_url": "<LLM API 地址>",
    "temperature": 0.7,
    "max_tokens": 2048,
}

EMBEDDING_CONFIG = {
    "model": "<嵌入模型名>",
    "api_key": "<Embedding API Key>",
    "base_url": "<Embedding API 地址>",
}

RERANKER_CONFIG = {
    "model": "<重排序模型名>",
    "api_key": "<Reranker API Key>",
    "base_url": "<Reranker API 地址>",
}

DB_CONFIG = {
    "hr": {
        "host": "<人事库IP>", "port": 2883,
        "user": "<用户名>", "password": "<密码>",
        "charset": "utf8mb4", "database": "<库名>",
    },
    "salary": {
        "host": "<薪酬库IP>", "port": 2883,
        "user": "<用户名>", "password": "<密码>",
        "charset": "utf8mb4", "database": "<库名>",
    },
}

# 以下 Schema 和 SQL 示例不涉及敏感数据，从 config.py 复制即可
# （完整内容见 config.py — 基于真实 DESCRIBE 结果维护）
