# coding=utf-8
"""
AI 分析结果格式化模块

将 AI 分析结果格式化为各推送渠道的样式

字段映射（v2 -> v3）：
  core_trends          -> what_happened       事实速报
  (新增)               -> mapping             深度映射
  sentiment_controversy-> momentum_sentiment  热点势能与舆论断层
  signals              -> signals             异动与弱信号（不变）
  standalone_summaries -> standalone_summaries 独立展示区概括（不变）
  rss_insights         -> rss_insights        RSS深度洞察（不变）
  outlook_strategy     -> strategy_question   策略研判与思考题

⚠️  重要：AIAnalysisResult（analyzer.py）中的字段定义需同步更新，
    否则访问 result.what_happened 等新字段时会抛出 AttributeError。
"""

import html as html_lib
import re
from .analyzer import AIAnalysisResult


# ─────────────────────────────────────────────
# 字段配置表（顺序即渲染顺序）
# standalone_summaries 有特殊格式化逻辑，单独处理，不在此表中
# ─────────────────────────────────────────────
FIELD_CONFIG = [
    ("what_happened",      "事实速报"),
    ("mapping",            "深度映射"),
    ("momentum_sentiment", "热点势能与舆论断层"),
    ("signals",            "异动与弱信号"),
    ("rss_insights",       "RSS 深度洞察"),
    ("strategy_question",  "策略研判与思考题"),
]


# ─────────────────────────────────────────────
# 辅助函数（无变化）
# ─────────────────────────────────────────────

def _escape_html(text: str) -> str:
    """转义 HTML 特殊字符，防止 XSS 攻击"""
    return html_lib.escape(text) if text else ""


def _format_list_content(text: str) -> str:
    """
    格式化列表内容，确保序号前有换行
    例如将 "1. xxx 2. yyy" 转换为:
    1. xxx
    2. yyy
    """
    if not text:
        return ""

    text = text.strip()

    # 0. 合并序号与紧随的【标签】（防御性处理）
    text = re.sub(r'(\d+\.)\s*【([^】]+)】([:：]?)', r'\1 \2：', text)

    # 1. 规范化：确保 "1." 后面有空格
    result = re.sub(r'(\d+)\.([^ \d])', r'\1. \2', text)

    # 2. 强制换行：匹配 "数字."，且前面不是换行符
    result = re.sub(r'(?<=[^\n])\s+(\d+\.)', r'\n\1', result)

    # 3. 处理 "1.**粗体**" 这种情况（防御性处理）
    result = re.sub(r'(?<=[^\n])(\d+\.\*\*)', r'\n\1', result)

    # 4. 处理中文标点后的换行
    result = re.sub(r'([：:;,。；，])\s*(\d+\.)', r'\1\n\2', result)

    # 5. 处理 "XX方面："、"XX领域：" 等子标题换行
    result = re.sub(r'([。！？；，、])\s*([a-zA-Z0-9\u4e00-\u9fa5]+(方面|领域)[:：])', r'\1\n\2', result)

    # 6. 处理 【标签】 格式
    # 6a. 标签前确保空行分隔（文本开头除外）
    result = re.sub(r'(?<=\S)\n*(【[^】]+】)', r'\n\n\1', result)
    # 6b. 合并标签与被换行拆开的冒号
    result = re.sub(r'(【[^】]+】)\n+([:：])', r'\1\2', result)
    # 6c. 标签后（含可选冒号），如果紧跟非空白非冒号内容则另起一行
    result = re.sub(r'(【[^】]+】[:：]?)[ \t]*(?=[^\s:：])', r'\1\n', result)

    # 7. 在列表项之间增加视觉空行
    result = re.sub(r'(?<![:：】])\n(\d+\.)', r'\n\n\1', result)

    return result


def _format_standalone_summaries(summaries: dict) -> str:
    """格式化独立展示区概括为纯文本行，每个源名称单独一行"""
    if not summaries:
        return ""
    lines = []
    for source_name, summary in summaries.items():
        if summary:
            lines.append(f"[{source_name}]:\n{_format_list_content(summary)}")
    return "\n\n".join(lines)


# ─────────────────────────────────────────────
# 通用渲染辅助：遍历 FIELD_CONFIG 输出标准块
# ─────────────────────────────────────────────

def _render_standard_fields_markdown(result: AIAnalysisResult, bold: bool = True) -> list[str]:
    """
    为 Markdown 类渲染函数生成标准字段块。
    bold=True  -> **标题**（通用 Markdown / 飞书）
    bold=False -> 直接返回字段列表供调用方加前缀（钉钉用 ####）
    """
    lines = []
    for field, title in FIELD_CONFIG:
        content = getattr(result, field, None)
        if content:
            heading = f"**{title}**" if bold else title
            lines.extend([heading, _format_list_content(content), ""])
    return lines


