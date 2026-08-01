// Восприятие бота: зрение (конус + рейкаст), слух, упреждение.
// Чистые вычисления, без логики поведения и без работы со сценой.

import { raycast } from '../world/collision.js';

// Полный угол конуса обзора (градусы)
const VIEW_ANGLE_DEG = 110;
// Половина конуса в радианах (сравнение идёт с отклонением от forward)
const HALF_VIEW_ANGLE = (VIEW_ANGLE_DEG * 0.5) * Math.PI / 180;
// Косинус половины конуса — для сравнения без вызова Math.acos
const COS_HALF_VIEW = Math.cos(HALF_VIEW_ANGLE);
// Радиус слышимости выстрела (м)
const HEARING_RADIUS = 40;
const HEARING_RADIUS_SQ = HEARING_RADIUS * HEARING_RADIUS;
// Максимальная дистанция зрения (м)
const MAX_VIEW_DIST = 120;
// Небольшой запас при рейкасте, чтобы не «сломаться» о геометрию самой цели
const RAY_EPSILON = 0.3;
// Минимальная скорость снаряда, защита от деления на ноль
const MIN_PROJECTILE_SPEED = 0.001;

// Модульные временные — никаких аллокаций в горячем пути
// Ожидается формат векторов с полями x, y, z (совместим с THREE.Vector3 и Rapier)
const tmpToTarget = { x: 0, y: 0, z: 0 };
const tmpHoriz = { x: 0, y: 0, z: 0 };

/**
 * Возводит вектор dir (горизонтальную составляющую нормализованного направления)
 * для сравнения с конусом обзора. Ничего не возвращает, пишет в tmpHoriz.
 * @param {{x:number,y:number,z:number}} dir
 */
function toHorizontalNorm(dir) {
  tmpHoriz.x = dir.x;
  tmpHoriz.y = 0;
  tmpHoriz.z = dir.z;
  const lenSq = tmpHoriz.x * tmpHoriz.x + tmpHoriz.z * tmpHoriz.z;
  if (lenSq > 1e-12) {
    const invLen = 1 / Math.sqrt(lenSq);
    tmpHoriz.x *= invLen;
    tmpHoriz.z *= invLen;
  }
}

/**
 * Создаёт объект восприятия бота.
 * @param {object} world Rapier-мир (нужен для рейкастов видимости)
 * @param {object} [deps] Зарезервированные зависимости (не используются)
 * @returns {{canSee: Function, hearShot: Function, leadTarget: Function}}
 */
export function createPerception(world, deps = {}) {

  /**
   * Может ли наблюдатель увидеть цель: цель внутри конуса обзора 110°
   * и между ними нет препятствий (рейкаст по статической геометрии).
   * @param {{x:number,y:number,z:number}} fromPos позиция глаз наблюдателя
   * @param {{x:number,y:number,z:number}} targetPos позиция цели
   * @param {{x:number,y:number,z:number}} forwardDir нормализованное направление взгляда
   * @returns {boolean}
   */
  function canSee(fromPos, targetPos, forwardDir) {
    // Вектор к цели
    tmpToTarget.x = targetPos.x - fromPos.x;
    tmpToTarget.y = targetPos.y - fromPos.y;
    tmpToTarget.z = targetPos.z - fromPos.z;

    const distSq = tmpToTarget.x * tmpToTarget.x +
      tmpToTarget.y * tmpToTarget.y +
      tmpToTarget.z * tmpToTarget.z;

    // Вне дальности зрения
    if (distSq > MAX_VIEW_DIST * MAX_VIEW_DIST || distSq < 1e-12) {
      return false;
    }
    const dist = Math.sqrt(distSq);

    // Проверка конуса в горизонтальной плоскости (бот смотрит "по горизонту")
    const invDist = 1 / dist;
    // Без направления взгляда конус проверить нельзя — считаем обзор
    // круговым и полагаемся только на рейкаст видимости ниже.
    if (forwardDir) {
      toHorizontalNorm(forwardDir);
      const dot = tmpHoriz.x * tmpToTarget.x * invDist +
        tmpHoriz.z * tmpToTarget.z * invDist;
      // Acos-free сравнение: угол зависит только от горизонтальной проекции
      if (dot < COS_HALF_VIEW) {
        return false;
      }
    }

    // Проверка линии видимости рейкастом
    const dir = {
      x: tmpToTarget.x * invDist,
      y: tmpToTarget.y * invDist,
      z: tmpToTarget.z * invDist,
    };
    const hit = raycast(world, fromPos, dir, dist);
    // Препятствие ближе цели (с запасом) — цель скрыта
    if (hit && hit.distance < dist - RAY_EPSILON) {
      return false;
    }
    return true;
  }

  /**
   * Слышит ли наблюдатель выстрел: выстрел в радиусе 40 м.
   * Сравнение по квадратам расстояний, без sqrt.
   * @param {{x:number,y:number,z:number}} fromPos позиция слушателя
   * @param {{x:number,y:number,z:number}} shotPos позиция выстрела
   * @returns {boolean}
   */
  function hearShot(fromPos, shotPos) {
    tmpToTarget.x = shotPos.x - fromPos.x;
    tmpToTarget.y = shotPos.y - fromPos.y;
    tmpToTarget.z = shotPos.z - fromPos.z;
    const distSq = tmpToTarget.x * tmpToTarget.x +
      tmpToTarget.y * tmpToTarget.y +
      tmpToTarget.z * tmpToTarget.z;
    return distSq <= HEARING_RADIUS_SQ;
  }

  /**
   * Вычисляет точку упреждения для стрельбы снарядом конечной скорости.
   * Итеративное уточнение времени подлёта (2 итерации достаточно для арены).
   * Пишет результат в переданный out либо возвращает новый объект.
   * @param {{x:number,y:number,z:number}} fromPos позиция стрелка
   * @param {{x:number,y:number,z:number}} targetPos текущая позиция цели
   * @param {{x:number,y:number,z:number}} targetVel скорость цели (м/с)
   * @param {number} projectileSpeed скорость снаряда (м/с)
   * @param {{x:number,y:number,z:number}} [out] куда писать результат
   * @returns {{x:number,y:number,z:number}} точка упреждения
   */
  function leadTarget(fromPos, targetPos, targetVel, projectileSpeed, out = { x: 0, y: 0, z: 0 }) {
    const speed = Math.max(projectileSpeed, MIN_PROJECTILE_SPEED);

    const dx = targetPos.x - fromPos.x;
    const dy = targetPos.y - fromPos.y;
    const dz = targetPos.z - fromPos.z;

    // Первая оценка времени подлёта
    let t = Math.sqrt(dx * dx + dy * dy + dz * dz) / speed;

    // Одно уточнение: время до уже упреждённой точки
    const px = targetPos.x + targetVel.x * t;
    const py = targetPos.y + targetVel.y * t;
    const pz = targetPos.z + targetVel.z * t;
    const ex = px - fromPos.x;
    const ey = py - fromPos.y;
    const ez = pz - fromPos.z;
    t = Math.sqrt(ex * ex + ey * ey + ez * ez) / speed;

    out.x = targetPos.x + targetVel.x * t;
    out.y = targetPos.y + targetVel.y * t;
    out.z = targetPos.z + targetVel.z * t;
    return out;
  }

  // canHear — псевдоним hearShot: под этим именем его зовёт src/ai/bot.js.
  return { canSee, hearShot, canHear: hearShot, leadTarget };
}
