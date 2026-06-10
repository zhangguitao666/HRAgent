"""
数据库连接工具 - 连接真实 HR 人事库和薪酬库
"""
import pymysql
from src.hr_assistant.config import DB_CONFIG


def get_hr_connection():
    """获取人事库连接（只读）"""
    cfg = DB_CONFIG["hr"]
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg["charset"],
        connect_timeout=10,
        read_timeout=30,
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_salary_connection():
    """获取薪酬库连接（只读）"""
    cfg = DB_CONFIG["salary"]
    return pymysql.connect(
        host=cfg["host"],
        port=cfg["port"],
        user=cfg["user"],
        password=cfg["password"],
        database=cfg["database"],
        charset=cfg["charset"],
        connect_timeout=10,
        read_timeout=30,
        cursorclass=pymysql.cursors.DictCursor,
    )


def execute_hr_query(sql: str) -> list[dict]:
    """执行人事库查询，返回字典列表"""
    conn = get_hr_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()


def execute_salary_query(sql: str) -> list[dict]:
    """执行薪酬库查询，返回字典列表"""
    conn = get_salary_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute(sql)
            return cursor.fetchall()
    finally:
        conn.close()


def format_query_result(rows: list[dict], max_rows: int = 20) -> str:
    """将查询结果格式化为 LLM 可读的文本"""
    if not rows:
        return "查询结果为空"

    total = len(rows)
    rows = rows[:max_rows]

    columns = list(rows[0].keys())
    header = " | ".join(columns)
    separator = "-" * len(header)

    lines = [f"共 {total} 条记录（显示前 {len(rows)} 条）：", separator, header, separator]

    for row in rows:
        values = []
        for col in columns:
            val = row[col]
            if val is None:
                val = "NULL"
            values.append(str(val))
        lines.append(" | ".join(values))

    if total > max_rows:
        lines.append(f"... 还有 {total - max_rows} 条未显示")

    return "\n".join(lines)
