/**
 * src/player/controller.js
 * Кинематический контроллер персонажа на базе Rapier KinematicCharacterController.
 * Капсула: радиус 0.35 м, общая высота стоя 1.8 м, в приседе 1.0 м.
 * Прыжок с coyote-time и буфером ввода, спринт, присед, слайд с инерцией,
 * воздушный контроль, автоподъём на ступеньки до 0.35 м, скольжение вдоль стен.
 */

import RAPIER from 'rapier';
import * as THREE from 'three';
import { bus } from '../core/events.js';

// ---------------------------------------------------------------------------
// Константы
// ---------------------------------------------------------------------------

/** Радиус капсулы, м. */
const CAPSULE_RADIUS = 0.35;
/** Полная высота капсулы стоя, м. */
const HEIGHT_STAND = 1.8;
/** Полная высота капсулы в приседе/слайде, м. */
const HEIGHT_CROUCH = 1.0;
/** Длина цилиндрической части = высота − 2R. */
const HALF_HEIGHT_STAND = HEIGHT_STAND * 0.5 - CAPSULE_RADIUS;
const HALF_HEIGHT_CROUCH = HEIGHT_CROUCH * 0.5 - CAPSULE_RADIUS;

/** Гравитация, м/с². */
const GRAVITY = 22.0;
/** Скорость прыжка (вертикальная), м/с. */
const JUMP_SPEED = 7.2;

/** Скорости ходьбы, м/с. */
const SPEED_WALK = 5.2;
const SPEED_SPRINT = 8.4;
const SPEED_CROUCH = 2.6;

/** Экспоненциальные коэффициенты ускорения/торможения, 1/с. */
const ACCEL_GROUND = 14.0;
const BRAKE_GROUND = 10.0;
/** Воздушный контроль: слабее земного, без резкого торможения. */
const ACCEL_AIR = 2.8;
/** Максимальная скорость, до которой можно разогнаться в воздухе воздушным контролем, м/с. */
const AIR_CONTROL_MAX = 6.5;

/** Слайд: стартовый множитель скорости и экспоненциальное затухание. */
const SLIDE_BOOST = 1.25;
const SLIDE_FRICTION = 2.4;
/** Минимальная скорость, при которой слайд ещё продолжается, м/с. */
const SLIDE_MIN_SPEED = 2.8;
/** Минимальная входная скорость для запуска слайда, м/с. */
const SLIDE_ENTER_SPEED = 5.5;

/** Coyote-time и буфер прыжка, с. */
const COYOTE_TIME = 0.12;
const JUMP_BUFFER_TIME = 0.1;

/** Настройки KinematicCharacterController Rapier. */
const KCC_OFFSET = 0.02;
const KCC_AUTOSTEP_HEIGHT = 0.35;
const KCC_AUTOSTEP_MIN_WIDTH = 0.2;
const KCC_SNAP_TO_GROUND = 0.4;
/** Разрешённый уклон поверхности, радианы (~50°). */
const KCC_SLOPE_UP = 0.9;
const KCC_SLOPE_DOWN = 0.9;

/** Макс. угол полёта вдоль наклонной поверхности — для извлечения grounded. */
const EPSILON = 1e-6;

/** Требование к скорости при быстром спаде импульса высокого прыжка (нет — не используется). */

// ---------------------------------------------------------------------------
// Модульные временные объекты (без аллокаций в горячем цикле)
// ---------------------------------------------------------------------------

const _wishDir = new THREE.Vector3();
const _horizVel = new THREE.Vector3();
const _desired = { x: 0, y: 0, z: 0 };
const _cosSin = { s: 0, c: 0 };

// ---------------------------------------------------------------------------
// Вспомогательные функции
// ---------------------------------------------------------------------------

/**
 * Экспоненциальное приближение значения к цели (фрейм-независимое).
 * @param {number} current Текущее значение.
 * @param {number} target Целевое значение.
 * @param {number} rate Коэффициент, 1/с.
 * @param {number} dt Шаг времени, с.
 * @returns {number} Новое значение.
 */
