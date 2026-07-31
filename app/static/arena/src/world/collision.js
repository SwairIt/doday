// src/world/collision.js
// Обёртка над Rapier3D: инициализация движка, статические коллайдеры города,
// плоскость земли и помощник для рейкастов.

import RAPIER from 'rapier';

/** Гравитация мира, м/с² (ось вниз). */
const GRAVITY_Y = -9.81;

/** Половинная толщина «плоскости» земли, м (обходится без бесконечного halfspace — детерминированнее в compat-сборке). */
const GROUND_HALF_THICKNESS = 1.0;

/** Максимальная дистанция рейкаста по умолчанию, м. */
const DEFAULT_RAYCAST_DIST = 1000;

/**
 * Инициализирует движок Rapier и создаёт физический мир.
 * compat-сборка требует обязательного ожидания RAPIER.init() — грузит wasm-ядро.
 *
 * @returns {Promise<RAPIER.World>} готовый физический мир
 */
export async function initPhysics() {
    await RAPIER.init();

    const world = new RAPIER.World({ x: 0, y: GRAVITY_Y, z: 0 });
    // Компромисс точности и стабильности для браузерного FPS.
    world.timestep = 1 / 60;

    return world;
}

/**
 * Строит неподвижные кубоид-коллайдеры по данным города.
 *
 * @param {RAPIER.World} world физический мир
 * @param {Array<{position: {x: number, y: number, z: number}, size: {x: number, y: number, z: number}}>} colliders
 *   описание коллайдеров из buildCity: position — центр, size — полные габариты по осям
 * @returns {RAPIER.Collider[]} созданные коллайдеры (порядок совпадает со входным массивом)
 */
export function buildStaticColliders(world, colliders) {
    const result = new Array(colliders.length);

    for (let i = 0; i < colliders.length; i++) {
        const { position, size } = colliders[i];

        const bodyDesc = RAPIER.RigidBodyDesc.fixed().setTranslation(
            position.x,
            position.y,
            position.z
        );
        const body = world.createRigidBody(bodyDesc);

        // Rapier принимает полу-экстенты, поэтому делим габариты пополам.
        const colliderDesc = RAPIER.ColliderDesc.cuboid(
            size.x * 0.5,
            size.y * 0.5,
            size.z * 0.5
        );
        colliderDesc.setFriction(0.8);

        result[i] = world.createCollider(colliderDesc, body);
    }

    return result;
}

/**
 * Добавляет горизонтальную плоскость земли (y = 0).
 * Реализована очень большим тонким кубоидом — предсказуемо на всех платформах.
 *
 * @param {RAPIER.World} world физический мир
 * @returns {RAPIER.Collider} коллайдер земли
 */
export function addGroundPlane(world) {
    const GROUND_HALF_EXTENT = 1000;

    const bodyDesc = RAPIER.RigidBodyDesc.fixed().setTranslation(
        0,
        -GROUND_HALF_THICKNESS,
        0
    );
    const body = world.createRigidBody(bodyDesc);

    const colliderDesc = RAPIER.ColliderDesc.cuboid(
        GROUND_HALF_EXTENT,
        GROUND_HALF_THICKNESS,
        GROUND_HALF_EXTENT
    );
    colliderDesc.setFriction(1.0);

    return world.createCollider(colliderDesc, body);
}

// Временные объекты рейкаста — переиспользуются, чтобы не аллоцировать в горячем цикле.
const _rayOrigin = { x: 0, y: 0, z: 0 };
const _rayDir = { x: 0, y: 0, z: 0 };

/**
 * Рейкаст по физическому миру. Направление должно быть нормализовано.
 *
 * @param {RAPIER.World} world физический мир
 * @param {{x: number, y: number, z: number}} origin точка начала луча
 * @param {{x: number, y: number, z: number}} dir нормализованное направление луча
 * @param {number} [maxDist] максимальная дистанция, м
 * @param {RAPIER.Collider|null} [filter] коллайдер, который нужно исключить (например, сам стрелок)
 * @returns {{point: {x: number, y: number, z: number}, normal: {x: number, y: number, z: number}, distance: number, collider: RAPIER.Collider}|null}
 *   ближайшее попадание или null
 */
export function raycast(world, origin, dir, maxDist = DEFAULT_RAYCAST_DIST, filter = null) {
    _rayOrigin.x = origin.x;
    _rayOrigin.y = origin.y;
    _rayOrigin.z = origin.z;
    _rayDir.x = dir.x;
    _rayDir.y = dir.y;
    _rayDir.z = dir.z;

    const ray = new RAPIER.Ray(_rayOrigin, _rayDir);
    // solid = true: попадание внутрь объёма считается на его границе,
    // что стабильнее при стрельбе вблизи стен.
    const hit = world.castRay(ray, maxDist, true, undefined, undefined, filter);

    if (hit === null) {
        return null;
    }

    const point = ray.pointAt(hit.timeOfImpact);
    const normal = world.castRayAndGetNormal
        ? null
        : null;

    // Нормаль возвращает only castRayAndGetNormal — делаем отдельный запрос,
    // дистанцию берём с первого (одинаковые параметры => тот же коллайдер).
    const hitWithNormal = world.castRayAndGetNormal(
        ray,
        maxDist,
        true,
        undefined,
        undefined,
        filter
    );

    const n = hitWithNormal !== null ? hitWithNormal.normal : { x: 0, y: 1, z: 0 };

    return {
        point: { x: point.x, y: point.y, z: point.z },
        normal: { x: n.x, y: n.y, z: n.z },
        distance: hit.timeOfImpact,
        collider: hit.collider
    };
}
