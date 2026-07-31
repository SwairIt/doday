/**
 * src/core/loop.js
 * Игровой цикл с фиксированным шагом физики и переменным рендером.
 * Реализует паттерн «accumulator»: физика всегда тикает с шагом step,
 * рендер получает alpha для интерполяции между физическими состояниями.
 */

/** Максимальная длительность одного кадра (с) — защита от «spiral of death». */
const MAX_FRAME_TIME = 0.25;
/** Коэффициент сглаживания счётчика FPS (экспоненциальное скользящее среднее). */
const FPS_SMOOTHING = 0.1;
/** Минимальное значение интерполяционного коэффициента. */
const ALPHA_MIN = 0;
/** Максимальное значение интерполяционного коэффициента. */
const ALPHA_MAX = 1;

export class Loop {
  /**
   * @param {Object} [options]
   * @param {number} [options.step=1/60] — фиксированный шаг физики в секундах.
   * @param {number} [options.maxSubSteps=5] — максимум физических шагов за кадр.
   */
  constructor({ step = 1 / 60, maxSubSteps = 5 } = {}) {
    /** @type {number} Фиксированный шаг физики (с). */
    this.step = step;
    /** @type {number} Лимит физических подшагов на один рендер-кадр. */
    this.maxSubSteps = maxSubSteps;

    /** @type {number} Сглаженный FPS, обновляется каждый кадр. */
    this.fps = 0;
    /** @type {boolean} Идёт ли цикл. */
    this.running = false;

    /** @private Аккумулятор невыполненного времени физики (с). */
    this._accumulator = 0;
    /** @private Метка времени предыдущего кадра (мс, performance.now). */
    this._lastTime = 0;
    /** @private id requestAnimationFrame. */
    this._rafId = 0;
    /** @private Была ли пауза по смене видимости вкладки. */
    this._pausedByVisibility = false;

    /** @private Подписчики фиксированного шага. @type {Array<(dt:number)=>void>} */
    this._fixedCallbacks = [];
    /** @private Подписчики рендера. @type {Array<(alpha:number, dt:number)=>void>} */
    this._renderCallbacks = [];

    // Привязка контекста один раз — без аллокаций в цикле.
    this._tick = this._tick.bind(this);
    this._onVisibilityChange = this._onVisibilityChange.bind(this);
  }

  /**
   * Подписывает функцию на фиксированный физический шаг.
   * @param {(dt:number)=>void} fn — получает фиксированный dt (с).
   * @returns {() => void} Функция отписки.
   */
  onFixed(fn) {
    this._fixedCallbacks.push(fn);
    return () => {
      const i = this._fixedCallbacks.indexOf(fn);
      if (i !== -1) this._fixedCallbacks.splice(i, 1);
    };
  }

  /**
   * Подписывает функцию на кадр рендера.
   * @param {(alpha:number, dt:number)=>void} fn — alpha в [0..1] для интерполяции,
   *   dt — реальное время кадра (с).
   * @returns {() => void} Функция отписки.
   */
  onRender(fn) {
    this._renderCallbacks.push(fn);
    return () => {
      const i = this._renderCallbacks.indexOf(fn);
      if (i !== -1) this._renderCallbacks.splice(i, 1);
    };
  }

  /** Запускает цикл. Повторный вызов при работающем цикле — no-op. */
  start() {
    if (this.running) return;
    this.running = true;
    this._accumulator = 0;
    this._lastTime = performance.now();
    document.addEventListener('visibilitychange', this._onVisibilityChange);
    this._rafId = requestAnimationFrame(this._tick);
  }

  /** Останавливает цикл и снимает слушатель видимости. */
  stop() {
    if (!this.running) return;
    this.running = false;
    cancelAnimationFrame(this._rafId);
    document.removeEventListener('visibilitychange', this._onVisibilityChange);
  }

  /** @private Обработчик смены видимости вкладки. */
  _onVisibilityChange() {
    if (document.hidden) {
      if (this.running) {
        this._pausedByVisibility = true;
        cancelAnimationFrame(this._rafId);
      }
    } else if (this._pausedByVisibility) {
      this._pausedByVisibility = false;
      // Сбрасываем время, чтобы не накапливать «долгий кадр» после возврата.
      this._lastTime = performance.now();
      this._rafId = requestAnimationFrame(this._tick);
    }
  }

  /**
   * @private Один кадр: физика с фиксированным шагом + рендер с интерполяцией.
   * @param {number} now — метка времени rAF (мс).
   */
  _tick(now) {
    if (!this.running || this._pausedByVisibility) return;
    this._rafId = requestAnimationFrame(this._tick);

    // Реальная длительность кадра с клампом против spiral of death.
    let frameTime = (now - this._lastTime) / 1000;
    this._lastTime = now;
    if (frameTime > MAX_FRAME_TIME) frameTime = MAX_FRAME_TIME;
    if (frameTime <= 0) return;

    // Сглаженный FPS: экспоненциальное скользящее среднее.
    const instantFps = 1 / frameTime;
    this.fps = this.fps === 0
      ? instantFps
      : this.fps + (instantFps - this.fps) * FPS_SMOOTHING;

    this._accumulator += frameTime;

    // Фиксированные шаги физики; лишнее время сбрасывается по лимиту подшагов.
    let subSteps = 0;
    while (this._accumulator >= this.step && subSteps < this.maxSubSteps) {
      for (let i = 0; i < this._fixedCallbacks.length; i++) {
        this._fixedCallbacks[i](this.step);
      }
      this._accumulator -= this.step;
      subSteps++;
    }
    if (subSteps === this.maxSubSteps && this._accumulator >= this.step) {
      // Физика не успевает — сбрасываем долг, чтобы не разгонять цикл.
      this._accumulator = 0;
    }

    // Коэффициент интерполяции между последним и следующим физшагом.
    let alpha = this._accumulator / this.step;
    if (alpha < ALPHA_MIN) alpha = ALPHA_MIN;
    else if (alpha > ALPHA_MAX) alpha = ALPHA_MAX;

    for (let i = 0; i < this._renderCallbacks.length; i++) {
      this._renderCallbacks[i](alpha, frameTime);
    }
  }
}
