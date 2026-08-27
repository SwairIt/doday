"""JSON, который безопасно положить внутрь тега <script> в HTML.

`json.dumps` экранирует кавычки и слэши внутри строк, но не `<` и `>` — а
HTML-парсер закрывает `<script>` на первой же последовательности `</script`,
и ему всё равно, что она стоит внутри JSON-строки. То есть заголовок вопроса

    Как решить</script><script>...

превращал JSON-LD на публичной странице в исполняемый чужой код.

Экранируем `<`, `>` и `&` их же \\uXXXX-формой: для JSON это тот же самый
текст, а для HTML-парсера — обычные буквы. Заодно U+2028/U+2029, которые
валидны в JSON, но ломают JavaScript-парсер.
"""

import json
from typing import Any

_REPLACEMENTS = (
    ("<", "\\u003c"),
    (">", "\\u003e"),
    ("&", "\\u0026"),
    ("\u2028", "\\u2028"),
    ("\u2029", "\\u2029"),
)


def script_json(data: Any) -> str:
    """Сериализовать данные для вставки в <script> внутри шаблона."""
    out = json.dumps(data, ensure_ascii=False)
    for char, escaped in _REPLACEMENTS:
        out = out.replace(char, escaped)
    return out
