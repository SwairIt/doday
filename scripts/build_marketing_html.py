"""Convert docs/marketing/*.md to HTML pages with a 'Copy Post' button +
H2-headings checklist for platforms that strip H2 on paste (VC.ru Editor.js).

The script writes:
- docs/marketing/vc-ru-post.html
- docs/marketing/reddit-sideproject-post.html

Run before commit if a marketing post changes. Served via
GET /marketing-preview/{slug} on prod for the one-click copy workflow.
"""

import re
from pathlib import Path

import markdown  # type: ignore[import-untyped]  # markdown lacks py.typed; we only call .markdown()


def main() -> None:
    posts: dict[str, dict[str, str]] = {
        "vc-ru-post": {
            "title": "VC.ru пост",
            "paste_target": "VC.ru",
            "platform_note": (
                "VC.ru Editor.js обрезает H2/H3 заголовки при paste — это их особенность. "
                "После вставки выдели каждый из заголовков ниже и нажми «H2» в их верхней панели "
                "форматирования (или клавиша «#» в начале строки в некоторых WYSIWYG). "
                "Это 2-3 минуты работы."
            ),
        },
        "reddit-sideproject-post": {
            "title": "Reddit r/SideProject пост",
            "paste_target": "Reddit",
            "platform_note": (
                "Reddit Markdown-editor: заголовки сохранятся при paste без правок. "
                "Если используешь Fancy Pants Editor — переключись на Markdown mode "
                "(кнопка справа от поля), тогда форматирование останется чистым."
            ),
        },
    }

    for slug, meta in posts.items():
        md_path = Path(f"docs/marketing/{slug}.md")
        html_path = Path(f"docs/marketing/{slug}.html")
        md_text = md_path.read_text(encoding="utf-8")
        html_body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])

        h2_headings = re.findall(r"<h2[^>]*>(.*?)</h2>", html_body, flags=re.DOTALL)
        checklist_items = "".join(
            f'<li><label><input type="checkbox" class="hl-check"> <code>{h.strip()}</code></label></li>\n'
            for h in h2_headings
        )

        # Build a plain-text version of the post with VERY visible heading markers.
        plain_text = _build_plain_with_markers(md_text)

        # Split the rendered article into H2-bounded sections. VC.ru rejects
        # paste-operations that contain too many elements at once, so we render
        # a per-section «Copy» button — the user pastes each chunk individually.
        sections = _split_into_h2_sections(html_body)
        section_cards = ""
        for idx, (heading, section_html) in enumerate(sections):
            section_id = f"sec-{idx}"
            section_cards += (
                f'<div class="section-card">\n'
                f'  <div class="section-header">\n'
                f'    <span class="section-num">{idx + 1}</span>\n'
                f'    <span class="section-title">{heading}</span>\n'
                f'    <button class="btn-copy-section" onclick="copySection(\'{section_id}\', this)">📋 Скопировать секцию</button>\n'
                f"  </div>\n"
                f'  <div class="section-body" id="{section_id}">{section_html}</div>\n'
                f"</div>\n"
            )

        full = _PAGE_TEMPLATE.format(
            title=meta["title"],
            paste_target=meta["paste_target"],
            platform_note=meta["platform_note"],
            checklist_items=checklist_items,
            article_body=html_body,
            plain_text=plain_text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"),
            section_cards=section_cards,
            section_count=len(sections),
        )
        html_path.write_text(full, encoding="utf-8")
        print(f"wrote {html_path} (with {len(h2_headings)} headings in checklist)")


def _split_into_h2_sections(html_body: str) -> list[tuple[str, str]]:
    """Cut rendered article HTML at H2 boundaries.

    Returns [(heading_text, section_html), ...] where each section_html starts
    with its own <h2>...</h2> followed by paragraphs until the next H2.
    The text BEFORE the first H2 (intro / TL;DR) goes into a section with
    heading «Введение» so the user has a clear starting chunk too.
    """
    parts = re.split(r"(<h2[^>]*>.*?</h2>)", html_body, flags=re.DOTALL)
    sections: list[tuple[str, str]] = []
    # parts[0] is everything before the first <h2>.
    intro_html = parts[0].strip()
    if intro_html:
        sections.append(("Введение (TL;DR + первые параграфы)", intro_html))
    # Then alternating: parts[1] = first <h2>, parts[2] = body until next h2, ...
    i = 1
    while i < len(parts):
        h2_tag = parts[i]
        body_after = parts[i + 1] if i + 1 < len(parts) else ""
        heading_text = re.sub(r"<[^>]+>", "", h2_tag).strip()
        section_html = h2_tag + body_after.strip()
        sections.append((heading_text, section_html))
        i += 2
    return sections


