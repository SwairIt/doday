import { InputState } from './input-state.js';

/** Коды клавиш движения: WASD + стрелки. */
// Стрелки намеренно НЕ управляют движением: они работают как мышь —
// вращают камеру (см. src/core/input-trackpad.js). Движение только WASD.
const KEY_FORWARD = new Set(['KeyW']);
const KEY_BACK = new Set(['KeyS']);
const KEY_LEFT = new Set(['KeyA']);
const KEY_RIGHT = new Set(['KeyD']);
const KEY_CROUCH = new Set(['ControlLeft', 'ControlRight', 'KeyC']);

/** Множитель перевода movementX/Y в радианы взгляда (до sensitivity). */
const LOOK_SCALE = 0.0022;

/** Кнопка ЛКМ в событиях мыши. */
const MOUSE_LEFT = 0;
/** Кнопка ПКМ в событиях мыши. */
const MOUSE_RIGHT = 2;

/**
 * Создаёт обработчики клавиатуры и мыши поверх InputState.
 * Pointer lock захватывается кликом по canvas, освобождается по Esc.
 *
 * @param {HTMLCanvasElement} canvas канвас рендера
 * @param {import('./settings.js').Settings} settings настройки (sensitivity)
 * @returns {{state: InputState, dispose(): void}}
 */
export function createInput(canvas, settings) {
  const state = new InputState();

  // Текущее положение осей движения от удерживаемых клавиш.
  let axisX = 0;
  let axisY = 0;

  const pressed = new Set();

  /** Пересчитывает целевые оси по набору нажатых клавиш и пишет в state. */
  function recomputeAxes() {
    axisX = 0;
    axisY = 0;
    for (const code of pressed) {
      if (KEY_LEFT.has(code)) axisX -= 1;
      else if (KEY_RIGHT.has(code)) axisX += 1;
      else if (KEY_FORWARD.has(code)) axisY += 1;
      else if (KEY_BACK.has(code)) axisY -= 1;
    }
    state.setMove(axisX, axisY);
  }

  /** @returns {boolean} активен ли pointer lock на нашем канвасе. */
  function isLocked() {
    return document.pointerLockElement === canvas;
  }

  function onKeyDown(e) {
    if (e.repeat) return;
    const code = e.code;
    pressed.add(code);

    if (KEY_FORWARD.has(code) || KEY_BACK.has(code) ||
        KEY_LEFT.has(code) || KEY_RIGHT.has(code)) {
      recomputeAxes();
      e.preventDefault();
    } else if (code === 'Space') {
      state.setButton('jump', true);
      e.preventDefault();
    } else if (code === 'ShiftLeft' || code === 'ShiftRight') {
      state.setButton('sprint', true);
    } else if (KEY_CROUCH.has(code)) {
      state.setButton('crouch', true);
      e.preventDefault();
    } else if (code === 'KeyR') {
      state.setButton('reload', true);
    } else if (code === 'KeyE') {
      state.setButton('interact', true);
    }
  }

  function onKeyUp(e) {
    const code = e.code;
    pressed.delete(code);

    if (KEY_FORWARD.has(code) || KEY_BACK.has(code) ||
        KEY_LEFT.has(code) || KEY_RIGHT.has(code)) {
      recomputeAxes();
    } else if (code === 'Space') {
      state.setButton('jump', false);
    } else if (code === 'ShiftLeft' || code === 'ShiftRight') {
      state.setButton('sprint', false);
    } else if (KEY_CROUCH.has(code)) {
      state.setButton('crouch', false);
    } else if (code === 'KeyR') {
      state.setButton('reload', false);
    } else if (code === 'KeyE') {
      state.setButton('interact', false);
    }
  }

  /** Зажата ли левая кнопка — для поворота мышью без захвата курсора. */
  let dragging = false;

  function onMouseMove(e) {
    // Чувствительность применяет камера: сюда отдаём сырые пиксели, иначе
    // множитель накладывается дважды и поворот становится незаметным.
    if (isLocked()) {
      state.addLook(e.movementX, e.movementY);
      return;
    }
    // Без захвата курсора работает перетаскивание с зажатой кнопкой —
    // так мышь крутит камеру даже если pointer lock недоступен.
    if (dragging) {
      state.addLook(e.movementX, e.movementY);
    }
  }

  function onMouseDown(e) {
    if (!isLocked()) {
      // Клик вне лока: пробуем захват, но и без него даём играть —
      // перетаскивание с зажатой кнопкой крутит камеру, левая кнопка стреляет.
      dragging = true;
      if (e.button === MOUSE_LEFT) state.setButton('fire', true);
      const request = canvas.requestPointerLock?.();
      if (request && typeof request.catch === 'function') request.catch(() => {});
      return;
    }
    if (e.button === MOUSE_LEFT) state.setButton('fire', true);
    else if (e.button === MOUSE_RIGHT) state.setButton('aim', true);
  }

  function onMouseUp(e) {
    dragging = false;
    if (e.button === MOUSE_LEFT) state.setButton('fire', false);
    else if (e.button === MOUSE_RIGHT) state.setButton('aim', false);
  }

  function onContextMenu(e) {
    e.preventDefault();
  }

  /** При потере pointer lock отпускаем все кнопки, чтобы не «залипли». */
  function onPointerLockChange() {
    if (isLocked()) return;
    pressed.clear();
    recomputeAxes();
    state.setButton('fire', false);
    state.setButton('aim', false);
    state.setButton('jump', false);
    state.setButton('sprint', false);
    state.setButton('crouch', false);
    state.setButton('reload', false);
    state.setButton('interact', false);
  }

  window.addEventListener('keydown', onKeyDown);
  window.addEventListener('keyup', onKeyUp);
  window.addEventListener('mousemove', onMouseMove);
  canvas.addEventListener('mousedown', onMouseDown);
  window.addEventListener('mouseup', onMouseUp);
  canvas.addEventListener('contextmenu', onContextMenu);
  document.addEventListener('pointerlockchange', onPointerLockChange);

  /** Снимает все слушатели. */
  function dispose() {
    window.removeEventListener('keydown', onKeyDown);
    window.removeEventListener('keyup', onKeyUp);
    window.removeEventListener('mousemove', onMouseMove);
    canvas.removeEventListener('mousedown', onMouseDown);
    window.removeEventListener('mouseup', onMouseUp);
    canvas.removeEventListener('contextmenu', onContextMenu);
    document.removeEventListener('pointerlockchange', onPointerLockChange);
  }

  return { state, dispose };
}
