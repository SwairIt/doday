/**
 * @file city.js — композитор города Doday Arena.
 * Собирает улицы, здания и уличный декор (InstancedMesh),
 * объединяет коллайдеры и точки спавна. Геометрию улиц/зданий
 * строят отдельные модули, здесь только композиция и декор.
 */

import * as THREE from 'three';
import { createRng } from './rng.js';
import { buildStreets } from './streets.js';
import { buildBuildings } from './buildings.js';
import { makeConcrete, makeMetal, tileTextures } from './textures.js';

// ---------------------------------------------------------------------------
// Константы декора
// ---------------------------------------------------------------------------

/** Плотность декора на метр периметра участка, по качеству. */
const DECOR_DENSITY = { low: 0.010, medium: 0.018, high: 0.028 };

/** Высоты объектов декора, м. */
const LAMP_HEIGHT = 5.2;
const LAMP_POLE_RADIUS = 0.07;
const LAMP_HEAD_SIZE = 0.42;
const LAMP_HEAD_W = LAMP_HEAD_SIZE;
const LAMP_HEAD_H = LAMP_HEAD_SIZE * 0.55;
const CAR_SIZE = { x: 1.9, y: 1.45, z: 4.4 };
const CONTAINER_SIZE = { x: 2.4, y: 2.6, z: 6.0 };
const BARRIER_SIZE = { x: 0.5, y: 1.0, z: 2.0 };

const LAMP_STEP = 14.0;          // шаг фонарей вдоль участка, м
const SIDEWALK_OFFSET = 1.2;     // отступ декора от границы участка, м
const MAX_DECOR_INSTANCES = 256; // жёсткий предел на тип
const DECOR_INSTANCES = MAX_DECOR_INSTANCES;     // псевдоним, используется ниже
const CAR_TOP_H = 0.55;                          // высота крыши машины, м
const CAR_TOP_Y = 0.95;                          // подъём крыши над кузовом, м
const LAMP_LIGHT_DISTANCE = 14.0;                // радиус света фонаря, м
const LAMP_LIGHT_DECAY = 1.6;                    // затухание света фонаря
const MAX_LITE_LIGHTS = 12;                      // потолок динамических источников

/** Палитра машин и контейнеров (инстанс-цвета). */
const CAR_COLORS = [0x8a2f2f, 0x2f4f7a, 0x777d84, 0xb8a04a, 0x3a3d42, 0x5d7a4a];
const CONTAINER_COLORS = [0x7a3b2e, 0x2e5a7a, 0x4f6b3a, 0x8a7434, 0x555a60];
const BARRIER_COLOR = 0xd8b13a;

// ---------------------------------------------------------------------------
// Модульные временные объекты (без аллокаций в циклах)
// ---------------------------------------------------------------------------

const _matrix = new THREE.Matrix4();
const _position = new THREE.Vector3();
const _quaternion = new THREE.Quaternion();
const _scale = new THREE.Vector3(1, 1, 1);
const _euler = new THREE.Euler();
const _color = new THREE.Color();

// ---------------------------------------------------------------------------
// Вспомогательные функции
// ---------------------------------------------------------------------------

/**
 * Создаёт InstancedMesh с матрицами-identiy, тенями по качеству.
 * @param {THREE.BufferGeometry} geometry
 * @param {THREE.Material} material
 * @param {number} capacity
 * @param {import('../core/settings.js').Settings} settings
 * @returns {THREE.InstancedMesh}
 */
function createInstanced(geometry, material, capacity, settings) {
  const mesh = new THREE.InstancedMesh(geometry, material, capacity);
  mesh.castShadow = settings.quality !== 'low';
  mesh.receiveShadow = true;
  mesh.frustumCulled = false; // инстансы разбросаны по карте, culling по группе
  mesh.count = 0;
  return mesh;
}

/**
 * Записывает трансформацию в i-й инстанс.
 * @param {THREE.InstancedMesh} mesh
 * @param {number} index
 * @param {number} x
 * @param {number} y
 * @param {number} z
 * @param {number} rotY
 * @param {number} [scale=1]
 */
function setInstance(mesh, index, x, y, z, rotY, scale = 1) {
  _euler.set(0, rotY, 0);
  _quaternion.setFromEuler(_euler);
  _position.set(x, y, z);
  _scale.setScalar(scale);
  _matrix.compose(_position, _quaternion, _scale);
  mesh.setMatrixAt(index, _matrix);
}

/**
 * Собирает точки вдоль периметров участков (тротуары) для размещения декора.
 * @param {Array<{x:number,z:number,w:number,d:number}>} plots
 * @returns {{lamps:Array<{x:number,z:number,rotY:number}>, spots:Array<{x:number,z:number,rotY:number}>}}
 */
