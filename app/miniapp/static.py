"""Inline статика для Mini App: JS отдаётся через эндпойнт.

В проекте нет StaticFiles mount (см. PWA-icon, OG-image — все inline).
Здесь тот же подход: JS-файл — Python-строка, отдаётся как text/javascript
с длинным cache-control.
"""

MINIAPP_JS = r"""// Doday Mini App — клиентская инициализация Telegram WebApp.
// Загружается на каждой /miniapp/* странице.

(function () {
  'use strict';

  const tg = window.Telegram && window.Telegram.WebApp;
  if (!tg) {
    console.warn('Telegram.WebApp не доступен — открой через Telegram-клиент');
    return;
  }

  // 1. Mark ready + expand до full-height
  try { tg.ready(); } catch (e) {}
  try { tg.expand(); } catch (e) {}
  try { tg.disableVerticalSwipes(); } catch (e) {}

  // 2. Sync CSS-vars с Telegram theme
  function applyTheme() {
    const p = tg.themeParams || {};
    const root = document.documentElement.style;
    if (p.bg_color) root.setProperty('--tg-bg', p.bg_color);
    if (p.text_color) root.setProperty('--tg-text', p.text_color);
    if (p.hint_color) root.setProperty('--tg-hint', p.hint_color);
    if (p.link_color) root.setProperty('--tg-link', p.link_color);
    if (p.button_color) root.setProperty('--tg-button', p.button_color);
    if (p.button_text_color) root.setProperty('--tg-button-text', p.button_text_color);
    if (p.secondary_bg_color) root.setProperty('--tg-secondary-bg', p.secondary_bg_color);
  }
  applyTheme();
  tg.onEvent('themeChanged', applyTheme);

  // 3. Auto-auth: шлём initData на /miniapp/auth, ставим cookie.
  //    На любой странице:
  //      - если 401 need_link → редирект на /miniapp/link
  //    Если мы на /miniapp/link и 200 → редирект на / (сессия установлена,
  //    onboarding больше не нужен).
  //    Если мы НЕ на /miniapp/link и 200 → ничего (cookie уже стоит,
  //    страница и так корректная).
  async function attemptAuth() {
    if (!tg.initData) return;  // открыто не из Telegram (debug в браузере)
    const onLinkPage = window.location.pathname.startsWith('/miniapp/link');
    try {
      const r = await fetch('/miniapp/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ init_data: tg.initData }),
        credentials: 'include',
      });
      if (r.ok) {
        // На link-странице после успеха — уходим на Today.
        if (onLinkPage) window.location.href = '/miniapp/';
        return;
      }
      const data = await r.json().catch(() => ({}));
      if (data.need_link && !onLinkPage) {
        const u = new URL('/miniapp/link', window.location.origin);
        u.searchParams.set('telegram_user_id', String(data.telegram_user_id));
        window.location.href = u.toString();
      }
    } catch (e) {
      console.warn('miniapp auth failed', e);
    }
  }

  attemptAuth();

  // 4. Globals для inline-страниц (haptic shortcuts)
  window.dodayHaptic = {
    light: () => { try { tg.HapticFeedback.impactOccurred('light'); } catch (e) {} },
    medium: () => { try { tg.HapticFeedback.impactOccurred('medium'); } catch (e) {} },
    heavy: () => { try { tg.HapticFeedback.impactOccurred('heavy'); } catch (e) {} },
    success: () => { try { tg.HapticFeedback.notificationOccurred('success'); } catch (e) {} },
    warning: () => { try { tg.HapticFeedback.notificationOccurred('warning'); } catch (e) {} },
    error: () => { try { tg.HapticFeedback.notificationOccurred('error'); } catch (e) {} },
    select: () => { try { tg.HapticFeedback.selectionChanged(); } catch (e) {} },
  };

  // 5. MainButton helper — вызывается из шаблонов
  window.dodayMainButton = {
    show(text, onClick) {
      tg.MainButton.setText(text);
      tg.MainButton.show();
      tg.MainButton.offClick();
      tg.MainButton.onClick(onClick);
    },
    hide() { tg.MainButton.hide(); tg.MainButton.offClick(); },
  };

  // 5.1. Per-screen MainButton — биндим автоматически по URL.
  function setupMainButton() {
    const path = window.location.pathname;
    if (path === '/miniapp/' || path === '/miniapp/inbox' || path.startsWith('/miniapp/projects/')) {
      // Today / Inbox / project → «Добавить» → фокус на quickadd
      window.dodayMainButton.show('Добавить задачу', () => {
        const inp = document.querySelector('input[type="text"], textarea');
        if (inp) inp.focus();
      });
    } else if (path === '/miniapp/calendar') {
      // Calendar → «На сегодня» (если ушли)
      const isToday = !window.location.search.includes('date=');
      if (!isToday) {
        window.dodayMainButton.show('На сегодня', () => {
          window.location.href = '/miniapp/calendar';
        });
      } else {
        window.dodayMainButton.hide();
      }
    } else if (path === '/miniapp/projects') {
      window.dodayMainButton.show('Новый проект', () => {
        // Триггерим click на «+» button — Alpine откроет sheet
        const btn = document.querySelector('header button[aria-label="Создать проект"]');
        if (btn) btn.click();
      });
    } else {
      window.dodayMainButton.hide();
    }
  }
  setupMainButton();

  // 6. BackButton — биндится автоматически если у элемента есть data-back-handler
  document.addEventListener('alpine:init', () => {});
  if (window.history.length > 1 && window.location.pathname !== '/miniapp/') {
    tg.BackButton.show();
    tg.BackButton.onClick(() => window.history.back());
  }

  // 7. Swipe-actions для task-card.
  //    Свайп влево past 80px → POST /complete → carry off вверх + fade.
  //    Свайп вправо past 80px → POST /snooze → carry off вниз + fade.
  //    Меньше 80px → spring обратно.
  const SWIPE_THRESHOLD = 80;
  let swipeState = null;

  // B1 — Long-press tracker для quick-actions sheet.
  let longPressTimer = null;
  let longPressFired = false;
  const LONG_PRESS_MS = 500;

  function onTouchStart(e) {
    const row = e.target.closest('[data-swipeable]');
    if (!row) return;
    const t = e.touches[0];
    swipeState = {
      row,
      content: row.querySelector('.swipe-content'),
      startX: t.clientX,
      startY: t.clientY,
      dx: 0,
      locked: null,
    };
    row.classList.add('swiping');
    // B1: arm long-press
    longPressFired = false;
    const taskRow = row.closest('[data-task-id]') || row;
    const taskId = taskRow.getAttribute('data-task-id');
    if (taskId) {
      clearTimeout(longPressTimer);
      longPressTimer = setTimeout(() => {
        if (swipeState && swipeState.locked === 'x') return; // user уже свайпит
        longPressFired = true;
        // Cancel swipe-state, reset transform
        if (swipeState) {
          swipeState.content.style.transform = '';
          swipeState.row.classList.remove('swiping');
        }
        window.dodayHaptic && window.dodayHaptic.medium();
        window.dispatchEvent(new CustomEvent('doday-open-quickactions', {detail: {taskId}}));
      }, LONG_PRESS_MS);
    }
  }

  function onTouchMove(e) {
    if (!swipeState) return;
    const t = e.touches[0];
    const dx = t.clientX - swipeState.startX;
    const dy = t.clientY - swipeState.startY;
    if (swipeState.locked === null) {
      if (Math.abs(dx) > 8 || Math.abs(dy) > 8) {
        swipeState.locked = Math.abs(dx) > Math.abs(dy) ? 'x' : 'y';
      }
    }
    if (swipeState.locked === 'x') {
      // B1: пользователь начал свайпать — отменяем long-press timer
      clearTimeout(longPressTimer);
      e.preventDefault();
      swipeState.dx = dx;
      swipeState.content.style.transform = 'translateX(' + dx + 'px)';
      // P5 polish: data-passed для CSS scale-up иконки при threshold
      if (dx <= -SWIPE_THRESHOLD) swipeState.row.setAttribute('data-passed', 'right');
      else if (dx >= SWIPE_THRESHOLD) swipeState.row.setAttribute('data-passed', 'left');
      else swipeState.row.removeAttribute('data-passed');
    } else if (Math.abs(dx) > 6 || Math.abs(dy) > 6) {
      // Movement detected before lock — кенселим long-press
      clearTimeout(longPressTimer);
    }
  }

  // A3: micro-confetti-burst из точки источника при complete.
  //     8 частиц физикой по приоритету-цвету.
  function burstConfettiAt(x, y, priorityColor) {
    if (!window.confetti) return;
    const colorMap = {
      p1: ['#fb7185', '#f87171'],
      p2: ['#fbbf24', '#fb923c'],
      p3: ['#38bdf8', '#60a5fa'],
      p4: ['#a78bfa', '#c4b5fd'],
    };
    const colors = colorMap[priorityColor || 'p4'] || colorMap.p4;
    try {
      window.confetti({
        particleCount: 8,
        spread: 50,
        startVelocity: 18,
        gravity: 1.2,
        scalar: 0.7,
        origin: { x: x / window.innerWidth, y: y / window.innerHeight },
        colors,
      });
    } catch (e) {}
  }

  // γ: показ toast при level-up или unlock achievement
  function showRewardToast(emoji, title, subtitle) {
    const el = document.createElement('div');
    el.style.cssText =
      'position:fixed;left:50%;top:80px;transform:translate(-50%,-200%);z-index:70;' +
      'background:var(--surface-2);color:var(--text);padding:14px 18px;border-radius:16px;' +
      'box-shadow:0 12px 32px rgba(0,0,0,0.4);display:flex;align-items:center;gap:10px;' +
      'transition:transform .35s cubic-bezier(0.34, 1.56, 0.64, 1);' +
      'border:2px solid var(--accent);min-width:220px;max-width:90vw;';
    el.innerHTML =
      '<span style="font-size:32px">' + emoji + '</span>' +
      '<div><div style="font-weight:bold;font-size:14px">' + title + '</div>' +
      '<div style="font-size:11px;opacity:.7">' + (subtitle || '') + '</div></div>';
    document.body.appendChild(el);
    requestAnimationFrame(() => { el.style.transform = 'translate(-50%, 0)'; });
    setTimeout(() => { el.style.transform = 'translate(-50%, -200%)'; }, 3500);
    setTimeout(() => { el.remove(); }, 4000);
    window.dodayHaptic && window.dodayHaptic.success();
  }
  window.dodayRewardToast = showRewardToast;

  async function commitComplete(taskId) {
    try {
      const r = await fetch('/miniapp/api/tasks/' + taskId + '/complete', {
        method: 'POST', credentials: 'include',
      });
      if (r.ok) {
        const data = await r.json().catch(() => ({}));
        // γ: новые achievements
        if (data.achievements_unlocked && data.achievements_unlocked.length) {
          data.achievements_unlocked.forEach((a, i) => {
            setTimeout(() => showRewardToast(a.emoji, a.title, a.description), i * 800);
          });
        }
        // γ: level-up
        if (data.level_up) {
          setTimeout(() => {
            showRewardToast('⭐', 'Уровень ' + data.new_level + '!', 'Так держать');
            // Дополнительные конфетти на level-up
            if (window.confetti) {
              window.confetti({
                particleCount: 80,
                spread: 100,
                origin: { y: 0.4 },
                colors: ['#7c3aed', '#d946ef', '#fbbf24', '#34d399'],
              });
            }
          }, 400);
        }
      }
    } catch (e) {}
  }
  async function commitSnooze(taskId) {
    try {
      await fetch('/miniapp/api/tasks/' + taskId + '/snooze', {
        method: 'POST', credentials: 'include',
      });
    } catch (e) {}
  }

  function onTouchEnd() {
    // B1: всегда чистим timer
    clearTimeout(longPressTimer);
    if (!swipeState) return;
    // Если long-press уже fired — не делаем swipe-action
    if (longPressFired) {
      swipeState.row.classList.remove('swiping');
      swipeState = null;
      return;
    }
    const { row, content, dx, locked } = swipeState;
    row.classList.remove('swiping');
    row.removeAttribute('data-passed');
    if (locked !== 'x') {
      content.style.transform = '';
      swipeState = null;
      return;
    }
    const taskId = row.getAttribute('data-task-id');
    if (dx <= -SWIPE_THRESHOLD) {
      // Свайп влево → action из user-config (default=complete)
      const action = window.dodaySwipeConfig.left;
      window.dodayHaptic && window.dodayHaptic[action === 'complete' ? 'success' : 'medium']();
      const rect = row.getBoundingClientRect();
      const prio = row.getAttribute('data-priority') || 'p4';
      if (action === 'complete') {
        burstConfettiAt(rect.left + rect.width * 0.5, rect.top + rect.height * 0.5, prio);
      }
      row.classList.add('removed');
      commitSwipeAction(taskId, action);
      if (action === 'edit') {
        row.classList.remove('removed');
        content.style.transform = '';
      } else {
        setTimeout(() => row.remove(), 300);
      }
    } else if (dx >= SWIPE_THRESHOLD) {
      // Свайп вправо → action из user-config (default=snooze)
      const action = window.dodaySwipeConfig.right;
      window.dodayHaptic && window.dodayHaptic[action === 'complete' ? 'success' : 'medium']();
      const rect = row.getBoundingClientRect();
      const prio = row.getAttribute('data-priority') || 'p4';
      if (action === 'complete') {
        burstConfettiAt(rect.left + rect.width * 0.5, rect.top + rect.height * 0.5, prio);
      }
      row.classList.add(action === 'complete' ? 'removed' : 'snoozed');
      commitSwipeAction(taskId, action);
      if (action === 'edit') {
        row.classList.remove('removed', 'snoozed');
        content.style.transform = '';
      } else {
        setTimeout(() => row.remove(), 300);
      }
    } else {
      // Cancel — spring back
      content.style.transform = '';
    }
    swipeState = null;
  }

  document.addEventListener('touchstart', onTouchStart, { passive: true });
  document.addEventListener('touchmove', onTouchMove, { passive: false });
  document.addEventListener('touchend', onTouchEnd, { passive: true });
  document.addEventListener('touchcancel', onTouchEnd, { passive: true });

  // 8.5. Week-swipe для /miniapp/calendar — горизонтальный свайп на
  //      контейнере с data-week-swipeable переключает неделю.
  let weekSwipe = null;
  function onWeekStart(e) {
    const container = e.target.closest('[data-week-swipeable]');
    if (!container) return;
    const t = e.touches[0];
    weekSwipe = { container, startX: t.clientX, startY: t.clientY };
  }
  function onWeekMove(e) {
    if (!weekSwipe) return;
    const t = e.touches[0];
    const dx = t.clientX - weekSwipe.startX;
    const dy = t.clientY - weekSwipe.startY;
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 10) {
      weekSwipe.dx = dx;
    }
  }
  function onWeekEnd() {
    if (!weekSwipe || weekSwipe.dx === undefined) { weekSwipe = null; return; }
    const { container, dx } = weekSwipe;
    weekSwipe = null;
    const TH = 60;
    if (dx <= -TH) {
      const nxt = container.getAttribute('data-next-week');
      if (nxt) {
        window.dodayHaptic && window.dodayHaptic.light();
        window.location.href = '/miniapp/calendar?date=' + nxt;
      }
    } else if (dx >= TH) {
      const prv = container.getAttribute('data-prev-week');
      if (prv) {
        window.dodayHaptic && window.dodayHaptic.light();
        window.location.href = '/miniapp/calendar?date=' + prv;
      }
    }
  }
  document.addEventListener('touchstart', onWeekStart, { passive: true });
  document.addEventListener('touchmove', onWeekMove, { passive: true });
  document.addEventListener('touchend', onWeekEnd, { passive: true });

  // 8. Tap-on-checkbox — toggle complete (без свайпа, для desktop/удобства)
  // 9. Tap-on-task-content — открыть task-sheet (МB4)
  document.addEventListener('click', async (e) => {
    const checkboxBtn = e.target.closest('[data-task-toggle]');
    if (checkboxBtn) {
      e.preventDefault();
      const taskId = checkboxBtn.getAttribute('data-task-toggle');
      const row = checkboxBtn.closest('[data-task-id]');
      const rect = checkboxBtn.getBoundingClientRect();
      const prio = row && row.getAttribute('data-priority') || 'p4';
      // A4: pulse чекбокс перед removal.
      checkboxBtn.classList.add('pulsing');
      setTimeout(() => checkboxBtn.classList.remove('pulsing'), 350);
      burstConfettiAt(rect.left + rect.width / 2, rect.top + rect.height / 2, prio);
      window.dodayHaptic && window.dodayHaptic.success();
      // Delay row-removal чтобы pulse-animation отыграл
      setTimeout(() => {
        if (row) {
          row.classList.add('completing');
          // Force layout, then add removed
          // eslint-disable-next-line no-unused-expressions
          row.offsetHeight;
          row.classList.add('removed');
        }
      }, 200);
      await commitComplete(taskId);
      setTimeout(() => row && row.remove(), 600);
      return;
    }
    // Если клик на самой карточке (не на чекбоксе) — открыть sheet
    const taskRow = e.target.closest('[data-task-id]');
    if (taskRow && !e.target.closest('button, a, input, textarea')) {
      const taskId = taskRow.getAttribute('data-task-id');
      window.dodayHaptic && window.dodayHaptic.light();
      window.dispatchEvent(new CustomEvent('doday-open-task', {detail: {taskId}}));
    }
  });

  // B3 — Drag-to-reorder. Long-press на task-card в Inbox/Project view
  //      (где задачи в одном проекте) → захват для drag. На Today/Calendar
  //      reorder не работает (разные проекты).
  //
  //      Используем существующий long-press handler — он dispatchит
  //      'doday-open-quickactions'. Заменим логику: на view'ах с reorder
  //      возможностью long-press запускает drag, а через quick-actions
  //      sheet вынесем «Reorder» как опцию для NOT-reorderable views.
  //
  //      Простейшая активация: в Inbox/Project — есть на task-card иконка
  //      drag-handle (3 точки слева внутри swipe-content), touchstart на
  //      ней начинает drag-mode непосредственно. Не конфликтует с
  //      long-press или swipe.
  // B4 — Кастомизация swipe-actions. localStorage-only (per-device).
  //      Default: left=complete, right=snooze (как было).
  window.dodaySwipeConfig = {
    get left() { return localStorage.getItem('doday-swipe-left') || 'complete'; },
    get right() { return localStorage.getItem('doday-swipe-right') || 'snooze'; },
    set(side, action) { localStorage.setItem('doday-swipe-' + side, action); },
  };

  async function commitSwipeAction(taskId, action) {
    if (action === 'complete') return commitComplete(taskId);
    if (action === 'snooze') return commitSnooze(taskId);
    if (action === 'delete') {
      try { await fetch('/miniapp/api/tasks/' + taskId, { method: 'DELETE', credentials: 'include' }); } catch (e) {}
      return;
    }
    if (action === 'edit') {
      window.dispatchEvent(new CustomEvent('doday-open-task', {detail: {taskId}}));
      return;
    }
  }

  let dragState = null;
  function findDraggableContext(target) {
    // Поиск контейнера с задачами одного проекта (current url начинается
    // с /miniapp/inbox или /miniapp/projects/<id>).
    const path = window.location.pathname;
    if (path === '/miniapp/inbox' || path.startsWith('/miniapp/projects/')) {
      const row = target.closest('[data-task-id][data-project-id]');
      if (row) return row;
    }
    return null;
  }
  document.addEventListener('touchstart', (e) => {
    const handle = e.target.closest('[data-drag-handle]');
    if (!handle) return;
    const row = findDraggableContext(handle);
    if (!row) return;
    e.preventDefault();
    e.stopPropagation();
    // Cancel any swipe/long-press
    clearTimeout(longPressTimer);
    longPressFired = true;  // prevent swipe-end action
    if (swipeState) { swipeState.content.style.transform = ''; swipeState = null; }
    const t = e.touches[0];
    const rect = row.getBoundingClientRect();
    dragState = {
      row,
      startY: t.clientY,
      offsetY: t.clientY - rect.top,
      projectId: row.getAttribute('data-project-id'),
    };
    row.classList.add('dragging');
    document.body.classList.add('miniapp-dragging');
    window.dodayHaptic && window.dodayHaptic.medium();
  }, { passive: false });

  document.addEventListener('touchmove', (e) => {
    if (!dragState) return;
    e.preventDefault();
    const t = e.touches[0];
    const dy = t.clientY - dragState.startY;
    dragState.row.style.transform = 'translateY(' + dy + 'px) scale(1.03) rotate(-1deg)';
    // Hit-test
    dragState.row.style.pointerEvents = 'none';
    const under = document.elementFromPoint(t.clientX, t.clientY);
    dragState.row.style.pointerEvents = '';
    const target = under && under.closest('[data-task-id]:not(.dragging)');
    if (target && target.getAttribute('data-project-id') === dragState.projectId) {
      const tRect = target.getBoundingClientRect();
      const mid = tRect.top + tRect.height / 2;
      if (t.clientY < mid) {
        target.parentNode.insertBefore(dragState.row, target);
      } else {
        target.parentNode.insertBefore(dragState.row, target.nextSibling);
      }
      const newRect = dragState.row.getBoundingClientRect();
      dragState.startY = t.clientY;
      dragState.offsetY = t.clientY - newRect.top;
      dragState.row.style.transform = 'translateY(0) scale(1.03) rotate(-1deg)';
    } else {
      // ζ K4: target пустая kanban-колонка (нет других карточек)
      const emptyCol = under && under.closest('[data-section-drop]');
      if (emptyCol && !emptyCol.contains(dragState.row)) {
        emptyCol.appendChild(dragState.row);
        const newRect = dragState.row.getBoundingClientRect();
        dragState.startY = t.clientY;
        dragState.offsetY = t.clientY - newRect.top;
        dragState.row.style.transform = 'translateY(0) scale(1.03) rotate(-1deg)';
      }
    }
    // Подсветить активную kanban-колонку
    document.querySelectorAll('.kanban-col.drag-target').forEach(c => c.classList.remove('drag-target'));
    const overCol = under && under.closest('.kanban-col');
    if (overCol) overCol.classList.add('drag-target');
  }, { passive: false });

  document.addEventListener('touchend', async () => {
    if (!dragState) return;
    const { row, projectId } = dragState;
    row.style.transform = '';
    row.classList.remove('dragging');
    document.body.classList.remove('miniapp-dragging');
    document.querySelectorAll('.kanban-col.drag-target').forEach(c => c.classList.remove('drag-target'));
    dragState = null;
    // ζ K4: если карточка осталась в другой kanban-col → PATCH section_id
    const currentCol = row.closest('[data-section-drop]');
    const taskId = row.getAttribute('data-task-id');
    if (currentCol) {
      const newSection = currentCol.getAttribute('data-section-drop') || '';
      const origSection = row.getAttribute('data-orig-section') || '';
      if (newSection !== origSection) {
        try {
          await fetch('/miniapp/api/tasks/' + taskId, {
            method: 'PATCH',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({section_id: newSection}),
            credentials: 'include',
          });
          row.setAttribute('data-orig-section', newSection);
        } catch (e) {}
      }
    }
    // Collect ordered ids в этом проекте — reorder в пределах одной section
    const siblings = Array.from(
      document.querySelectorAll('[data-task-id][data-project-id="' + projectId + '"]')
    ).map(el => el.getAttribute('data-task-id'));
    try {
      await fetch('/miniapp/api/tasks/reorder', {
        method: 'POST',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({project_id: projectId, ordered_ids: siblings}),
        credentials: 'include',
      });
      window.dodayHaptic && window.dodayHaptic.success();
    } catch (e) {}
  }, { passive: true });

  // B2 — Bulk-select mode. Активируется через двойной long-press
  //      или через кнопку (см. Today/Inbox header). Состояние в
  //      window.dodayBulk = {active, ids: Set}.
  window.dodayBulk = {
    active: false,
    ids: new Set(),
    listeners: [],
    onChange(fn) { this.listeners.push(fn); },
    _notify() { this.listeners.forEach(fn => { try { fn(this); } catch (e) {} }); },
    toggleMode() {
      this.active = !this.active;
      if (!this.active) this.ids.clear();
      this._notify();
      this._updateBar();
    },
    toggleTask(id) {
      if (this.ids.has(id)) this.ids.delete(id);
      else this.ids.add(id);
      this._notify();
      this._updateBar();
    },
    _updateBar() {
      const bar = document.getElementById('bulk-bar');
      if (!bar) return;
      if (this.active && this.ids.size > 0) {
        bar.style.transform = 'translateY(0)';
        const count = bar.querySelector('[data-bulk-count]');
        if (count) count.textContent = String(this.ids.size);
      } else {
        bar.style.transform = 'translateY(120%)';
      }
    },
    async perform(action) {
      if (this.ids.size === 0) return;
      try {
        const r = await fetch('/miniapp/api/tasks/bulk', {
          method: 'POST',
          headers: {'Content-Type':'application/json'},
          body: JSON.stringify({ids: Array.from(this.ids), action}),
          credentials: 'include',
        });
        if (r.ok) {
          window.dodayHaptic && window.dodayHaptic.success();
          this.ids.clear();
          this.active = false;
          this._notify();
          window.location.reload();
        }
      } catch (e) {}
    },
  };

  // Update task-card visuals в bulk-mode
  window.dodayBulk.onChange(state => {
    document.querySelectorAll('[data-task-id]').forEach(row => {
      const tid = row.getAttribute('data-task-id');
      row.classList.toggle('bulk-mode', state.active);
      row.classList.toggle('bulk-selected', state.ids.has(tid));
    });
  });

  // В bulk-mode tap на task-card — toggle selection (не open sheet)
  // Перехватываем перед normal click-handler через capture phase.
  document.addEventListener('click', (e) => {
    if (!window.dodayBulk.active) return;
    const row = e.target.closest('[data-task-id]');
    if (!row) return;
    // Skip clicks on buttons (toggle/etc)
    if (e.target.closest('button, a, input, textarea')) return;
    e.preventDefault();
    e.stopPropagation();
    window.dodayBulk.toggleTask(row.getAttribute('data-task-id'));
  }, true);

  // 10. Haptic на bottom-nav tab switch
  document.addEventListener('click', (e) => {
    const navLink = e.target.closest('.miniapp-nav a');
    if (navLink) window.dodayHaptic && window.dodayHaptic.light();
  });

  // 11. Pull-to-refresh — кастомный круговой spinner. P6 redesign.
  //     На pull <threshold кольцо опционально появляется на верху.
  //     При release >threshold — spinner крутится → reload.
  let pullState = null;
  const PULL_THRESHOLD = 80;
  const ptr = document.createElement('div');
  ptr.innerHTML =
    '<svg viewBox="0 0 36 36" width="28" height="28">' +
    '<circle cx="18" cy="18" r="14" fill="none" stroke="var(--surface-2)" stroke-width="3"/>' +
    '<circle id="ptr-arc" cx="18" cy="18" r="14" fill="none" stroke="var(--accent)" stroke-width="3" ' +
    'stroke-dasharray="88" stroke-dashoffset="88" stroke-linecap="round" transform="rotate(-90 18 18)"/>' +
    '</svg>';
  ptr.style.cssText =
    'position:fixed;top:8px;left:50%;transform:translate(-50%,-120%);z-index:60;' +
    'width:44px;height:44px;border-radius:50%;background:var(--bg);' +
    'box-shadow:0 4px 12px rgba(0,0,0,0.25);display:flex;align-items:center;justify-content:center;' +
    'transition:transform .18s ease, opacity .18s ease;pointer-events:none;opacity:0;';
  document.body.appendChild(ptr);
  const ptrArc = () => ptr.querySelector('#ptr-arc');

  document.addEventListener('touchstart', (e) => {
    if (window.scrollY > 0) return;
    if (e.target.closest('.swipe-row, [data-week-swipeable], textarea, input')) return;
    pullState = { y0: e.touches[0].clientY };
  }, { passive: true });

  document.addEventListener('touchmove', (e) => {
    if (!pullState) return;
    const dy = e.touches[0].clientY - pullState.y0;
    if (dy <= 0) return;
    pullState.dy = dy;
    const pct = Math.min(1, dy / PULL_THRESHOLD);
    const ty = -120 + pct * 140;  // -120% → +20%
    ptr.style.transform = 'translate(-50%, ' + ty + '%)';
    ptr.style.opacity = String(pct);
    // Arc dashoffset 88 → 0 by pct
    const arc = ptrArc();
    if (arc) arc.setAttribute('stroke-dashoffset', String(88 * (1 - pct)));
  }, { passive: true });

  document.addEventListener('touchend', () => {
    if (!pullState) return;
    const { dy } = pullState;
    pullState = null;
    if (dy && dy >= PULL_THRESHOLD) {
      window.dodayHaptic && window.dodayHaptic.medium();
      // Spin animation
      const arc = ptrArc();
      if (arc) {
        arc.style.transition = 'none';
        ptr.style.animation = 'spin 0.6s linear infinite';
      }
      setTimeout(() => window.location.reload(), 200);
    } else {
      ptr.style.transform = 'translate(-50%, -120%)';
      ptr.style.opacity = '0';
    }
  }, { passive: true });

  // Expose для отладки
  window.tg = tg;
})();
"""
