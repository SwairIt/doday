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

  // 6. BackButton — биндится автоматически если у элемента есть data-back-handler
  document.addEventListener('alpine:init', () => {});
  if (window.history.length > 1 && window.location.pathname !== '/miniapp/') {
    tg.BackButton.show();
    tg.BackButton.onClick(() => window.history.back());
  }

  // Expose для отладки
  window.tg = tg;
})();
"""
