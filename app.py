"""翻译记忆学习系统 - Streamlit 主应用"""

import io
import csv
import re
import streamlit as st
from translator import translate, PROVIDER_LABELS, DIRECTION_LABELS
from config import DEFAULT_PROVIDER
from database import init_db
from tracker import record_modification, confirm_rule, ignore_rule, defer_rule
from document import parse_uploaded_file, filter_chinese_only, filter_english_only
from term_manager import (
    detect_domains, load_terminology,
    get_terms_for_domain, match_terms,
    build_domain_prompt, DOMAIN_KEYWORDS,
)

st.set_page_config(page_title="翻译记忆学习系统", page_icon="🌐", layout="wide")
init_db()

# ── Session State ────────────────────────────────────
if "style_prompt" not in st.session_state:
    st.session_state.style_prompt = None
if "provider" not in st.session_state:
    st.session_state.provider = DEFAULT_PROVIDER
if "segments" not in st.session_state:
    st.session_state.segments = []
if "doc_translations" not in st.session_state:
    st.session_state.doc_translations = {}
if "doc_direction" not in st.session_state:
    st.session_state.doc_direction = "zh2en"
if "doc_edits" not in st.session_state:
    st.session_state.doc_edits = {}
if "doc_editing" not in st.session_state:
    st.session_state.doc_editing = False
if "app_domain" not in st.session_state:
    st.session_state.app_domain = "其他"
if "last_retrieval" not in st.session_state:
    st.session_state.last_retrieval = None

# ── 文本切分工具 ────────────────────────────────────
_SENTENCE_SPLITTER = re.compile(r"(?<=[。！？.!?])(?:\s+|\n|)(?=[^\s])")