function expDamp(current, target, rate, dt) {
  return target + (current - target) * Math.exp(-rate * dt);
}

/**
 * Создаёт коллайдер капсулы для тела.
 * @param {RAPIER.World} world
 * @param {RAPIER.RigidBody} body
 * @param {number} halfHeight Половина цилиндрической части.
 * @returns {RAPIER.Collider}
 */
function createCapsule(world, body, halfHeight) {
  const desc = RAPIER.ColliderDesc.capsule(halfHeight, CAPSULE_RADIUS)
    .setFriction(0.0)
    .setRestitution(0.0);
  return world.createCollider(desc, body);
}

/**
 * Заменяет капсулу на капсулу другой высоты (присесть/встать).
 * @param {object} player Состояние игрока.
 * @param {number} halfHeight Новый полурост цилиндрической части.
 */
function resizeCapsule(player, halfHeight) {
  if (player._halfHeight === halfHeight) return;
  const translation = player.body.translation();
  player.world.removeCollider(player.collider, false);
  player.collider = createCapsule(player.world, player.body, halfHeight);
  player._halfHeight = halfHeight;
  // Центр капсулы пересчитываем от «ног», чтобы низ остался на месте.
  const feetY = translation.y - (player._prevHalfHeight + CAPSULE_RADIUS);
  player.body.setTranslation(
    { x: translation.x, y: feetY + halfHeight + CAPSULE_RADIUS, z: translation.z },
    true
  );
  player._prevHalfHeight = halfHeight;
}

// ---------------------------------------------------------------------------
// Публичная фабрика
// ---------------------------------------------------------------------------

/**
 * Создаёт контроллер игрока.
 * @param {RAPIER.World} world Физический мир Rapier.
 * @param {{x:number,y:number,z:number}} spawnPoint Точка спавна (позиция «ног»).
 * @returns {{
 *   update: (dt:number, input:object, cameraYaw:number) => void,
 *   position: THREE.Vector3,
 *   velocity: THREE.Vector3,
 *   grounded: boolean,
 *   state: { state:string, height:number, eyeHeight:number }
 * }} Объект игрока.
 */
