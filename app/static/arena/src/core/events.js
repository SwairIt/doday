// src/core/events.js — минимальная шина событий для Doday Arena.
// Не зависит от three.js / rapier, используется всеми модулями игры.

/**
 * Шина событий с защитой от исключений в подписчиках.
 * Хранит обработчики в Map<имя, Set<функция>>, так что off работает за O(1)
 * и повторная подписка одной и той же функции не создаёт дубликата.
 */
export class EventBus {
  constructor() {
    /** @type {Map<string, Set<Function>>} */
    this._handlers = new Map();
  }

  /**
   * Подписать обработчик на событие.
   * @param {string} name — имя события.
   * @param {Function} fn — обработчик вида (payload) => void.
   * @returns {Function} функция-отписка (удобно для useEffect-подобного кода).
   */
  on(name, fn) {
    if (typeof fn !== 'function') {
      throw new TypeError(`EventBus.on: обработчик события "${name}" должен быть функцией`);
    }
    let set = this._handlers.get(name);
    if (set === undefined) {
      set = new Set();
      this._handlers.set(name, set);
    }
    set.add(fn);
    return () => this.off(name, fn);
  }

  /**
   * Отписать обработчик от события.
   * @param {string} name — имя события.
   * @param {Function} fn — та же ссылка на функцию, что передавалась в on().
   */
  off(name, fn) {
    const set = this._handlers.get(name);
    if (set === undefined) return;
    set.delete(fn);
    if (set.size === 0) {
      this._handlers.delete(name);
    }
  }

  /**
   * Подписать одноразовый обработчик: сработает не более одного раза.
   * @param {string} name — имя события.
   * @param {Function} fn — обработчик вида (payload) => void.
   * @returns {Function} функция-отписка.
   */
  once(name, fn) {
    // Обёртку сохраняем на оригинале, чтобы off(name, fn) тоже отписывал once-подписку.
    const wrapped = (payload) => {
      this.off(name, wrapped);
      fn(payload);
    };
    Object.defineProperty(wrapped, '__originalHandler', { value: fn });
    return this.on(name, wrapped);
  }

  /**
   * Испустить событие: вызвать всех подписчиков с payload.
   * Исключение в одном обработчике логируется, но не прерывает остальные.
   * @param {string} name — имя события.
   * @param {*} [payload] — произвольные данные события.
   */
  emit(name, payload) {
    const set = this._handlers.get(name);
    if (set === undefined) return;
    // Копия массива нужна, чтобы обработчик мог отписаться прямо во время emit
    // (например, наш once-обёртник) без влияния на проход итерации.
    const snapshot = Array.from(set);
    for (let i = 0; i < snapshot.length; i++) {
      try {
        snapshot[i](payload);
      } catch (err) {
        // Упавший подписчик не должен ломать остальные обработчики и игровой цикл.
        console.error(`EventBus: исключение в обработчике события "${name}"`, err);
      }
    }
  }

  /**
   * Снять все подписки (со всех событий или только с одного).
   * @param {string} [name] — если передано, чистится только это событие.
   */
  clear(name) {
    if (name === undefined) {
      this._handlers.clear();
    } else {
      this._handlers.delete(name);
    }
  }
}

/** Глобальный экземпляр шины — общий для всех модулей игры. */
export const bus = new EventBus();
