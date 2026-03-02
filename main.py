"""
爬虫工具，爬取官网的各种信息，包括图片：https://lol.qq.com/tft/

目前包含以下内容：
  - 棋子 chess
  - 海克斯 hex
  - 装备 equipment
  - 种族 race
  - 职业 job
"""

from tft_spider import RawDataCollector, TFTDataProcessor
from tft_spider.config import (
    TFT_IMG_FILE,
    TFT_PROCESSED_DATA_FILE,
    TFT_PY_CLASS_FILE,
    TFT_RAW_DATA_FILE,
)

if __name__ == "__main__":
    # 下载官方的raw数据
    rdc = RawDataCollector()
    # 保存爬取的信息到 TFT_RAW_DATA_FILE = 'tft_raw_data.json'
    print()
    print("================ 下载所有原始数据 ================")
    rdc.save_tft_raw_data()
    print(f"\033[32m原始数据爬取完成，保存到：{TFT_RAW_DATA_FILE}\033[0m")
    print()

    # 下载图片
    print("================ 下载棋子、技能、海克斯、装备图片 ================")
    print("\033[31m如果图片有错，比如版本不对，请将所有图片删除重新下载。\033[0m")
    rdc.download_all_imgs()
    print(f"\033[32m图片下载完成，保存到：{TFT_IMG_FILE}\033[0m")
    print()

    # 作者根据自己的需求对数据进行了处理和汇总
    tdp = TFTDataProcessor()
    # 处理好的数据保存到 TFT_PROCESSED_DATA_FILE = 'tft_processed_data.json'
    print("================ 处理数据，导出json ================")
    tdp.save_tft_processed_data()
    print(f"\033[32m数据处理完成，保存到：{TFT_PROCESSED_DATA_FILE}\033[0m")
    print()

    # 保存一份TFTData.py的Singleton，方便作者自己调用。
    print("================ 处理数据，导出py Singleton ================")
    tdp.save_py_class()
    print(f"\033[32mSingleton构建完成，保存到：{TFT_PY_CLASS_FILE}\033[0m")
    print()