def _split_raw_text(text: str) -> list[dict]:
    """将原始文本切分为句子段落，格式与 parse_uploaded_file 一致"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\n\n" in text:
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    else:
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    sentences = []
    for para in paragraphs:
        for part in _SENTENCE_SPLITTER.split(para):
            s = part.strip()
            if s:
                sentences.append(s)

    results = []
    for i, sent in enumerate(sentences, 1):
        results.append({"sentence_id": f"S{i}", "source_text": sent})
    return results

# ── 侧边栏 ────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 模型")
    provider = st.selectbox(
        "翻译引擎",
        options=list(PROVIDER_LABELS.keys()),
        format_func=lambda k: PROVIDER_LABELS[k],
        key="provider_selector",
    )
    st.session_state.provider = provider

# ── 主界面 ────────────────────────────────────────────
st.title("🌐 翻译记忆学习系统")

tab1, tab2, tab3 = st.tabs(["🌐 智能翻译", "📁 我的文件", "📚 术语库"])

# ═══════════════════════════════════════════════════════
#  Tab 1：智能翻译 — 文档解析 + 术语检测 + AI 翻译
# ═══════════════════════════════════════════════════════
with tab1:
    # ── 输入模式选择 ──
    input_mode = st.radio(
        "选择输入方式",
        options=["📄 上传文档", "📝 手动输入文本"],
        horizontal=True,
        key="input_mode",
    )

    if input_mode == "📄 上传文档":
        uploaded_file = st.file_uploader(
            "上传文档", type=["docx", "txt"],
            help="支持 .docx 和 .txt 格式", key="doc_uploader",
        )

        if uploaded_file is not None:
            if st.button("🔍 解析文档", type="primary"):
                with st.spinner("正在解析文档..."):
                    try:
                        st.session_state.segments = parse_uploaded_file(uploaded_file)
                        from database import add_file_history
                        add_file_history(uploaded_file.name, len(st.session_state.segments))
                        st.success(f"解析完成！共 {len(st.session_state.segments)} 个句子")
                    except Exception as e:
                        st.error(f"解析失败：{e}")
                        st.session_state.segments = []
    else:  # 手动输入文本
        user_text = st.text_area(
            "输入文本",
            placeholder="在此粘贴需要翻译的中文或英文文本...",
            height=200,
            key="manual_text_input",
        )
        if user_text.strip():
            if st.button("🔍 解析文本", type="primary"):
                with st.spinner("正在解析文本..."):
                    try:
                        st.session_state.segments = _split_raw_text(user_text)
                        st.success(f"解析完成！共 {len(st.session_state.segments)} 个句子")
                    except Exception as e:
                        st.error(f"解析失败：{e}")
                        st.session_state.segments = []

    if st.session_state.segments:
        lang_filter = st.radio(
            "📋 句子过滤", options=["全部显示", "仅显示中文", "仅显示英文"],
            horizontal=True, key="lang_filter",
        )
        if lang_filter == "仅显示中文":
            display_segments = filter_chinese_only(st.session_state.segments)
            col_label = "Source Text（中文）"
        elif lang_filter == "仅显示英文":
            display_segments = filter_english_only(st.session_state.segments)
            col_label = "Source Text（英文）"
        else:
            display_segments = st.session_state.segments
            col_label = "Source Text"

        if display_segments:
            st.markdown(f"**共 {len(display_segments)} 个句子**（全部 {len(st.session_state.segments)} 个）")

            col_dir, col_dom, col_btn = st.columns([1, 1, 2])
            with col_dir:
                st.session_state.doc_direction = st.selectbox(
                    "翻译方向", options=list(DIRECTION_LABELS.keys()),
                    format_func=lambda k: DIRECTION_LABELS[k], key="doc_direction_selector",
                )
            with col_dom:
                st.session_state.app_domain = st.selectbox(
                    "Domain", options=["经济金融", "传统文化", "政治外交", "化学化工", "教育", "法律", "医学", "其他"], key="doc_domain",
                )
            with col_btn:
                st.write(""); st.write("")
                translate_all_clicked = st.button("🌐 翻译全部", type="primary", use_container_width=True)

            # ── 领域分析与术语匹配（预翻译分析）──
            analysis_text = "\n".join(seg["source_text"] for seg in st.session_state.segments)
            detected = detect_domains(analysis_text, DOMAIN_KEYWORDS)

            if not detected:
                best_domain = "其他"
                active_domains = list(DOMAIN_KEYWORDS.keys())
            else:
                best_domain = detected[0][0]
                active_domains = [d for d, _ in detected]

            terminology = load_terminology()
            active_terms: list = []
            for d in active_domains:
                active_terms.extend(get_terms_for_domain(d, terminology))

            matched_terms: list = []
            if active_terms:
                matched_terms, _ = match_terms(analysis_text, active_terms)

            system_prompt_preview = build_domain_prompt(
                text=analysis_text,
                direction=st.session_state.doc_direction,
                domain=best_domain if best_domain != "其他" else None,
                matched_terms=matched_terms if matched_terms else None,
            )

            expander_label = "🔍 领域分析与术语匹配"
            if detected:
                expander_label += f" · 检测到：{'、'.join(d for d, _ in detected[:3])}"
            with st.expander(expander_label, expanded=True):
                if detected:
                    st.markdown("**🎯 领域检测**")
                    cols_det = st.columns(len(detected))
                    for i, (domain, score) in enumerate(detected):
                        with cols_det[i]:
                            st.metric(f"🏷 {domain}", f"{score} 词匹配")
                else:
                    st.info("未能自动判断领域，将匹配全部术语库")

                if matched_terms:
                    st.markdown(f"**📋 匹配术语（共 {len(matched_terms)} 个）**")
                    term_html = (
                        "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
                        "<tr style='background:#e0e0e0;'><th style='padding:6px;text-align:left;'>🇨🇳 中文</th><th style='padding:6px;text-align:left;'>🇬🇧 英文</th></tr>"
                        + "".join(
                            f"<tr style='border-bottom:1px solid #eee;'><td style='padding:6px;'>{ch}</td><td style='padding:6px;'>{en}</td></tr>"
                            for ch, en in matched_terms
                        )
                        + "</table>"
                    )
                    st.markdown(term_html, unsafe_allow_html=True)
                else:
                    st.info("未匹配到术语")

                st.markdown("**📝 系统 Prompt 预览**")
                st.code(system_prompt_preview, language="markdown")

            if translate_all_clicked:
                st.session_state.doc_translations = {}
                st.session_state.last_retrieval = None
                progress_bar = st.progress(0)
                total = len(display_segments)
                for i, seg in enumerate(display_segments):
                    try:
                        translation, retrieval = translate(
                            seg["source_text"], provider=st.session_state.provider,
                            direction=st.session_state.doc_direction,
                            domain=None if best_domain == "其他" else best_domain,
                            matched_terms=matched_terms if matched_terms else None,
                        )
                        st.session_state.doc_translations[seg["sentence_id"]] = translation
                        if retrieval:
                            st.session_state.last_retrieval = retrieval
                    except Exception as e:
                        st.session_state.doc_translations[seg["sentence_id"]] = f"❌ {e}"
                    progress_bar.progress((i + 1) / total)
                st.success(f"翻译完成！共 {total} 句")

            # 修改模式切换
            if st.session_state.doc_translations:
                col_tbl, col_edit, _ = st.columns([2, 1, 1])
                with col_edit:
                    if not st.session_state.doc_editing:
                        if st.button("✏️ 批量修改", use_container_width=True):
                            st.session_state.doc_editing = True
                            for seg in display_segments:
                                sid = seg["sentence_id"]
                                if sid not in st.session_state.doc_edits:
                                    st.session_state.doc_edits[sid] = st.session_state.doc_translations.get(sid, "")
                            st.rerun()
                    else:
                        if st.button("👁 查看模式", use_container_width=True):
                            st.session_state.doc_editing = False
                            st.rerun()

            # 编辑模式
            if st.session_state.doc_editing and st.session_state.doc_translations:
                st.info("📝 横向对比修改每条译文，可逐句保存或一键保存全部")
                for seg in display_segments:
                    sid = seg["sentence_id"]
                    ai_text = st.session_state.doc_translations.get(sid, "")
                    saved_mark = " ✅" if f"saved_{sid}" in st.session_state and st.session_state[f"saved_{sid}"] else ""
                    with st.expander(f"{sid}{saved_mark} — {seg['source_text'][:80]}...", expanded=False):
                        col_src, col_ai, col_edit = st.columns([1, 1, 1])
                        with col_src:
                            st.markdown("**原文**")
                            st.markdown(f'<div style="background:#f0f2f6;padding:12px;border-radius:8px;min-height:120px;white-space:pre-wrap;font-size:14px;">{seg["source_text"]}</div>', unsafe_allow_html=True)
                        with col_ai:
                            st.markdown("**AI Translation**")
                            st.markdown(f'<div style="background:#e8f5e9;padding:12px;border-radius:8px;min-height:120px;white-space:pre-wrap;font-size:14px;word-wrap:break-word;">{ai_text}</div>', unsafe_allow_html=True)
                        with col_edit:
                            st.markdown("**Human Translation**")
                            edited = st.text_area("Human Translation", value=st.session_state.doc_edits.get(sid, ai_text), height=140, label_visibility="collapsed", key=f"edit_{sid}")
                            st.session_state.doc_edits[sid] = edited
                            if st.button(f"💾 保存 {sid}", key=f"save_{sid}", use_container_width=True):
                                original, modified = ai_text, edited
                                if original.strip() != modified.strip():
                                    result = record_modification(source=seg["source_text"], original=original, modified=modified)
                                    if result["should_prompt"]:
                                        st.session_state.style_prompt = {"rule_id": result["rule_id"], "original": result["original_phrase"], "modified": result["modified_phrase"], "count": result["count"], "status": result["status"]}
                                    from database import insert_asset
                                    insert_asset(source=seg["source_text"], target=modified, domain=st.session_state.app_domain)
                                st.session_state[f"saved_{sid}"] = True
                                st.success(f"{sid} 已保存 → 术语库")
                                st.rerun()

                col_save_all, _ = st.columns([1, 3])
                with col_save_all:
                    if st.button("💾 保存全部修改", type="primary", use_container_width=True):
                        saved_count, last_prompt = 0, None
                        from database import insert_asset
                        for seg in display_segments:
                            sid = seg["sentence_id"]
                            original = st.session_state.doc_translations.get(sid, "")
                            modified = st.session_state.doc_edits.get(sid, "")
                            if original.strip() != modified.strip():
                                result = record_modification(source=seg["source_text"], original=original, modified=modified)
                                if result["should_prompt"]:
                                    last_prompt = {"rule_id": result["rule_id"], "original": result["original_phrase"], "modified": result["modified_phrase"], "count": result["count"], "status": result["status"]}
                                insert_asset(source=seg["source_text"], target=modified, domain=st.session_state.app_domain)
                            st.session_state[f"saved_{sid}"] = True
                            saved_count += 1
                        st.session_state.doc_editing = False
                        if last_prompt:
                            st.session_state.style_prompt = last_prompt
                        st.success(f"已保存 {saved_count} 条 → 术语库")
                        st.rerun()

            # 表格
            if st.session_state.doc_translations:
                if st.session_state.doc_edits:
                    headers = ["Sentence ID", "Source Text", "AI Translation", "Human Translation"]
                    rows_html = "".join(
                        f"<tr><td style='white-space:nowrap;vertical-align:top;padding:8px;'>{seg['sentence_id']}</td>"
                        f"<td style='white-space:pre-wrap;word-wrap:break-word;vertical-align:top;padding:8px;'>{seg['source_text']}</td>"
                        f"<td style='white-space:pre-wrap;word-wrap:break-word;vertical-align:top;padding:8px;'>{st.session_state.doc_translations.get(seg['sentence_id'], '')}</td>"
                        f"<td style='white-space:pre-wrap;word-wrap:break-word;vertical-align:top;padding:8px;'>{st.session_state.doc_edits.get(seg['sentence_id'], '')}</td></tr>"
                        for seg in display_segments
                    )
                else:
                    headers = ["Sentence ID", "Source Text", "AI Translation"]
                    rows_html = "".join(
                        f"<tr><td style='white-space:nowrap;vertical-align:top;padding:8px;'>{seg['sentence_id']}</td>"
                        f"<td style='white-space:pre-wrap;word-wrap:break-word;vertical-align:top;padding:8px;'>{seg['source_text']}</td>"
                        f"<td style='white-space:pre-wrap;word-wrap:break-word;vertical-align:top;padding:8px;'>{st.session_state.doc_translations.get(seg['sentence_id'], '')}</td></tr>"
                        for seg in display_segments
                    )
            else:
                headers = ["Sentence ID", "Source Text"]
                rows_html = "".join(
                    f"<tr><td style='white-space:nowrap;vertical-align:top;padding:8px;'>{seg['sentence_id']}</td>"
                    f"<td style='white-space:pre-wrap;word-wrap:break-word;vertical-align:top;padding:8px;'>{seg['source_text']}</td></tr>"
                    for seg in display_segments
                )

            header_html = "".join(f"<th style='position:sticky;top:0;background:#e0e0e0;padding:10px;text-align:left;'>{h}</th>" for h in headers)
            st.markdown(f"<div style='max-height:500px;overflow-y:auto;border:1px solid #ddd;border-radius:8px;'><table style='width:100%;border-collapse:collapse;font-size:14px;'><thead><tr>{header_html}</tr></thead><tbody>{rows_html}</tbody></table></div>", unsafe_allow_html=True)
            st.caption(f"共 {len(display_segments)} 条")

            # CSV 导出
            csv_buffer = io.StringIO(newline="")
            writer = csv.writer(csv_buffer, quoting=csv.QUOTE_ALL)
            if st.session_state.doc_translations:
                if st.session_state.doc_edits:
                    writer.writerow(["Sentence ID", "Source Text", "AI Translation", "Human Translation"])
                    for seg in display_segments:
                        sid = seg["sentence_id"]
                        writer.writerow([sid, seg["source_text"], st.session_state.doc_translations.get(sid, ""), st.session_state.doc_edits.get(sid, "")])
                else:
                    writer.writerow(["Sentence ID", "Source Text", "AI Translation"])
                    for seg in display_segments:
                        writer.writerow([seg["sentence_id"], seg["source_text"], st.session_state.doc_translations.get(seg["sentence_id"], "")])
            else:
                writer.writerow(["Sentence ID", "Source Text"])
                for seg in display_segments:
                    writer.writerow([seg["sentence_id"], seg["source_text"]])
            csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")
            import base64
            st.markdown(f'<a href="data:text/csv;charset=utf-8;base64,{base64.b64encode(csv_bytes).decode()}" download="sentences.csv" style="display:inline-block;padding:6px 16px;background:#4CAF50;color:#fff;text-decoration:none;border-radius:6px;font-size:14px;">📥 下载 CSV</a>', unsafe_allow_html=True)
        else:
            st.warning("过滤后无匹配句子")
    else:
        st.info("👆 请选择输入方式（上传文档或手动输入文本），然后点击解析按钮")

# ═══════════════════════════════════════════════════════
#  Tab 2：我的文件
# ═══════════════════════════════════════════════════════
with tab2:
    st.subheader("📁 我的文件")
    from database import get_file_history, delete_file_history

    files = get_file_history(limit=50)
    if files:
        for f in files:
            col_f, col_d = st.columns([6, 1])
            with col_f:
                st.markdown(f"📄 **{f['filename']}** — {f['sentence_count']} 句 — _{f['uploaded_at']}_")
            with col_d:
                if st.button("🗑", key=f"tab2_del_{f['id']}"):
                    delete_file_history(f["id"])
                    st.rerun()
    else:
        st.info("暂无上传记录")

# ═══════════════════════════════════════════════════════
#  Tab 3：术语库
# ═══════════════════════════════════════════════════════
with tab3:
    from database import get_all_assets, get_asset_stats, get_asset_domains, delete_asset, insert_asset

    DOMAIN_OPTIONS = ["医疗", "法律", "信息技术", "金融", "经济金融", "传统文化", "政治外交", "化学化工", "教育", "其他"]

    def auto_detect_columns(headers: list[str], sample_rows: list[list[str]]) -> dict:
        """
        自动识别 CSV 列的中文/英文/领域归属。
        返回 {'zh_col': str, 'en_col': str, 'domain_col': str|None}
        """
        import re

        zh_pattern = re.compile(r"[一-鿿]")
        en_pattern = re.compile(r"^[a-zA-Z0-9\s\-_.,;:!?()/&+\"'<>\[\]{}|~@#$%^*=]+$")

        col_data = {h: [] for h in headers}
        for row in sample_rows:
            for i, h in enumerate(headers):
                if i < len(row):
                    col_data[h].append(str(row[i]) if row[i] is not None else "")

        scores = {}
        for h, vals in col_data.items():
            non_empty = [v for v in vals if v.strip()]
            if not non_empty:
                scores[h] = {"zh": 0, "en": 0, "domain_hint": 0}
                continue
            zh_count = sum(1 for v in non_empty if zh_pattern.search(v))
            en_count = sum(1 for v in non_empty if en_pattern.match(v.strip()))
            zh_ratio = zh_count / len(non_empty)
            en_ratio = en_count / len(non_empty)
            hl = h.lower()
            domain_hint = 1 if any(kw in hl for kw in ["领域", "domain", "field", "category", "行业", "分类", "类型"]) else 0
            scores[h] = {"zh": zh_ratio, "en": en_ratio, "domain_hint": domain_hint}

        zh_candidates = sorted(
            [(h, s) for h, s in scores.items() if s["zh"] >= 0.3],
            key=lambda x: x[1]["zh"], reverse=True,
        )
        zh_col = zh_candidates[0][0] if zh_candidates else headers[0] if headers else ""

        en_candidates = sorted(
            [(h, s) for h, s in scores.items() if s["en"] >= 0.3 and h != zh_col],
            key=lambda x: x[1]["en"], reverse=True,
        )
        en_col = en_candidates[0][0] if en_candidates else (headers[1] if len(headers) > 1 else "")

        domain_col = None
        domain_candidates = sorted(
            [(h, s) for h, s in scores.items() if h != zh_col and h != en_col],
            key=lambda x: (-x[1]["domain_hint"], x[1]["zh"] + x[1]["en"]),
        )
        if domain_candidates:
            best = domain_candidates[0]
            domain_col = best[0]

        return {"zh_col": zh_col, "en_col": en_col, "domain_col": domain_col}

    # ── 统计 ──
    stats = get_asset_stats()
    m1, m2, m3 = st.columns(3)
    with m1: st.metric("📊 术语总数", stats["total"])
    with m2: st.metric("✅ 启用", stats.get("active", stats["total"]))
    with m3: st.metric("📂 领域数", len(get_asset_domains()) if stats["total"] > 0 else 0)

    # ── 上传 CSV ──
    with st.expander("📥 上传术语 CSV", expanded=False):
        st.caption("CSV 文件将自动识别中文列、英文列和领域列")
        imp_file = st.file_uploader(
            "选择 CSV 文件", type=["csv"], key="term_import_file",
            label_visibility="collapsed",
        )
        if imp_file is not None:
            raw_bytes = imp_file.read()
            imp_file.seek(0)
            try:
                content = raw_bytes.decode("utf-8-sig")
            except UnicodeDecodeError:
                content = raw_bytes.decode("gbk", errors="replace")

            reader = csv.reader(io.StringIO(content))
            rows_list = list(reader)
            if len(rows_list) < 2:
                st.warning("CSV 至少需要表头 + 1 行数据")
            else:
                headers = rows_list[0]
                sample_rows = rows_list[1:6]
                all_rows = rows_list[1:]

                detected = auto_detect_columns(headers, sample_rows)

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.success(f"🇨🇳 中文列 → **{detected['zh_col']}**")
                with col_b:
                    st.success(f"🇬🇧 英文列 → **{detected['en_col']}**")
                with col_c:
                    if detected["domain_col"]:
                        st.info(f"🏷 领域列 → **{detected['domain_col']}**")
                    else:
                        st.caption("未检测到领域列，默认使用「其他」")

                st.markdown("**📋 预览（前 5 条）**")
                zh_idx = headers.index(detected["zh_col"]) if detected["zh_col"] in headers else 0
                en_idx = headers.index(detected["en_col"]) if detected["en_col"] in headers else (1 if len(headers) > 1 else 0)
                domain_idx = headers.index(detected["domain_col"]) if detected.get("domain_col") and detected["domain_col"] in headers else None

                preview_rows = []
                for row in all_rows[:5]:
                    zh_val = row[zh_idx].strip() if zh_idx < len(row) else ""
                    en_val = row[en_idx].strip() if en_idx < len(row) else ""
                    domain_val = row[domain_idx].strip() if domain_idx is not None and domain_idx < len(row) else "其他"
                    preview_rows.append((zh_val, en_val, domain_val))

                preview_html = (
                    "<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
                    "<tr style='background:#e0e0e0;'><th style='padding:8px;text-align:left;'>中文</th><th style='padding:8px;text-align:left;'>英文</th><th style='padding:8px;text-align:left;'>领域</th></tr>"
                    + "".join(
                        f"<tr><td style='padding:8px;border-bottom:1px solid #eee;'>{zh}</td><td style='padding:8px;border-bottom:1px solid #eee;'>{en}</td><td style='padding:8px;border-bottom:1px solid #eee;'>{dom}</td></tr>"
                        for zh, en, dom in preview_rows
                    )
                    + "</table>"
                )
                st.markdown(preview_html, unsafe_allow_html=True)

                if st.button("📥 确认导入", type="primary", use_container_width=True, key="term_confirm_import"):
                    imported = skipped = 0
                    for row in all_rows:
                        zh_val = (row[zh_idx].strip() if zh_idx < len(row) else "")
                        en_val = (row[en_idx].strip() if en_idx < len(row) else "")
                        domain_val = (row[domain_idx].strip() if domain_idx is not None and domain_idx < len(row) else "其他")
                        if not zh_val or not en_val:
                            skipped += 1
                            continue
                        insert_asset(source=zh_val, target=en_val, domain=domain_val if domain_val else "其他")
                        imported += 1

                    msg = f"✅ 导入 {imported} 条术语"
                    if skipped:
                        msg += f"，跳过 {skipped} 条空行"
                    st.success(msg)
                    st.rerun()

    # ── 搜索 + 领域筛选 ──
    st.divider()

    existing_domains = get_asset_domains()
    domain_options = ["全部"] + [d for d in DOMAIN_OPTIONS if d in existing_domains] + [d for d in existing_domains if d not in DOMAIN_OPTIONS]

    c1, c2 = st.columns(2)
    with c1:
        keyword = st.text_input("🔍 搜索术语", key="term_search", placeholder="输入中文或英文关键词...")
    with c2:
        domain_filter = st.selectbox("🏷 领域筛选", options=domain_options, key="term_domain")

    assets = get_all_assets(
        domain=None if domain_filter == "全部" else domain_filter,
        keyword=keyword.strip() or None,
    )

    st.markdown(f"**共 {len(assets)} 条术语**" + (f"（总计 {stats['total']} 条）" if keyword or domain_filter != "全部" else ""))

    # ── 术语表格 ──
    if not assets:
        st.info("🙅 暂无术语。请上传 CSV 文件导入术语库。")
    else:
        table_html = (
            "<div style='max-height:550px;overflow-y:auto;border:1px solid #ddd;border-radius:8px;'>"
            "<table style='width:100%;border-collapse:collapse;font-size:14px;'>"
            "<thead><tr style='position:sticky;top:0;background:#e0e0e0;'>"
            "<th style='padding:10px;text-align:left;'>🇨🇳 中文</th>"
            "<th style='padding:10px;text-align:left;'>🇬🇧 英文</th>"
            "<th style='padding:10px;text-align:left;width:100px;'>🏷 领域</th>"
            "<th style='padding:10px;text-align:center;width:60px;'>操作</th>"
            "</tr></thead><tbody>"
            + "".join(
                f"<tr style='border-bottom:1px solid #eee;'>"
                f"<td style='padding:8px;vertical-align:top;'>{a['source_text']}</td>"
                f"<td style='padding:8px;vertical-align:top;'>{a['target_text']}</td>"
                f"<td style='padding:8px;vertical-align:top;white-space:nowrap;'>{a['domain']}</td>"
                f"<td style='padding:8px;text-align:center;vertical-align:top;'>"
                f"</td>"
                f"</tr>"
                for a in assets
            )
            + "</tbody></table></div>"
        )
        st.markdown(table_html, unsafe_allow_html=True)

        # ── CSV 导出 ──
        csv_buffer = io.StringIO(newline="")
        writer = csv.writer(csv_buffer, quoting=csv.QUOTE_ALL)
        writer.writerow(["中文", "英文", "领域"])
        for a in assets:
            writer.writerow([a["source_text"], a["target_text"], a["domain"]])
        csv_bytes = csv_buffer.getvalue().encode("utf-8-sig")
        import base64
        st.markdown(
            f'<a href="data:text/csv;charset=utf-8;base64,{base64.b64encode(csv_bytes).decode()}" '
            f'download="terminology.csv" '
            f'style="display:inline-block;padding:6px 16px;background:#4CAF50;color:#fff;'
            f'text-decoration:none;border-radius:6px;font-size:14px;">📥 下载术语 CSV</a>',
            unsafe_allow_html=True,
        )

        # 批量删除
        st.divider()
        st.markdown("### 🗑 删除术语")

        delete_options = {f"#{a['id']} | {a['source_text']} → {a['target_text']}": a["id"] for a in assets}
        selected_labels = st.multiselect(
            "选择要删除的术语（可多选）",
            options=list(delete_options.keys()),
            key="term_delete_select",
        )

        col_del, _ = st.columns([1, 3])
        with col_del:
            if selected_labels:
                if st.button(f"🗑 删除选中 ({len(selected_labels)})", type="secondary", use_container_width=True):
                    for label in selected_labels:
                        delete_asset(delete_options[label])
                    st.success(f"已删除 {len(selected_labels)} 条术语")
                    st.rerun()

# ── 规则发现弹窗（全局）──────────────────────────────
if st.session_state.style_prompt:
    pd_data = st.session_state.style_prompt
    st.divider()
    st.warning(f"🔍 **发现稳定修订模式**\n\n以下相同修改已出现 **{pd_data['count']} 次**：\n\n**before_text**\n> {pd_data['original']}\n\n**after_text**\n> {pd_data['modified']}\n\n句对已自动存入 **术语库**。")
    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        if st.button("确认", type="primary", use_container_width=True): confirm_rule(pd_data["rule_id"]); st.session_state.style_prompt = None; st.success("已确认 🎉"); st.rerun()
    with col2:
        if st.button("忽略", use_container_width=True): ignore_rule(pd_data["rule_id"]); st.session_state.style_prompt = None; st.rerun()
    with col3:
        if st.button("以后再说", use_container_width=True): defer_rule(pd_data["rule_id"]); st.session_state.style_prompt = None; st.rerun()
