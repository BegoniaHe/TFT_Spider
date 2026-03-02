"""数据处理器：对原始数据进行加工，并输出 JSON / Python Singleton 文件。"""

from .config import TFT_PROCESSED_DATA_FILE, TFT_PY_CLASS_FILE, TFT_RAW_DATA_FILE
from .utils import load_json, save_json

# OCR 无法识别的字符替换表
_OCR_REPLACE: dict[str, str] = {
    "菈": "拉",
}


class TFTDataProcessor:
    """读取原始数据并生成结构化的处理结果。"""

    def __init__(self) -> None:
        self.raw_data: dict = load_json(TFT_RAW_DATA_FILE)
        self.processed_data: dict = {
            "all_chess_name": "",
            "all_race_name": "",
            "all_job_name": "",
            "job_chess": {},
            "race_chess": {},
            "price_chess": {},
            "chess_name_info": {},
        }
        self._process_data()

    # ------------------------------------------------------------------
    # 内部处理步骤
    # ------------------------------------------------------------------

    def _match_job_chess(self) -> None:
        res: dict[str, list[str]] = {}
        for job in self.raw_data["job"]:
            job_id, job_name = job["jobId"], job["name"]
            res[job_name] = [
                chess["displayName"]
                for chess in self.raw_data["chess"]
                if job_id in chess["jobIds"].split(",")
            ]
        self.processed_data["job_chess"] = res

    def _match_race_chess(self) -> None:
        res: dict[str, list[str]] = {}
        for race in self.raw_data["race"]:
            race_id, race_name = race["raceId"], race["name"]
            res[race_name] = [
                chess["displayName"]
                for chess in self.raw_data["chess"]
                if race_id in chess["raceIds"].split(",")
            ]
        self.processed_data["race_chess"] = res

    def _match_price_chess(self) -> None:
        res: dict[str, list[str]] = {str(p): [] for p in range(1, 6)}
        for chess in self.raw_data["chess"]:
            price = chess["price"]
            if price in res:
                res[price].append(chess["displayName"])
        self.processed_data["price_chess"] = res

    def _parse_all_strings(self) -> None:
        """拼接所有棋子/种族/职业名称字符串，方便 OCR 后模糊匹配。"""
        self.processed_data["all_chess_name"] = "-".join(
            c["displayName"] for c in self.raw_data["chess"]
        )
        self.processed_data["all_race_name"] = "-".join(r["name"] for r in self.raw_data["race"])
        self.processed_data["all_job_name"] = "-".join(j["name"] for j in self.raw_data["job"])

    def _parse_chess_name_info(self) -> None:
        self.processed_data["chess_name_info"] = {
            info["displayName"]: info for info in self.raw_data["chess"]
        }

    def _process_data(self) -> None:
        self._match_job_chess()
        self._match_race_chess()
        self._match_price_chess()
        self._parse_all_strings()
        self._parse_chess_name_info()
        save_json(self.processed_data, TFT_PROCESSED_DATA_FILE)

    # ------------------------------------------------------------------
    # 公开接口
    # ------------------------------------------------------------------

    def save_tft_processed_data(self) -> None:
        """将处理后的数据保存到磁盘。"""
        save_json(self.processed_data, TFT_PROCESSED_DATA_FILE)

    def save_py_class(self) -> None:
        """生成 TFTData.py 单例文件，供外部项目直接引用。"""
        simplified: dict = {}
        for name, val in self.processed_data["chess_name_info"].items():
            jobs = [j for j, names in self.processed_data["job_chess"].items() if name in names]
            races = [r for r, names in self.processed_data["race_chess"].items() if name in names]
            simplified[name] = {
                "name": name,
                "jobs": jobs,
                "races": races,
                "price": val["price"],
                "gui_name": f"{val['price']}-{val['displayName']}",
                "gui_checkbox_key": f"checkbox_{name}",
                "gui_combo_num_key": f"combo_num_{name}",
            }

        content = (
            f"class TFTData:\n"
            f"    _instance = None\n"
            f"    _is_first_init = True\n"
            f"\n"
            f"    def __new__(cls, *args, **kwargs):\n"
            f"        if cls._instance is None:\n"
            f"            cls._instance = object.__new__(cls)\n"
            f"        return cls._instance\n"
            f"\n"
            f"    def __init__(self):\n"
            f"        if not self._is_first_init:\n"
            f"            return\n"
            f"        self._is_first_init = False\n"
            f"        self.version_config = {self.raw_data['version_config']}\n"
            f'        self.all_chess_name_str = "{self.processed_data["all_chess_name"]}"\n'
            f'        self.all_race_name_str = "{self.processed_data["all_race_name"]}"\n'
            f'        self.all_job_name_str = "{self.processed_data["all_job_name"]}"\n'
            f"        self.race_chess = {self.processed_data['race_chess']}\n"
            f"        self.job_chess = {self.processed_data['job_chess']}\n"
            f"        self.price_chess = {self.processed_data['price_chess']}\n"
            f"        self.chess_name_info = {simplified}\n"
        )

        for old, new in _OCR_REPLACE.items():
            content = content.replace(old, new)

        with open(TFT_PY_CLASS_FILE, "w", encoding="utf-8") as f:
            f.write(content)
