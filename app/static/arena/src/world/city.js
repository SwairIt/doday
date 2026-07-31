/**
 * @module src/world/city
 * Seeded-генератор городского квартала 200x200 м для Doday Arena.
 *
 * Структура:
 *  - сетка улиц с тротуарами и бордюрами;
 *  - здания разной высоты, часть — с аркадами на колоннах (проходной 1-й этаж);
 *  - окна — эмиссивные InstancedMesh со случайным включением;
 *  - фонари, машины, контейнеры, отбойники — InstancedMesh;
 *  - запечённое затенение в vertexColors (низ зданий и углы темнее);
 *  - LOD для дальних зданий;
 *  - colliders — AABB для физики, spawnPoints — точки на улицах.
 *
 * ГПСЧ: mulberry32 — полная детерминированность по seed.
 */

import * as THREE from 'three';

// ---------------------------------------------------------------------------
// Константы
// ---------------------------------------------------------------------------

/** Полный размер квартала (м), центр в (0,0). */
const CITY_SIZE = 200;
const HALF = CITY_SIZE / 2;

/** Сетка улиц: координаты осей дорог (центры проезжей части). */
const ROAD_WIDTH = 8;
const SIDEWALK_WIDTH = 3;
const CURB_HEIGHT = 0.14;

const BLOCK_PITCH = 40;               // шаг сетки
const ROAD_COORDS = [-80, -40, 0, 40, 80]; // центры дорог

const BUILDING_MIN_H = 8;
const BUILDING_MAX_H = 34;
const BUILDING_MARGIN = 1.2;          // отступ здания от края участка
const ARCADE_CHANCE = 0.35;           // вероятность аркады первого этажа
const ARCADE_HEIGHT = 4;
const COLUMN_RADIUS = 0.35;

const WINDOW_W = 1.2;
const WINDOW_H = 1.6;
const WINDOW_COL_SPACING = 2.2;
const WINDOW_ROW_SPACING = 3.0;
const WINDOW_LIT_CHANCE = 0.3;

const LAMP_HEIGHT = 5.2;
const LAMP_SPACING = 16;

const LOD_SWITCH_DISTANCE = 90;       // дальше — low-poly

const CAR_CHANCE_PER_SPOT = 0.4;
const CAR_SPACING = 7;

const PROP_DENSITY = 0.5;             // доля углов квартала с пропсами

const AO_BOTTOM_DARK = 0.45;          // множитель у земли
const AO_CORNER_DARK = 0.75;          // множитель у углов

const EMISSIVE_WINDOW_COLOR = 0xffd9a0;

// ---------------------------------------------------------------------------
// ГПСЧ mulberry32
// ---------------------------------------------------------------------------

/**
 * mulberry32: детерминированный ГПСЧ.
 * @param {number} seed
 * @returns {() => number} функция, возвращающая [0,1)
 */
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// Временные объекты (без аллокаций в циклах)
// ---------------------------------------------------------------------------

const _tmpMatrix = new THREE.Matrix4();
const _tmpPos = new THREE.Vector3();
const _tmpQuat = new THREE.Quaternion();
const _tmpScale = new THREE.Vector3();
const _tmpEuler = new THREE.Euler();
const _tmpColor = new THREE.Color();

/**
 * Собрать матриц во временный объект.
 */
function composeMatrix(x, y, z, rotY, sx, sy, sz) {
  _tmpPos.set(x, y, z);
  _tmpEuler.set(0, rotY, 0);
  _tmpQuat.setFromEuler(_tmpEuler);
  _tmpScale.set(sx, sy, sz);
  _tmpMatrix.compose(_tmpPos, _tmpQuat, _tmpScale);
  return _tmpMatrix;
}

// ---------------------------------------------------------------------------
// Здания: геометрия с запечённым AO в вершинных цветах
// ---------------------------------------------------------------------------

/**
 * Создать геометрию коробки здания с вершинным AO:
 * низ темнее, углы по X/Z темнее.
 * @param {number} w
 * @param {number} h
 * @param {number} d
 * @returns {THREE.BoxGeometry}
 */
function makeBuildingGeometry(w, h, d) {
  const geo = new THREE.BoxGeometry(w, h, d, 1, 3, 1);
  geo.translate(0, h / 2, 0);
  const pos = geo.attributes.position;
  const colors = new Float32Array(pos.count * 3);
  const wallW2 = w / 2, wallD2 = d / 2;
  for (let i = 0; i < pos.count; i++) {
    const y = pos.getY(i);
    const x = pos.getX(i);
    const z = pos.getZ(i);
    // Вертикальный градиент: низ темнее
    const tY = Math.min(1, y / (h * 0.6));
    let lum = AO_BOTTOM_DARK + (1 - AO_BOTTOM_DARK) * tY * tY;
    // Углы темнее: близость к углу по обеим осям
    const fx = Math.abs(x) / wallW2;
    const fz = Math.abs(z) / wallD2;
    const corner = fx * fz; // 1 на углу
    lum *= 1 - (1 - AO_CORNER_DARK) * corner;
    colors[i * 3] = lum;
    colors[i * 3 + 1] = lum;
    colors[i * 3 + 2] = lum;
  }
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geo;
}

