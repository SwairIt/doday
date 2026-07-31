// src/ui/touch.js — тач-управление поверх canvas: виртуальные стики и кнопки.
// Рисуется в DOM (не в WebGL), multi-touch по identifier, safe-area учитывается.

import { bus } from '../core/events.js';

// ---------- Константы геометрии и поведения ----------
const STICK_RADIUS_PX = 64;           // радиус внешнего кольца стика
const STICK_KNOB_RADIUS_PX = 28;      // радиус бегунка
const STICK_DEAD_ZONE = 0.12;         // мёртвая зона (доля от радиуса)
const LOOK_SENSITIVITY_K = 0.0045;    // рад на пиксель свайпа по области обзора
const BUTTON_SIZE_PX = 68;            // диаметр круглой кнопки
const FIRE_BUTTON_SIZE_PX = 84;       // огонь — крупнее остальных
const EDGE_MARGIN_PX = 24;            // отступ от краёв (сверх safe-area)
const DOUBLE_TAP_MS = 280;            // окно двойного тапа (не используется для fire)
const TOUCH_DETECT_EVENT = 'touchstart';
const PI_HALF_LOOK_CLAMP = 0;         // оглядку клампит camera, тут только дельты

// Действия кнопок — имена должны совпадать с Input.setAction
const BTN_DEFS = [
    { action: 'fire',   label: 'ОГОНЬ', size: FIRE_BUTTON_SIZE_PX, right: EDGE_MARGIN_PX + 8,  bottom: EDGE_MARGIN_PX + 96 },
    { action: 'aim',    label: 'ПРИЦ',  size: BUTTON_SIZE_PX,      right: EDGE_MARGIN_PX + 96, bottom: EDGE_MARGIN_PX + 40 },
    { action: 'jump',   label: 'ПРЫЖ',  size: BUTTON_SIZE_PX,      right: EDGE_MARGIN_PX + 12, bottom: EDGE_MARGIN_PX + 200 },
    { action: 'reload', label: 'ПЕРЕЗ', size: BUTTON_SIZE_PX,      right: EDGE_MARGIN_PX + 104, bottom: EDGE_MARGIN_PX + 128 },
];

/**
 * Проверка наличия тачскрина.
 * @returns {boolean}
 */
function isTouchDevice() {
    return (typeof window !== 'undefined') &&
        (('ontouchstart' in window) || (navigator.maxTouchPoints > 0));
}

/**
 * Создаёт DOM-элемент с базовыми стилями-константами (без inline-каша классов,
 * стилей немного, проще держать в JS, чтобы не тянуть CSS-файл).
 * @param {string} tag
 * @param {Partial<CSSStyleDeclaration>} style
 * @param {HTMLElement} parent
 * @returns {HTMLElement}
 */
function el(tag, style, parent) {
    const node = document.createElement(tag);
    Object.assign(node.style, style);
    parent.appendChild(node);
    return node;
}

/**
 * Создаёт тач-контролы. На устройствах без тача управляющие элементы не создаются вообще,
 * но API {show, hide, destroy} остаётся валидным.
 * @param {HTMLElement} container — контейнер поверх canvas (position:relative у родителя).
 * @param {import('../core/input.js').Input} input — вход, куда пишем состояние.
 * @returns {{show: function(): void, hide: function(): void, destroy: function(): void}}
 */
