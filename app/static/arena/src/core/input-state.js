/**
 * InputState — чистая структура состояния ввода без слушателей событий.
 * Слушатели навешивают другие модули (touch.js, keyboard-модуль и т.д.).
 */

/** Имена кнопок, используемых в игре. */
const BUTTON_NAMES = [
  'fire',
  'aim',
  'jump',
  'crouch',
  'sprint',
  'reload',
  'interact',
];

/** Предел нормализации осей движения. */
const AXIS_LIMIT = 1;

/**
 * Создаёт объект кнопки.
 * @returns {{pressed: boolean, justPressed: boolean}}
 */
function makeButton() {
  return { pressed: false, justPressed: false };
}

export class InputState {
  constructor() {
    /** @type {{x: number, y: number}} Ось движения, -1..1 (y — вперёд/назад). */
    this.move = { x: 0, y: 0 };

    /** @type {{x: number, y: number}} Накопленная дельта взгляда за кадр. */
    this.look = { x: 0, y: 0 };

    /** @type {Object<string, {pressed: boolean, justPressed: boolean}>} */
    this.buttons = {};
    for (const name of BUTTON_NAMES) {
      this.buttons[name] = makeButton();
    }
  }

  /**
   * Устанавливает состояние кнопки.
   * @param {string} name — имя кнопки (fire, aim, jump и т.д.).
   * @param {boolean} down — true при нажатии, false при отпускании.
   */
  setButton(name, down) {
    const button = this.buttons[name];
    if (!button) return;
    if (down && !button.pressed) {
      button.justPressed = true;
    }
    button.pressed = down;
  }

  /**
   * Устанавливает ось движения с клампом в -1..1.
   * @param {number} x — стрейф (-1 влево, 1 вправо).
   * @param {number} y — вперёд/назад (1 вперёд).
   */
  setMove(x, y) {
    this.move.x = Math.max(-AXIS_LIMIT, Math.min(AXIS_LIMIT, x));
    this.move.y = Math.max(-AXIS_LIMIT, Math.min(AXIS_LIMIT, y));
  }

  /**
   * Добавляет дельту взгляда за текущий кадр.
   * @param {number} dx — дельта по yaw (радианы в нормированном виде пиксельной дельты).
   * @param {number} dy — дельта по pitch.
   */
  addLook(dx, dy) {
    this.look.x += dx;
    this.look.y += dy;
  }

  /** Сбрасывает конец кадра: затирает justPressed и обнуляет look. */
  endFrame() {
    for (const name of BUTTON_NAMES) {
      this.buttons[name].justPressed = false;
    }
    this.look.x = 0;
    this.look.y = 0;
  }

  /**
   * Статическое определение тач-устройства.
   * @returns {boolean}
   */
  static get isTouch() {
    return (
      typeof window !== 'undefined' &&
      ('ontouchstart' in window || navigator.maxTouchPoints > 0)
    );
  }

  // Удобные геттеры для прямого доступа к кнопкам
  get fire() { return this.buttons.fire; }
  get aim() { return this.buttons.aim; }
  get jump() { return this.buttons.jump; }
  get crouch() { return this.buttons.crouch; }
  get sprint() { return this.buttons.sprint; }
  get reload() { return this.buttons.reload; }
  get interact() { return this.buttons.interact; }
}
