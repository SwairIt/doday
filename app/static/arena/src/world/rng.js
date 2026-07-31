/**
 * Детерминированный генератор псевдослучайных чисел (mulberry32).
 * Чистые функции, без зависимостей. Используется для генерации города,
 * разброса оружия и любых мест, где нужна воспроизводимость по сиду.
 */

/** Начальный сид по умолчанию, если передан не число/не конечное число. */
const DEFAULT_SEED = 0x9e3779b9;
/** Множитель mulberry32 (`>>> 0` гарантирует uint32). */
const MULBERRY32_MUL = 0x6d2b79f5;
/** Константы финального перемешивания (finalizer из murmur3). */
const SHIFT_A = 15;
const SHIFT_B = 13;
const SHIFT_C = 16;
const MIX_MUL_1 = 0x2c1b3c6d;
const MIX_MUL_2 = 0x297a2d39;
/** Нормализатор uint32 -> [0, 1). */
const UINT32_TO_FLOAT = 1 / 4294967296;

/**
 * Нормализует сид в uint32.
 * @param {number} seed
 * @returns {number}
 */
function normalizeSeed(seed) {
  if (!Number.isFinite(seed)) return DEFAULT_SEED;
  return seed >>> 0;
}

/**
 * Создаёт функцию mulberry32: каждая итерация смешивает состояние,
 * возвращает float в [0, 1). Детерминирована по сиду.
 * @param {number} seed начальное значение
 * @returns {() => number} функция random() -> [0, 1)
 */
export function mulberry32(seed) {
  let state = normalizeSeed(seed);
  return function random() {
    state = (state + MULBERRY32_MUL) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> SHIFT_A), MIX_MUL_1);
    t = Math.imul(t ^ (t >>> SHIFT_B), MIX_MUL_2);
    t ^= t >>> SHIFT_C;
    return (t >>> 0) * UINT32_TO_FLOAT;
  };
}

/**
 * Высокоуровневый ГПСЧ с удобными помощниками.
 * @param {number} seed начальное значение
 * @returns {{random: () => number, range: (min: number, max: number) => number,
 *   int: (min: number, max: number) => number, pick: <T>(array: readonly T[]) => T,
 *   chance: (p: number) => boolean}}
 */
export function createRng(seed) {
  const random = mulberry32(seed);

  /**
   * Случайное число в [min, max).
   * @param {number} min
   * @param {number} max
   * @returns {number}
   */
  function range(min, max) {
    return min + (max - min) * random();
  }

  /**
   * Случайное целое в [min, max] включительно.
   * @param {number} min
   * @param {number} max
   * @returns {number}
   */
  function int(min, max) {
    return min + Math.floor(random() * (max - min + 1));
  }

  /**
   * Случайный элемент массива. Пустой массив -> undefined.
   * @template T
   * @param {readonly T[]} array
   * @returns {T}
   */
  function pick(array) {
    return array[int(0, array.length - 1)];
  }

  /**
   * Истина с вероятностью p (p клампится в [0, 1]).
   * @param {number} p вероятность от 0 до 1
   * @returns {boolean}
   */
  function chance(p) {
    return random() < Math.min(Math.max(p, 0), 1);
  }

  return { random, range, int, pick, chance };
}
