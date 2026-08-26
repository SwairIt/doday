"""Шаблоны вопросов — чипы над полем ввода.

Нажатие подставляет текст в поле, курсор встаёт в конец: школьник дописывает
своё условие и отправляет. Смысл — убрать ступор «а как спросить».
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptTemplate:
    label: str
    text: str


TEMPLATES: tuple[PromptTemplate, ...] = (
    PromptTemplate("Объясни просто", "Объясни простыми словами, как будто мне 12 лет: "),
    PromptTemplate("По шагам", "Разбери по шагам, объясняя каждый переход: "),
    PromptTemplate("Проверь решение", "Проверь моё решение и укажи, где ошибка:\n"),
    PromptTemplate("Что значит слово", "Что означает термин "),
    PromptTemplate("В 200 словах", "Ответь в пределах 200 слов: "),
    PromptTemplate("План сочинения", "Составь план сочинения по теме: "),
    PromptTemplate("Как запомнить", "Придумай, как запомнить: "),
    PromptTemplate("С чего начать", "С чего начать, если ничего не понимаю в теме: "),
)
