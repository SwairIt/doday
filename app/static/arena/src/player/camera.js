/**
 * @fileoverview Камера от первого лица для Doday Arena.
 * Управление обзором, ADS/спринт FOV, покачивание, тряска и отдача.
 */

import * as THREE from 'three';

/** Максимальный угол тангажа в радианах (±89°). */
const PITCH_LIMIT = THREE.MathUtils.degToRad(89);

/** FOV при прицеливании. */
const ADS_FOV = 55;
/** Добавка к FOV при спринте. */
const SPRINT_FOV_BONUS = 8;
/** Скорость смены FOV (1/сек, экспоненциальное сглаживание). */
const FOV_LERP_SPEED = 10;

/** Частота покачивания при ходьбе (циклов/сек). */
const BOB_FREQUENCY = 6.5;
/** Базовая амплитуда покачивания (метры). */
const BOB_AMPLITUDE = 0.035;
/** Доля бокового покачивания от вертикального. */
const BOB_SIDE_FACTOR = 0.6;
/** Минимальная скорость для покачивания. */
const BOB_MIN_SPEED = 0.5;

/** Затухание тряски (экспонента, 1/сек). */
const SHAKE_DECAY = 8;
/** Затухание отдачи (экспонента, 1/сек). */
const RECOIL_DECAY = 9;
/** Доля отдачи, остающаяся «выстреленной» без возврата. */
const RECOIL_RETURN_FACTOR = 0.85;

/** Тряска при приземлении от вертикальной скорости. */
const LAND_SHAKE_FACTOR = 0.008;

// Модульные временные переменные — без аллокаций в цикле.
const _euler = new THREE.Euler(0, 0, 0, 'YXZ');

/**
 * Создаёт контроллер камеры от первого лица.
 * @param {import('../core/settings.js').Settings} settings Настройки игры.
 * @returns {{camera: THREE.PerspectiveCamera,
 *   update: (dt: number, player: object, input: object) => void,
 *   applyRecoil: (pitch: number, yaw: number) => void,
 *   setAim: (aiming: boolean) => void}}
 */
