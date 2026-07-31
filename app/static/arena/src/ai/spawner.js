import * as THREE from 'three';
import { createBot } from './bot.js';
import { bus } from '../core/events.js';

/** Максимум одновременно живых ботов по уровню качества */
const MAX_ALIVE = { low: 6, medium: 10, high: 16 };
/** Минимальная дистанция спавна от игрока, м */
const MIN_SPAWN_DIST = 25;
/** Квадрат минимальной дистанции — для сравнения без sqrt */
const MIN_SPAWN_DIST_SQ = MIN_SPAWN_DIST * MIN_SPAWN_DIST;
/** Угол обзора игрока, половина (рад) — точки внутри конуса считаются видимыми */
const HALF_FOV_RAD = Math.PI * 0.55;
/** Пауза между попытками подспавна, с */
const RESPAWN_INTERVAL = 1.5;
/** Высота точки спавна, м */
const SPAWN_Y = 0;

// Модульные временные — без аллокаций в горячем цикле
const _tmpForward = new THREE.Vector3();
const _tmpDir = new THREE.Vector3();
const _tmpPos = new THREE.Vector3();

/**
 * Создаёт менеджер популяции ботов.
 * @param {THREE.Scene} scene
 * @param {object} world физический мир Rapier
 * @param {THREE.Vector3[]} spawnPoints точки спавна
 * @param {{settings: import('../core/settings.js').Settings}} deps
 */
export function createSpawner(scene, world, spawnPoints, deps) {
  const settings = deps.settings;
  /** Пул ботов (живых и ожидающих) */
  const pool = [];
  let alive = 0;
  let killed = 0;
  let respawnTimer = 0;

  /** Максимум живых для текущего качества */
  function maxAlive() {
    const q = settings.quality;
    return MAX_ALIVE[q] !== undefined ? MAX_ALIVE[q] : MAX_ALIVE.low;
  }

  /**
   * Косинус половины угла обзора (учитываем fov из настроек, но не меньше константы).
   * @param {number} fovDeg вертикальный fov камеры в градусах
   */
  function fovCos(fovDeg) {
    const h = Math.max(fovDeg * 0.5, HALF_FOV_RAD * 180 / Math.PI * 0.9) * Math.PI / 180;
    return Math.cos(h);
  }

  /**
   * Видно ли точку из позиции игрока с направлением взгляда.
   * @param {THREE.Vector3} point
   * @param {THREE.Vector3} playerPos
   * @param {THREE.Vector3} forward нормализованный вектор взгляда
   * @param {number} cosLimit
   */
  function inView(point, playerPos, forward, cosLimit) {
    _tmpDir.subVectors(point, playerPos);
    _tmpDir.y = 0;
    const lenSq = _tmpDir.lengthSq();
    if (lenSq < 1e-6) return true;
    return _tmpDir.divideScalar(Math.sqrt(lenSq)).dot(forward) > cosLimit;
  }

  /**
   * Найти валидную точку спавна: дальше MIN_SPAWN_DIST и вне конуса зрения.
   * @returns {THREE.Vector3|null}
   */
  function pickSpawnPoint(playerPos, forward, cosLimit) {
    const n = spawnPoints.length;
    if (n === 0) return null;
    // случайный стартовый индекс, чтобы не отдавать предпочтение началу массива
    const start = (Math.random() * n) | 0;
    let fallback = null; // дальняя точка, видимая — на крайний случай
    for (let i = 0; i < n; i++) {
      const p = spawnPoints[(start + i) % n];
      _tmpPos.set(p.x, SPAWN_Y, p.z);
      _tmpDir.subVectors(_tmpPos, playerPos);
      _tmpDir.y = 0;
      if (_tmpDir.lengthSq() < MIN_SPAWN_DIST_SQ) continue;
      if (inView(_tmpPos, playerPos, forward, cosLimit)) {
        if (fallback === null) fallback = p;
        continue;
      }
      return p;
    }
    return fallback;
  }

  /**
   * Взять мёртвого бота из пула или создать нового.
   */
  function acquireBot() {
    for (let i = 0; i < pool.length; i++) {
      if (!pool[i].alive) return pool[i];
    }
    const bot = createBot(scene, world, { settings });
    pool.push(bot);
    return bot;
  }

  /**
   * Заспавнить волну ботов.
   * @param {number} count желаемое количество (обрезается лимитом качества)
   * @param {THREE.Vector3} [playerPos]
   * @param {number} [fov]
   * @param {THREE.Vector3} [forward]
   * @returns {number} сколько реально заспавнено
   */
  function spawnWave(count, playerPos, fov, forward) {
    if (!playerPos || !forward) return 0;
    const cosLimit = fovCos(fov || settings.fov || 75);
    let spawned = 0;
    const budget = maxAlive() - alive;
    const target = Math.min(count, budget);
    for (let i = 0; i < target; i++) {
      const point = pickSpawnPoint(playerPos, forward, cosLimit);
      if (point === null) break;
      const bot = acquireBot();
      _tmpPos.set(point.x, SPAWN_Y, point.z);
      bot.reset(_tmpPos, playerPos);
      alive++;
      spawned++;
      bus.emit('bot:spawned', { bot });
    }
    return spawned;
  }

  /** Убрать мёртвых из счётчика, вернуть в пул */
  function retireDead() {
    for (let i = 0; i < pool.length; i++) {
      const b = pool[i];
      if (b.dead && !b.counted) {
        b.counted = true;
        alive--;
        killed++;
        bus.emit('bot:killed', { bot: b, killed });
      }
    }
  }

  /**
   * Кадровое обновление: тики ботов + поддержание популяции.
   * @param {number} dt секунды
   * @param {{position: THREE.Vector3, forward: THREE```javascript
.Vector3, fov?: number}} player
   */
  function update(dt, player) {
    // тики живых ботов
    for (let i = 0; i < pool.length; i++) {
      const b = pool[i];
      if (b.alive) b.update(dt, player.position);
    }
    retireDead();

    // периодический подспавн до лимита качества
    respawnTimer -= dt;
    if (respawnTimer <= 0 && alive < maxAlive() && player && player.forward) {
      spawnWave(1, player.position, player.fov, player.forward);
      respawnTimer = RESPAWN_INTERVAL;
    }
  }

  /** Деактивировать всех ботов и обнулить статистику */
  function reset() {
    for (let i = 0; i < pool.length; i++) {
      pool[i].dispose();
    }
    pool.length = 0;
    alive = 0;
    killed = 0;
    respawnTimer = 0;
  }

  return {
    update,
    spawnWave,
    reset,
    /** Текущее количество живых ботов */
    get alive() { return alive; },
    /** Сколько ботов убито за матч */
    get killed() { return killed; },
  };
}