function collectPerimeterPoints(plots) {
  const lamps = [];
  const spots = [];
  for (let p = 0; p < plots.length; p++) {
    const plot = plots[p];
    const halfW = plot.w * 0.5 + SIDEWALK_OFFSET;
    const halfD = plot.d * 0.5 + SIDEWALK_OFFSET;
    const perimeter = 2 * (plot.w + plot.d);

    // Фонари — равномерно с шагом LAMP_STEP по периметру.
    const lampCount = Math.max(2, Math.floor(perimeter / LAMP_STEP));
    for (let i = 0; i < lampCount; i++) {
      const t = (i / lampCount) * perimeter;
      const pt = perimeterPoint(plot.x, plot.z, halfW, halfD, t, plot.w, plot.d);
      lamps.push(pt);
    }
    // Свободные пятна для машин/контейнеров/отбойников.
    const spotCount = Math.floor(perimeter / 6);
    for (let i = 0; i < spotCount; i++) {
      const t = ((i + 0.5) / spotCount) * perimeter;
      spots.push(perimeterPoint(plot.x, plot.z, halfW, halfD, t, plot.w, plot.d));
    }
  }
  return { lamps, spots };
}

/**
 * Точка на прямоугольном контуре (обход против часовой, начало — юго-запад).
 * rotY направлен вдоль касательной контура.
 * @returns {{x:number, z:number, rotY:number}}
 */
function perimeterPoint(cx, cz, halfW, halfD, t, w, d) {
  const p = 2 * (w + d);
  let s = ((t % p) + p) % p;
  if (s < w) {
    return { x: cx - halfW + s, z: cz - halfD, rotY: 0 };
  }
  s -= w;
  if (s < d) {
    return { x: cx + halfW, z: cz - halfD + s, rotY: Math.PI * 0.5 };
  }
  s -= d;
  if (s < w) {
    return { x: cx + halfW - s, z: cz + halfD, rotY: Math.PI };
  }
  s -= w;
  return { x: cx - halfW, z: cz + halfD - s, rotY: Math.PI * 1.5 };
}

/**
 * Проверка: не попадает ли декор в точку спавна (радиус безопасности).
 * @param {Array<{x:number,y:number,z:number}>} spawnPoints
 * @param {number} x
 * @param {number} z
 * @returns {boolean}
 */
function isClearOfSpawns(spawnPoints, x, z) {
  const SAFE_R2 = 9; // 3 м в квадрате
  for (let i = 0; i < spawnPoints.length; i++) {
    const dx = spawnPoints[i].x - x;
    const dz = spawnPoints[i].z - z;
    if (dx * dx + dz * dz < SAFE_R2) return false;
  }
  return true;
}

// ---------------------------------------------------------------------------
// Построение декора
// ---------------------------------------------------------------------------

/**
 * Строит весь уличный декор города инстансированными мешами.
 * @param {Array} plots — участки от buildStreets
 * @param {Array} spawnPoints — точки спавна (для отсечения декора)
 * @param {import('../core/settings.js').Settings} settings
 * @param {ReturnType<typeof createRng>} rng
 * @returns {{group: THREE.Group, colliders: Array}}
 */
