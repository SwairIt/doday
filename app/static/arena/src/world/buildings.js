/**
 * src/world/buildings.js
 * Процедурные здания на участках: коробки с эмиссивными окнами,
 * аркады укрытий, запечённое затенение в вершинных цветах, LOD.
 */

import * as THREE from 'three';
import { makeBrick, makeConcrete, tileTextures } from './textures.js';

/** Высота зданий, м */
const MIN_BUILDING_HEIGHT = 8;
const MAX_BUILDING_HEIGHT = 34;
/** Высота аркадного этажа, м */
const ARCADE_HEIGHT = 4;
/** Высота аркадного этажа со свесом крыши */
const ARCADE_FULL_HEIGHT = 4.6;
/** Радиус колонн аркады, м */
const COLUMN_RADIUS = 0.35;
/** Глубина отступа колонн от фасада, м */
const ARCADE_INSET = 3.0;
/** Отступ здания от края участка, м */
const PLOT_INSET_MIN = 1.0;
const PLOT_INSET_MAX = 3.0;
/** Размер окна, м */
const WINDOW_WIDTH = 1.4;
const WINDOW_HEIGHT = 1.8;
/** Шаг оконной сетки, м */
const WINDOW_STEP_X = 3.0;
const WINDOW_STEP_Z = 3.2;
/** Шанс включённого света в окне */
const WINDOW_LIT_CHANCE = 0.35;
/** Дистанция переключения LOD, м */
const LOD_DISTANCE_HIGH = 90;

// Модульные временные — без аллокаций в циклах
const _matrix = new THREE.Matrix4();
const _pos = new THREE.Vector3();
const _quat = new THREE.Quaternion();
const _scale = new THREE.Vector3();
const _yAxis = new THREE.Vector3(0, 1, 0);
const _color = new THREE.Color();

/**
 * Добавляет колонну аркады: инстанс + коллайдер.
 * @param {Array<{x:number,y:number,z:number}>} columnInstances
 * @param {Array<object>} colliders
 * @param {number} x
 * @param {number} z
 */
function pushColumn(columnInstances, colliders, x, z) {
  columnInstances.push({ x, y: ARCADE_HEIGHT * 0.5, z });
  colliders.push({
    position: { x, y: ARCADE_HEIGHT * 0.5, z },
    rotation: { x: 0, y: 0, z: 0, w: 1 },
    halfExtents: {
      x: COLUMN_RADIUS,
      y: ARCADE_HEIGHT * 0.5,
      z: COLUMN_RADIUS,
    },
  });
}

/**
 * Пишет вершинные цвета с запечённым затенением: низ и углы темнее.
 * @param {THREE.BoxGeometry} geometry
 * @param {number} width
 * @param {number} height
 * @param {number} depth
 */
function bakeShadingToVertexColors(geometry, width, height, depth) {
  const position = geometry.getAttribute('position');
  const count = position.count;
  const colors = new Float32Array(count * 3);
  const halfH = height * 0.5;
  const halfW = width * 0.5;
  const halfD = depth * 0.5;

  for (let i = 0; i < count; i++) {
    const x = position.getX(i);
    const y = position.getY(i);
    const z = position.getZ(i);
    // Вертикальный градиент: 0.35 внизу -> 1.0 вверху
    const vertical = 0.35 + 0.65 * (y + halfH) / height;
    // Углы темнее на 25%
    const nx = Math.abs(x) / halfW;
    const nz = Math.abs(z) / halfD;
    const corner = 1.0 - 0.25 * Math.min(1, nx * nz);
    const shade = Math.min(1, vertical * corner);
    colors[i * 3] = shade;
    colors[i * 3 + 1] = shade;
    colors[i * 3 + 2] = shade;
  }
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
}

/**
 * Геометрии корпуса здания, кэш по ключу размеров.
 * @type {Map<string, THREE.BoxGeometry>}
 */
const bodyGeomCache = new Map();

/**
 * @param {number} w
 * @param {number} h
 * @param {number} d
 * @param {boolean} withColors
 * @returns {THREE.BoxGeometry}
 */
function getBodyGeometry(w, h, d, withColors) {
  const key = `${w.toFixed(2)}|${h.toFixed(2)}|${d.toFixed(2)}|${withColors ? 1 : 0}`;
  let geom = bodyGeomCache.get(key);
  if (!geom) {
    geom = new THREE.BoxGeometry(w, h, d);
    geom.translate(0, h * 0.5, 0);
    if (withColors) {
      bakeShadingToVertexColors(geom, w, h, d);
    }
    bodyGeomCache.set(key, geom);
  }
  return geom;
}