def _render_standalone_markdown(result: AIAnalysisResult, heading: str) -> list[str]:
    """为 Markdown 类渲染函数生成 standalone_summaries 块"""
    lines = []
    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend([heading, summaries_text, ""])
    return lines


# ─────────────────────────────────────────────
# 渲染函数
# ─────────────────────────────────────────────

def render_ai_analysis_markdown(result: AIAnalysisResult) -> str:
    """渲染为通用 Markdown 格式（Telegram、企业微信、ntfy、Bark、Slack）"""
    if not result.success:
        return f"⚠️ AI 分析失败: {result.error}"

    lines = ["**✨ AI 热点分析**", ""]
    lines.extend(_render_standard_fields_markdown(result, bold=True))
    lines.extend(_render_standalone_markdown(result, "**独立展示区概括**"))
    return "\n".join(lines)


def render_ai_analysis_feishu(result: AIAnalysisResult) -> str:
    """渲染为飞书卡片 Markdown 格式"""
    if not result.success:
        return f"⚠️ AI 分析失败: {result.error}"

    lines = ["**✨ AI 热点分析**", ""]
    lines.extend(_render_standard_fields_markdown(result, bold=True))
    lines.extend(_render_standalone_markdown(result, "**独立展示区概括**"))
    return "\n".join(lines)


def render_ai_analysis_dingtalk(result: AIAnalysisResult) -> str:
    """渲染为钉钉 Markdown 格式"""
    if not result.success:
        return f"⚠️ AI 分析失败: {result.error}"

    lines = ["### ✨ AI 热点分析", ""]
    for field, title in FIELD_CONFIG:
        content = getattr(result, field, None)
        if content:
            lines.extend([f"#### {title}", _format_list_content(content), ""])
    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend(["#### 独立展示区概括", summaries_text, ""])
    return "\n".join(lines)


def render_ai_analysis_plain(result: AIAnalysisResult) -> str:
    """渲染为纯文本格式"""
    if not result.success:
        return f"AI 分析失败: {result.error}"

    lines = ["【✨ AI 热点分析】", ""]
    for field, title in FIELD_CONFIG:
        content = getattr(result, field, None)
        if content:
            lines.extend([f"[{title}]", _format_list_content(content), ""])
    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            lines.extend(["[独立展示区概括]", summaries_text, ""])
    return "\n".join(lines)


def render_ai_analysis_html(result: AIAnalysisResult) -> str:
    """渲染为 HTML 格式（邮件简版）"""
    if not result.success:
        return f'<div class="ai-error">⚠️ AI 分析失败: {_escape_html(result.error)}</div>'

    html_parts = ['<div class="ai-analysis">', "<h3>✨ AI 热点分析</h3>"]

    for field, title in FIELD_CONFIG:
        content = getattr(result, field, None)
        if content:
            content_html = _escape_html(_format_list_content(content)).replace("\n", "<br>")
            html_parts.extend([
                '<div class="ai-section">',
                f"<h4>{_escape_html(title)}</h4>",
                f'<div class="ai-content">{content_html}</div>',
                "</div>",
            ])

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            summaries_html = _escape_html(summaries_text).replace("\n", "<br>")
            html_parts.extend([
                '<div class="ai-section">',
                "<h4>独立展示区概括</h4>",
                f'<div class="ai-content">{summaries_html}</div>',
                "</div>",
            ])

    html_parts.append("</div>")
    return "\n".join(html_parts)


def render_ai_analysis_html_rich(result: AIAnalysisResult) -> str:
    """渲染为丰富样式的 HTML 格式（HTML 报告用）"""
    if not result:
        return ""

    if not result.success:
        error_msg = result.error or "未知错误"
        return f"""
                <div class="ai-section">
                    <div class="ai-error">⚠️ AI 分析失败: {_escape_html(str(error_msg))}</div>
                </div>"""

    ai_html = """
                <div class="ai-section">
                    <div class="ai-section-header">
                        <div class="ai-section-title">✨ AI 热点分析</div>
                        <span class="ai-section-badge">AI</span>
                    </div>"""

    for field, title in FIELD_CONFIG:
        content = getattr(result, field, None)
        if content:
            content_html = _escape_html(_format_list_content(content)).replace("\n", "<br>")
            ai_html += f"""
                    <div class="ai-block">
                        <div class="ai-block-title">{_escape_html(title)}</div>
                        <div class="ai-block-content">{content_html}</div>
                    </div>"""

    if result.standalone_summaries:
        summaries_text = _format_standalone_summaries(result.standalone_summaries)
        if summaries_text:
            summaries_html = _escape_html(summaries_text).replace("\n", "<br>")
            ai_html += f"""
                    <div class="ai-block">
                        <div class="ai-block-title">独立展示区概括</div>
                        <div class="ai-block-content">{summaries_html}</div>
                    </div>"""

    ai_html += """
                </div>"""
    return ai_html
