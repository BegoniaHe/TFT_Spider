"""
Markdown 导出器：将 TFT 处理后数据渲染为供 AI 阅读的纯文字 Markdown 文件。

支持类型：
  all      — 全量单文件（默认）
  chess    — 仅弈子
  race     — 仅种族羁绊
  job      — 仅职业羁绊
  synergy  — 种族 + 职业（合并）
  equip    — 仅装备
  hex      — 仅海克斯增益

导出模式：
  合并导出（默认） — 同一 export_type 内容写入单个 .md
  分类导出（split）— 每个子类别写入独立 .md（如每条职业一个文件）
  单项导出         — 通过 name_filter 仅导出特定名称的棋子 / 装备 / 海克斯
"""

from __future__ import annotations

import os
import re
import textwrap

# ─── 技能描述清理 ─────────────────────────────────────────────────────────────

# 需要连同内容一起删除的标签
_STRIP_WITH_CONTENT: list[tuple[str, str]] = [
    ("<rules>", "</rules>"),
    ("<TFTTrackerLabel>", "</TFTTrackerLabel>"),
]

# 所有 %i:xxx% 占位符到可读标签的映射
_SCALE_TOKEN_MAP: dict[str, str] = {
    "%i:scaleAP%": "[法强]",
    "%i:scaleAD%": "[攻击力]",
    "%i:TFTBaseAD%": "[基础攻击]",
    "%i:scaleMR%": "[魔抗]",
    "%i:scaleArmor%": "[护甲]",
    "%i:scaleHP%": "[生命]",
    "%i:scaleLevel%": "[等级]",
    "%i:scaleCritChance%": "[暴击率]",
    "%i:scaleCritDamage%": "[暴击伤害]",
}

