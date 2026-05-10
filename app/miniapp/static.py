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
      e.preventDefault();
      swipeState.dx = dx;
      swipeState.content.style.transform = 'translateX(' + dx + 'px)';
    }
  }

  async function commitComplete(taskId) {
    try {
      await fetch('/miniapp/api/tasks/' + taskId + '/complete', {
        method: 'POST', credentials: 'include',
      });
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
    if (!swipeState) return;
    const { row, content, dx, locked } = swipeState;
    row.classList.remove('swiping');
    if (locked !== 'x') {
      content.style.transform = '';
      swipeState = null;
      return;
    }
    const taskId = row.getAttribute('data-task-id');
    if (dx <= -SWIPE_THRESHOLD) {
      // Complete (свайп влево)
      window.dodayHaptic && window.dodayHaptic.success();
      row.classList.add('removed');
      commitComplete(taskId);
      setTimeout(() => row.remove(), 300);
    } else if (dx >= SWIPE_THRESHOLD) {
      // Snooze (свайп вправо)
      window.dodayHaptic && window.dodayHaptic.medium();
      row.classList.add('snoozed');
      commitSnooze(taskId);
      setTimeout(() => row.remove(), 300);
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
      if (row) row.classList.add('removed');
      window.dodayHaptic && window.dodayHaptic.success();
      await commitComplete(taskId);
      setTimeout(() => row && row.remove(), 300);
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

  // 10. Haptic на bottom-nav tab switch
  document.addEventListener('click', (e) => {
    const navLink = e.target.closest('.miniapp-nav a');
    if (navLink) window.dodayHaptic && window.dodayHaptic.light();
  });

  // 11. Pull-to-refresh — простая реализация. При пуле >80px на scrollTop=0
  //     показываем индикатор и reload'им страницу.
  let pullState = null;
  const PULL_THRESHOLD = 80;
  const indicator = document.createElement('div');
  indicator.style.cssText = 'position:fixed;top:0;left:50%;transform:translate(-50%,-100%);z-index:60;background:var(--accent);color:var(--tg-button-text);padding:8px 16px;border-radius:0 0 12px 12px;font-size:12px;font-weight:600;transition:transform .2s;pointer-events:none;';
  indicator.textContent = '⤓ Тяни ниже…';
  document.body.appendChild(indicator);

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
    indicator.style.transform = 'translate(-50%, ' + (-100 + pct * 100) + '%)';
    if (dy >= PULL_THRESHOLD) indicator.textContent = '↻ Отпусти чтобы обновить';
    else indicator.textContent = '⤓ Тяни ниже…';
  }, { passive: true });

  document.addEventListener('touchend', () => {
    if (!pullState) return;
    const { dy } = pullState;
    pullState = null;
    if (dy && dy >= PULL_THRESHOLD) {
      indicator.textContent = '↻ Обновляю…';
      window.dodayHaptic && window.dodayHaptic.medium();
      setTimeout(() => window.location.reload(), 200);
    } else {
      indicator.style.transform = 'translate(-50%, -100%)';
    }
  }, { passive: true });

  // Expose для отладки
  window.tg = tg;
})();
"""
