/**
 * @file src/core/settings.js
 * Настройки игры Doday Arena: качество графики, чувствительность, FOV, громкость.
 * Персист в localStorage, события изменения, автоопределение качества.
 */

/** Ключ хранилища localStorage */
const STORAGE_KEY = 'doday-arena-settings';

/** Границы числовых полей */
const LIMITS = Object.freeze({
  sensitivity: { min: 0.1, max: 3.0 },
  fov:         { min: 60,  max: 110 },
  volume:      { min: 0.0, max: 1.0 },
});

/** Допустимые уровни качества */
const QUALITY_LEVELS = Object.freeze(['low', 'medium', 'high']);

/**
 * Пресеты качества рендеринга.
 * shadowMapSize — размер карты теней в пикселях (0 = тени выключены),
 * maxPixelRatio — потолок devicePixelRatio,
 * postfx — включать ли пост-эффекты,
 * shadowCascades — число каскадов CSM (0 = обычная одна карта),
 * fogDensity — плотность экспоненциального тумана,
 * drawDistance — дальность отсечения камеры, метры.
 */
export const QUALITY_PRESETS = Object.freeze({
  low: Object.freeze({
    shadowMapSize: 0,
    maxPixelRatio: 1.0,
    postfx: false,
    shadowCascades: 0,
    fogDensity: 0.025,
    drawDistance: 120,
  }),
  medium: Object.freeze({
    shadowMapSize: 1024,
    maxPixelRatio: 1.5,
    postfx: false,
    shadowCascades: 1,
    fogDensity: 0.015,
    drawDistance: 220,
  }),
  high: Object.freeze({
    shadowMapSize: 2048,
    maxPixelRatio: 2.0,
    postfx: true,
    shadowCascades: 3,
    fogDensity: 0.008,
    drawDistance: 400,
  }),
});

/** Значения по умолчанию (качество подставляется после автоопределения) */
function buildDefaults() {
  return {
    quality: detectQuality(),
    sensitivity: 1.0,
    fov: 90,
    volume: 0.8,
  };
}

/**
 * Автоопределение уровня качества по железу:
 * число логических ядер, devicePixelRatio, наличие тач-скрина.
 * @returns {'low'|'medium'|'high'}
 */
function detectQuality() {
  // SSR/экзотические окружения — безопасный середнячок
  if (typeof navigator === 'undefined') return 'medium';

  const cores = navigator.hardwareConcurrency || 4;
  const dpr = (typeof window !== 'undefined' && window.devicePixelRatio) || 1;
  const hasTouch =
    (typeof window !== 'undefined' && 'ontouchstart' in window) ||
    (navigator.maxTouchPoints || 0) > 0;

  // Бюджетные мобильные устройства — всегда low
  if (hasTouch && cores <= 4) return 'low';
  // Слабый десктоп
  if (!hasTouch && cores <= 2) return 'low';
  // Мобильные помощнее или средний десктоп
  if (cores <= 6) return 'medium';
  // Мощное железо: много ядер и не задранный DPR
  if (cores >= 8 && dpr <= 2.5) return 'high';

  return 'medium';
}

/**
 * Класс настроек игры. Загружает/сохраняет в localStorage,
 * валидирует значения, уведомляет подписчиков об изменениях.
 */
export class Settings {
  constructor() {
    /** @type {Set<Function>} подписчики на изменения */
    this._listeners = new Set();

    const defaults = buildDefaults();
    const saved = this._load();

    // Сливаем поверх дефолтов только валидные сохранённые поля
    this._data = { ...defaults };
    if (saved) {
      for (const key of Object.keys(this._data)) {
        if (key in saved) {
          const value = this._sanitize(key, saved[key]);
          if (value !== undefined) this._data[key] = value;
        }
      }
    }
  }

  /**
   * Читает сохранённые настройки из localStorage.
   * @returns {Object|null}
   * @private
   */
  _load() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      return raw ? JSON.parse(raw) : null;
    } catch {
      // Повреждённый JSON или недоступное хранилище — игнорируем
      return null;
    }
  }

  /**
   * Сохраняет текущие настройки в localStorage.
   * @private
   */
  _save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(this._data));
    } catch {
      // Приватный режим / переполнение — живём без персиста
    }
  }

  /**
   * Валидирует и нормализует значение для ключа.
   * @param {string} key
   * @param {*} value
   * @returns {*} нормализованное значение или undefined, если невалидно
   * @private
   */
  _sanitize(key, value) {
    if (key === 'quality') {
      return QUALITY_LEVELS.includes(value) ? value : undefined;
    }
    const limit = LIMITS[key];
    if (limit) {
      const num = Number(value);
      if (!Number.isFinite(num)) return undefined;
      return Math.min(limit.max, Math.max(limit.min, num));
    }
    return undefined;
  }

  /**
   * Возвращает значение настройки.
   * @param {string} key
   * @returns {*}
   */
  get(key) {
    return this._data[key];
  }

  /**
   * Устанавливает настройку с валидацией, сохраняет и уведомляет подписчиков.
   * @param {string} key
   * @param {*} value
   * @returns {boolean} true, если значение применено
   */
  set(key, value) {
    if (!(key in this._data)) return false;
    const sanitized = this._sanitize(key, value);
    if (sanitized === undefined) return false;
    if (sanitized === this._data[key]) return false;

    this._data[key] = sanitized;
    this._save();
    this._emit(key, sanitized);
    return true;
  }

  /**
   * Сбрасывает все настройки к значениям по умолчанию
   * (качество определяется автоматически заново).
   */
  reset() {
    this._data = buildDefaults();
    this._save();
    this._emit('*', this._data);
  }

  /**
   * Подписывает на изменения настроек.
   * Колбэк получает (key, value); при reset key === '*', value — весь объект.
   * @param {Function} callback
   * @returns {Function} функция отписки
   */
  onChange(callback) {
    this._listeners.add(callback);
    return () => this._listeners.delete(callback);
  }

  /**
   * Уведомляет всех подписчиков.
   * @param {string} key
   * @param {*} value
   * @private
   */
  _emit(key, value) {
    for (const cb of this._listeners) {
      cb(key, value);
    }
  }

  /** @returns {'low'|'medium'|'high'} */
  get quality() { return this._data.quality; }
  set quality(v) { this.set('quality', v); }

  /** @returns {number} чувствительность мыши, 0.1..3 */
  get sensitivity() { return this._data.sensitivity; }
  set sensitivity(v) { this.set('sensitivity', v); }

  /** @returns {number} поле зрения камеры, градусы 60..110 */
  get fov() { return this._data.fov; }
  set fov(v) { this.set('fov', v); }

  /** @returns {number} громкость, 0..1 */
  get volume() { return this._data.volume; }
  set volume(v) { this.set('volume', v); }

  /**
   * Возвращает активный пресет качества.
   * @returns {Readonly<{shadowMapSize:number, maxPixelRatio:number, postfx:boolean, shadowCascades:number, fogDensity:number, drawDistance:number}>}
   */
  getQualityPreset() {
    return QUALITY_PRESETS[this._data.quality];
  }
}