_BR_RE = re.compile(r"<br\s*/?>", re.IGNORECASE)
_TAG_RE = re.compile(r"</?[a-zA-Z_][^>]*?>")
_AT_PLACEHOLDER_RE = re.compile(r"@[^@]+@")
_MULTI_SPACE_RE = re.compile(r"[ \t]{2,}")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def _clean_skill(text: str) -> str:
    """将包含游戏内 HTML 标签的技能描述清理为纯文本。"""
    if not text:
        return ""

    # 先删除 <rules>...</rules> 等（注释性内容，AI 无需）
    for open_tag, close_tag in _STRIP_WITH_CONTENT:
        pattern = re.compile(re.escape(open_tag) + r".*?" + re.escape(close_tag), re.DOTALL)
        text = pattern.sub("", text)

    # <br> → 换行
    text = _BR_RE.sub("\n", text)

    # @占位符@ → 删除
    text = _AT_PLACEHOLDER_RE.sub("", text)

    # %i:xxx% → 可读标签
    for token, label in _SCALE_TOKEN_MAP.items():
        text = text.replace(token, label)
    # 未知的 %i:xxx% 统一删除
    text = re.sub(r"%i:[^%]+%", "", text)

    # 移除所有剩余 HTML 标签（保留内容）
    text = _TAG_RE.sub("", text)

    # 清理空白
    lines = [_MULTI_SPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    lines = [line for line in lines if line]
    text = "\n".join(lines)
    text = _MULTI_NL_RE.sub("\n\n", text).strip()
    return text


# ─── 辅助函数 ─────────────────────────────────────────────────────────────────


def _split_stars(raw: str) -> tuple[str, str, str]:
    """将 "55/83/124" 格式拆成 (1星值, 2星值, 3星值)。"""
    parts = raw.split("/")
    if len(parts) == 3:
        return parts[0].strip(), parts[1].strip(), parts[2].strip()
    val = parts[0].strip() if parts else "0"
    return val, val, val


def _wrap(text: str, width: int = 80, indent: str = "  ") -> str:
    """对长段文字进行折行，并加缩进（保持可读性）。"""
    return textwrap.fill(text, width=width, subsequent_indent=indent)


# ─── 导出器主类 ───────────────────────────────────────────────────────────────

EXPORT_TYPES = ("all", "chess", "race", "job", "synergy", "equip", "hex")


class TFTMarkdownExporter:
    """
    TFT 数据 Markdown 导出器。

    使用方式::

        exporter = TFTMarkdownExporter(processed_data, raw_data)
        paths = exporter.save(export_type="chess", out_dir="output/")
    """

    def __init__(self, processed_data: dict, raw_data: dict) -> None:
        self.pd = processed_data  # tft_processed_data.json 内容
        self.rd = raw_data  # tft_raw_data.json 内容

    # ─── 元数据行 ─────────────────────────────────────────────────────────────

    def _meta_header(self) -> str:
        vc = self.rd.get("version_config", {})
        lines = [
            "# TFT 数据文档（AI 阅读版）",
            "",
            f"- 赛季：{vc.get('赛季名称', '未知')}",
            f"- 版本：{vc.get('版本信息', '未知')}",
            f"- 爬取日期：{vc.get('爬取日期', '未知')}",
            "",
            "> 本文档由程序自动生成，供 AI 解析使用。"
            " 弈子属性按 1星/2星/3星列出，固定属性仅展示一次。",
            "",
        ]
        return "\n".join(lines)

    # ─── 弈子 ─────────────────────────────────────────────────────────────────

    def _chess_entry(self, name: str, info: dict) -> str:
        """渲染单个弈子的 Markdown 块。"""
        price = info.get("price", "?")
        races = info.get("races", "") or ""
        jobs = info.get("jobs", "") or ""
        race_str = races if races else "无"
        job_str = jobs if jobs else "无"

        # 基础属性
        armor = info.get("armor", "?")
        mr = info.get("spellBlock", "?")
        spd = float(info.get("attackSpeed", 0))
        rng = info.get("attackRange", "?")
        crit = info.get("crit", "?")
        mana_start = info.get("startMagic", "0")
        mana_max = info.get("magic", "0")

        # 1/2/3 星攻击 & 生命
        atk1, atk2, atk3 = _split_stars(info.get("attackData", "0/0/0"))
        hp1, hp2, hp3 = _split_stars(info.get("lifeData", "0/0/0"))

        # 技能
        skill_name = info.get("skillName", "")
        skill_type = info.get("skillType", "主动")
        skill_raw = info.get("skillIntroduce", "") or info.get("skillDetail", "") or ""
        skill_text = _clean_skill(skill_raw)

        lines: list[str] = []
        lines.append(f"### {name}（{price}费 | 种族：{race_str} | 职业：{job_str}）")
        lines.append(
            f"固定属性：护甲 {armor} · 魔抗 {mr} · 攻速 {spd:.2f}"
            f" · 攻距 {rng}格 · 暴击 {crit}%"
            f" · 法力 {mana_start}/{mana_max}"
        )
        lines.append(
            f"星级属性："
            f"1星(HP {hp1} 攻击 {atk1})"
            f" | 2星(HP {hp2} 攻击 {atk2})"
            f" | 3星(HP {hp3} 攻击 {atk3})"
        )

        if skill_name:
            lines.append(f"技能（{skill_type}）：{skill_name}")
        if skill_text:
            # 多行技能描述缩进展示
            for seg in skill_text.splitlines():
                if seg:
                    lines.append(f"  {seg}")

        lines.append("")  # 空行分隔
        return "\n".join(lines)

    def render_chess(self, *, name_filter: str | None = None) -> str:
        """
        渲染弈子章节。
        name_filter: 非空时仅渲染该名称的弈子（单项导出）。
        """
        chess_info: dict = self.pd.get("chess_name_info", {})
        price_chess: dict = self.pd.get("price_chess", {})

        lines: list[str] = []
        lines.append("## 弈子（按费用分组）")
        lines.append("")

        for price in ("1", "2", "3", "4", "5"):
            names = price_chess.get(price, [])
            if not names:
                continue

            entries: list[str] = []
            for name in names:
                if name_filter and name != name_filter:
                    continue
                info = chess_info.get(name)
                if info:
                    entries.append(self._chess_entry(name, info))

            if entries:
                lines.append(f"### {price} 费弈子")
                lines.append("")
                lines.extend(entries)

        return "\n".join(lines)

    # ─── 种族羁绊 ─────────────────────────────────────────────────────────────

    def _race_entry(self, race: dict) -> str:
        name = race.get("name", "未知")
        introduce = race.get("introduce", "") or race.get("description", "") or ""
        introduce_clean = _clean_skill(introduce)

        chess_names = self.pd.get("race_chess", {}).get(name, [])

        lines: list[str] = []
        lines.append(f"### {name}")
        if introduce_clean:
            lines.append(f"效果：{introduce_clean}")
        lines.append(
            f"弈子（{len(chess_names)}个）：{' / '.join(chess_names) if chess_names else '暂无'}"
        )
        lines.append("")
        return "\n".join(lines)

    def render_race(self) -> str:
        """渲染种族羁绊章节。"""
        races: list[dict] = self.rd.get("race", [])
        lines: list[str] = ["## 种族羁绊", ""]
        for race in races:
            lines.append(self._race_entry(race))
        return "\n".join(lines)

    # ─── 职业羁绊 ─────────────────────────────────────────────────────────────

    def _job_entry(self, job: dict) -> str:
        name = job.get("name", "未知")
        introduce = job.get("introduce", "") or job.get("description", "") or ""
        introduce_clean = _clean_skill(introduce)

        chess_names = self.pd.get("job_chess", {}).get(name, [])

        lines: list[str] = []
        lines.append(f"### {name}")
        if introduce_clean:
            lines.append(f"效果：{introduce_clean}")
        lines.append(
            f"弈子（{len(chess_names)}个）：{' / '.join(chess_names) if chess_names else '暂无'}"
        )
        lines.append("")
        return "\n".join(lines)

    def render_job(self) -> str:
        """渲染职业羁绊章节。"""
        jobs: list[dict] = self.rd.get("job", [])
        lines: list[str] = ["## 职业羁绊", ""]
        for job in jobs:
            lines.append(self._job_entry(job))
        return "\n".join(lines)

    # ─── 种族 + 职业合并 ──────────────────────────────────────────────────────

    def render_synergy(self) -> str:
        """渲染羁绊章节（种族 + 职业）。"""
        return self.render_race() + "\n\n" + self.render_job()

    # ─── 装备 ─────────────────────────────────────────────────────────────────

    def _equip_entry(self, equip: dict) -> str:
        name = equip.get("name") or equip.get("equipName") or equip.get("displayName") or "未知装备"
        brief = equip.get("brief", "") or equip.get("shortDesc", "") or ""
        desc = (
            equip.get("description", "")
            or equip.get("introduce", "")
            or equip.get("skillIntroduce", "")
            or ""
        )
        desc_clean = _clean_skill(desc or brief)

        lines: list[str] = []
        lines.append(f"### {name}")
        if desc_clean:
            lines.append(f"效果：{desc_clean}")
        lines.append("")
        return "\n".join(lines)

    def render_equip(self, *, name_filter: str | None = None) -> str:
        """渲染装备章节。"""
        equips: list[dict] = self.rd.get("equip", [])
        lines: list[str] = ["## 装备", ""]
        for eq in equips:
            name = eq.get("name") or eq.get("equipName") or eq.get("displayName") or ""
            if name_filter and name != name_filter:
                continue
            lines.append(self._equip_entry(eq))
        return "\n".join(lines)

    # ─── 海克斯增益 ───────────────────────────────────────────────────────────

    def _hex_entry(self, item: dict | list) -> str:
        """海克斯数据结构可能是 dict 或 dict 的 list（按稀有度分组），统一处理。"""
        # 如果是列表（同一海克斯多个等级），逐条展开
        if isinstance(item, list):
            return "\n".join(self._hex_entry(sub) for sub in item if isinstance(sub, dict))

        name = item.get("name") or item.get("buffName") or item.get("displayName") or "未知海克斯"
        desc = item.get("description") or item.get("introduce") or item.get("buffIntroduce") or ""
        rarity = item.get("rarity", "") or item.get("buffLevel", "") or ""
        desc_clean = _clean_skill(desc)

        lines: list[str] = []
        header = f"### {name}"
        if rarity:
            header += f"（{rarity}）"
        lines.append(header)
        if desc_clean:
            lines.append(f"效果：{desc_clean}")
        lines.append("")
        return "\n".join(lines)

    def render_hex(self, *, name_filter: str | None = None) -> str:
        """渲染海克斯增益章节。"""
        hex_data = self.rd.get("hex", [])
        lines: list[str] = ["## 海克斯增益", ""]
        for item in hex_data:
            # 尝试提取名称来做过滤
            if name_filter:
                item_name = ""
                if isinstance(item, dict):
                    item_name = (
                        item.get("name") or item.get("buffName") or item.get("displayName") or ""
                    )
                if item_name and item_name != name_filter:
                    continue
            lines.append(self._hex_entry(item))
        return "\n".join(lines)

    # ─── 概览索引 ─────────────────────────────────────────────────────────────

    def render_index(self) -> str:
        """渲染顶部概览：所有弈子/种族/职业名称列表，方便 AI 快速定位。"""
        lines: list[str] = ["## 数据索引", ""]

        all_chess = self.pd.get("all_chess_name", "")
        all_race = self.pd.get("all_race_name", "")
        all_job = self.pd.get("all_job_name", "")

        if all_chess:
            chess_list = [n for n in all_chess.split("-") if n]
            lines.append(f"弈子（{len(chess_list)}个）：{' · '.join(chess_list)}")
            lines.append("")
        if all_race:
            race_list = [n for n in all_race.split("-") if n]
            lines.append(f"种族羁绊（{len(race_list)}个）：{' · '.join(race_list)}")
            lines.append("")
        if all_job:
            job_list = [n for n in all_job.split("-") if n]
            lines.append(f"职业羁绊（{len(job_list)}个）：{' · '.join(job_list)}")
            lines.append("")

        # 按费用分类索引
        price_chess: dict = self.pd.get("price_chess", {})
        for price in ("1", "2", "3", "4", "5"):
            names = price_chess.get(price, [])
            if names:
                lines.append(f"{price}费弈子：{' · '.join(names)}")
        lines.append("")

        return "\n".join(lines)

    # ─── 全量导出 ─────────────────────────────────────────────────────────────

    def render_all(self) -> str:
        """渲染全量文档（单文件）。"""
        sections = [
            self._meta_header(),
            self.render_index(),
            self.render_chess(),
            self.render_synergy(),
            self.render_equip(),
            self.render_hex(),
        ]
        return "\n\n---\n\n".join(s for s in sections if s.strip())

    # ─── 保存 API ─────────────────────────────────────────────────────────────

    def save(
        self,
        export_type: str = "all",
        *,
        split: bool = False,
        out_dir: str,
        name_filter: str | None = None,
    ) -> list[str]:
        """
        导出 Markdown 文件到 out_dir，返回写入的文件路径列表。

        Parameters
        ----------
        export_type : str
            导出类型：all / chess / race / job / synergy / equip / hex
        split : bool
            True → 每个子类别（种族/职业/装备/海克斯）写入独立文件；
            False → 同类型内容写入单个文件
        out_dir : str
            输出目录（不存在则自动创建）
        name_filter : str | None
            非空时仅导出该名称的单个条目（仅对 chess / equip / hex 有效）
        """
        if export_type not in EXPORT_TYPES:
            raise ValueError(f"export_type 须为以下之一：{EXPORT_TYPES}，实际传入 {export_type!r}")

        os.makedirs(out_dir, exist_ok=True)
        written: list[str] = []

        def _write(filename: str, content: str) -> str:
            path = os.path.join(out_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return path

        # ── all ──
        if export_type == "all":
            path = _write("tft_all.md", self._meta_header() + "\n\n" + self.render_all())
            written.append(path)
            return written

        # ── chess ──
        if export_type == "chess":
            if split:
                # 按费用分文件
                price_chess: dict = self.pd.get("price_chess", {})
                chess_info: dict = self.pd.get("chess_name_info", {})
                for price in ("1", "2", "3", "4", "5"):
                    names = price_chess.get(price, [])
                    entries = [
                        self._chess_entry(n, chess_info[n])
                        for n in names
                        if n in chess_info and (not name_filter or n == name_filter)
                    ]
                    if entries:
                        content = (
                            self._meta_header() + f"\n\n## {price}费弈子\n\n" + "\n".join(entries)
                        )
                        path = _write(f"chess_{price}cost.md", content)
                        written.append(path)
            else:
                content = self._meta_header() + "\n\n" + self.render_chess(name_filter=name_filter)
                fname = f"chess_{name_filter}.md" if name_filter else "chess_all.md"
                written.append(_write(fname, content))
            return written

        # ── race ──
        if export_type == "race":
            if split:
                for race in self.rd.get("race", []):
                    n = race.get("name", "unknown")
                    content = (
                        self._meta_header() + f"\n\n## 种族羁绊：{n}\n\n" + self._race_entry(race)
                    )
                    path = _write(f"race_{n}.md", content)
                    written.append(path)
            else:
                content = self._meta_header() + "\n\n" + self.render_race()
                written.append(_write("race_all.md", content))
            return written

        # ── job ──
        if export_type == "job":
            if split:
                for job in self.rd.get("job", []):
                    n = job.get("name", "unknown")
                    content = (
                        self._meta_header() + f"\n\n## 职业羁绊：{n}\n\n" + self._job_entry(job)
                    )
                    path = _write(f"job_{n}.md", content)
                    written.append(path)
            else:
                content = self._meta_header() + "\n\n" + self.render_job()
                written.append(_write("job_all.md", content))
            return written

        # ── synergy ──
        if export_type == "synergy":
            if split:
                written += self.save("race", split=True, out_dir=out_dir)
                written += self.save("job", split=True, out_dir=out_dir)
            else:
                content = self._meta_header() + "\n\n" + self.render_synergy()
                written.append(_write("synergy_all.md", content))
            return written

        # ── equip ──
        if export_type == "equip":
            if split:
                for eq in self.rd.get("equip", []):
                    n = eq.get("name") or eq.get("equipName") or eq.get("displayName") or "unknown"
                    if name_filter and n != name_filter:
                        continue
                    content = self._meta_header() + f"\n\n## 装备：{n}\n\n" + self._equip_entry(eq)
                    path = _write(f"equip_{n}.md", content)
                    written.append(path)
            else:
                content = self._meta_header() + "\n\n" + self.render_equip(name_filter=name_filter)
                fname = f"equip_{name_filter}.md" if name_filter else "equip_all.md"
                written.append(_write(fname, content))
            return written

        # ── hex ──
        if export_type == "hex":
            hex_data = self.rd.get("hex", [])
            if split:
                for item in hex_data:
                    if isinstance(item, dict):
                        n = (
                            item.get("name")
                            or item.get("buffName")
                            or item.get("displayName")
                            or "unknown"
                        )
                        if name_filter and n != name_filter:
                            continue
                        content = (
                            self._meta_header()
                            + f"\n\n## 海克斯增益：{n}\n\n"
                            + self._hex_entry(item)
                        )
                        path = _write(f"hex_{n}.md", content)
                        written.append(path)
            else:
                content = self._meta_header() + "\n\n" + self.render_hex(name_filter=name_filter)
                fname = f"hex_{name_filter}.md" if name_filter else "hex_all.md"
                written.append(_write(fname, content))
            return written

        return written  # 正常不会走到这里