/**
 * Наполняет массив матриц окон для одного здания.
 * Окна кладутся на 4 фасада, начиная выше аркадного/первого этажа.
 * @param {Array<THREE.Matrix4>} out
 * @param {Array<boolean>} outLit
 * @param {number} bx центр здания X
 * @param {number} bz центр здания Z
 * @param {number} w
 * @param {number} h
 * @param {number} d
 * @param {number} baseY нижний ряд окон
 * @param {() => number} rng
 */
function collectWindows(out, outLit, bx, bz, w, h, d, baseY, rng) {
  const topY = h - WINDOW_HEIGHT * 0.5 - 0.6;
  const inset = 0.06; // чуть наружу стены, чтобы не было z-fight
  const halfW = w * 0.5 + inset;
  const halfD = d * 0.5 + inset;

  for (let y = baseY + WINDOW_HEIGHT * 0.5; y < topY; y += WINDOW_STEP_Z) {
    // Фасады по X (стены, смотрящие вдоль Z)
    for (let x = -w * 0.5 + WINDOW_STEP_X; x < w * 0.5 - WINDOW_STEP_X * 0.4; x += WINDOW_STEP_X) {
      for (let side = 0; side < 2; side++) {
        const z = side === 0 ? halfD : -halfD;
        _pos.set(bx + x, y, bz + z);
        _quat.setFromAxisAngle(_yAxis, side === 0 ? 0 : Math.PI);
        _matrix.compose(_pos, _quat, _scale.set(1, 1, 1));
        out.push(_matrix.clone());
        outLit.push(rng() < WINDOW_LIT_CHANCE);
      }
    }
    // Фасады по Z (стены, смотрящие вдоль X)
    for (let z = -d * 0.5 + WINDOW_STEP_X; z < d * 0.5 - WINDOW_STEP_X * 0.4; z += WINDOW_STEP_X) {
      for (let side = 0; side < 2; side++) {
        const x = side === 0 ? halfW : -halfW;
        _pos.set(bx + x, y, bz + z);
        _quat.setFromAxisAngle(_yAxis, side === 0 ? Math.PI * 0.5 : -Math.PI * 0.5);
        _matrix.compose(_pos, _quat, _scale.set(1, 1, 1));
        out.push(_matrix.clone());
        outLit.push(rng() < WINDOW_LIT_CHANCE);
      }
    }
  }
}

/**
 * Строит здания на участках.
 * @param {Array<{x:number, z:number, w:number, d:number}>} plots участки (центр + размеры)
 * @param {import('../core/settings.js').Settings} settings
 * @param {() => number} rng функция 0..1 (mulberry32 из rng.js)
 * @returns {{meshes: THREE.Object3D[], colliders: Array<object>}}
 */