/**
 * Набор материалов для зданий с вершинным цветом.
 */
function makeBuildingMaterial(tint) {
  return new THREE.MeshStandardMaterial({
    color: tint,
    vertexColors: true,
    roughness: 0.9,
    metalness: 0.05,
  });
}

// Тёплые оттенки бетона/кирпича (линейная палитра выбирается ГПСЧ)
const BUILDING_TINTS = [0xb8b0a4, 0x9aa3ab, 0xa08```javascript
4d4a, 0xc2b49a, 0x8f9799, 0xab9a8a];

// ---------------------------------------------------------------------------
// Дороги, тротуары, бордюры
// ---------------------------------------------------------------------------

/**
 * Построить дорожную сетку: асфальт, тротуары вдоль краёв, бордюры.
 * @param {THREE.Group} group
 * @param {Array<{position:number[], size:number[]}>} colliders
 */
function buildRoads(group, colliders) {
  const asphaltMat = new THREE.MeshStandardMaterial({ color: 0x3a3d40, roughness: 1.0, metalness: 0 });
  const sidewalkMat = new THREE.MeshStandardMaterial({ color: 0x777a7c, roughness: 0.95, metalness: 0 });
  const curbMat = new THREE.MeshStandardMaterial({ color: 0x999c9e, roughness: 0.9, metalness: 0 });
  const lineMat = new THREE.MeshBasicMaterial({ color: 0xd8c94a });

  const span = CITY_SIZE;
  const curbW = 0.3;

  for (let i = 0; i < ROAD_COORDS.length; i++) {
    const c = ROAD_COORDS[i];
    const vert = new THREE.Mesh(new THREE.BoxGeometry(ROAD_WIDTH, 0.1, span + ROAD_WIDTH), asphaltMat);
    vert.position.set(c, 0.05, 0);
    vert.receiveShadow = true;
    group.add(vert);

    const horiz = new THREE.Mesh(new THREE.BoxGeometry(span + ROAD_WIDTH, 0.1, ROAD_WIDTH), asphaltMat);
    horiz.position.set(0, 0.05, c);
    horiz.receiveShadow = true;
    group.add(horiz);

    // Разметка вдоль дороги (для визуала, без коллайдеров)
    const segLen = 2.5, gapLen = 2.0;
    const lineW = 0.2;
    for (let p = -HALF; p < HALF; p += segLen + gapLen) {
      const mid = p + segLen / 2;
      const lv = new THREE.Mesh(new THREE.BoxGeometry(lineW, 0.02, segLen), lineMat);
      lv.position.set(c, 0.115, mid);
      group.add(lv);
      const lh = new THREE.Mesh(new THREE.BoxGeometry(segLen, 0.02, lineW), lineMat);
      lh.position.set(mid, 0.115, c);
      group.add(lh);
    }
  }

  // Тротуары: внутри каждого квартала по периметру участка
  const inner = BLOCK_PITCH - ROAD_WIDTH;
  for (let bx = 0; bx < ROAD_COORDS.length - 1; bx++) {
    for (let bz = 0; bz < ROAD_COORDS.length - 1; bz++) {
      const cx = (ROAD_COORDS[bx] + ROAD_COORDS[bx + 1]) / 2;
      const cz = (ROAD_COORDS[bz] + ROAD_COORDS[bz + 1]) / 2;

      // Плита тротуара кольцом (полный участок), над которой сидят здания
      const slab = new THREE.Mesh(new THREE.BoxGeometry(inner, CURB_HEIGHT + 0.02, inner), sidewalkMat);
      slab.position.set(cx, (CURB_HEIGHT + 0.02) / 2, cz);
      slab.receiveShadow = true;
      group.add(slab);

      // Бордюры по четырём сторонам участка (узкие порожки) + коллайдеры
      const outer = ROAD_WIDTH / 2;
      const positions = [
        [cx, CURB_HEIGHT / 2, cz - inner / 2 - 0.0, inner + curbW * 2, CURB_HEIGHT, curbW],
        [cx, CURB_HEIGHT / 2, cz + inner / 2 + 0.0, inner + curbW * 2, CURB_HEIGHT, curbW],
        [cx - inner / 2 - 0.0, CURB_HEIGHT / 2, cz, curbW, CURB_HEIGHT, inner],
        [cx + inner / 2 + 0.0, CURB_HEIGHT / 2, cz, curbW, CURB_HEIGHT, inner],
      ];
      for (const [px, py, pz, sx, sy, sz] of positions) {
        const curb = new THREE.Mesh(new THREE.BoxGeometry(sx, sy, sz), curbMat);
        curb.position.set(px, sy / 2, pz);
        group.add(curb);
        colliders.push({ position: [px, sy / 2, pz], size: [sx, sy, sz] });
      }
      void outer;
    }
  }
}

// ---------------------------------------------------------------------------
// Здания и LOD
// ---------------------------------------------------------------------------

/**
 * Найти внутренние участки (блоки) квартала.
 * @returns {Array<{cx:number, cz:number, size:number}>}
 */
function getBlocks() {
  const blocks = [];
  const inner = BLOCK_PITCH - ROAD_WIDTH - 2 * SIDEWALK_WIDTH;
  for (let bx = 0; bx < ROAD_COORDS.length - 1; bx++) {
    for (let bz = 0; bz < ROAD_COORDS.length - 1; bz++) {
      const cx = (ROAD_COORDS[bx] + ROAD_COORDS[bx + 1]) / 2;
      const cz = (ROAD_COORDS[bz] + ROAD_COORDS[bz + 1]) / 2;
      blocks.push({ cx, cz, size: inner });
    }
  }
  return blocks;
}

/**
 * Построить здания: высокая детализация (или аркады) и дальний LOD-куб.
 * @param {THREE.Group} group
 * @param {Array} colliders
 * @param {() => number} rand
 * @param {{x:number, z:number}[]} windowSpecs накапливаемые окна (позиция/нормаль)
 */
function buildBuildings(group, colliders, rand, windowSpecs) {
  const blocks = getBlocks();
  for (const block of blocks) {
    // 1, 2 или 4 строения на участок
    const pattern = rand();
    const subCells = [];
    if (pattern < 0.35) {
      subCells.push({ x: block.cx, z: block.cz, w: block.size, d: block.size });
    } else if (pattern < 0.7) {
      const splitX = rand() < 0.5;
      const half = block.size / 2;
      if (splitX) {
        subCells.push({ x: block.cx - half / 2, z: block.cz, w: half, d: block.size });
        subCells.push({ x: block.cx + half / 2, z: block.cz, w: half, d: block.size });
      } else {
        subCells.push({ x: block.cx, z: block.cz - half / 2, w: block.size, d: half });
        subCells.push({ x: block.cx, z: block.cz + half / 2, w: block.size, d: half });
      }
    } else {
      const half = block.size / 2;
      subCells.push(
        { x: block.cx - half / 2, z: block.cz - half / 2, w: half, d: half },
        { x: block.cx + half / 2, z: block.cz - half / 2, w: half, d: half },
        { x: block.cx - half / 2, z: block.cz + half / 2, w: half, d: half },
        { x: block.cx + half / 2, z: block.cz + half / 2, w: half, d: half },
      );
    }

    for (const cell of subCells) {
      const w = Math.max(4, cell.w - 2 * BUILDING_MARGIN - rand() * 3);
      const d = Math.max(4, cell.d - 2 * BUILDING_MARGIN - rand() * 3);
      const h = BUILDING_MIN_H + rand() * (BUILDING_MAX_H - BUILDING_MIN_H);
      const bx = cell.x + (rand() - 0.5) * (cell.w - w) * 0.5;
      const bz = cell.z + (rand() - 0.5) * (cell.d - d) * 0.5;
      const tint = BUILDING_TINTS[(rand() * BUILDING_TINTS.length) | 0];
      const hasArcade = rand() < ARCADE_CHANCE;

      // LOD-контейнер
      const lod = new THREE.LOD();
      lod.position.set(bx, CURB_HEIGHT, bz);

      if (hasArcade) {
        // --- Высокая детализация: колонны + вертикальное ядро с 2-го этажа
        const upper = new THREE.Mesh```javascript
(
        bakeAO(new THREE.BoxGeometry(w, h - ARCADE_HEIGHT, d), ARCADE_HEIGHT, h, 1.0),
        new THREE.MeshStandardMaterial({ color: tint, roughness: 0.85, vertexColors: true })
      );
      upper.position.y = ARCADE_HEIGHT + (h - ARCADE_HEIGHT) / 2;
      upper.castShadow = true;
      upper.receiveShadow = true;

      const highGroup = new THREE.Group();
      highGroup.add(upper);

      // Колонны по периметру первого этажа
      const colStep = 3.0;
      const inset = 0.6;
      const colGeo = bakeAO(new THREE.BoxGeometry(0.5, ARCADE_HEIGHT, 0.5), 0, ARCADE_HEIGHT, 0.55);
      const colMat = new THREE.MeshStandardMaterial({ color: 0x8e9296, roughness: 0.8, vertexColors: true });
      const colPositions = [];
      for (let x = -w / 2 + inset; x <= w / 2 - inset + 0.01; x += colStep) {
        colPositions.push([x, -d / 2 + inset], [x, d / 2 - inset]);
      }
      for (let z = -d / 2 + inset + colStep; z <= d / 2 - inset - 0.01; z += colStep) {
        colPositions.push([-w / 2 + inset, z], [w / 2 - inset, z]);
      }
      const colInst = new THREE.InstancedMesh(colGeo, colMat, colPositions.length);
      for (let i = 0; i < colPositions.length; i++) {
        _m4.makeTranslation(colPositions[i][0], ARCADE_HEIGHT / 2, colPositions[i][1]);
        colInst.setMatrixAt(i, _m4);
        colInst.instanceMatrix.needsUpdate = true;
      }
      colInst.castShadow = true;
      highGroup.add(colInst);

      // Плита-перекрытие аркады
      const slabGeo = bakeAO(new THREE.BoxGeometry(w, 0.4, d), ARCADE_HEIGHT - 0.4, ARCADE_HEIGHT, 0.5);
      const slab = new THREE.Mesh(slabGeo, colMat);
      slab.position.y = ARCADE_HEIGHT - 0.2;
      highGroup.add(slab);

      lod.addLevel(highGroup, 0);

      // Коллайдеры: только колонны (первый этаж проходной) + верхний блок
      for (const [lx, lz] of colPositions) {
        colliders.push({ position: [bx + lx, CURB_HEIGHT + ARCADE_HEIGHT / 2, bz + lz], size: [0.5, ARCADE_HEIGHT, 0.5] });
      }
      colliders.push({ position: [bx, CURB_HEIGHT + ARCADE_HEIGHT + (h - ARCADE_HEIGHT) / 2, bz], size: [w, h - ARCADE_HEIGHT, d] });
      } else {
        // --- Высокая детализация: сплошной объём с запечённым затенением
        const geo = bakeAO(new THREE.BoxGeometry(w, h, d), 0, h, 1.0);
        const mesh = new THREE.Mesh(geo, new THREE.MeshStandardMaterial({ color: tint, roughness: 0.85, vertexColors: true```javascript
 }));
        mesh.position.y = h / 2;
        mesh.castShadow = true;
        mesh.receiveShadow = true;
        lod.addLevel(mesh, 0);

        colliders.push({ position: [bx, CURB_HEIGHT + h / 2, bz], size: [w, h, d] });
      }

      // --- Дальний LOD: плоский тёмный куб без вершинных цветов
      const lodGeo = bakeAO(new THREE.BoxGeometry(w, h, d), 0, h, 0.6);
      const lodMat = getLodMaterial(tint);
      const far = new THREE.Mesh(lodGeo, lodMat);
      far.position.y = h / 2;
      lod.addLevel(far, LOD_DISTANCE);

      group.add(lod);

      // Собрать окна по фасадам (только высокая детализация видит их до LOD_DISTANCE)
      const windowBaseY = hasArcade ? ARCADE_HEIGHT + 0.6 : 1.1;
      collectWindows(windowSpecs, bx, CURB_HEIGHT + windowBaseY, bz, w, d, h - (windowBaseY) - 0.8, rand);
    }
  }
}

// ---------------------------------------------------------------------------
// Окна
// ---------------------------------------------------------------------------

/**
 * Разложить окна по четырём фасадам здания.
 * @param {Array} specs выходной массив окон
 * @param {number} bx центр здания X
 * @param {number} baseY низ первого оконного ряда
 * @param {number} bz центр здания Z
 * @param {number} w ширина здания
 * @param {number} d глубина здания
 * @param {number} winH высота зоны остекления
 * @param {() => number} rand
 */
function collectWindows(specs, bx, baseY, bz, w, d, winH, rand) {
  const rows = Math.max(0, Math.floor(winH / WINDOW_STEP));
  const yawOffsets = [
    { // фасад +Z
      nx: 0, nz: 1, offX: 0, offZ: d / 2 + WINDOW_DEPTH, yaw: 0,
      span: w, axis: 'x',
    },
    { // фасад -Z
      nx: 0, nz: -1, offX: 0, offZ: -d / 2 - WINDOW_DEPTH, yaw: Math.PI,
      span: w, axis: 'x',
    },
    { // фасад +X
      nx: 1, nz: 0, offX: w / 2 + WINDOW_DEPTH, offZ: 0, yaw: Math.PI / 2,
      span: d, axis: 'z',
    },
    { // фасад -X
      nx: -1, nz: 0, offX: -w / 2 - WINDOW_DEPTH, offZ: 0, yaw: -Math.PI / 2,
      span: d, axis: 'z',
    },
  ];

  for (const face of yawOffsets) {
    const cols = Math.max(1, Math.floor((face.span - 1.5) / WINDOW_STEP));
    if (cols < 1 || rows < 1) continue;
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        // Случайно пропускаем часть окон — фасад не «решётчатый»
        if (rand() < 0.25) continue;
        const t = (c + 0.5) / cols - 0.5;
        const along = t * (face.span - 1.5);
        const px = bx + face.offX + (face.axis === 'x' ? along : 0);
        const pz = bz + face.offZ + (face.axis === 'z' ? along : 0);
        const py = baseY + 0.4 + r * WINDOW_STEP + WINDOW_SIZE * 0.5;
        specs.push({ x: px, y: py, z: pz, yaw: face.yaw, lit: rand() < WINDOW_LIT_CHANCE });
      }
    }
  }
}

/**
 * Отрисовать все окна одним InstancedMesh с эмиссивным материалом.
 * Тёмные окна получают почти чёрный цвет экземпляра.
 * @param {THREE.Group} group
 * @param {Array} specs
 */
function buildWindows(group, specs) {
  if (specs.length === 0) return;
  const geo = new THREE.PlaneGeometry(WINDOW_SIZE, WINDOW_SIZE);
  const mat = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    emissive: 0xffffff,
    emissiveIntensity: 2.0,
    roughness: 0.4,
    metalness: 0.0,
    side: THREE.DoubleSide,
  });
  const inst = new THREE.InstancedMesh(geo, mat, specs.length);
  inst.instanceColor = new THREE.InstancedBufferAttribute(new Float32Array(specs.length * 3), 3);
  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  for (let i = 0; i < specs.length; i++) {
    const s = specs[i];
    e.set(0, s.yaw, 0);
    q.setFromEuler(e);
    _m4.compose(_v1.set(s.x, s.y, s.z), q, _v2.set(1, 1, 1));
    inst.setMatrixAt(i, _m4);
    if (s.lit) {
      _c1.setHex(WINDOW_LIT_COLOR);
      // Лёгкий разброс яркости включённых окон
      const k = 0.7 + ((i * 7919) % 100) / 300;
      inst.setColorAt(i, _c1.multiplyScalar(k));
    } else {
      _c1.setHex(WINDOW_DARK_COLOR);
      inst.setColorAt(i, _c1);
    }
  }
  inst.instanceMatrix.needsUpdate = true;
  inst.instanceColor.needsUpdate = true;
  inst.frustumCulled = false;
  group.add(inst);
}

// ---------------------------------------------------------------------------
// Материалы и текстуры (генерируются кодом, без ассетов)
// ---------------------------------------------------------------------------

/** @returns {HTMLCanvasElement} процедурная разметка асфальта */
function makeRoadCanvas() {
  const cv = document.createElement('canvas');
  cv.width = 256;
  cv.height = 256;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#2e3134';
  ctx.fillRect(0, 0, 256, 256);
  // Шум асфальта
  for (let i = 0; i < 2600; i++) {
    const v = 38 + ((i * 2654435761) >>> 0) % 26;
    ctx.fillStyle = `rgb(${v},${v},${v})`;
    ctx.fillRect```javascript
(((i * 97) % 256)), (i * 57) % 256, 2, 2);
  }
  // Осевая прерывистая линия
  ctx.fillStyle = '#c9c9b8';
  for (let y = 0; y < 256; y += 64) {
    ctx.fillRect(124, y + 8, 8, 32);
  }
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/** @returns {HTMLCanvasElement} процедурная плитка тротуара */
function makeSidewalkCanvas() {
  const cv = document.createElement('canvas');
  cv.width = 128;
  cv.height = 128;
  const ctx = cv.getContext('2d');
  ctx.fillStyle = '#7d7d78';
  ctx.fillRect(0, 0, 128, 128);
  // Швы плитки
  ctx.strokeStyle = '#5f5f5a';
  ctx.lineWidth = 2;
  for (let i = 0; i <= 128; i += 32) {
    ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, 128); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, i); ctx.lineTo(128, i); ctx.stroke();
  }
  // Зерно бетона
  for (let i = 0; i < 900; i++) {
    const v = 104 + ((i * 2246822519) >>> 0) % 30;
    ctx.fillStyle = `rgb(${v},${v},${v - 4})`;
    ctx.fillRect((i * 41) % 128, (i * 73) % 128, 1, 1);
  }
  const tex = new THREE.CanvasTexture(cv);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

/** Кэш LOD-материалов по цвету, чтобы не плодить одинаковые */
const _lodMatCache = new Map();

/**
 * @param {number} tint
 * @returns {THREE.MeshStandardMaterial}
 */
function getLodMaterial(tint) {
  let m = _lodMatCache.get(tint);
  if (!m) {
    m = new THREE.MeshStandardMaterial({ color: tint, roughness: 1.0, vertexColors: true });
    _lodMatCache.set(tint, m);
  }
  return m;
}

/**
 * Материал колонн аркад (общий на все здания).
 * @returns {THREE.MeshStandardMaterial}
 */
function getColumnMaterial() {
  if (!_columnMat) {
    _columnMat = new THREE.MeshStandardMaterial({ color: 0x8f8b84, roughness: 0.9 });
  }
  return _columnMat;
}

/** @type {THREE.MeshStandardMaterial|null} */
let _columnMat = null;

// ---------------------------------------------------------------------------
// Уличная мебель: фонари, машины, контейнеры, отбойники
// ---------------------------------------------------------------------------

/**
 * Фонари вдоль улиц: столб + эмиссивная голова, всё InstancedMesh.
 * @param {THREE.Group} group
 * @param {number[]} roadCenters координаты центров улиц
 * @param {number} rand
 */
function buildStreetLights(group, roadCenters, rand) {
  const positions = [];
  for (const c of roadCenters) {
    // Вдоль горизонтальных улиц
    for (let x = -HALF + 8; x <= HALF - 8; x += 26) {
      positions.push({ x, z: c - HALF_ROAD - 0.8, yaw: 0 });
      positions.push({ x: x + 13, z: c + HALF_ROAD + 0.8, yaw: Math.PI });
    }
    // Вдоль вертикальных улиц
    for (let z = -HALF + 8; z <= HALF - 8; z += 26) {
      positions.push({ x: c - HALF_ROAD - 0.8, z, yaw: Math.PI / 2 });
      positions.push({ x: c + HALF_ROAD + 0.8, z: z + 13, yaw: -Math.PI / 2 });
    }
  }
  // Отфильтровать позиции, попавшие во внутренние кварталы
  const valid = positions.filter(p => Math.abs(p.x) <= HALF && Math.abs(p.z) <= HALF);
  const n = valid.length;

  const poleGeo = bakeAO(new THREE.CylinderGeometry(0.07, 0.1, LAMP_HEIGHT, 6), 0, LAMP_HEIGHT, 0.7);
  const poleMat = new THREE.MeshStandardMaterial({ color: 0x3a3f44, roughness: 0.7, metalness: 0.5, vertexColors: true });
  const poleInst = new THREE.InstancedMesh(poleGeo, poleMat, n);

  const headGeo = new THREE.BoxGeometry(0.5, 0.18, 0.28);
  const headMat = new THREE.MeshStandardMaterial({
    color: 0xffe2b0, emissive: LAMP_EMISSIVE, emissiveIntensity: 2.4, roughness: 0.5,
  });
  const headInst = new THREE.InstancedMesh(headGeo, headMat, n);

  const armGeo = new THREE.BoxGeometry(0.06, 0.06, 1.0);
  const armInst = new THREE.InstancedMesh(armGeo, poleMat, n);

  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  for (let i = 0; i < n; i++) {
    const p = valid[i];
    e.set(0, p.yaw, 0);
    q.setFromEuler(e);
    // Столб
    _m4.compose(_v1.set(p.x, LAMP_HEIGHT / 2, p.z), q, _v2.set(1, 1, 1));
    poleInst.setMatrixAt(i, _m4);
    // Кронштейн к проезжей части
    const dirX = Math.sin(p.yaw);
    const dirZ = Math.cos(p.yaw);
    _m4.compose(
      _v1.set(p.x + dirX * 0.45, LAMP_HEIGHT - 0.1, p.z + dirZ * 0.45), q, _v2.set(1, 1, 1));
    armInst.setMatrixAt(i, _m4);
    // Голова светильника
    _m4.compose(
      _v1.set(p.x + dirX * 0.9, LAMP_HEIGHT - 0.12, p.z + dirZ * 0.9), q, _v2.set(1, 1, 1));
    headInst.setMatrixAt(i, _m4);

    colliders.push({ position: [p.x, LAMP_HEIGHT / 2, p.z], size: [0.22, LAMP_HEIGHT, 0.22] });
  }
  poleInst.instanceMatrix.needsUpdate = true;
  armInst.instanceMatrix.needsUpdate = true;
  headInst.instanceMatrix.needsUpdate = true;
  poleInst.castShadow = true;
  group.add(poleInst, armInst, headInst);
}

/**
 * Машины-коробки, припаркованные вдоль бордюров, и контейнеры/отбойники у зданий.
 * @param {THREE.Group} group
 * @param {number[]} roadCenters
 * @param {BlockRect[]} blocks
 * @param {() => number} rand
 */
function buildStreetProps(group, roadCenters, blocks, rand) {
  const carPoses = [];
  const boxPoses = [];
  const barPoses = [];

  for (const c of roadCenters) {
    // Машины вдоль горизонтальных улиц
    for (let x = -HALF + 10; x <= HALF - 10; x += 14) {
      if (rand() < 0.4) {
        carPoses.push({
          x: x + (rand() - 0.5) * 4,
          z: c + (rand() < 0.5 ? -1 : 1) * (HALF_ROAD - 1.4),
          yaw: (rand() - 0.5) * 0.12,
        });
      }
    }
    // Машины вдоль вертикальных улиц
    for (let z = -HALF + 10; z <= HALF - 10; z += 14) {
      if (rand() < 0.4) {
        carPoses.push({
          x: c + (rand() < 0.5 ? -1 : 1) * (HALF_ROAD - 1.4),
          z: z + (rand() - 0.5) * 4,
          yaw: Math.PI / 2 + (rand() - 0.5) * 0.12,
        });
      }
    }
  }

  // Контейнеры и отбойники — у кромок кварталов, со стороны тротуара
  for (const b of blocks) {
    const edges = [
      { x: b.x, z: b.z - b.d / 2 - SIDEWALK_WIDTH / 2, yaw: 0 },
      { x: b.x, z: b.z + b.d / 2 + SIDEWALK_WIDTH / 2, yaw: 0 },
      { x: b.x - b.w / 2 - SIDEWALK_WIDTH / 2, z: b.z, yaw: Math.PI / 2 },
      { x: b.x + b.w / 2 + SIDEWALK_WIDTH / 2, z: b.z, yaw: Math.PI / 2 },
    ];
    for (const ePos of edges) {
      const r = rand();
      if (r < 0.12) {
        boxPoses.push({ x: ePos.x + (rand() - 0.5) * 6, z: ePos.z + (rand() - 0.5) * 2, yaw: ePos.yaw + (rand() - 0.5) * 0.4 });
      } else if (r < 0.3) {
        barPoses.push({ x: ePos.x + (rand() - 0.5)
F + 8; x <= HALF - 8; x += 26) {
      positions.push({ x, z: c - HALF_ROAD - 0.8, yaw: 0 });
      positions.push({ x: x + 13, z: c + HALF_ROAD + 0.8, yaw: Math.PI });
    }
    // Вдоль вертикальных улиц
    for (let z = -HALF + 8; z <= HALF - 8; z += 26) {
      positions.push({ x: c - HALF_ROAD - 0.8, z, yaw: Math.PI / 2 });
      positions.push({ x: c + HALF_ROAD + 0.8, z: z + 13, yaw: -Math.PI / 2 });
    }
  }
  // Отфильтровать позиции, попавшие во внутренние кварталы
  const valid = positions.filter(p => Math.abs(p.x) <= HALF && Math.abs(p.z) <= HALF);
  const n = valid.length;

  const poleGeo = bakeAO(new THREE.CylinderGeometry(0.07, 0.1, LAMP_HEIGHT, 6), 0, LAMP_HEIGHT, 0.7);
  const poleMat = new THREE.MeshStandardMaterial({ color: 0x3a3f44, roughness: 0.7, metalness: 0.5, vertexColors: true });
  const poleInst = new THREE.InstancedMesh(poleGeo, poleMat, n);

  const headGeo = new THREE.BoxGeometry(0.5, 0.18, 0.28);
  const headMat = new THREE.MeshStandardMaterial({
    color: 0xffe2b0, emissive: LAMP_EMISSIVE, emissiveIntensity: 2.4, roughness: 0.5,
  });
  const headInst = new THREE.InstancedMesh(headGeo, headMat, n);

  const armGeo = new THREE.BoxGeometry(0.06, 0.06, 1.0);
  const armInst = new THREE.InstancedMesh(armGeo, poleMat, n);

  const q = new THREE.Quaternion();
  const e = new THREE.Euler();
  for (let i = 0; i < n; i++) {
    const p = valid[i];
    e.set(0, p.yaw, 0);
    q.setFromEuler(e);
    // Столб
    _m4.compose(_v1.set(p.x, LAMP_HEIGHT / 2, p.z), q, _v2.set(1, 1, 1));
    poleInst.setMatrixAt(i, _m4);
    // Кронштейн к проезжей части
    const dirX = Math.sin(p.yaw);
    const dirZ = Math.cos(p.yaw);
    _m4.compose(
      _v1.set(p.x + dirX * 0.45, LAMP_HEIGHT - 0.1, p.z + dirZ * 0.45), q, _v2.set(1, 1, 1));
    armInst.setMatrixAt(i, _m4);
    // Голова светильника
    _m4.compose(
      _v1.set(p.x + dirX * 0.9, LAMP_HEIGHT - 0.12, p.z + dirZ * 0.9), q, _v2.set(1, 1, 1));
    headInst.setMatrixAt(i, _m4);

    colliders.push({ position: [p.x, LAMP_HEIGHT / 2, p.z], size: [0.22, LAMP_HEIGHT, 0.22] });
  }
  poleInst.instanceMatrix.needsUpdate = true;
  armInst.instanceMatrix.needsUpdate = true;
  headInst.instanceMatrix.needsUpdate = true;
  poleInst.castShadow = true;
  group.add(poleInst, armInst, headInst);
}

/**
 * Машины-коробки, припаркованные вдоль бордюров, и контейнеры/отбойники у зданий.
 * @param {THREE.Group} group
 * @param {number[]} roadCenters
 * @param {BlockRect[]} blocks
 * @param {() => number} rand
 */
function buildStreetProps(group, roadCenters, blocks, rand) {
  const carPoses = [];
  const boxPoses = [];
  const barPoses = [];

  for (const c of roadCenters) {
    // Машины вдоль горизонтальных улиц
    for (let x = -HALF + 10; x <= HALF - 10; x += 14) {
      if (rand() < 0.4) {
        carPoses.push({
          x: x + (rand() - 0.5) * 4,
          z: c + (rand() < 0.5 ? -1 : 1) * (HALF_ROAD - 1.4),
          yaw: (rand() - 0.5) * 0.12,
        });
      }
    }
    // Машины вдоль вертикальных улиц
    for (let z = -HALF + 10; z <= HALF - 10; z += 14) {
      if (rand() < 0.4) {
        carPoses.push({
          x: c + (rand() < 0.5 ? -1 : 1) * (HALF_ROAD - 1.4),
          z: z + (rand() - 0.5) * 4,
          yaw: Math.PI / 2 + (rand() - 0.5) * 0.12,
        });
      }
    }
  }

  // Контейнеры и отбойники — у кромок кварталов, со стороны тротуара
  for (const b of blocks) {
    const edges = [
      { x: b.x, z: b.z - b.d / 2 - SIDEWALK_WIDTH / 2, yaw: 0 },
      { x: b.x, z: b.z + b.d / 2 + SIDEWALK_WIDTH / 2, yaw: 0 },
      { x: b.x - b.w / 2 - SIDEWALK_WIDTH / 2, z: b.z, yaw: Math.PI / 2 },
      { x: b.x + b.w / 2 + SIDEWALK_WIDTH / 2, z: b.z, yaw: Math.PI / 2 },
    ];
    for (const ePos of edges) {
      const r = rand();
      if (r < 0.12) {
        boxPoses.push({ x: ePos.x + (rand() - 0.5) * 6, z: ePos.z + (rand() - 0.5) * 2, yaw: ePos.yaw + (rand() - 0.5) * 0.4 });
      } else if (r < 0.3) {
        barPoses.push({ x: ePos.x + (rand() - 0.5) * 6, z: ePos.z + (rand() - 0.5) * 2, yaw: ePos.yaw + (rand() - 0.5) * 0.3 });
      }
    }
  }

  // ---- Машины (кузов + кабина) ----
  const nCars = carPoses.length;
  if (nCars > 0) {
    const bodyGeo = bakeAO(new THREE.BoxGeometry(CAR_LENGTH, CAR_BODY_H, CAR_WIDTH), 0, CAR_BODY_H, 0.65);
    const bodyMat = new THREE.MeshStandardMaterial({ roughness: 0.45, metalness: 0.35, vertexColors: true });
    const bodyInst = new THREE.InstancedMesh(bodyGeo, bodyMat, nCars);

    const cabinGeo = bakeAO(new THREE.BoxGeometry(CAR_LENGTH * 0.45, CAR_CABIN_H, CAR_WIDTH * 0.86), 0, CAR_CABIN_H, 0.85);
    const cabinMat = new THREE.MeshStandardMaterial({ color: 0x1c2126, roughness: 0.25, metalness: 0.6, vertexColors: true });
    const cabinInst = new THREE.InstancedMesh(cabinGeo, cabinMat, nCars);

    for (let i = 0; i < nCars; i++) {
      const p = carPoses[i];
      _euler.set(0, p.yaw, 0);
      _quat.setFromEuler(_euler);
      const cosY = Math.cos(p.yaw);
      const sinY = Math.sin(p.yaw);

      _m4.compose(_v1.set(p.x, CAR_BODY_H / 2 + 0.25, p.z), _quat, _v2.set(1, 1, 1));
      bodyInst.setMatrixAt(i, _m4);
      bodyInst.setColorAt(i, _color.setHSL(rand(), 0.55, 0.35 + rand() * 0.25));

      // Кабина смещена назад по локальной оси X
      _m4.compose(
        _v1.set(p.x - cosY * 0.3, CAR_BODY_H + 0.25 + CAR_CABIN_H / 2, p.z + sinY * 0.3),
        _quat, _v2.set(1, 1, 1));
      cabinInst.setMatrixAt(i, _m4);

      // Коллайдер машины — выровнен по оси (yaw близок к 0 или PI/2)
      const along = Math.abs(sinY) > 0.5;
      colliders.push({
        position: [p.x, (CAR_BODY_H + CAR_CABIN_H) / 2 + 0.25, p.z],
        size: along ? [CAR_WIDTH, CAR_BODY_H + CAR_CABIN_H, CAR_LENGTH] : [CAR_LENGTH, CAR_BODY_H + CAR_CABIN_H, CAR_WIDTH],
      });
    }
    bodyInst.instanceMatrix.needsUpdate = true;
    cabinInst.instanceMatrix.needsUpdate = true;
    if (bodyInst.instanceColor) bodyInst.instanceColor.needsUpdate = true;
    bodyInst.castShadow = true;
    cabinInst.castShadow = true;
    group.add(bodyInst, cabinInst);
  }

  // ---- Контейнеры ----
  const nBox = boxPoses.length;
  if (nBox > 0) {
    const g = bakeAO(new THREE.BoxGeometry(2.2, 1.3, 1.1), 0, 1.3, 0.55);
    const m = new THREE.MeshStandardMaterial({ roughness: 0.8, metalness: 0.2, vertexColors: true });
    const inst = new THREE.InstancedMesh(g, m, nBox);
    for (let i = 0; i < nBox; i++) {
      const p = boxPoses[i];
      _euler.set(0, p.yaw, 0);
      _quat.setFromEuler(_euler);
      _m4.compose(_v1.set(p.x, 0.65, p.z), _quat, _v2.set(1, 1, 1));
      inst.setMatrixAt(i, _m4);
      inst.setColorAt(i, _color.setHSL(0.05 + rand() * 0.5, 0.3, 0.28 + rand() * 0.15));
      colliders.push({ position: [p.x, 0.65, p.z], size: [2.2, 1.3, 1.3] });
    }
    inst.instanceMatrix.needsUpdate = true;
    if (inst.instanceColor) inst.instanceColor.needsUpdate = true;
    inst.castShadow = true;
    group.add(inst);
  }

  // ---- Отбойники (бетонные блоки) ----
  const nBar = barPoses.length;
  if (nBar > 0) {
    const g = bakeAO(new THREE.BoxGeometry(1.6, 0.55, 0.45), 0, 0.55, 0.5);
    const m = new THREE.MeshStandardMaterial({ color: 0x9
