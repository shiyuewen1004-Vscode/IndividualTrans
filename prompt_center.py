"""Prompt Center — 领域/风格模板配置 + 用户覆写管理"""

from database import get_prompt_override

# ── 翻译风格标签 ────────────────────────────────────

STYLE_LABELS = {
    "default": "🌐 通用",
    "financial": "💰 经济金融",
    "political": "🏛 政治外交",
    "legal": "⚖️ 法律",
    "medical": "🏥 医学",
    "chemical": "🧪 化学化工",
    "education": "🎓 教育",
    "cultural": "🏮 传统文化",
}

# ── Prompt 模板标签 ─────────────────────────────────

PROMPT_LABELS = {
    "default": "📋 默认通用",
    "financial": "💰 经济金融",
    "political": "🏛 政治外交",
    "legal": "⚖️ 法律",
    "medical": "🏥 医学",
    "chemical": "🧪 化学化工",
    "education": "🎓 教育",
    "cultural": "🏮 传统文化",
    "custom": "✏️ 自定义",
}

# ── 风格配置（受众 + 默认原则）──────────────────────

STYLE_CONFIGS = {
    "default": {
        "audience": "Professional Readers",
        "style_name": "通用",
        "principles": [
            "准确传达原文意思，不增不减",
            "保持专业术语的一致性",
            "译文流畅自然，符合目标语言习惯",
            "保留原文的格式和段落结构",
        ],
    },
    "financial": {
        "audience": "金融从业者、投资者、监管机构",
        "style_name": "经济金融",
        "principles": [
            "专业、严谨，符合财经行业合规性与时效性",
            "准确传达市场分析、财务报表或经济数据的核心逻辑",
            "金融术语严格统一（如 PE ratio → 市盈率）",
            "数字、百分比、日期格式按目标语言规范转换",
        ],
    },
    "political": {
        "audience": "外交人员、政策制定者、国际组织",
        "style_name": "政治外交",
        "principles": [
            "严谨、客观、高度程式化",
            "确保术语的政治准确性和外交礼仪",
            "字斟句酌，消除一切表意歧义",
            "敏感表述需符合目标语言的外交规范",
        ],
    },
    "legal": {
        "audience": "法律从业者、合同当事方",
        "style_name": "法律",
        "principles": [
            "严谨、客观、字斟句酌",
            "确保条文的权威性和可执行性",
            "法律术语严格对应（如 force majeure → 不可抗力）",
            "消除一切表意歧义，保留原文的法律效力",
        ],
    },
    "medical": {
        "audience": "医疗从业者、患者、监管机构",
        "style_name": "医学",
        "principles": [
            "极其严密、专业、中立",
            "符合医学文献与临床手册规范",
            "医学专有名词与诊疗表述绝对精确",
            "剂量、单位、检验数值严格保留",
        ],
    },
    "chemical": {
        "audience": "化学研究者、工程师",
        "style_name": "化学化工",
        "principles": [
            "化学命名严格遵循 IUPAC / 中国标准",
            "反应式、结构式保留原格式",
            "单位换算按目标语言规范",
        ],
    },
    "education": {
        "audience": "教育工作者、学生",
        "style_name": "教育",
        "principles": [
            "语言清晰易懂，适合教育场景",
            "学术术语保持一致性",
        ],
    },
    "cultural": {
        "audience": "文化研究者、大众读者",
        "style_name": "传统文化",
        "principles": [
            "准确传达文化内涵，兼顾可读性",
            "传统术语使用约定俗成的译法",
            "文化意象可适当意译以保证理解",
        ],
    },
}


def get_default_prompt_text(style_key: str) -> str:
    """获取某个风格的默认提示词文本（原则列表合并为字符串）。"""
    config = STYLE_CONFIGS.get(style_key, STYLE_CONFIGS["default"])
    return "\n".join(config.get("principles", []))


def get_effective_principles(style_key: str) -> list[str]:
    """
    获取某个风格当前生效的翻译原则。
    优先返回用户覆写，否则返回默认原则。
    """
    override = get_prompt_override(style_key)
    if override:
        # 用户覆写按行拆分，过滤空行
        return [line.strip() for line in override.split("\n") if line.strip()]

    config = STYLE_CONFIGS.get(style_key, STYLE_CONFIGS["default"])
    return list(config.get("principles", []))