def _build_plain_with_markers(md_text: str) -> str:
    """Convert markdown source to plain text with visible heading markers.

    - `# Title` → bare title on its own line
    - `## Heading` → `═══ HEADING ═══` so the user can find and H2-ify after paste
    - `### Sub` → `── SUB ──`
    - `**bold**` → `bold` (kept as text — user makes bold in editor manually if needed)
    - `*italic*` → `italic`
    - `` `code` `` → `code` (kept as text)
    - `[text](url)` → `text (url)` so the URL is visible inline
    - lists `- item` → `• item`
    - everything else: pass through with paragraph spacing intact
    """
    out_lines: list[str] = []
    for raw_line in md_text.splitlines():
        line = raw_line.rstrip()
        if line.startswith("# ") and not line.startswith("##"):
            # Title — keep as plain bold-ish line
            out_lines.append(line[2:].upper())
            out_lines.append("")
            continue
        if line.startswith("## "):
            heading = line[3:].strip()
            out_lines.append("")
            out_lines.append(f"═══ H2: {heading} ═══")
            out_lines.append("")
            continue
        if line.startswith("### "):
            heading = line[4:].strip()
            out_lines.append("")
            out_lines.append(f"── H3: {heading} ──")
            continue
        # Strip simple markdown inline syntax
        line = re.sub(r"\*\*(.*?)\*\*", r"\1", line)
        line = re.sub(r"\*(.*?)\*", r"\1", line)
        line = re.sub(r"`(.*?)`", r"\1", line)
        line = re.sub(r"\[(.*?)\]\((.*?)\)", r"\1 (\2)", line)
        if line.startswith("- "):
            line = "• " + line[2:]
        out_lines.append(line)
    return "\n".join(out_lines).strip() + "\n"


