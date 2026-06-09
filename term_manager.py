"""术语管理器 — 领域检测 + CSV 术语加载 + 领域感知 Prompt 生成

从 term_annotator.py 提取核心逻辑，供 Streamlit 应用使用。
"""

import csv
import os
import re
from pathlib import Path

# ═══════════════════════════════════════════════════════════════
#  领域关键词库（中英文混合，覆盖 医疗 / 法律 / 信息技术 / 金融）
# ═══════════════════════════════════════════════════════════════

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "医疗": [
        "患者", "诊断", "治疗", "手术", "药物", "症状", "临床", "病理",
        "医生", "护士", "医院", "病房", "处方", "剂量", "副作用", "康复",
        "影像", "检验", "体检", "急诊", "发热", "头痛", "咳嗽", "炎症",
        "麻醉", "切除", "移植", "疫苗", "感染", "肿瘤", "细胞", "血液",
        "patient", "diagnosis", "treatment", "surgery", "medication",
        "symptom", "clinical", "pathology", "doctor", "nurse", "hospital",
        "prescription", "dosage", "side effect", "rehabilitation",
        "imaging", "fever", "headache", "cough", "inflammation",
        "anesthesia", "resection", "transplant", "vaccine", "infection",
        "tumor", "cell", "blood",
    ],
    "法律": [
        "合同", "法律", "诉讼", "判决", "仲裁", "条款", "违约", "原告",
        "被告", "法院", "律师", "证据", "上诉", "赔偿", "知识产权", "专利",
        "商标", "法人", "债权", "债务", "抵押", "担保", "管辖", "起诉",
        "应诉", "调解", "裁定", "法条", "立法", "司法", "违法", "合法",
        "contract", "lawsuit", "judgment", "arbitration", "clause",
        "breach", "plaintiff", "defendant", "court", "attorney",
        "evidence", "appeal", "compensation", "intellectual property",
        "patent", "trademark", "legal person", "creditor", "debt",
        "mortgage", "guarantee", "jurisdiction", "prosecute",
        "mediation", "ruling", "legislation", "judicial",
    ],
    "信息技术": [
        "服务器", "数据库", "算法", "接口", "前端", "后端", "云计算",
        "人工智能", "机器学习", "部署", "调试", "网络", "软件", "硬件",
        "编程", "代码", "系统", "架构", "并发", "缓存", "容器", "微服务",
        "API", "DevOps", "Python", "Java", "数据", "存储", "安全",
        "server", "database", "algorithm", "API", "frontend", "backend",
        "cloud computing", "AI", "machine learning", "deployment",
        "debugging", "network", "software", "hardware", "programming",
        "code", "system", "architecture", "concurrency", "cache",
        "container", "microservice", "data", "storage", "security",
    ],
    "金融": [
        "股票", "基金", "利率", "汇率", "资产", "负债", "利润", "现金流",
        "分红", "贷款", "投资", "理财", "保险", "信用卡", "营收", "市盈率",
        "K线", "牛市", "熊市", "通胀", "通缩", "央行", "降息", "加息",
        "证券", "期货", "期权", "信托", "风投", "融资", "上市", "市值",
        "stock", "fund", "interest rate", "exchange rate", "asset",
        "liability", "profit", "cash flow", "dividend", "loan",
        "investment", "insurance", "credit card", "revenue",
        "bull market", "bear market", "inflation", "deflation",
        "central bank", "securities", "futures", "option",
        "venture capital", "financing", "IPO", "market cap",
    ],
}

# ═══════════════════════════════════════════════════════════════
#  领域语调描述
# ═══════════════════════════════════════════════════════════════

DOMAIN_TONES: dict[str, str] = {
    "医疗": "极其严密、专业、中立，符合医学文献与临床手册规范，确保医学专有名词与诊疗表述绝对精确",
    "法律": "严谨、客观、高度程式化，字斟句酌，确保条文的权威性，消除一切表意歧义",
    "信息技术": "简练、现代、注重逻辑，符合现代科技产品 UI、技术文档规范及开发者的阅读习惯",
    "金融": "专业、严谨，符合财经行业合规性与时效性，准确传达市场分析、财务报表或经济数据的核心逻辑",
}

# ═══════════════════════════════════════════════════════════════
#  CSV 术语加载
# ═══════════════════════════════════════════════════════════════

# 默认术语 CSV 路径
DEFAULT_CSV_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "..", "term_tool", "terminology.csv"
)


