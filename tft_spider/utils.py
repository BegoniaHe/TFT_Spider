"""通用工具函数"""

import json
import os


def load_json(filename: str) -> dict:
    with open(filename, encoding="utf-8") as f:
        return json.load(f)


def save_json(data: dict, filename: str, indent: int = 4) -> None:
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
