/**
 * Баллистика hitscan-оружия Doday Arena.
 * Модуль чистый: никакой работы со сценой, эффектов и аллокаций в горячем пути.
 */
import { Vector3 } from 'three';
import { raycast } from '../world/collision.js';

// --- Константы баллистики ---
/** Максимальная дистальная дальность луча по умолчанию, м. */
const DEFAULT_RANGE = 300;
/** Максимум пробитий тонких препятствий за один выстрел. */
const MAX_PENETRATIONS = 2;
/** Доля урона, сохраняемая после каждого пробития. */
const PENETRATION_DAMAGE_FACTOR = 0.55;
/** Дополнительная потеря урона за каждый метр внутри препятствия (условная толщина). */
const PENETRATION_THICKNESS = 0.12;
/** Смещение новой точки старта луча за поверхностью, чтобы не попасть в то же тело. */
const SURFACE_OFFSET = 0.02;

// Модульные временные объекты (переиспользуются, без аллокаций в цикле)
const _dir = new Vector3();
const _origin = new Vector3();
const _orthogonal = new Vector3();
const _basisU = new Vector3();
const _basisV = new Vector3();

/**
 * Строит ортонормированный базис (u, v) в плоскости, перпендикулярной оси луча.
 * @param {Vector3} axis нормализованное направление луча
 * @param {Vector3} u выходной первый вектор базиса
 * @param {Vector3} v выходной второй вектор базиса
 */
function buildPerpBasis(axis, u, v) {
  // Берём наименее параллельную ось привязки, чтобы избежать вырождения
  if (Math.abs(axis.y) < 0.999) {
    _orthogonal.set(0, 1, 0);
  } else {
    _orthogonal.set(1, 0, 0);
  }
  u.crossVectors(axis, _orthogonal).normalize();
  v.crossVectors(axis, u).normalize();
}

/**
 * Применяет равномерный разброс в конусе к направлению.
 * Равномерность по площади: cos(theta) равномерен в [cos(spread), 1].
 * @param {Vector3} out выходной вектор (нормализованный)
 * @param {Vector3} direction исходное направление (нормализованное)
 * @param {number} spread полуугол конуса разброса, рад
 * @param {Function} rng генератор случайных чисел [0, 1)
 * @returns {Vector3} out
 */
function applySpread(out, direction, spread, rng) {
  if (spread <= 0) {
    return out.copy(direction);
  }
  const cosMax = Math.cos(spread);
  const rand = rng || Math.random;
  const cosTheta = cosMax + (1 - cosMax) * rand();
  const sinTheta = Math.sqrt(Math.max(0, 1 - cosTheta * cosTheta));
  const phi = rand() * Math.PI * 2;

  buildPerpBasis(direction, _basisU, _basisV);

  const cosPhi = Math.cos(phi);
  const sinPhi = Math.sin(phi);
  out.set(
    direction.x * cosTheta + ( _basisU.x * cosPhi + _basisV.x * sinPhi) * sinTheta,
    direction.y * cosTheta + ( _basisU.y * cosPhi + _basisV.y * sinPhi) * sinTheta,
    direction.z * cosTheta + ( _basisU.z * cosPhi + _basisV.z * sinPhi) * sinTheta
  );
  return out.normalize();
}

/**
 * Спад урона по дистанции: до rangeFalloff.start — полный урон,
 * до rangeFalloff.end — линейно до нуля, дальше — ноль.
 * @param {number} baseDamage базовый урон оружия
 * @param {number} distance дистанция до точки попадания, м
 * @param {{start:number, end:number}|undefined} falloff параметры спада
 * @returns {number} итоговый множитель урона (0..1)
 */
function damageFalloffMultiplier(distance, falloff) {
  if (!falloff || falloff.end <= falloff.start) {
    return 1;
  }
  if (distance <= falloff.start) {
    return 1;
  }
  if (distance >= falloff.end) {
    return 0;
  }
  return 1 - (distance - falloff.start) / (falloff.end - falloff.start);
}

/**
 * Hitscan-выстрел с разбросом в конусе, спадом урона по дистанции
 * и пробитием до двух тонких препятствий с потерей урона.
 *
 * @param {object} world мир/физический мир для raycast
 * @param {Vector3} origin точка выстрела
 * @param {Vector3} direction направление выстрела (не обязано быть нормализовано — нормализуется внутри)
 * @param {object} weapon описание оружия: {damage, range?, rangeFalloff?{start,end}}
 * @param {number} spread полуугол конуса разброса, рад (0 — без разброса)
 * @param {Function} [rng] генератор случайных чисел [0, 1), по умолчанию Math.random
 * @returns {{
 *   hit: boolean,
 *   point: Vector3|null,
 *   normal: Vector3|null,
 *   distance: number,
 *   damage: number,
 *   target: object|null,
 *   penetrations: number
 * }} результат выстрела; point/normal возвращаются как копии (без алиасинга временных)
 */
export function fireHitscan(world, origin, direction, weapon, spread, rng) {
  // Совместимость: src/weapons/weapon.js зовёт эту функцию ОДНИМ объектом
  // {origin, direction, damage, headshotMult, targets, maxDistance}, а не
  // позиционными аргументами. Разбираем оба вида вызова.
  if (world && world.origin && world.direction) {
    const opts = world;
    world = opts.world ?? null;
    origin = opts.origin;
    direction = opts.direction;
    weapon = {
      damage: opts.damage,
      headshotMultiplier: opts.headshotMult,
      range: opts.maxDistance,
    };
    spread = opts.spread ?? 0;
    rng = opts.rng ?? Math.random;
    // targets прокидываем через weapon, чтобы не менять остальную логику
    weapon.targets = opts.targets;
  }
  const result = {
    hit: false,
    point: null,
    normal: null,
    distance: 0,
    damage: 0,
    target: null,
    penetrations: 0
  };

  const baseDamage = weapon.damage || 0;
  const maxRange = weapon.range || DEFAULT_RANGE;
  const falloff = weapon.rangeFalloff;

  _origin.copy(origin);
  applySpread(_dir, direction, spread, rng);

  let traveled = 0;

  for (let i = 0; i <= MAX_PENETRATIONS; i++) {
    const remaining = maxRange - traveled;
    if (remaining <= 0) {
      break;
    }

    const ray = raycast(world, _origin, _dir, remaining);
    if (!ray || !ray.hit) {
      break;
    }

    const distance = traveled + ray.distance;
    // Спад урона считается от суммарной дистанции от ствола
    let damage = baseDamage * damageFalloffMultiplier(distance, falloff);
    // Потеря урона за предыдущие пробития (геометрически)
    for (let p = 0; p < i; p++) {
      damage *= PENETRATION_DAMAGE_FACTOR;
    }
    // Штраф за условную толщину внутреннего слоя каждого пробития
    damage *= Math.max(0, 1 - PENETRATION_THICKNESS * i);

    if (i === MAX_PENETRATIONS || ray.distance + SURFACE_OFFSET > remaining) {
      // Финальное попадание: пробитий больше нет — возвращаем его
      result.hit = true;
      result.point = ray.point.clone();
      result.normal = ray.normal.clone();
      result.distance = distance;
      result.damage = damage;
      result.target = ray.collider || null;
      result.penetrations = i;
      return result;
    }

    // Препятствие считаем тонким: пробиваем и продолжаем луч дальше
    traveled = distance + SURFACE_OFFSET;
    _origin.copy(ray.point).addScaledVector(_dir, SURFACE_OFFSET);
    result.penetrations = i + 1;
  }

  return result;
}
