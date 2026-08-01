/**
 * @file src/core/input-trackpad.js
 * Управление под трекпад Mac: игра без мыши.
 * Режимы обзора: pointer lock со сглаживанием, двухпальцевый свайп (wheel),
 * стрелки клавиатуры. ADS — переключатель (F / Shift+клик), стрельба — ЛКМ/Пробел/J.
 */

/** Скорость взгляда со стрелок, рад/с */
// Скорость обзора стрелками в ПИКСЕЛЯХ в секунду (как если бы вели мышью).
const ARROW_LOOK_SPEED = 500;
/** Порог дельты wheel, ниже которого считаем жест двухпальцевым скроллом */
const WHEEL_SCROLL_MAX_DELTA = 40;
/** Множитель перевода wheel-дельты в радианы обзора */
// Скролл двумя пальцами приходит в «строках прокрутки» — приводим к пикселям.
const WHEEL_TO_PIXELS = 1.6;
/** Коэффициент экспоненциального сглаживания movementX/Y (0..1, больше — резче) */
const LOOK_SMOOTHING = 0.35;
/** Мёртвая зона сглаженной дельты, рад */
const LOOK_EPSILON = 0.00001;
/** Чувствительность трекпада по умолчанию (трекпад даёт меньшую дельту, чем мышь) */
const DEFAULT_TRACKPAD_SENSITIVITY = 1.8;
/** Базовый перевод пиксельной дельты в радианы */
const PIXEL_TO_RAD = 0.0022;
/** Период кадра для авто-повтора стрелок, мс */
const FRAME_MS = 1000 / 60;

/**
 * Определяет, похоже ли wheel-событие на двухпальцевый скролл трекпада.
 * @param {WheelEvent} e
 * @returns {boolean}
 */
function isTrackpadWheel(e) {
  if (e.deltaMode !== 0) return false;
  if (e.ctrlKey) return false; // pinch-zoom, не трогаем
  const small = Math.abs(e.deltaX) < WHEEL_SCROLL_MAX_DELTA &&
                Math.abs(e.deltaY) < WHEEL_SCROLL_MAX_DELTA;
  const fractional = (e.deltaX % 1 !== 0) || (e.deltaY % 1 !== 0);
  return small || fractional;
}

/**
 * Определяет платформу Mac.
 * @returns {boolean}
 */
function detectMac() {
  const uaData = navigator.userAgentData;
  if (uaData && uaData.platform) return uaData.platform.toUpperCase().includes('MAC');
  const platform = navigator.platform || '';
  return platform.toUpperCase().includes('MAC');
}

/**
 * Создаёт слой управления под трекпад поверх InputState.
 * @param {HTMLCanvasElement} canvas
 * @param {import('./settings.js').Settings} settings
 * @param {import('./input-state.js').InputState} state
 * @returns {{enabled: boolean, setEnabled(on: boolean): void, dispose(): void, isTrackpadLikely(): boolean}}
 */