def load_terminology(csv_path: str | None = None) -> dict[str, list[tuple[str, str]]]:
    """
    从 CSV + SQLite 数据库加载术语表，按领域分组。

    优先读取 CSV 文件，再合并数据库中用户通过界面添加的术语（去重）。

    CSV 格式：中文术语,英文术语,领域

    Returns:
        {domain: [(chinese, english), ...]}
    """
    path = csv_path or DEFAULT_CSV_PATH
    terminology: dict[str, list[tuple[str, str]]] = {}

    # 1. 从 CSV 文件加载
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                chinese = row.get("中文术语", "").strip()
                english = row.get("英文术语", "").strip()
                domain = row.get("领域", "").strip()
                if not chinese or not english:
                    continue
                if domain not in terminology:
                    terminology[domain] = []
                terminology[domain].append((chinese, english))

    # 2. 从数据库 memory_assets 表加载（用户通过界面添加的术语）
    try:
        from database import get_all_assets
        assets = get_all_assets(status="active")
        for a in assets:
            domain = a.get("domain", "其他")
            source = a.get("source_text", "").strip()
            target = a.get("target_text", "").strip()
            if not source or not target:
                continue
            if domain not in terminology:
                terminology[domain] = []
            entry = (source, target)
            # 去重：避免与 CSV 中的条目重复
            if entry not in terminology[domain]:
                terminology[domain].append(entry)
    except Exception:
        pass  # 数据库未初始化或不可用时静默跳过

    return terminology


def get_terms_for_domain(
    domain: str,
    terminology: dict[str, list[tuple[str, str]]] | None = None,
) -> list[tuple[str, str]]:
    """获取指定领域的术语列表。"""
    if terminology is None:
        terminology = load_terminology()
    return terminology.get(domain, [])


# ═══════════════════════════════════════════════════════════════
#  领域检测
# ═══════════════════════════════════════════════════════════════

def detect_domains(
    text: str,
    keywords: dict[str, list[str]] | None = None,
) -> list[tuple[str, int]]:
    """
    关键词匹配检测文本所属领域。

    Returns:
        [(domain, score), ...] 按得分降序排列
    """
    if keywords is None:
        keywords = DOMAIN_KEYWORDS

    scores: dict[str, int] = {}
    for domain, kw_list in keywords.items():
        score = sum(1 for kw in kw_list if kw in text)
        if score > 0:
            scores[domain] = score

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def detect_best_domain(text: str) -> str:
    """返回最佳匹配领域，无匹配返回 '其他'。"""
    detected = detect_domains(text)
    if not detected:
        return "其他"
    return detected[0][0]


# ═══════════════════════════════════════════════════════════════
#  语言检测
# ═══════════════════════════════════════════════════════════════

def detect_input_language(text: str) -> str:
    """粗略检测输入文本的主要语言（中文/英文）。"""
    chinese_count = sum(1 for c in text if '一' <= c <= '鿿')
    english_count = sum(1 for c in text if c.isascii() and c.isalpha())
    total = chinese_count + english_count
    if total == 0:
        return "中文"
    if chinese_count / total > 0.5:
        return "中文"
    return "英文"


# ═══════════════════════════════════════════════════════════════
#  英文复数变体
# ═══════════════════════════════════════════════════════════════

def en_variants(english: str) -> list[str]:
    """生成英文术语的可能文本形式（原形 + 常见复数/变体）。"""
    variants = {english}
    words = english.split()

    if len(words) == 1:
        w = english
        low = w.lower()
        variants.add(w + "s")
        if low.endswith(("s", "x", "ch", "sh", "z")):
            variants.add(w + "es")
        if low.endswith("y") and len(w) > 2 and w[-2].lower() not in "aeiou":
            variants.add(w[:-1] + "ies")
        if low.endswith("sis"):
            variants.add(w[:-3] + "ses")
        if low.endswith("us"):
            variants.add(w[:-2] + "i")
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
#  术语匹配 + 标注
# ═══════════════════════════════════════════════════════════════

