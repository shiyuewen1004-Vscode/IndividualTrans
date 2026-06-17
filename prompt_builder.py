"""Prompt Builder — 将各模块结果组装成最终 System Prompt"""

from prompt_center import STYLE_CONFIGS, get_effective_principles


def build_prompt_context(
    source_text: str = "",
    template_name: str = "default",
    terminology_prompt: str = "",
    tm_hits: list[dict] | None = None,
    extra_principles: list[str] | None = None,
) -> str:
    """
    将 Style Config + Terminology + TM Hits + Extra Principles 组装成
    最终送给翻译模型的 System Prompt。

    Args:
        source_text: 待翻译文本（用于上下文）
        template_name: 模板名（default / financial / legal 等）
        terminology_prompt: build_terminology_prompt() 的输出
        tm_hits: 检索到的翻译记忆命中列表
        extra_principles: 额外的翻译原则（如自定义 prompt）

    Returns:
        组装好的 System Prompt 字符串
    """
    config = STYLE_CONFIGS.get(template_name, STYLE_CONFIGS["default"])
    principles = get_effective_principles(template_name)

    # 如果调用方传入了额外原则，合并进去
    if extra_principles:
        principles = list(principles) + list(extra_principles)

    parts: list[str] = []

    # ── 角色 ──────────────────────────────────────────
    style_name = config.get("style_name", template_name)
    parts.append(f"You are a professional {style_name} translator.")

    # ── 受众 ──────────────────────────────────────────
    audience = config.get("audience", "Professional Readers")
    if audience:
        parts.append(f"Target audience: {audience}")

    # ── 翻译原则 ──────────────────────────────────────
    if principles:
        lines = ["## Translation Principles"]
        for i, p in enumerate(principles, 1):
            lines.append(f"{i}. {p}")
        parts.append("\n".join(lines))

    # ── 术语表（强制统一）─────────────────────────────
    if terminology_prompt.strip():
        parts.append(terminology_prompt.strip())

    # ── 翻译记忆参考 ──────────────────────────────────
    if tm_hits:
        lines = ["## Reference Translations (for style guidance only)"]
        for h in tm_hits[:5]:
            lines.append(f"- {h['source_text']} → {h['target_text']}")
        parts.append("\n".join(lines))

    # ── 指令 ──────────────────────────────────────────
    parts.append("Translate the following text accurately and naturally.")

    return "\n\n".join(parts)
