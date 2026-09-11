"""data/models.json 读写单点（auth 与 admin 共用，消除双份实现）

models.json 结构：{模型id: {label, provider}, "_agent_models": {...}, "_agent_voices": {...}}
"""

import json
import os

from utils.data_path import root_path

_MODELS_PATH = os.path.join(root_path(), "data", "models.json")


def read_models_file() -> dict:
    if os.path.exists(_MODELS_PATH):
        with open(_MODELS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def write_models_file(data: dict):
    os.makedirs(os.path.dirname(_MODELS_PATH), exist_ok=True)
    with open(_MODELS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
