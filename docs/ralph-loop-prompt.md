# Ralph Loop — канонический промпт авто-разработки Doday

Это промпт, которым запускается непрерывный Ralph-цикл авто-разработки Doday.
Запуск: skill `ralph-loop:ralph-loop` с этим текстом в args (без круглых скобок —
обёртка скрипта их ломает).

Останов: skill `ralph-loop:cancel-ralph`.

---

Ралф-цикл авто-разработки Doday. Проект Doday в projectsflow, репо SwairIt/doday, рабочая директория c:/www-Yaroslav/SchoolProject, авто-деплой на getdoday.ru через cron-poll за минуту. ПОЛНАЯ АВТОНОМИЯ: пользователь даёт все права на любые идеи, главное чтобы они были. Работай непрерывно, ничего не спрашивай у пользователя, сам думай как лучше и принимай все решения сам. Не жди подтверждений. Каждую итерацию делай ПОЛНОСТЬЮ один шаг и заканчивай.

ШАГ 1 ПРОВЕРЬ ДОСКУ: pf_list_projects, найди проект Doday с gitRepoUrl SwairIt/doday, projectId fac16dd4-499a-4cba-aed2-8b9ae6bebb47, pf_list_tasks.

ШАГ 2 ЕСТЬ ОТКРЫТАЯ ЗАДАЧА todo или in_progress: возьми верхнюю, pf_get_task если есть вложения или комментарии, переведи в in_progress, реализуй ПОЛНОСТЬЮ только ДОБАВЛЯЯ не ломая существующий функционал и веб-роуты и API и архитектуру. Планка качества Doday обязательна: pre-commit зелёный - ruff format check, ruff check E F I UP B S A RUF, mypy strict app и scripts, lint_templates. Затем pytest -q зелёный. Перезапусти uvicorn по процедуре из CLAUDE.md - убей PID на 8000 через netstat, старт с reload, curl-проверь новый роут на 401 не 404. Playwright-смоук: страница грузится, ноль console errors. Скриншоты в docs/screenshots сохрани и закоммить. Commit Russian past-tense с author 112168281+SwairIt@users.noreply.github.com. Пушь через TOKEN из .env на SwairIt/doday master, cron-poll сам redeploy за минуту, потом smoke_test https://getdoday.ru должен быть зелёный. Затем ОБЯЗАТЕЛЬНО pf_link_commit_to_task привяжи коммит к задаче, и pf_create_task_comment добавь комментарий-отчёт что именно сделал плюс пути к скринам, и pf_write_kb_document worklog. Если pf_create_task_comment ещё недоступен в этой сессии используй worklog как fallback. Затем pf_move_task в done. Обнови PROGRESS.md.

ШАГ 3 НЕТ ОТКРЫТЫХ ЗАДАЧ: придумай ОДНУ конкретную фишку для Doday в русле focused todo плюс командная работа, СНАЧАЛА сверься со спеком 2026-05-13-doday-simplify-and-teams-design.md и git log чтобы не предлагать уже существующее или намеренно удалённое. pf_create_task со спеком. НЕ реализуй в этой же итерации.

ВСЕГДА: одна задача за итерацию, не пушь сломанное, не трогай прод-секреты, .env gitignored проверь перед git add, не ломай существующий функционал.