_PAGE_TEMPLATE = """\
<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>{title}</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 760px; margin: 0 auto; padding: 1em; line-height: 1.6; color: #222; background: #fafafa; }}
  .toolbar {{ position: sticky; top: 0; z-index: 10; background: #fafafa; padding: 1em 0; border-bottom: 1px solid #ddd; margin-bottom: 1em; display: flex; gap: 0.6em; align-items: center; flex-wrap: wrap; }}
  .toolbar button {{ padding: 0.6em 1.2em; border-radius: 6px; border: none; cursor: pointer; font-weight: 600; font-size: 0.95em; transition: all 0.15s; }}
  .btn-primary {{ background: #1a73e8; color: white; }}
  .btn-primary:hover {{ background: #1557b0; }}
  .btn-primary.ok {{ background: #16a34a; }}
  .hint {{ font-size: 0.85em; color: #666; }}
  .instructions {{ background: #fffbea; border-left: 4px solid #f59e0b; padding: 1em 1.2em; margin: 1em 0 2em; border-radius: 4px; font-size: 0.92em; }}
  .instructions h3 {{ margin-top: 0; color: #92400e; font-size: 1.1em; }}
  .instructions ol {{ padding-left: 1.4em; margin: 0.5em 0; }}
  .checklist {{ background: #ecfdf5; border-left: 4px solid #10b981; padding: 1em 1.2em; margin: 1em 0 2em; border-radius: 4px; font-size: 0.92em; }}
  .checklist h3 {{ margin-top: 0; color: #065f46; font-size: 1.05em; }}
  .checklist ol {{ padding-left: 1.4em; margin: 0.5em 0; list-style: decimal; }}
  .checklist input[type="checkbox"] {{ margin-right: 0.4em; vertical-align: middle; }}
  .checklist code {{ background: #fff; padding: 0.1em 0.4em; border-radius: 3px; font-size: 0.95em; }}
  .article {{ background: white; padding: 2em; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04); }}
  .article h1 {{ font-size: 1.8em; border-bottom: 2px solid #eee; padding-bottom: 0.3em; margin-top: 0; }}
  .article h2 {{ font-size: 1.4em; margin-top: 1.8em; border-bottom: 1px solid #eee; padding-bottom: 0.2em; }}
  .article h3 {{ font-size: 1.15em; }}
  .section-card {{ background: white; border-radius: 8px; padding: 1em 1.5em; margin-bottom: 1em; box-shadow: 0 1px 4px rgba(0,0,0,0.05); border: 1px solid #e5e7eb; }}
  .section-header {{ display: flex; align-items: center; gap: 0.75em; padding-bottom: 0.6em; border-bottom: 1px solid #eee; margin-bottom: 1em; flex-wrap: wrap; }}
  .section-num {{ display: inline-flex; align-items: center; justify-content: center; width: 1.8em; height: 1.8em; background: #2563eb; color: white; border-radius: 50%; font-weight: 700; font-size: 0.85em; flex-shrink: 0; }}
  .section-title {{ flex: 1; font-weight: 600; min-width: 0; }}
  .btn-copy-section {{ padding: 0.5em 1em; border-radius: 6px; border: 1px solid #2563eb; background: white; color: #2563eb; cursor: pointer; font-weight: 600; font-size: 0.88em; transition: all 0.15s; flex-shrink: 0; }}
  .btn-copy-section:hover {{ background: #2563eb; color: white; }}
  .btn-copy-section.ok {{ background: #16a34a; color: white; border-color: #16a34a; }}
  .section-body {{ font-size: 0.95em; line-height: 1.6; color: #444; }}
  .section-body h2 {{ font-size: 1.3em; margin: 0 0 0.5em 0; color: #1e293b; }}
  .section-body p {{ margin: 0.5em 0; }}
  .section-body code {{ background: #f4f4f4; padding: 0.1em 0.3em; border-radius: 3px; }}
  .section-body a {{ color: #2563eb; }}
  .article code {{ background: #f4f4f4; padding: 0.15em 0.4em; border-radius: 3px; font-size: 0.92em; }}
  .article pre {{ background: #f4f4f4; padding: 1em; overflow-x: auto; border-radius: 4px; }}
  .article blockquote {{ border-left: 4px solid #ccc; padding-left: 1em; color: #555; margin-left: 0; }}
  .article table {{ border-collapse: collapse; width: 100%; }}
  .article th, .article td {{ border: 1px solid #ddd; padding: 0.5em 0.8em; text-align: left; }}
  .article th {{ background: #f4f4f4; }}
  .article a {{ color: #0066cc; }}
  .article ul, .article ol {{ padding-left: 1.4em; }}
  .article li {{ margin: 0.25em 0; }}
  .article hr {{ border: none; border-top: 1px solid #ddd; margin: 2em 0; }}
</style>
</head>
<body>

<div class="toolbar">
  <button id="copy-btn" class="btn-primary" onclick="copyPost()">📋 Скопировать пост</button>
  <span class="hint">→ Вставь Ctrl+V в редактор {paste_target}</span>
</div>

<div class="instructions">
<h3>Как опубликовать</h3>
<ol>
<li>Жми синюю кнопку <strong>«📋 Скопировать пост»</strong> сверху.</li>
<li>В редакторе {paste_target} удали старый текст если был, нажми <code>Ctrl+V</code>.</li>
<li><strong>Важная особенность:</strong> {platform_note}</li>
<li>Используй чек-лист ниже чтобы не забыть ни один заголовок.</li>
</ol>
</div>

<div class="checklist">
<h3>Чек-лист: заголовки которые нужно сделать H2 в редакторе {paste_target}</h3>
<p style="margin: 0 0 0.6em 0;">После вставки найди эти заголовки (они будут как обычный текст), выдели каждый, нажми «H2» в панели форматирования:</p>
<ol>
{checklist_items}</ol>
<p style="margin: 0.6em 0 0 0; font-size: 0.85em; color: #666;">Галочки сохранятся пока ты не закроешь страницу. Клики на этой странице ничего не делают с самим постом — это просто блокнот для тебя.</p>
</div>

<div style="background: #eff6ff; border-left: 4px solid #2563eb; padding: 1em 1.2em; margin: 1em 0 2em; border-radius: 4px; font-size: 0.92em;">
<h3 style="margin-top: 0; color: #1e40af; font-size: 1.05em;">🔥 Если ОДНА большая вставка не работает (VC.ru ругается «слишком много текста»)</h3>
<p>Копируй по <strong>СЕКЦИЯМ</strong> ниже. Каждая секция = заголовок H2 + параграфы под ним. Жми «📋 Скопировать секцию», вставляй в редактор {paste_target}, после вставки выдели первую строку (заголовок) и нажми H2 в их панели. Повтори для каждой из {section_count} секций.</p>
</div>

<div id="sections-list">
{section_cards}
</div>

<details style="margin-top: 2em; background: white; padding: 1em 1.5em; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
<summary style="cursor: pointer; font-weight: 600; color: #1a73e8;">Запасной запасной вариант: plain text с маркерами заголовков</summary>
<p style="margin: 1em 0 0.6em 0; font-size: 0.92em; color: #555;">
Если совсем ничего не работает — выдели текст ниже (клик в поле → Ctrl+A → Ctrl+C) и вставь в редактор {paste_target}.
Заголовки помечены ▶ <code>═══ H2: ... ═══</code> ◀ — найди каждый в редакторе, выдели, нажми H2, удали маркеры.
</p>
<textarea readonly id="plain-textarea" style="width: 100%; height: 400px; font-family: 'SF Mono', Consolas, monospace; font-size: 0.85em; padding: 1em; border: 1px solid #ddd; border-radius: 4px; resize: vertical; line-height: 1.5;" onclick="this.select()">{plain_text}</textarea>
<button onclick="copyPlainText()" style="margin-top: 0.6em; padding: 0.5em 1em; border-radius: 4px; border: 1px solid #1a73e8; background: white; color: #1a73e8; cursor: pointer; font-weight: 600;">📋 Скопировать plain text</button>
</details>

<details style="margin-top: 1em; background: white; padding: 1em 1.5em; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.04);">
<summary style="cursor: pointer; font-weight: 600; color: #666;">Предпросмотр всего поста как одной статьи</summary>
<article class="article" id="article" style="margin-top: 1em;">
{article_body}
</article>
</details>

<script>
async function copyPost() {{
  const article = document.getElementById("article");
  const html = article.innerHTML;
  const text = article.innerText;
  const btn = document.getElementById("copy-btn");
  try {{
    if (navigator.clipboard && window.ClipboardItem) {{
      await navigator.clipboard.write([
        new ClipboardItem({{
          "text/html": new Blob([html], {{ type: "text/html" }}),
          "text/plain": new Blob([text], {{ type: "text/plain" }}),
        }})
      ]);
    }} else {{
      const range = document.createRange();
      range.selectNode(article);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      document.execCommand("copy");
      sel.removeAllRanges();
    }}
    btn.textContent = "✓ Скопировано! Теперь вставь в редактор";
    btn.classList.add("ok");
    setTimeout(() => {{ btn.textContent = "📋 Скопировать пост"; btn.classList.remove("ok"); }}, 3000);
  }} catch (e) {{
    alert("Не получилось скопировать автоматически. Выдели текст в белом блоке через Ctrl+A и скопируй Ctrl+C. Ошибка: " + e.message);
  }}
}}

async function copySection(sectionId, btn) {{
  const el = document.getElementById(sectionId);
  if (!el) return;
  const html = el.innerHTML;
  const text = el.innerText;
  try {{
    if (navigator.clipboard && window.ClipboardItem) {{
      await navigator.clipboard.write([
        new ClipboardItem({{
          "text/html": new Blob([html], {{ type: "text/html" }}),
          "text/plain": new Blob([text], {{ type: "text/plain" }}),
        }})
      ]);
    }} else {{
      const range = document.createRange();
      range.selectNode(el);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      document.execCommand("copy");
      sel.removeAllRanges();
    }}
    const origText = btn.textContent;
    btn.textContent = "✓ Готово";
    btn.classList.add("ok");
    setTimeout(() => {{ btn.textContent = origText; btn.classList.remove("ok"); }}, 2500);
  }} catch (e) {{
    alert("Не получилось. Выдели текст руками через Ctrl+A в блоке выше. Ошибка: " + e.message);
  }}
}}

async function copyPlainText() {{
  const ta = document.getElementById("plain-textarea");
  ta.select();
  try {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      await navigator.clipboard.writeText(ta.value);
    }} else {{
      document.execCommand("copy");
    }}
    alert("Plain text скопирован в буфер. Вставь в редактор {paste_target}.");
  }} catch (e) {{
    alert("Не получилось. Ошибка: " + e.message);
  }}
}}
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
