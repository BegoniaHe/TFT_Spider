"""
爬虫工具，爬取官网的各种信息，包括图片：https://lol.qq.com/tft/

目前包含以下内容：
  - 棋子 chess
  - 海克斯 hex
  - 装备 equipment
  - 种族 race
  - 职业 job

用法示例：
  python main.py                            # 下载数据 + 图片
  python main.py --no-images               # 仅下载数据，跳过图片
  python main.py --no-scrape --export-md   # 不爬数据，直接从本地 JSON 导出 Markdown
  python main.py --export-md               # 爬取后额外导出全量 Markdown
  python main.py --export-md --export-type chess          # 仅导出弈子
  python main.py --export-md --export-type chess --export-split  # 按费用分文件
  python main.py --export-md --export-type chess --export-name 安妮  # 单条目
"""

import argparse

from tft_spider import RawDataCollector, TFTDataProcessor, TFTMarkdownExporter
from tft_spider.config import (
    TFT_IMG_FILE,
    TFT_MD_EXPORT_DIR,
    TFT_PROCESSED_DATA_FILE,
    TFT_PY_CLASS_FILE,
    TFT_RAW_DATA_FILE,
)
from tft_spider.exporter import EXPORT_TYPES
from tft_spider.utils import load_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TFT 数据爬虫 - 爬取官网棋子、装备、海克斯等信息")
    parser.add_argument(
        "--no-images",
        action="store_true",
        default=False,
        help="跳过所有图片下载，仅采集并处理数据",
    )
    parser.add_argument(
        "--no-scrape",
        action="store_true",
        default=False,
        help="跳过爬取和数据处理，直接从本地已有的 JSON 文件操作（配合 --export-md 使用）",
    )
    # ── Markdown 导出参数 ──────────────────────────────────────────────────────
    parser.add_argument(
        "--export-md",
        action="store_true",
        default=False,
        help="爬取 / 处理完成后额外导出 Markdown 文档（供 AI 阅读）",
    )
    parser.add_argument(
        "--export-type",
        choices=EXPORT_TYPES,
        default="all",
        metavar="TYPE",
        help=(f"导出类型（需配合 --export-md）：{' / '.join(EXPORT_TYPES)}，默认 all"),
    )
    parser.add_argument(
        "--export-split",
        action="store_true",
        default=False,
        help="按子类别分文件导出（需配合 --export-md）",
    )
    parser.add_argument(
        "--export-name",
        default=None,
        metavar="NAME",
        help="仅导出该名称的单个条目（需配合 --export-md，对 chess/equip/hex 有效）",
    )
    parser.add_argument(
        "--export-dir",
        default=TFT_MD_EXPORT_DIR,
        metavar="DIR",
        help=f"Markdown 导出目录，默认 {TFT_MD_EXPORT_DIR}",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if args.no_scrape:
        print("\033[33m已跳过爬取和数据处理（--no-scrape），直接使用本地 JSON 文件。\033[0m")
    else:
        # 下载官方的 raw 数据
        rdc = RawDataCollector()
        print()
        print("================ 下载所有原始数据 ================")
        rdc.save_tft_raw_data()
        print(f"\033[32m原始数据爬取完成，保存到：{TFT_RAW_DATA_FILE}\033[0m")
        print()

        # 下载图片（可通过 --no-images 跳过）
        if args.no_images:
            print("\033[33m已跳过图片下载（--no-images）\033[0m")
        else:
            print("================ 下载棋子、技能、海克斯、装备图片 ================")
            print("\033[31m如果图片有错，比如版本不对，请将所有图片删除重新下载。\033[0m")
            rdc.download_all_imgs()
            print(f"\033[32m图片下载完成，保存到：{TFT_IMG_FILE}\033[0m")
        print()

        # 处理数据并导出
        tdp = TFTDataProcessor()
        print("================ 处理数据，导出json ================")
        tdp.save_tft_processed_data()
        print(f"\033[32m数据处理完成，保存到：{TFT_PROCESSED_DATA_FILE}\033[0m")
        print()

        print("================ 处理数据，导出py Singleton ================")
        tdp.save_py_class()
        print(f"\033[32mSingleton构建完成，保存到：{TFT_PY_CLASS_FILE}\033[0m")
        print()

    # Markdown 导出（可选）
    if args.export_md:
        print(f"================ 导出 Markdown（类型：{args.export_type}）================")
        processed = load_json(TFT_PROCESSED_DATA_FILE)
        raw = load_json(TFT_RAW_DATA_FILE)
        exporter = TFTMarkdownExporter(processed, raw)
        written = exporter.save(
            export_type=args.export_type,
            split=args.export_split,
            out_dir=args.export_dir,
            name_filter=args.export_name,
        )
        for path in written:
            print(f"  \033[32m已导出：{path}\033[0m")
        print()
