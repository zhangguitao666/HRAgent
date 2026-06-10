"""
数据加载工具 - 从 JSON 文件读取模拟数据库数据
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def load_employees() -> list[dict]:
    with open(os.path.join(DATA_DIR, "employees.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_salary() -> list[dict]:
    with open(os.path.join(DATA_DIR, "salary.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_attendance() -> list[dict]:
    with open(os.path.join(DATA_DIR, "attendance.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def load_policy() -> str:
    policy_path = os.path.join(DATA_DIR, "company_policy.txt")
    if os.path.exists(policy_path):
        with open(policy_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""