export function createTouchControls(container, input) {
    const touchAvailable = isTouchDevice();

    /** @type {HTMLElement|null} */
    let root = null;

    /** Активные пальцы: identifier -> роль. */
    const touches = {
        moveId: -1,       // палец левого стика
        lookId: -1,       // палец области обзора
        moveOriginX: 0,
        moveOriginY: 0,
        lookLastX: 0,
        lookLastY: 0,
        /** @type {Map<number, string>} action-кнопки: identifier -> action */
        buttons: new Map(),
        /** последняя фаза движения для each-frame чтения */
        moveX: 0,
        moveY: 0,
    };

    // Ссылки на DOM стика (создаются лениво ниже)
    let stickBase = null;
    let stickKnob = null;

    /** @type {Array<{node: HTMLElement, action: string, setVisual: function(boolean): void}>} */
    const buttonNodes = [];

    // ---------- Обработчики ----------

    /**
     * Находит кнопку под точкой касания (для touchstart — по target,
     * для надёжности ищем по closest('[data-action]')).
     * @param {Touch} t
     * @returns {{node: HTMLElement, action: string, setVisual: function(boolean): void}|null}
     */
    function buttonAt(t) {
        const node = document.elementFromPoint(t.clientX, t.clientY);
        if (!node) return null;
        const holder = node.closest('[data-action]');
        if (!holder) return null;
        for (let i = 0; i < buttonNodes.length; i++) {
            if (buttonNodes[i].node === holder) return buttonNodes[i];
        }
        return null;
    }

    /**
     * Обновляет состояние движения в Input по текущему вектору стика.
     */
    function applyMove() {
        input.setMoveAxis(touches.moveX, touches.moveY);
    }

    /**
     * Сбрасывает палец движения.
     */
    function resetMove() {
        touches.moveId = -1;
        touches.moveX = 0;
        touches.moveY = 0;
        if (stickKnob) {
            stickKnob.style.transform = 'translate(-50%, -50%)';
        }
        if (stickBase) stickBase.style.opacity = '0.35';
        applyMove();
    }

    /**
     * Обработчик touchstart.
     * @param {TouchEvent} e
     */
    function onTouchStart(e) {
        e.preventDefault();
        const halfW = window.innerWidth * 0.5;
        for (let i = 0; i < e.changedTouches.length; i++) {
            const t = e.changedTouches[i];

            // Кнопки имеют приоритет
            const btn = buttonAt(t);
            if (btn) {
                touches.buttons.set(t.identifier, btn.action);
                btn.setVisual(true);
                input.setAction(btn.action, true);
                bus.emit('touch:button', btn.action);
                continue;
            }

            if (t.clientX < halfW) {
                // Левая половина — стик движения
                if (touches.moveId === -1) {
                    touches.moveId = t.identifier;
                    touches.moveOriginX = t.clientX;
                    touches.moveOriginY = t.clientY;
                    if (stickBase) {
                        stickBase.style.left = `${t.clientX}px`;
                        stickBase.style.top = `${t.clientY}px`;
                        stickBase.style.opacity = '0.85';
                    }
                }
            } else {
                // Правая половина — обзор
                if (touches.lookId === -1) {
                    touches.lookId = t.identifier;
                    touches.lookLastX = t.clientX;
                    touches.lookLastY = t.clientY;
                }
            }
        }
    }

    /**
     * Обработчик touchmove.
     * @param {TouchEvent} e
     */
    function onTouchMove(e) {
        e.preventDefault();
        for (let i = 0; i < e.changedTouches.length; i++) {
            const t = e.changedTouches[i];
            const id = t.identifier;

            if (id === touches.moveId) {
                let dx = (t.clientX - touches.moveOriginX) / STICK_RADIUS_PX;
                let dy = (t.clientY - touches.moveOriginY) / STICK_RADIUS_PX;
                const len = Math.hypot(dx, dy);
                if (len > 1) { dx /= len; dy /= len; }
                // Мёртвая зона
                const mag = Math.hypot(dx, dy);
                if (mag < STICK_DEAD_ZONE) {
                    dx = 0; dy = 0;
                }
                touches.moveX = dx;
                // Вперёд — палец вверх (y инвертирован)
                touches.moveY = -dy;
                if (stickKnob) {
                    stickKnob.style.transform =
                        `translate(calc(-50% + ${dx * STICK_RADIUS_PX}px), calc(-50% + ${dy * STICK_RADIUS_PX}px))`;
                }
                applyMove();
            } else if (id === touches.lookId) {
                const dx = t.clientX - touches.lookLastX;
                const dy = t.clientY - touches.lookLastY;
                touches.lookLastX = t.clientX;
                touches.lookLastY = t.clientY;
                input.addLookDelta(dx * LOOK_SENSITIVITY_K, dy * LOOK_SENSITIVITY_K);
            }
        }
    }

    /**
     * Обработчик touchend / touchcancel.
     * @param {TouchEvent} e
     */
    function onTouchEnd(e) {
        for (let i = 0; i < e.changedTouches.length; i++) {
            const t = e.changedTouches[i];
            const id = t.identifier;

            if (id === touches.moveId) {
                resetMove();
            } else if (id === touches.lookId) {
                touches.lookId = -1;
            } else if (touches.buttons.has(id)) {
                const action = touches.buttons.get(id);
                touches.buttons.delete(id);
                input.setAction(action, false);
                for (let b = 0; b < buttonNodes.length; b++) {
                    if (buttonNodes[b].action === action) buttonNodes[b].setVisual(false);
                }
            }
        }
    }

    // ---------- Построение DOM ----------

    /**
     * Строит дерево контролов.
     */
    function build() {
        // Корень: покрывает весь экран, центр не перекрыт — там полупрозрачный
        // слой только перехватывает тачи для стика/обзора, указательные события мышью не блок        //ирует (pointer-events: none на центральной зоне обеспечивается тем,
        // что сам root — пустой слой, события ловим через touchstart на нём).
        root = document.createElement('div');
        root.id = 'touch-controls';
        root.style.cssText = `
            position: fixed;
            inset: 0;
            z-index: 50;
            display: none;
            touch-action: none;
            -webkit-user-select: none;
            user-select: none;
            pointer-events: none;
            font-family: system-ui, sans-serif;
        `;

        // Слой-перехватчик касаний (без визуала, только события).
        const catcher = document.createElement('div');
        catcher.style.cssText = `
            position: absolute;
            inset: 0;
            pointer-events: auto;
        `;
        root.appendChild(catcher);

        // ---- Левый стик движения (появляется под пальцем) ----
        stickBase = document.createElement('div');
        stickBase.style.cssText = `
            position: absolute;
            width: ${STICK_RADIUS_PX * 2}px;
            height: ${STICK_RADIUS_PX * 2}px;
            margin-left: -${STICK_RADIUS_PX}px;
            margin-top: -${STICK_RADIUS_PX}px;
            border-radius: 50%;
            border: 2px solid rgba(255, 255, 255, 0.6);
            background: rgba(255, 255, 255, 0.08);
            opacity: 0.35;
            left: 20%;
            top: 75%;
            pointer-events: none;
        `;
        stickKnob = document.createElement('div');
        stickKnob.style.cssText = `
            position: absolute;
            left: 50%;
            top: 50%;
            width: ${KNOB_SIZE_PX}px;
            height: ${KNOB_SIZE_PX}px;
            border-radius: 50%;
            background: rgba(255, 255, 255, 0.55);
            transform: translate(-50%, -50%);
        `;
        stickBase.appendChild(stickKnob);
        root.appendChild(stickBase);

        // ---- Кнопки справа ----
        const btnsWrap = document.createElement('div');
        btnsWrap.style.cssText = `
            position: absolute;
            right: max(16px, env(safe-area-inset-right));
            bottom: max(20px, env(safe-area-inset-bottom));
            display: grid;
            grid-template-columns: repeat(2, ${BUTTON_SIZE_PX}px);
            gap: ${BUTTON_GAP_PX}px;
            pointer-events: none;
        `;
        root.appendChild(btnsWrap);

        /** Создаёт круглую кнопку действия. */
        function makeButton(action, label, color) {
            const node = document.createElement('div');
            node.dataset.action = action;
            node.textContent = label;
            node.style.cssText = `
                width: ${BUTTON_SIZE_PX}px;
                height: ${BUTTON_SIZE_PX}px;
                border-radius: 50%;
                background: ${color};
                border: 2px solid rgba(255, 255, 255, 0.65);
                color: #fff;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.05em;
                pointer-events: auto;
                opacity: 0.8;
            `;
            const setVisual = (pressed) => {
                node.style.opacity = pressed ? '1' : '0.8';
                node.style.transform = pressed ? 'scale(0.92)' : 'scale(1)';
            };
            btnsWrap.appendChild(node);
            buttonNodes.push({ node, action, setVisual });
        }

        makeButton('fire', 'FIRE', 'rgba(220, 60, 50, 0.45)');
        makeButton('aim', 'AIM', 'rgba(70, 120, 220, 0.45)');
        makeButton('jump', 'JUMP', 'rgba(80, 190, 90, 0.45)');
        makeButton('reload', 'RLD', 'rgba(200, 150, 50, 0.45)');

        // Fire — крупнее и выше остальных: переносим в удобное место
        // (первый элемент сетки уже справа внизу — оставляем компактную сетку).

        container.appendChild(root);

        // Слушатели на catcher: полная поверхность, мультитач
        root.addEventListener('touchstart', onTouchStart, { passive: false });
        root.addEventListener('touchmove', onTouchMove, { passive: false });
        root.addEventListener('touchend', onTouchEnd, { passive: false });
        root.addEventListener('touchcancel', onTouchEnd, { passive: false });
    }

    /**
     * Уничтожает DOM и слушатели.
     */
    function destroy() {
        if (!root) return;
        root.removeEventListener('touchstart', onTouchStart);
        root.removeEventListener('touchmove', onTouchMove);
        root.removeEventListener('touchend', onTouchEnd);
        root.removeEventListener('touchcancel', onTouchEnd);
        root.remove();
        root = null;
        stickBase = null;
        stickKnob = null;
        buttonNodes.length = 0;
        resetMove();
        bus.emit('touch:destroyed');
    }

    /** Показывает контролы. */
    function show() {
        if (!root) build();
        if (root) root.style.display = 'block';
        visible = true;
        bus.emit('touch:shown');
    }

    /** Скрывает контролы и сбрасывает состояние ввода. */
    function hide() {
        if (root) root.style.display = 'none';
        visible = false;
        resetMove();
        // Сброс зажатых кнопок, чтобы не "залипали"
        for (const [, action] of touches.buttons) {
            input.setAction(action, false);
        }
        touches.buttons.clear();
        bus.emit('touch:hidden');
    }

    // Не создаём контролы на устройствах без тача
    if (isTouchDevice()) {
        build();
        // Изначально скрыты — Game решит, когда показать
        if (root) root.style.display = 'none';
    }

    /**
     * @typedef {Object} TouchControls
     * @property {() => void} show
     * @property {() => void} hide
     * @property {() => void} destroy
     */

    /** @type {TouchControls} */
    return { show, hide, destroy };
}