export function createPlayerCamera(settings) {
  const camera = new THREE.PerspectiveCamera(
    settings.fov,
    window.innerWidth / window.innerHeight,
    0.05,
    500
  );
  camera.rotation.order = 'YXZ';

  const state = {
    yaw: 0,                 // текущий рыскание
    pitch: 0,               // текущий тангаж
    recoilPitch: 0,         // остаточная отдача по тангажу
    recoilYaw: 0,           // остаточная отдача по рысканию
    shake: 0,               // энергия тряски
    shakeTime: 0,           // фаза шума тряски
    bobPhase: 0,            // фаза покачивания
    bobAmount: 0,           // сглаженная амплитуда покачивания
    aiming: false,          // режим прицеливания
    currentFov: settings.fov,
    eyeHeight: 1.7,         // высота глаз, плавно меняется (присед)
    prevVelY: 0,            // верт. скорость прошлого кадра (приземление)
    wasGrounded: true,
  };

  /**
   * Целевой FOV с учётом ADS и спринта.
   * @param {boolean} sprinting Идёт ли спринт.
   * @returns {number}
   */
  function targetFov(sprinting) {
    if (state.aiming) return ADS_FOV;
    if (sprinting) return settings.fov + SPRINT_FOV_BONUS;
    return settings.fov;
  }

  /**
   * Обновляет камеру за кадр.
   * @param {number} dt Дельта времени, секунды.
   * @param {object} player Данные игрока: {position: THREE.Vector3,
   *   velocity: THREE.Vector3, speed: number, grounded: boolean,
   *   sprinting: boolean, eyeHeight?: number}.
   * @param {object} input Ввод: {mouseDX: number, mouseDY: number} —
   *   смещение мыши за кадр в пикселях.
   */
  function update(dt, player, input) {
    // --- Обзор по мыши ---
    const sens = settings.sensitivity * 0.0022;
    state.yaw -= input.mouseDX * sens;
    state.pitch -= input.mouseDY * sens;
    state.pitch = THREE.MathUtils.clamp(state.pitch, -PITCH_LIMIT, PITCH_LIMIT);

    // --- Отдача: экспоненциальный возврат ---
    const recoilK = 1 - Math.exp(-RECOIL_DECAY * dt);
    state.recoilPitch *= Math.exp(-RECOIL_DECAY * dt);
    state.recoilYaw *= Math.exp(-RECOIL_DECAY * dt);
    void recoilK;

    // --- Тряска: затухание + шум ---
    state.shake *= Math.exp(-SHAKE_DECAY * dt);
    state.shakeTime += dt * 30;

    // Приземление: резкая смена вертикальной скорости при ударе о землю
    if (player.grounded && !state.wasGrounded && state.prevVelY < -2) {
      state.shake += Math.min(0.25, -state.prevVelY * LAND_SHAKE_FACTOR);
    }
    state.prevVelY = player.velocity.y;
    state.wasGrounded = player.grounded
    // --- Покачивание при ходьбе ---
    const moving = player.grounded && player.speed > BOB_MIN_SPEED && !state.aiming;
    const targetBob = moving ? Math.min(1, player.speed / 6) : 0;
    state.bobAmount += (targetBob - state.bobAmount) * (1 - Math.exp(-8 * dt));
    if (moving) {
      state.bobPhase += dt * BOB_FREQUENCY * (0.6 + 0.4 * Math.min(1, player.speed / 6));
    }

    // --- Плавная высота глаз (присед и т.п.) ---
    const targetEye = player.eyeHeight !== undefined ? player.eyeHeight : 1.7;
    state.eyeHeight += (targetEye - state.eyeHeight) * (1 - Math.exp(-12 * dt));

    // --- FOV: ADS / спринт ---
    const tf = targetFov(player.sprinting);
    state.currentFov += (tf - state.currentFov) * (1 - Math.exp(-FOV_LERP_SPEED * dt));
    if (Math.abs(state.currentFov - camera.fov) > 0.01) {
      camera.fov = state.currentFov;
      camera.updateProjectionMatrix();
    }

    // --- Сборка позиции ---
    const bobY = Math.sin(state.bobPhase * Math.PI * 2) * BOB_AMPLITUDE * state.bobAmount;
    const bobX = Math.cos(state.bobPhase * Math.PI) * BOB_AMPLITUDE * BOB_SIDE_FACTOR * state.bobAmount;
    const shakeX = Math.sin(state.shakeTime * 1.3) * state.shake;
    const shakeY = Math.cos(state.shakeTime * 1.7) * state.shake;

    camera.position.set(
      player.position.x + bobX + shakeX * 0.05,
      player.position.y + state.eyeHeight + bobY + shakeY * 0.05,
      player.position.z
    );

    // --- Сборка поворота ---
    const shakePitch = Math.sin(state.shakeTime * 2.1) * state.shake * 0.03;
    const shakeYaw = Math.cos(state.shakeTime * 2.7) * state.shake * 0.03;
    _euler.set(
      state.pitch + state.recoilPitch + shakePitch,
      state.yaw + state.recoilYaw + shakeYaw,
      Math.sin(state.shakeTime * 1.1) * state.shake * 0.02
    );
    camera.quaternion.setFromEuler(_euler);
  }

  /**
   * Применяет отдачу от выстрела.
   * @param {number} pitch Вертикальная отдача, радианы (положительно — вверх).
   * @param {number} yaw Горизонтальная отдача, радианы.
   */
  function applyRecoil(pitch, yaw) {
    state.recoilPitch += pitch * RECOIL_RETURN_FACTOR;
    state.recoilYaw += yaw * RECOIL_RETURN_FACTOR;
    state.shake += Math.abs(pitch) * 0.4;
  }

  /**
   * Включает/выключает режим прицеливания.
   * @param {boolean} aiming
   */
  function setAim(aiming) {
    state.aiming = aiming;
  }

  /**
   * Обновляет соотношение сторон при ресайзе окна.
   * @param {number} width Ширина вьюпорта.
   * @param {number} height Высота вьюпорта.
   */
  function resize(width, height) {
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  return { camera, update, applyRecoil, setAim, resize };
}
