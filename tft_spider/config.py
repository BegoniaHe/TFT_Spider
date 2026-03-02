"""路径常量配置"""

import os

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_DATA_DIR = os.path.join(ROOT_DIR, "tft_data")

TFT_RAW_DATA_FILE = os.path.join(_DATA_DIR, "tft_raw_data.json")
TFT_PROCESSED_DATA_FILE = os.path.join(_DATA_DIR, "tft_processed_data.json")
TFT_PY_CLASS_FILE = os.path.join(_DATA_DIR, "TFTData.py")
TFT_IMG_FILE = os.path.join(ROOT_DIR, "tft_images")
