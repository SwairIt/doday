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
    posts = {
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

        full = _PAGE_TEMPLATE.format(
            title=meta["title"],
            paste_target=meta["paste_target"],
            platform_note=meta["platform_note"],
            checklist_items=checklist_items,
            article_body=html_body,
        )
        html_path.write_text(full, encoding="utf-8")
        print(f"wrote {html_path} (with {len(h2_headings)} headings in checklist)")


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

<article class="article" id="article">
{article_body}
</article>

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
</script>
</body></html>
"""


if __name__ == "__main__":
    main()