function buildStreetDecor(plots, spawnPoints, settings, rng) {
  const group = new THREE.Group();
  group.name = 'streetDecor';
  const colliders = [];

  const metal = tileTextures(makeMetal(), 1, 1);
  const concrete = tileTextures(makeConcrete(), 1, 1);

  const metalMat = new THREE.MeshStandardMaterial({ map: metal.map, normalMap: metal.normalMap, roughnessMap: metal.roughnessMap, roughness: 0.55, metalness: 0.7 });
  const darkMat = new THREE.MeshStandardMaterial({ color: 0x22262b, roughness: 0.4, metalness: 0.6 });
  const lampGlowMat = new THREE.MeshStandardMaterial({
    color: 0xfff2cc,
    emissive: 0xffdf9e,
    emissiveIntensity: settings.quality === 'low' ? 0.8 : 1.6,
  });
  const carMat = new THREE.MeshStandardMaterial({ map: metal.map, normalMap: metal.normalMap, roughnessMap: metal.roughnessMap, roughness: 0.5, metalness: 0.4 });
  const containerMat = new THREE.MeshStandardMaterial({ roughness: 0.8, metalness: 0.25 });
  const barrierMat = new THREE.MeshStandardMaterial({ map: concrete.map, normalMap: concrete.normalMap, roughnessMap: concrete.roughnessMap, color: BARRIER_COLOR, roughness: 0.9 });

  // Геометрии (создаём по одной, переиспользуем инстансингом).
  const poleGeo = new THREE.CylinderGeometry(LAMP_POLE_RADIUS, LAMP_POLE_RADIUS * 1.3, LAMP_HEIGHT, 6);
  poleGeo.translate(0, LAMP_HEIGHT * 0.5, 0);
  const headGeo = new THREE.BoxGeometry(LAMP_HEAD_W, LAMP_HEAD_H, LAMP_HEAD_W);
  headGeo.translate(0, LAMP_HEIGHT - LAMP_HEAD_H * 0.5, 0);
  const carGeo = new THREE.BoxGeometry(CAR_SIZE.x, CAR_SIZE.y, CAR_SIZE.z);
  const carTopGeo = new THREE.BoxGeometry(CAR_SIZE.x * 0.8, CAR_TOP_H, CAR_SIZE.z * 0.55);
  carTopGeo.translate(0, CAR_TOP_Y, -CAR_SIZE.z * 0.12);
  const containerGeo = new THREE.BoxGeometry(CONTAINER_SIZE.x, CONTAINER_SIZE.y, CONTAINER_SIZE.z);
  const barrierGeo = new THREE.BoxGeometry(BARRIER_SIZE.x, BARRIER_SIZE.y, BARRIER_SIZE.z);

  // Инстанс-меши с фиксированной ёмкостью.
  const poles = createInstanced(poleGeo, darkMat, DECOR_INSTANCES, settings);
  const heads = createInstanced(headGeo, lampGlowMat, DECOR_INSTANCES, settings);
  const cars = createInstanced(carGeo, carMat, DECOR_INSTANCES, settings);
  const carTops = createInstanced(carTopGeo, darkMat, DECOR_INSTANCES, settings);
  const containers = createInstanced(containerGeo, containerMat, DECOR_INSTANCES, settings);
  const barriers = createInstanced(barrierGeo, barrierMat, DECOR_INSTANCES, settings);

  const { lamps, spots } = collectPerimeterPoints(plots);

  // --- Фонари ---
  const lightPositions = [];
  for (let i = 0; i < lamps.length && poles.count < DECOR_INSTANCES; i++) {
    const pt = lamps[i];
    setInstance(poles, poles.count, pt.x, 0, pt.z, pt.rotY);
    setInstance(heads, heads.count, pt.x, 0, pt.z, pt.rotY);
    poles.count++;
    heads.count++;
    // На low PointLight не ставим — светит только emissive.
    if (settings.quality !== 'low' && lightPositions.length < MAX_LITE_LIGHTS) {
      lightPositions.push(pt);
    }
  }

  // --- Машины, контейнеры, отбойники по свободным пятнам ---
  for (let i = 0; i < spots.length; i++) {
    const pt = spots[i];
    if (!isClearOfSpawns(spawnPoints, pt.x, pt.z)) continue;

    const roll = rng.random(); // 0..1
    const yaw = pt.rotY + (rng.random() - 0.5) * 0.35; // лёгкий разброс по углу

    if (roll < 0.45 && cars.count < DECOR_INSTANCES) {
      // Машина: корпус + кабина.
      setInstance(cars, cars.count, pt.x, CAR_SIZE.y * 0.5, pt.z, yaw);
      setInstance(carTops, carTops.count, pt.x, CAR_SIZE.y * 0.5, pt.z, yaw);
      _color.setHex(CAR_COLORS[(rng.random() * CAR_COLORS.length) | 0]);
      cars.setColorAt(cars.count, _color);
      cars.count++;
      carTops.count++;
      colliders.push({
        x: pt.x, y: (CAR_SIZE.y + CAR_TOP_H) * 0.5, z: pt.z,
        hw: CAR_SIZE.x * 0.55, hh: (CAR_SIZE.y + CAR_TOP_H) * 0.5, hd: CAR_SIZE.z * 0.5,
        rotY: yaw,
      });
    } else if (roll < 0.7 && containers.count < DECOR_INSTANCES) {
      setInstance(containers, containers.count, pt.x, CONTAINER_SIZE.y * 0.5, pt.z, yaw);
      _color.setHex(CONTAINER_COLORS[(rng.random() * CONTAINER_COLORS.length) | 0]);
      containers.setColorAt(containers.count, _color);
      containers.count++;
      colliders.push({
        x: pt.x, y: CONTAINER_SIZE.y * 0.5, z: pt.z,
        hw: CONTAINER_SIZE.x * 0.5, hh: CONTAINER_SIZE.y * 0.5, hd: CONTAINER_SIZE.z * 0.5,
        rotY: yaw,
      });
    } else if (roll < 0.9 && barriers.count < DECOR_INSTANCES) {
      setInstance(barriers, barriers.count, pt.x, BARRIER_SIZE.y * 0.5, pt.z, pt.rotY);
      barriers.count++;
      colliders.push({
        x: pt.x, y: BARRIER_SIZE.y * 0.5, z: pt.z,
        hw: BARRIER_SIZE.x * 0.5, hh: BARRIER_SIZE.y * 0.5, hd: BARRIER_SIZE.z * 0.5,
        rotY: pt.rotY,
      });
    }
  }

  // Финализация инстансов.
  for (const m of [poles, heads, cars, carTops, containers, barriers]) {
    m.instanceMatrix.needsUpdate = true;
    if (m.instanceColor) m.instanceColor.needsUpdate = true;
    group.add(m);
  }

  // --- Реальные точечные источники света у фонарей (medium/high) ---
  if (settings.quality !== 'low') {
    const intensity = settings.quality === 'high' ? 6 : 4;
    for (let i = 0; i < lightPositions.length; i++) {
      const pt = lightPositions[i];
      const light = new THREE.PointLight(0xffdf9e, intensity, LAMP_LIGHT_DISTANCE, LAMP_LIGHT_DECAY);
      light.position.set(pt.x, LAMP_HEIGHT - LAMP_HEAD_H, pt.z);
      group.add(light);
    }
  }

  return { group, colliders };
}

