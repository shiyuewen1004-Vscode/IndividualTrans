"""术语自动标注引擎 — 领域检测 + 术语匹配 + 高亮标注 + CSV 维护"""

import csv
import re
import os
from pathlib import Path

_SCRIPT_DIR = Path(__file__).parent
_CSV_PATH = os.path.join(_SCRIPT_DIR, "terminology.csv")

# ═══════════════════════════════════════════════════════════════
# 领域关键词库
# ═══════════════════════════════════════════════════════════════
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "医疗": [
        "患者", "诊断", "治疗", "手术", "药物", "症状", "临床", "病理",
        "医生", "护士", "医院", "病房", "处方", "剂量", "副作用", "康复",
        "影像", "检验", "体检", "急诊", "发热", "头痛", "咳嗽", "炎症",
        "麻醉", "切除", "移植", "疫苗", "感染", "肿瘤", "细胞", "血液",
    ],
    "法律": [
        "合同", "法律", "诉讼", "判决", "仲裁", "条款", "违约", "原告",
        "被告", "法院", "律师", "证据", "上诉", "赔偿", "知识产权", "专利",
        "商标", "法人", "债权", "债务", "抵押", "担保", "管辖", "起诉",
        "应诉", "调解", "裁定", "法条", "立法", "司法", "违法", "合法",
    ],
    "信息技术": [
        "服务器", "数据库", "算法", "接口", "前端", "后端", "云计算",
        "人工智能", "机器学习", "部署", "调试", "网络", "软件", "硬件",
        "编程", "代码", "系统", "架构", "并发", "缓存", "容器", "微服务",
        "API", "SDK", "DevOps", "Python", "Java", "数据", "存储", "安全",
    ],
    "金融": [
        "股票", "基金", "利率", "汇率", "资产", "负债", "利润", "现金流",
        "分红", "贷款", "投资", "理财", "保险", "信用卡", "营收", "市盈率",
        "K线", "牛市", "熊市", "通胀", "通缩", "央行", "降息", "加息",
        "证券", "期货", "期权", "信托", "风投", "融资", "上市", "市值",
    ],
}


# ═══════════════════════════════════════════════════════════════
# CSV 读写
# ═══════════════════════════════════════════════════════════════

def get_csv_path() -> str:
    return _CSV_PATH


def load_terminology(csv_path: str = "") -> dict[str, list[tuple[str, str]]]:
    """加载术语 CSV，返回 {领域: [(中文, 英文), ...]}"""
    path = csv_path or _CSV_PATH
    terminology: dict[str, list[tuple[str, str]]] = {}
    if not os.path.exists(path):
        return terminology
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            chinese = row.get("中文术语", "").strip()
            english = row.get("英文术语", "").strip()
            domain = row.get("领域", "").strip()
            if chinese and english and domain:
                terminology.setdefault(domain, []).append((chinese, english))
    return terminology


def get_all_domains(csv_path: str = "") -> list[str]:
    """返回 CSV 中所有领域"""
    return list(load_terminology(csv_path).keys())


def get_term_count(csv_path: str = "") -> int:
    """返回术语总数"""
    return sum(len(v) for v in load_terminology(csv_path).values())


def append_to_csv(chinese: str, english: str, domain: str, csv_path: str = "") -> bool:
    """
    将新术语追加写入 CSV（去重）。
    返回 True=新增，False=已存在。
    """
    path = csv_path or _CSV_PATH
    fieldnames = ["中文术语", "英文术语", "领域"]
    rows: list[dict] = []
    exists = False

    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
                if (row.get("中文术语", "").strip() == chinese
                        and row.get("英文术语", "").strip() == english
                        and row.get("领域", "").strip() == domain):
                    exists = True

    if exists:
        return False

    rows.append({"中文术语": chinese, "英文术语": english, "领域": domain})
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


# ═══════════════════════════════════════════════════════════════
# 领域检测
# ═══════════════════════════════════════════════════════════════

def detect_domains(text: str) -> list[tuple[str, int]]:
    """基于关键词检测领域，返回 [(领域, 命中数), ...] 降序"""
    scores: dict[str, int] = {}
    for domain, kw_list in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in kw_list if kw in text)
        if score > 0:
            scores[domain] = score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def detect_domains_by_terms(
    text: str,
    terminology: dict[str, list[tuple[str, str]]],
) -> list[tuple[str, int]]:
    """基于英文术语在文本中的出现来辅助检测领域"""
    scores: dict[str, int] = {}
    for domain, term_list in terminology.items():
        score = 0
        for _ch, en in term_list:
            if en:
                for v in en_variants(en):
                    if re.search(r'\b' + re.escape(v) + r'\b', text, re.IGNORECASE):
                        score += 1
                        break
        if score > 0:
            scores[domain] = score
    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


# ═══════════════════════════════════════════════════════════════
# 英文复数变体
# ═══════════════════════════════════════════════════════════════