def match_terms(
    text: str,
    terms: list[tuple[str, str]],
) -> tuple[list[tuple[str, str]], list[tuple[int, int, str, str]]]:
    """
    在文本中匹配术语（中文 + 英文含变体）。

    Returns:
        (matched_terms, match_positions)
        - matched_terms: [(chinese, english), ...] 去重后的匹配术语
        - match_positions: [(start, end, chinese, english), ...] 匹配位置
    """
    if not terms:
        return [], []

    all_matches: list[tuple[int, int, str, str]] = []
    used: set[int] = set()

    # 按术语长度降序排列，优先匹配长术语
    sorted_terms = sorted(
        terms,
        key=lambda x: max(len(x[0]) * 3, max((len(v) for v in en_variants(x[1])), default=0)),
        reverse=True,
    )

    for chinese, english in sorted_terms:
        # 中文匹配
        for m in re.finditer(re.escape(chinese), text):
            start, end = m.start(), m.end()
            positions = set(range(start, end))
            if not (positions & used):
                all_matches.append((start, end, chinese, english))
                used.update(positions)

        # 英文匹配（含复数变体）
        if english and not all('一' <= c <= '鿿' for c in english):
            for variant in en_variants(english):
                pattern = r'\b' + re.escape(variant) + r'\b'
                for m in re.finditer(pattern, text, re.IGNORECASE):
                    start, end = m.start(), m.end()
                    positions = set(range(start, end))
                    if not (positions & used):
                        all_matches.append((start, end, chinese, english))
                        used.update(positions)

    all_matches.sort(key=lambda x: x[0])

    # 去重
    seen: set[str] = set()
    unique_terms: list[tuple[str, str]] = []
    for _, _, ch, en in all_matches:
        if ch not in seen:
            seen.add(ch)
            unique_terms.append((ch, en))

    return unique_terms, all_matches


def annotate_text_html(
    text: str,
    terms: list[tuple[str, str]],
) -> str:
    """
    对文本中的术语进行 HTML 高亮标注。
    匹配的术语用 <mark> 标签包裹，适合 Streamlit 渲染。
    """
    _, matches = match_terms(text, terms)
    if not matches:
        return text

    parts: list[str] = []
    cursor = 0
    for start, end, chinese, english in matches:
        if start >= cursor:
            parts.append(text[cursor:start])
            parts.append(
                f'<mark style="background:#a8e6cf;padding:1px 4px;border-radius:3px;" '
                f'title="{chinese} → {english}">{text[start:end]}</mark>'
            )
            cursor = end

    parts.append(text[cursor:])
    return "".join(parts)


# ═══════════════════════════════════════════════════════════════
#  Domain-aware System Prompt 构建
# ═══════════════════════════════════════════════════════════════

def build_domain_prompt(
    text: str,
    direction: str = "zh2en",
    domain: str | None = None,
    matched_terms: list[tuple[str, str]] | None = None,
    tm_hits: list[dict] | None = None,
) -> str:
    """
    构建领域感知的 System Prompt。

    Args:
        text: 待翻译原文
        direction: 翻译方向 zh2en / en2zh
        domain: 领域名称（None 则自动检测）
        matched_terms: 预匹配的术语列表（None 则自动匹配）
        tm_hits: 翻译记忆检索命中

    Returns:
        结构化的 System Prompt 字符串
    """
    # 自动检测领域
    if domain is None:
        domain = detect_best_domain(text)

    # 自动检测源语言
    src_lang = detect_input_language(text)
    tgt_lang = "英文" if src_lang == "中文" else "中文"

    # 获取语调
    tone = DOMAIN_TONES.get(domain, "专业、准确、自然流畅")

    # 构建术语表
    if matched_terms is None:
        terminology = load_terminology()
        domain_terms = get_terms_for_domain(domain, terminology)
        if domain_terms:
            matched_terms, _ = match_terms(text, domain_terms)

    sections: list[str] = []

    # ── Role ──
    sections.append(f"# Role\n你是一位资深的{domain}领域翻译专家。")

    # ── Context ──
    sections.append(
        f"# Context\n"
        f"- 源语言：{src_lang}\n"
        f"- 目标语言：{tgt_lang}\n"
        f"- 语调：{tone}"
    )

    # ── Terminology & Rules ──
    if matched_terms:
        term_lines = "\n".join(
            f"  • {ch} → {en}" for ch, en in matched_terms
        )
        sections.append(
            f"# Terminology & Rules（必须严格遵循）\n{term_lines}"
        )
    else:
        sections.append(
            "# Terminology & Rules\n（无匹配术语，请根据上下文选择最准确的专业译法）"
        )

    # ── Translation Memory ──
    if tm_hits:
        tm_lines = "\n".join(
            f"  • {h['source_text']} → {h['target_text']}" for h in tm_hits
        )
        sections.append(f"# Translation Memory（参考）\n{tm_lines}")

    # ── 指令 ──
    sections.append(
        "# Instruction\n"
        "请基于以上术语表和语调要求翻译以下文本，只返回译文，不要解释。"
    )

    return "\n\n".join(sections)


def get_domain_tone(domain: str) -> str:
    """获取指定领域的语调描述。"""
    return DOMAIN_TONES.get(domain, "专业、准确、自然流畅")
