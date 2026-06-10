"""
SQL 查询日志工具
"""
import os
import logging
from datetime import datetime

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

_logger = None


def _get_logger():
    global _logger
    if _logger is None:
        _logger = logging.getLogger("sql_query")
        _logger.setLevel(logging.DEBUG)

        log_file = os.path.join(LOG_DIR, f"sql_{datetime.now().strftime('%Y%m%d')}.log")
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        _logger.addHandler(handler)

        # 也输出到控制台
        console = logging.StreamHandler()
        console.setFormatter(logging.Formatter("[SQL] %(message)s"))
        _logger.addHandler(console)
    return _logger


def log_sql(question: str, sql: str, result: str = "", error: str = ""):
    """记录SQL查询"""
    logger = _get_logger()
    logger.info(f"问题: {question}")
    logger.info(f"SQL : {sql}")
    if result:
        logger.info(f"结果: {result[:200]}")
    if error:
        logger.error(f"错误: {error}")
    logger.info("-" * 60)


def log_tool_call(tool: str, question: str):
    """记录工具调用"""
    logger = _get_logger()
    logger.info(f"工具: {tool} | 查询: {question}")


def log_answer(answer: str):
    """记录最终回答"""
    logger = _get_logger()
    logger.info(f"回答: {answer[:300]}")