def en_variants(english: str) -> list[str]:
    """生成英文术语的可能文本形式（原形 + 常见复数/变体）。"""
    variants: set[str] = {english}
    words = english.split()

    if len(words) == 1:
        w = english
        low = w.lower()
        # 基础复数
        variants.add(w + "s")
        # -s/-x/-ch/-sh/-z → -es
        if low.endswith(("s", "x", "ch", "sh", "z")):
            variants.add(w + "es")
        # 辅音+y → -ies
        if low.endswith("y") and len(w) > 2 and w[-2].lower() not in "aeiou":
            variants.add(w[:-1] + "ies")
        # -sis → -ses
        if low.endswith("sis"):
            variants.add(w[:-3] + "ses")
        # -us → -i
        if low.endswith("us"):
            variants.add(w[:-2] + "i")
        # 大小写变体
        variants.add(w.lower())
        variants.add(w.capitalize())
    else:
        *rest, last = words
        for lv in en_variants(last):
            joined = " ".join(rest + [lv])
            variants.add(joined)
            variants.add(joined.lower())

    return list(variants)


# ═══════════════════════════════════════════════════════════════
# 标注引擎（Web 版 — 返回结构化数据）
# ═══════════════════════════════════════════════════════════════

def annotate_text(
    text: str,
    terms: list[tuple[str, str]],
    user_terms: list[tuple[str, str]] | None = None,
) -> dict:
    """
    在文本中匹配术语并返回结构化标注结果。

    返回:
      {
        "annotated_segments": [
          {"text": "...", "is_match": False},
          {"text": "...", "is_match": True, "chinese": "...", "english": "...", "is_user": False},
          ...
        ],
        "matched_csv": [(ch, en), ...],    # 来自 CSV 的匹配
        "matched_user": [(ch, en), ...],   # 用户补充的匹配
      }

    匹配规则：
      - 中文术语：在文本中直接匹配
      - 英文术语（含复数变体）：按词边界 \b 匹配，忽略大小写
      - 长术语优先，避免短术语截断长术语
      - CSV 术语标记 is_user=False，用户补充标记 is_user=True
    """
    user_terms = user_terms or []

    if not terms and not user_terms:
        return {
            "annotated_segments": [{"text": text, "is_match": False}],
            "matched_csv": [],
            "matched_user": [],
        }

    all_matches: list[tuple[int, int, str, str, bool]] = []
    used: set[int] = set()
    matched_csv: list[tuple[str, str]] = []
    matched_user: list[tuple[str, str]] = []

    # 合并术语按长度降序（长术语优先）
    all_items: list[tuple[str, str, bool]] = []
    for ch, en in terms:
        all_items.append((ch, en, False))
    for ch, en in user_terms:
        all_items.append((ch, en, True))

    def sort_key(item: tuple[str, str, bool]) -> int:
        ch, en, _ = item
        cn_len = len(ch) * 3
        ev = en_variants(en) if en else []
        en_max = max((len(v) for v in ev), default=0)
        return max(cn_len, en_max)

    all_items.sort(key=sort_key, reverse=True)

    for chinese, english, is_user in all_items:
        # ── 中文匹配 ──
        for m in re.finditer(re.escape(chinese), text):
            start, end = m.start(), m.end()
            positions = set(range(start, end))
            if not (positions & used):
                all_matches.append((start, end, chinese, english, is_user))
                (matched_user if is_user else matched_csv).append((chinese, english))
                used.update(positions)

        # ── 英文匹配（含复数变体）──
        if english and not all('一' <= c <= '鿿' for c in english):
            for variant in en_variants(english):
                pattern = r'\b' + re.escape(variant) + r'\b'
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    start, end = m.start(), m.end()
                    positions = set(range(start, end))
                    if not (positions & used):
                        all_matches.append((start, end, chinese, english, is_user))
                        (matched_user if is_user else matched_csv).append((chinese, english))
                        used.update(positions)

    # 按位置排序，构建分段
    all_matches.sort(key=lambda x: x[0])

    segments: list[dict] = []
    cursor = 0
    for start, end, chinese, english, is_user in all_matches:
        if cursor < start:
            segments.append({"text": text[cursor:start], "is_match": False})
        segments.append({
            "text": text[start:end],
            "is_match": True,
            "chinese": chinese,
            "english": english,
            "is_user": is_user,
        })
        cursor = end

    if cursor < len(text):
        segments.append({"text": text[cursor:], "is_match": False})

    return {
        "annotated_segments": segments,
        "matched_csv": matched_csv,
        "matched_user": matched_user,
    }


def get_unique_terms(
    matched_csv: list[tuple[str, str]],
    matched_user: list[tuple[str, str]],
) -> list[tuple[str, str, bool]]:
    """去重合并匹配术语，返回 [(ch, en, is_user), ...]"""
    seen: set[str] = set()
    unique: list[tuple[str, str, bool]] = []
    for ch, en in matched_csv:
        if ch not in seen:
            seen.add(ch)
            unique.append((ch, en, False))
    for ch, en in matched_user:
        if ch not in seen:
            seen.add(ch)
            unique.append((ch, en, True))
    return unique