// ---------------------------------------------------------------------------
/**
 * Приводит коллайдер к формату, который ждёт buildStaticColliders:
 * {position: {x, y, z}, size: {x, y, z}} с ПОЛНЫМИ габаритами.
 *
 * Модули писались независимо и договориться о формате не могли: улицы отдают
 * массивы [x,y,z], здания — объекты с halfExtents, декор — плоский вид
 * {x, y, z, hw, hh, hd}. Нормализуем здесь, в месте сборки.
 *
 * @param {object} raw коллайдер в любом из трёх видов
 * @returns {{position: {x: number, y: number, z: number}, size: {x: number, y: number, z: number}}}
 */
function normalizeCollider(raw) {
  // Улицы: position и size массивами
  if (Array.isArray(raw.position)) {
    const [px, py, pz] = raw.position;
    const [sx, sy, sz] = raw.size;
    return { position: { x: px, y: py, z: pz }, size: { x: sx, y: sy, z: sz } };
  }
  // Здания: halfExtents вместо габаритов
  if (raw.halfExtents) {
    const h = raw.halfExtents;
    return {
      position: raw.position,
      size: { x: h.x * 2, y: h.y * 2, z: h.z * 2 },
    };
  }
  // Декор: плоский вид с полу-габаритами hw/hh/hd
  if (raw.hw !== undefined) {
    return {
      position: { x: raw.x, y: raw.y, z: raw.z },
      size: { x: raw.hw * 2, y: raw.hh * 2, z: raw.hd * 2 },
    };
  }
  return raw;
}

// Публичный API
// ---------------------------------------------------------------------------

/**
 * Строит весь город: улицы, здания, уличный декор.
 * Файл-композитор: геометрию улиц/зданий собирают их модули,
 * здесь — только слияние результатов, декор и список коллайдеров.
 *
 * @param {THREE.Scene} scene
 * @param {import('../core/settings.js').Settings} settings
 * @param {number} seed — сид генерации мира
 * @returns {{group: THREE.Group, colliders: Array, spawnPoints: Array<{x:number,y:number,z:number}>}}
 */
export function buildCity(scene, settings, seed) {
  const rng = createRng(seed);

  const group = new THREE.Group();
  group.name = 'city';

  // Улицы: { group, plots, colliders, spawnPoints }
  const streets = buildStreets(settings, rng.random);
  for (const mesh of streets.meshes) group.add(mesh);

  // Здания по участкам от улиц.
  const buildings = buildBuildings(streets.plots, settings, rng.random);
  for (const mesh of buildings.meshes) group.add(mesh);

  // Уличный декор (инстансинг) + его коллайдеры.
  const spawnPoints = streets.spawnPoints;
  const decor = buildStreetDecor(streets.plots, spawnPoints, settings, rng);
  group.add(decor.group);

  const colliders = [];
  for (const c of streets.colliders) colliders.push(normalizeCollider(c));
  for (const c of buildings.colliders) colliders.push(normalizeCollider(c));
  for (const c of decor.colliders) colliders.push(normalizeCollider(c));

  scene.add(group);

  return { group, colliders, spawnPoints };
}