export function createPlayer(world, spawnPoint) {
  // Кинематическое позиционное тело; центр капсулы = ноги + полувысота + R.
  const body = world.createRigidBody(
    RAPIER.RigidBodyDesc.kinematicPositionBased()
      .setTranslation(
        spawnPoint.x,
        spawnPoint.y + HALF_HEIGHT_STAND + CAPSULE_RADIUS,
        spawnPoint.z
      )
      .setCcdEnabled(true)
  );

  const collider = createCapsule(world, body, HALF_HEIGHT_STAND);

  const kcc = world.createCharacterController(KCC_OFFSET);
  kcc.enableAutostep(KCC_AUTOSTEP_HEIGHT, KCC_AUTOSTEP_MIN_WIDTH, true);
  kcc.enableSnapToGround(KCC_SNAP_TO_GROUND);
  kcc.setMaxSlopeClimbAngle(KCC_SLOPE_UP);
  kcc.setMinSlopeSlideAngle(KCC_SLOPE_DOWN);
  kcc.setApplyImpulsesToDynamicBodies(true);
  // Характер-контроллер отодвигается от пересечений автоматически.
  kcc.setCharacterMass(75);

  /** @type {'stand'|'crouch'|'slide'|'air'} */
  let state = 'air';

  let coyoteTimer = 0;
  let jumpBufferTimer = 0;
  let wasJumpPressed = false;

  const player = {
    world,
    body,
    collider,
    kcc,
    position: new THREE.Vector3(spawnPoint.x, spawnPoint.y, spawnPoint.z),
    velocity: new THREE.Vector3(),
    grounded: false,
    state: {
      /** Строковое состояние: 'stand' | 'crouch' | 'slide' | 'air'. */
      get state() { return state; },
      /** Текущая высота капсулы, м. */
      height: HEIGHT_STAND,
      /** Высота «глаз» над ногами, м (для камеры). */
      eyeHeight: HEIGHT_STAND - 0.15,
    },
    _halfHeight: HALF_HEIGHT_STAND,
    _prevHalfHeight: HALF_HEIGHT_STAND,
    update,
  };

  /**
   * Проверка, есть ли место над головой для вставания (луч вверх).
   * @returns {boolean} true, если встать можно.
   */
  function canStandUp() {
    const t = body.translation();
    const standHalfTotal = HALF_HEIGHT_STAND + CAPSULE_RADIUS;
    const crouchHalfTotal = HALF_HEIGHT_CROUCH + CAPSULE_RADIUS;
    const castLen = standHalfTotal - crouchHalfTotal + KCC_OFFSET;
    const ray = new RAPIER.Ray(
      { x: t.x, y: t.y + crouchHalfTotal - CAPSULE_RADIUS * 0.5, z: t.z },
      { x: 0, y: 1, z: 0 }
    );
    const hit = world.castRay(
      ray, castLen, true, undefined, undefined, collider, body
    );
    return hit === null;
  }

  /**
   * Главный апдейт.
   * @param {number} dt Шаг времени, с.
   * @param {object} input Состояние ввода:
   *   { moveX:number, moveZ:number, sprint:boolean, crouch:boolean, jump:boolean }
   *   moveX/moveZ ∈ [-1,1] (strafe/forward).
   * @param {number} cameraYaw Рыскание камеры, рад (вокруг Y).
   */
  function update(dt, input, cameraYaw) {
    if (dt <= 0) return;

    const t = body.translation();

    // --- Желанное направление движения в мировых координатах ---------------
    _cosSin.s = Math.sin(cameraYaw);
    _cosSin.c = Math.cos(cameraYaw);
    // forward = (-sin(yaw), 0, -cos(yaw)), right = (cos(yaw), 0, -sin(yaw))
    _wishDir.set(
      input.moveX * _cosSin.c - input.moveZ * _cosSin.s,
      0,
      -input.moveX * _cosSin.s - input.moveZ * _cosSin.c
    );
    const wishLen = _wishDir.length();
    if (wishLen > EPSILON) _wishDir.divideScalar(wishLen);
    const hasInput = wishLen > EPSILON;

    // --- Состояния: присед / слайд ------------------------------------------
    _horizVel.set(player.velocity.x, 0, player.velocity.z);
    const horizSpeed = _horizVel.length();

    if (input.crouch && state !== 'crouch' && state !== 'slide') {
      if (player.grounded && horizSpeed > SLIDE_ENTER_SPEED) {
        state = 'slide';
        // Сохраняем импульс и добавляем небольшой буст вперёд.
        player.velocity.x *= SLIDE_BOOST;
        player.velocity.z *= SLIDE_BOOST;
        resizeCapsule(player, HALF_HEIGHT_CROUCH);
        bus.emit('player:slide', horizSpeed);
      } else {
        state = 'crouch';
        resizeCapsule(player, HALF_HEIGHT_CROUCH);
      }
    } else if (!input.crouch && (state === 'crouch' || state === 'slide')) {
      if (canStandUp()) {
        state = player.grounded ? 'stand' : 'air';
        resizeCapsule(player, HALF_HEIGHT_STAND);
      } else if (state === 'slide') {
        state = 'crouch'; // Под потолком — продолжаем красться.
      }
    }

    if (state === 'slide' && horizSpeed < SLIDE_MIN_SPEED) {
      state = 'crouch';
    }
    if (!player.grounded && state !== 'crouch' && state !== 'slide') {
      state = 'air';
    } else if (player.grounded && state === 'air') {
      state = 'stand';
      bus.emit('player:land', horizSpeed);
    }

    player.state.height = player._halfHeight * 2 + CAPSULE_RADIUS * 2;
    player.state.eyeHeight = player.state.height - 0.15;

    // --- Прыжок: coyote-time + буфер ввода -----------------------------------
    if (player.grounded) {
      coyoteTimer = COYOTE_TIME;
    } else {
      coyoteTimer = Math.max(0, coyoteTimer - dt);
    }
    if (input.jump && !wasJumpPressed) {
      jumpBufferTimer = JUMP_BUFFER_TIME;
    } else {
      jumpBufferTimer = Math.max(0, jumpBufferTimer - dt);
    }
    wasJumpPressed = !!input.jump;

    if (jumpBufferTimer > 0 && coyoteTimer > 0) {
      player.velocity.y = JUMP_SPEED;
      coyoteTimer = 0;
      jumpBufferTimer = 0;
      if (state === 'crouch' && canStandUp()) {
        state = 'air';
        resizeCapsule(player, HALF_HEIGHT_STAND);
      } else {
        state = 'air';
      }
      bus.emit('player:jump');
    }

    // --- Гравитация ------------------------------------------------------------
    player.velocity.y -= GRAVITY * dt;
    if (player.grounded && player.velocity.y < 0) {
      player.velocity.y = -0.5; // Прижим к земле для snap-to-ground.
    }

    // --- Горизонтальное движение -----------------------------------------------
    if (state === 'slide') {
      // Слайд: чистое экспоненциальное затухание, курс не меняем.
      const decay = Math.exp(-SLIDE_FRICTION * dt);
      player.velocity.x *= decay;
      player.velocity.z *= decay;
    } else if (player.grounded) {
      let targetSpeed = SPEED_WALK;
      if (state === 'crouch') {
        targetSpeed = SPEED_CROUCH;
      } else if (input.sprint && input.moveZ < -0.1) {
        // Спринт только при движении вперёд.
        targetSpeed = SPEED_SPRINT;
      }
      const tx = hasInput ? _wishDir.x * targetSpeed : 0;
      const tz = hasInput ? _wishDir.z * targetSpeed : 0;
      const rate = hasInput ? ACCEL_GROUND : BRAKE_GROUND;
      player.velocity.x = expDamp(player.velocity.x, tx, rate, dt);
      player.velocity.z = expDamp(player.velocity.z, tz, rate, dt);
    } else {
      // Воздушный контроль: только догоняемся до wish-направления,
      // без торможения существующего импульса.
      if (hasInput && horizSpeed < AIR_CONTROL_MAX) {
        player.velocity.x = expDamp(
          player.velocity.x, _wishDir.x * SPEED_WALK, ACCEL_AIR, dt
        );
        player.velocity.z = expDamp(
          player.velocity.z, _wishDir.z * SPEED_WALK, ACCEL_AIR, dt
        );
      }
      // В приседе в воздухе ничего не делаем — сохраняем инерцию.
    }

    // --- Интеграция через Rapier KCC --------------------------------------------
    _desired.x = player.velocity.x * dt;
    _desired.y = player.velocity.y * dt;
    _desired.z = player.velocity.z * dt;

    kcc.computeColliderMovement(collider, _desired, undefined, undefined, body);
    const corrected = kcc.computedMovement();
    const wasGrounded = player.grounded;
    player.grounded = kcc.computedGrounded();

    const newX = t.x + corrected.x;
    const newY = t.y + corrected.y;
    const newZ = t.z + corrected.z;
    body.setNextKinematicTranslation({ x: newX, y: newY, z: newZ });

    // Фактически достигнутая скорость (учитывает скольжение вдоль стен).
    if (dt > EPSILON) {
      player.velocity.x = corrected.x / dt;
      player.velocity.z = corrected.z / dt;
      const actualVy = corrected.y / dt;
      // Обнулять vy при ударе об землю/потолок, иначе накапливается.
      if (player.grounded && actualVy <= 0) {
        player.velocity.y = 0;
      } else if (actualVy < player.velocity.y - EPSILON && player.velocity.y > 0) {
        player.velocity.y = 0; // Столкновение с потолком.
      }
    }

    if (!wasGrounded && player.grounded) {
      bus.emit('player:grounded');
    }

    // Позиция «ног» для внешних систем (камера, звук, сетка).
    const feet = player._halfHeight + CAPSULE_RADIUS;
    player.position.set(newX, newY - feet, newZ);
  }

  return player;
}
