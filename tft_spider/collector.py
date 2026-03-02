"""原始数据采集器：从官网爬取 TFT 数据及图片"""

import datetime
import os

import requests
from rich.progress import track

from .config import TFT_IMG_FILE, TFT_RAW_DATA_FILE
from .utils import is_valid_chess, save_json


class RawDataCollector:
    """从腾讯官网采集 TFT 原始数据，并提供图片下载功能。"""

    # 版本信息 API
    _VERSION_URL = "https://lol.qq.com/zmtftzone/public-lib/versionconfig.json"

    def __init__(self) -> None:
        # 每个 requests 请求超时时间
        self._timeout: int = 5
        self.version_config: dict = {
            "赛季名称": "",
            "版本信息": "",
            "爬取日期": f"{datetime.date.today()}",
            "url_chess_data": "https://game.gtimg.cn/images/lol/act/img/tft/js/chess.js",
            "url_race_data": "https://game.gtimg.cn/images/lol/act/img/tft/js/race.js",
            "url_job_data": "https://game.gtimg.cn/images/lol/act/img/tft/js/job.js",
            "url_equip_data": "https://game.gtimg.cn/images/lol/act/img/tft/js/equip.js",
            "url_hex_data": "https://game.gtimg.cn/images/lol/act/img/tft/js/hex.js",
        }
        self.raw_data: dict = {
            "version_config": self.version_config,
            "chess": [],
            "race": [],
            "job": [],
            "equip": [],
            "hex": [],
        }
        self._get_version_info()
        self._collect_raw_data()

    # 版本信息

    def _get_version_info(self) -> None:
        """从官网获取当前赛季及各数据接口 URL。"""
        response = requests.get(self._VERSION_URL, timeout=self._timeout)
        res = response.json()[0]

        self.version_config["赛季名称"] = f"{res['idSeason']}-{res['stringName']}"
        self.version_config["url_chess_data"] = res["urlChessData"]
        self.version_config["url_race_data"] = res["urlRaceData"]
        self.version_config["url_job_data"] = res["urlJobData"]
        self.version_config["url_equip_data"] = res["urlEquipData"]
        self.version_config["url_hex_data"] = res["urlBuffData"]
        self.version_config["url_powerup_data"] = res.get("urlPowerupData")

        # 通过 race 接口获取版本号
        race_resp = requests.get(self.version_config["url_race_data"], timeout=self._timeout)
        self.version_config["版本信息"] = race_resp.json()["version"]

    # 数据采集

    def _collect_raw_data(self) -> None:
        """采集所有分类的原始数据并保存到 JSON 文件。"""
        for data_kind in ("chess", "race", "job", "equip"):
            url = self.version_config[f"url_{data_kind}_data"]
            resp = requests.get(url, timeout=self._timeout)
            self.raw_data[data_kind] = resp.json()["data"]

        # powerup（部分赛季不存在）
        powerup_url = self.version_config.get("url_powerup_data")
        if powerup_url:
            resp = requests.get(powerup_url, timeout=self._timeout)
            self.raw_data["powerup"] = resp.json()["data"]
        else:
            self.raw_data["powerup"] = {}

        # hex 结构特殊，需单独处理
        resp = requests.get(self.version_config["url_hex_data"], timeout=self._timeout)
        hex_res = resp.json()
        self.raw_data["hex"] = [hex_res[key] for key in hex_res]

        save_json(self.raw_data, TFT_RAW_DATA_FILE)

    def save_tft_raw_data(self) -> None:
        """将采集的原始数据保存到磁盘。"""
        save_json(self.raw_data, TFT_RAW_DATA_FILE)

    # 图片下载

    def _download_image(self, img_path: str, img_url: str) -> None:
        headers = {
            "authority": "game.gtimg.cn",
            "user-agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/84.0.4147.105 Safari/537.36"
            ),
        }
        if os.path.exists(img_path):
            return
        resp = requests.get(img_url, headers=headers, timeout=self._timeout)
        if b"was not found" in resp.content:
            resp = requests.get(img_url, headers=headers, timeout=self._timeout, verify=False)
        with open(img_path, mode="wb") as f:
            f.write(resp.content)

    def download_chess_imgs(self) -> None:
        version_id = self.version_config["赛季名称"].split("-")[0]
        chess_list = [c for c in self.raw_data["chess"] if is_valid_chess(c)]
        for chess in track(chess_list, description="正在爬取棋子图片"):
            img_path = os.path.join(
                TFT_IMG_FILE,
                "chess",
                f"{chess['TFTID']}-{chess['title']}-{chess['displayName']}.jpg",
            )
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            img_url = (
                f"https://game.gtimg.cn/images/lol/tftstore/{version_id}"
                f"/624x318/{chess['TFTID']}.jpg"
            )
            try:
                self._download_image(img_path, img_url)
            except Exception:
                print(f"{chess['TFTID']}-{chess['title']}-{chess['displayName']} 图片下载失败。")
                print(f"chess - url: {img_url}")

    def download_skill_imgs(self) -> None:
        chess_list = [c for c in self.raw_data["chess"] if is_valid_chess(c)]
        for chess in track(chess_list, description="正在爬取技能图片"):
            skill_name = chess["skillName"].replace("/", "-").replace("：", "-")
            img_path = os.path.join(
                TFT_IMG_FILE,
                "skill",
                f"{chess['TFTID']}-{chess['title']}-{chess['displayName']}-{skill_name}.jpg",
            )
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            try:
                self._download_image(img_path, chess["skillImage"])
            except Exception:
                print(
                    f"{chess['TFTID']}-{chess['title']}-"
                    f"{chess['displayName']}-{chess['skillName']} 图片下载失败。"
                )
                print(f"skill - url: {chess['skillImage']}")

    def download_hex_imgs(self) -> None:
        hex_list = self.raw_data["hex"][4]
        for hex_key in track(hex_list, description="正在爬取海克斯图片"):
            hex_info = hex_list[hex_key]
            img_path = os.path.join(
                TFT_IMG_FILE, "hex", f"{hex_info['hexId']}-{hex_info['name']}.jpg"
            )
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            try:
                self._download_image(img_path, hex_info["imgUrl"])
            except Exception:
                print(f"{hex_info['hexId']}-{hex_info['name']} 图片下载失败。")
                print(f"hex - url: {hex_info['imgUrl']}")

    def download_equipment_imgs(self) -> None:
        for equip in track(self.raw_data["equip"], description="正在爬取装备图片"):
            clean_name = equip["name"].replace("/", "").replace(" ", "")
            img_path = os.path.join(TFT_IMG_FILE, "equip", f"{equip['TFTID']}-{clean_name}.jpg")
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            try:
                self._download_image(img_path, equip["imagePath"])
            except Exception:
                print(f"{equip['TFTID']}-{clean_name} 图片下载失败。")
                print(f"url: {equip['imagePath']}")

    def download_powerup_imgs(self) -> None:
        powerup_dict = self.raw_data.get("powerup", {})
        if not powerup_dict:
            print("当前赛季无 powerup 数据，跳过。")
            return
        for key in track(powerup_dict, description="正在爬取果实（powerup）图片"):
            powerup = powerup_dict[key]
            clean_name = powerup["title"].replace("/", "").replace(" ", "")
            img_path = os.path.join(TFT_IMG_FILE, "powerup", f"{powerup['id']}-{clean_name}.jpg")
            os.makedirs(os.path.dirname(img_path), exist_ok=True)
            try:
                self._download_image(img_path, powerup["imageUrl"])
            except Exception:
                print(f"{powerup['id']}-{clean_name} 图片下载失败。")
                print(f"url: {powerup['imageUrl']}")

    def download_all_imgs(self) -> None:
        """下载全部类别的图片。"""
        self.download_chess_imgs()
        self.download_skill_imgs()
        self.download_hex_imgs()
        self.download_equipment_imgs()
        self.download_powerup_imgs()
