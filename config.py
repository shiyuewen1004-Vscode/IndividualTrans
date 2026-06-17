"""配置管理模块 - 支持 OpenAI、DeepSeek、Gemini 多翻译引擎"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── .env 文件路径 ───────────────────────────────────
_ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")

# ── OpenAI ──────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")

# ── DeepSeek ────────────────────────────────────────
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

# ── Gemini ──────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── 默认翻译引擎 ────────────────────────────────────
DEFAULT_PROVIDER = os.getenv("DEFAULT_PROVIDER", "openai")

# ── 数据库路径 ──────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "translation_memory.db")


# ═══════════════════════════════════════════════════════════════
#  .env 读写工具（供 Web UI 持久化 API Key）
# ═══════════════════════════════════════════════════════════════

# 已知的 API Key 环境变量名及其显示标签
API_KEY_VARS = {
    "OPENAI_API_KEY": "OpenAI",
    "DEEPSEEK_API_KEY": "DeepSeek",
    "GEMINI_API_KEY": "Gemini",
}


def get_env_file_path() -> str:
    """返回项目 .env 文件的绝对路径。"""
    return _ENV_PATH


def save_env_var(key: str, value: str) -> str:
    """
    将 KEY=VALUE 写入（或更新）到项目 .env 文件。
    - 保留已有内容，只更新/追加目标 key
    - 自动去除值两端的引号
    返回 .env 文件路径。
    """
    lines: list[str] = []
    found = False

    if os.path.exists(_ENV_PATH):
        with open(_ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                    lines.append(f"{key}={value}\n")
                    found = True
                else:
                    lines.append(line.rstrip("\n") + "\n")

    if not found:
        lines.append(f"{key}={value}\n")

    # 确保末尾有换行
    if lines and not lines[-1].endswith("\n"):
        lines.append("\n")

    with open(_ENV_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)

    # 同步更新模块级变量和环境变量
    _refresh_key(key, value)

    return _ENV_PATH


def _refresh_key(key: str, value: str) -> None:
    """更新模块级全局变量和 os.environ（线程不安全，仅 Streamlit 单线程安全）。"""
    import sys
    mod = sys.modules[__name__]
    os.environ[key] = value
    if key == "OPENAI_API_KEY":
        mod.OPENAI_API_KEY = value
    elif key == "DEEPSEEK_API_KEY":
        mod.DEEPSEEK_API_KEY = value
    elif key == "GEMINI_API_KEY":
        mod.GEMINI_API_KEY = value


def mask_key(key: str) -> str:
    """返回脱敏后的 Key 字符串，如 sk-a***b12c。"""
    if not key:
        return "（未配置）"
    if len(key) <= 8:
        return key[:2] + "****"
    return key[:4] + "****" + key[-4:]