export function buildBuildings(plots, settings, rng) {
  const meshes = [];
  const colliders = [];
  const quality = settings.get('quality');

  // Материалы
  const brick = tileTextures(makeBrick(), 1, 1);
  const concrete = tileTextures(makeConcrete(), 1, 1);

  const bodyMaterial = new THREE.MeshStandardMaterial({
    map: brick.map,
    normalMap: brick.normalMap,
    roughnessMap: brick.roughnessMap,
    vertexColors: true,
    roughness: 0.9,
    metalness: 0.0,
  });
  const lodMaterial = new THREE.MeshStandardMaterial({
    map: concrete.map,
    roughness: 0.95,
    metalness: 0.0,
  });
  const columnMaterial = new THREE.MeshStandardMaterial({
    map: concrete.map,
    roughness: 0.85,
    metalness: 0.0,
  });

  // Сбор данных
  /** @type {Array<THREE.Matrix4>} */
  const windowMatrices = [];
  /** @type {Array<boolean>} */
  const windowLit = [];
  /** @type {Array<{x:number,y:number,z:number}>} */
  const columnInstances = [];

  // Группы зданий по размеру для InstancedMesh (небольшое число уникальных размеров)
  // Чтобы не плодить сотни дробных ключей, здания идут отдельными LOD-объектами,
  // но телесная геометрия кэшируется, а окна/колонны — инстансами.
  const maxBuildings = quality === 'low' ? Math.min(plots.length, 24) : plots.length;

  for (let i = 0; i < maxBuildings; i++) {
    const plot = plots[i];
    const inset = PLOT_INSET_MIN + rng() * (PLOT_INSET_MAX - PLOT_INSET_MIN);
    const w = Math.max(6, plot.w - inset * 2);
    const d = Math.max(6, plot.d - inset * 2);
    const h = MIN_BUILDING_HEIGHT + rng() * (MAX_BUILDING_HEIGHT - MIN_BUILDING_HEIGHT);
    const hasArcade = rng() < 1 / 3;
    const bx = plot.x;
    const bz = plot.z;

    // Коллайдер здания
    if (!hasArcade) {
      colliders.push({
        position: { x: bx, y: h * 0.5, z: bz },
        rotation: { x: 0, y: 0, z: 0, w: 1 },
        halfExtents: { x: w * 0.5, y: h * 0.5, z: d * 0.5 },
      });
    } else {
      // Аркада: коллайдер сплошного верхнего объёма + колонны по периметру
      const upperH = h - ARCADE_HEIGHT;
      colliders.push({
        position: { x: bx, y: ARCADE_HEIGHT + upperH * 0.5, z: bz },
        rotation: { x: 0, y: 0, z: 0, w: 1 },
        halfExtents: { x: w * 0.5, y: upperH * 0.5, z: d * 0.5 },
      });
      // Колонны по периметру (внутри аркадного отступа)
      const step = ARCADE_INSET * 1.5;
      const innerW = w * 0.5 - COLUMN_RADIUS;
      const innerD = d * 0.5 - COLUMN_RADIUS;
      for (let x = -innerW; x <= innerW + 0.001; x += step) {
        pushColumn(columnInstances, colliders, bx + x, bz - innerD);
        pushColumn(columnInstances, colliders, bx + x, bz + innerD);
      }
      for (let z = -innerD + step; z <= innerD - step + 0.001; z += step) {
        pushColumn(columnInstances, colliders, bx - innerW, bz + z);
        pushColumn(columnInstances, colliders, bx + innerW, bz + z);
      }
    }

    // LOD-объект здания
    const bodyHeight = hasArcade ? h - ARCADE_HEIGHT : h;
    const bodyGeom = getBodyGeometry(w, bodyHeight, d, true);
    const hiMesh = new THREE.Mesh(bodyGeom, bodyMaterial);
    hiMesh.castShadow = quality !== 'low';
    hiMesh.receiveShadow = true;
    if (hasArcade) {
      // Сплошная часть поднята над аркадой
      hiMesh.position.y = ARCADE_HEIGHT;
    }

    const lodGeom = getBodyGeometry(w, h, d, false);
    const loMesh = new THREE.Mesh(lodGeom, lodMaterial);

    const lod = new THREE.LOD();
    lod.addLevel(hiMesh, 0);
    lod.addLevel(loMesh, LOD_DISTANCE_HIGH);
    lod.position.set(bx, 0, bz);
    meshes.push(lod);

    // Окна только для high-уровня детализации (и не на низком качестве)
    if (quality !== 'low') {
      const baseY = hasArcade ? ARCADE_FULL_HEIGHT : WINDOW_STEP_Z * 0.5;
      collectWindows(windowMatrices, windowLit, bx, bz, w, h, d, baseY, rng);
    }
  }

  // Инстансированные колонны аркад
  if (columnInstances.length > 0) {
    const columnGeom = new THREE.BoxGeometry(
      COLUMN_RADIUS * 2,
      ARCADE_HEIGHT,
      COLUMN_RADIUS * 2,
    );
    const columns = new THREE.InstancedMesh(columnGeom, columnMaterial, columnInstances.length);
    for (let i = 0; i < columnInstances.length; i++) {
      const c = columnInstances[i];
      _pos.set(c.x, c.y, c.z);
      _quat.identity();
      _matrix.compose(_pos, _quat, _scale.set(1, 1, 1));
      columns.setMatrixAt(i, _matrix);
    }
    columns.instanceMatrix.needsUpdate = true;
    columns.castShadow = quality !== 'low';
    columns.receiveShadow = true;
    meshes.push(columns);
  }

  // Инстансированные эмиссивные окна
  if (windowMatrices.length > 0) {
    const winGeom = new THREE.PlaneGeometry(WINDOW_WIDTH, WINDOW_HEIGHT);
    const winMat = new THREE.MeshStandardMaterial({
      color: 0x11131a,
      emissive: 0xffffff,
      emissiveIntensity: 1.6,
      roughness: 0.4,
      metalness: 0.2,
      side: THREE.DoubleSide,
    });
    const windows = new THREE.InstancedMesh(winGeom, winMat, windowMatrices.length);
    for (let i = 0; i < windowMatrices.length; i++) {
      windows.setMatrixAt(i, windowMatrices[i]);
      if (windowLit[i]) {
        // Тёплый или холодный свет, случайная яркость
        if (rng() < 0.7) {
          _color.setHSL(0.09 + rng() * 0.04, 0.7, 0.55 + rng() * 0.2);
        } else {
          _color.setHSL(0.58, 0.5, 0.6 + rng() * 0.2);
        }
      } else {
        _color.setRGB(0, 0, 0);
      }
      windows.setColorAt(i, _color);
    }
    windows.instanceMatrix.needsUpdate = true;
    if (windows.instanceColor) {
      windows.instanceColor.needsUpdate = true;
    }
    meshes.push(windows);
  }

  return { meshes, colliders };
}
