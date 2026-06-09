"""Prompt Builder — 领域感知的 System Prompt 组装器

基于 term_manager 的领域检测 + CSV 术语匹配，构建结构化的翻译 System Prompt。

组装结构：
    Role:           {领域}翻译专家
    Context:        源语言 / 目标语言 / 语调
    Terminology:    {从 CSV 术语库匹配到的术语表}
    Translation Memory: {TM 检索结果，可选}
    Instruction:    翻译指令
"""

from typing import Optional

from retriever import retrieve
from term_manager import (
    build_domain_prompt,
    detect_best_domain,
    load_terminology,
    get_terms_for_domain,
    match_terms,
    get_domain_tone,
)


def build_prompt_context(
    source_text: str,
    template_name: str = "default",
    terminology_prompt: str = "",
    tm_hits: Optional[list[dict]] = None,
    style_examples: Optional[str] = None,
    extra_principles: Optional[list[str]] = None,
) -> str:
    """
    构建领域感知的 System Prompt（兼容旧接口）。

    流程：
        1. 自动检测领域
        2. 加载 CSV 术语库，匹配文本中的术语
        3. 组装 Role + Context + Terminology + TM + Instruction

    Args:
        source_text:         待翻译的原文
        template_name:       保留兼容（不再使用旧的风格模板，由领域自动决定语调）
        terminology_prompt:  保留兼容（不再使用，术语由 CSV 自动匹配）
        tm_hits:             retriever.retrieve() 返回的 hits 列表
        style_examples:      保留兼容（暂未使用）
        extra_principles:    额外的翻译原则

    Returns:
        结构化 System Prompt 字符串
    """
    # 使用 term_manager 构建领域感知 prompt
    return build_domain_prompt(
        text=source_text,
        tm_hits=tm_hits,
    )


def build_system_prompt(source_text: str, base_prompt: str = "") -> tuple[str, dict]:
    """
    以 base_prompt 为基础，叠加术语库和 TM 检索。

    兼容旧接口。

    Returns:
        (system_prompt, retrieval_result)
    """
    result = retrieve(source_text)

    system_prompt = build_prompt_context(
        source_text=source_text,
        tm_hits=result.get("hits") if result else None,
    )

    system_prompt += "\n\n---\nTranslate the following text according to the above specifications."

    return system_prompt, result
