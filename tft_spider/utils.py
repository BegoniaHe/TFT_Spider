"""通用工具函数"""

import json
import os


def load_json(filename: str) -> dict:
    with open(filename, encoding="utf-8") as f:
        return json.load(f)


def is_valid_chess(chess: dict) -> bool:
    """判断是否为真实棋子（费用 1-5，且 isShow 不为 '0'）。"""
    try:
        price = int(chess.get("price", 0))
    except (ValueError, TypeError):
        return False
    if price not in range(1, 6):
        return False
    if chess.get("isShow", "1") == "0":
        return False
    return True


def save_json(data: dict, filename: str, indent: int = 4) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