export function createTrackpadInput(canvas, settings, state) {
  const api = {
    enabled: false,
    setEnabled,
    dispose,
    isTrackpadLikely,
  };

  let trackpadLikely = detectMac();
  let smoothX = 0;
  let smoothY = 0;
  let pointerCaptured = false;
  const arrows = { left: false, right: false, up: false, down: false };
  let arrowTimer = 0;

  /** Текущий множитель чувствительности трекпада. */
  function getSensitivity() {
    const raw = settings.get('trackpadSensitivity');
    const v = raw === undefined || raw === null ? DEFAULT_TRACKPAD_SENSITIVITY : Number(raw);
    return Number.isFinite(v) && v > 0 ? v : DEFAULT_TRACKPAD_SENSITIVITY;
  }

  /** Отдаёт накопленную сглаженную дельту взгляда в InputState. */
  function flushLook() {
    const outX = smoothX;
    const outY = smoothY;
    smoothX = 0;
    smoothY = 0;
    if (Math.abs(outX) < LOOK_EPSILON && Math.abs(outY) < LOOK_EPSILON) return;
    // Сырые пиксели: перевод в радианы и чувствительность — на камере.
    state.addLook(outX, outY);
  }

  function onPointerLockChange() {
    pointerCaptured = document.pointerLockElement === canvas;
  }

  function onMouseMove(e) {
    if (!api.enabled || !pointerCaptured) return;
    const sens = getSensitivity();
    // Экспоненциальный фильтр: сглаживаем рывки пальца, без ускорения — линейно
    smoothX += (e.movementX * sens - smoothX) * LOOK_SMOOTHING + e.movementX * sens * (1 - LOOK_SMOOTHING) * 0;
    smoothY += (e.movementY * sens - smoothY) * LOOK_SMOOTHING;
    flushLook();
  }

  function onWheel(e) {
    if (!isTrackpadWheel(e)) return;
    trackpadLikely = true;
    if (!api.enabled || pointerCaptured) return;
    // Двухпальцевый свайп без pointer lock — вращаем камеру
    e.preventDefault();
    const sens = getSensitivity();
    state.addLook(e.deltaX * WHEEL_TO_PIXELS, e.deltaY * WHEEL_TO_PIXELS);
  }

  function onPointerDown(e) {
    if (e.pointerType === 'touch') trackpadLikely = true;
  }

  function onMouseDown(e) {
    if (!api.enabled) return;
    if (e.button === 0) {
      state.setButton('fire', true);
      if (e.shiftKey) {
        // Shift+клик — переключатель ADS
        adsToggle = !adsToggle;
        state.setButton('aim', adsToggle);
      } else if (!pointerCaptured) {
        canvas.requestPointerLock?.();
      }
    }
  }

  function onMouseUp(e) {
    if (!api.enabled) return;
    if (e.button === 0) state.setButton('fire', false);
  }

  let adsToggle = false;

  /** Удержание ПКМ тоже работает как классический ADS. */
  function onContextMenu(e) {
    if (api.enabled) e.preventDefault();
  }

  function onAuxDown(e) {
    if (!api.enabled) return;
    if (e.button === 2 && !adsToggle) state.setButton('aim', true);
  }

  function onAuxUp(e) {
    if (!api.enabled) return;
    if (e.button === 2 && !adsToggle) state.setButton('aim', false);
  }

  function toggleAim() {
    adsToggle = !adsToggle;
    state.setButton('aim', adsToggle);
  }

  function onKeyDown(e) {
    if (!api.enabled) return;
    switch (e.code) {
      case 'KeyJ':
      case 'Enter':
        state.setButton('fire', true);
        break;
      case 'KeyF':
        if (!e.repeat) toggleAim();
        break;
      case 'ArrowLeft': arrows.left = true; e.preventDefault(); break;
      case 'ArrowRight': arrows.right = true; e.preventDefault(); break;
      case 'ArrowUp': arrows.up = true; e.preventDefault(); break;
      case 'ArrowDown': arrows.down = true; e.preventDefault(); break;
    }
  }

  function onKeyUp(e) {
    switch (e.code) {
      case 'KeyJ':
      case 'Enter':
        state.setButton('fire', false);
        break;
      case 'ArrowLeft': arrows.left = false; break;
      case 'ArrowRight': arrows.right = false; break;
      case 'ArrowUp': arrows.up = false; break;
      case 'ArrowDown': arrows.down = false; break;
    }
  }

  const ARROW_CODES = new Set(['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown']);

  /** Обзор стрелками с постоянной скоростью; null — авто-повтор не требуется. */
  let arrowLastTime = 0;

  function arrowTick() {
    if (!api.enabled) return;
    const now = performance.now();
    const elapsed = arrowLastTime ? (now - arrowLastTime) / 1000 : FRAME_MS / 1000;
    arrowLastTime = now;

    const dx = (arrows.right ? 1 : 0) - (arrows.left ? 1 : 0);
    const dy = (arrows.down ? 1 : 0) - (arrows.up ? 1 : 0);
    if (dx === 0 && dy === 0) return;

    // Шаг считаем по РЕАЛЬНО прошедшему времени, а не по номинальному кадру:
    // при низком FPS браузер схлопывает накопившиеся вызовы таймера, и по
    // константе выходил один тик вместо десятка — стрелки почти не поворачивали.
    const step = ARROW_LOOK_SPEED * Math.min(elapsed, 0.25);
    state.addLook(dx * step, dy * step);
  }

  /** Включить/выключить слой трекпада.
   * @param {boolean} on */
  function setEnabled(on) {
    if (api.enabled === on) return;
    api.enabled = on;
    if (on) {
      document.addEventListener('pointerlockchange', onPointerLockChange);
      document.addEventListener('mousemove', onMouseMove);
      canvas.addEventListener('wheel', onWheel, { passive: false });
      canvas.addEventListener('pointerdown', onPointerDown);
      document.addEventListener('mousedown', onMouseDown);
      document.addEventListener('mouseup', onMouseUp);
      document.addEventListener('mousedown', onAuxDown);
      document.addEventListener('mouseup', onAuxUp);
      canvas.addEventListener('contextmenu', onContextMenu);
      document.addEventListener('keydown', onKeyDown);
      document.addEventListener('keyup', onKeyUp);
      arrowTimer = window.setInterval(arrowTick, FRAME_MS);
    } else {
      removeAll();
      if (pointerCaptured) document.exitPointerLock?.();
    }
  }

  /** Снять все обработчики и сбросить зажатые кнопки. */
  function removeAll() {
    document.removeEventListener('pointerlockchange', onPointerLockChange);
    document.removeEventListener('mousemove', onMouseMove);
    canvas.removeEventListener('wheel', onWheel);
    canvas.removeEventListener('pointerdown', onPointerDown);
    document.removeEventListener('mousedown', onMouseDown);
    document.removeEventListener('mouseup', onMouseUp);
    document.removeEventListener('mousedown', onAuxDown);
    document.removeEventListener('mouseup', onAuxUp);
    canvas.removeEventListener('contextmenu', onContextMenu);
    document.removeEventListener('keydown', onKeyDown);
    document.removeEventListener('keyup', onKeyUp);
    if (arrowTimer) {
      window.clearInterval(arrowTimer);
      arrowTimer = 0;
    }
    state.setButton('fire', false);
    state.setButton('aim', false);
    adsToggle = false;
    arrows.left = arrows.right = arrows.up = arrows.down = false;
    smoothX = 0;
    smoothY = 0;
    pointerCaptured = false;
  }

  /** Признак вероятного трекпада (Mac-устройство или наблюдался тач-скролл).
   * @returns {boolean} */
  function isTrackpadLikely() {
    return trackpadLikely;
  }

  /** Полная очистка: выключает слой и снимает все обработчики. */
  function dispose() {
    removeAll();
    api.enabled = false;
  }

  return api;
}
