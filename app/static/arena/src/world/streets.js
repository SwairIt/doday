/**
 * Генерация городского квартала 200x200 м: дороги, тротуары, бордюры,
 * разметка, участки под застройку и точки спауна.
 */

import * as THREE from 'three';
import { makeAsphalt, makeConcrete, tileTextures } from './textures.js';

/** Размер квартала (м), квадрат [-HALF..HALF] */
const WORLD_SIZE = 200;
const HALF = WORLD_SIZE / 2;
/** Центры улиц по обеим осям */
const ROAD_CENTERS = [-80, -40, 0, 40, 80];
/** Ширина проезжей части (м) */
const ROAD_W = 8;
/** Ширина тротуара с каждой стороны дороги (м) */
const WALK_W = 3;
/** Высота бордюра / плиты тротуара (м) */
const CURB_H = 0.14;
/** Толщина бордюрного камня (м) */
const CURB_T = 0.15;
/** Отступ участка от уличной кромки (м) */
const PLOT_MARGIN = 0.5;
/** Смещение улиц второго направления по Y, чтобы не было z-fighting */
const ROAD_Y_LIFT = 0.002;
/** Высота линий разметки над асфальтом */
const MARK_Y = 0.006;
/** Длина штриха и зазор прерывистой осевой (м) */
const DASH_LEN = 3;
const DASH_GAP = 3;
const MARK_W = 0.15;

// Переиспользуемые геометрии (создаются один раз)
const unitBox = new THREE.BoxGeometry(1, 1, 1);

/**
 * Создаёт меш-плиту из единичного бокса.
 * @param {THREE.Material} material
 * @param {number} x центр
 * @param {number} y центр
 * @param {number} z центр
 * @param {number} w размер по X
 * @param {number} h размер по Y
 * @param {number} d размер по Z
 * @returns {THREE.Mesh}
 */
function makeSlab(material, x, y, z, w, h, d) {
  const mesh = new THREE.Mesh(unitBox, material);
  mesh.position.set(x, y, z);
  mesh.scale.set(w, h, d);
  mesh.receiveShadow = true;
  mesh.matrixAutoUpdate = false;
  mesh.updateMatrix();
  return mesh;
}

/**
 * Строит сетку улиц, тротуары, бордюры и разметку квартала 200x200 м.
 * @param {import('../core/settings.js').Settings} settings настройки качества
 * @param {() => number} rng генератор случайных чисел [0,1)
 * @returns {{meshes: THREE.Mesh[], colliders: Array<{position:number[],size:number[]}>, spawnPoints: Array<{x:number,y:number,z:number}>, plots: Array<{x:number,z:number,w:number,d:number}>}}
 */
export function buildStreets(settings, rng) {
  const meshes = [];
  const colliders = [];
  const spawnPoints = [];
  const plots = [];

  // Текстуры с повторением по всей плоскости квартала
  const asphalt = tileTextures(makeAsphalt(), WORLD_SIZE / ROAD_W, WORLD_SIZE / ROAD_W);
  const concrete = tileTextures(makeConcrete(), WORLD_SIZE / 4, WORLD_SIZE / 4);

  const asphaltMat = new THREE.MeshStandardMaterial({
    map: asphalt.map,
    normalMap: asphalt.normalMap,
    roughnessMap: asphalt.roughnessMap,
    roughness: 0.95,
    metalness: 0.0,
  });
  const concreteMat = new THREE.MeshStandardMaterial({
    map: concrete.map,
    normalMap: concrete.normalMap,
    roughnessMap: concrete.roughnessMap,
    roughness: 0.9,
    metalness: 0.0,
  });
  const curbMat = new THREE.MeshStandardMaterial({
    color: 0x9a9a96,
    roughness: 0.85,
    metalness: 0.0,
  });
  const markMat = new THREE.MeshBasicMaterial({ color: 0xf2f2e8 });

  const detail = settings.quality !== 'low';

  // --- Проезжая часть: полосы вдоль X и вдоль Z ---
  for (const c of ROAD_CENTERS) {
    // Улица вдоль оси X (центр по Z = c)
    meshes.push(makeSlab(asphaltMat, 0, 0, c, WORLD_SIZE, 0.02, ROAD_W));
    // Улица вдоль оси Z (центр по X = c), чуть выше во избежание z-fighting
    meshes.push(makeSlab(asphaltMat, c, 0, ROAD_Y_LIFT, WORLD_SIZE, 0.02, ROAD_W));
    // Поворот оси: улица «вдоль Z» — это полоса шириной ROAD_W по X
    // (ширина и глубина меняются местами)
  }

  // --- Тротуары: полосы по обе стороны каждой улицы ---
  for (const c of ROAD_CENTERS) {
    for (const side of [-1, 1]) {
      const off = side * (ROAD_W / 2 + WALK_W / 2);
      // Вдоль X (тротуар смещён по Z)
      meshes.push(makeSlab(concreteMat, 0, CURB_H / 2, c + off, WORLD_SIZE, CURB_H, WALK_W));
      // Вдоль Z (тротуар смещён по X)
      meshes.push(makeSlab(concreteMat, c + off, CURB_H / 2 + ROAD_Y_LIFT, 0, WALK_W, CURB_H, WORLD_SIZE));
    }
  }

  // --- Бордюры: узкие камни по краям проезжей части, это единственные коллайдеры улиц ---
  for (const c of ROAD_CENTERS) {
    for (const side of [-1, 1]) {
      const off = side * (ROAD_W / 2 - CURB_T / 2);
      // Бордюры улиц вдоль X
      meshes.push(makeSlab(curbMat, 0, CURB_H / 2, c + off, WORLD_SIZE, CURB_H, CURB_T));
      colliders.push({
        position: [0, CURB_H / 2, c + off],
        size: [WORLD_SIZE, CURB_H, CURB_T],
      });
      // Бордюры улиц вдоль Z
      meshes.push(makeSlab(curbMat, c + off, CURB_H / 2 + ROAD_Y_LIFT, 0, CURB_T, CURB_H, WORLD_SIZE));
      colliders.push({
        position: [c + off, CURB_H / 2 + ROAD_Y_LIFT, 0],
        size: [CURB_T, CURB_H, WORLD_SIZE],
      });
    }
  }

  // --- Разметка: прерывистая осевая по центру каждой улицы ---
  if (detail) {
    const step = DASH_LEN + DASH_GAP;
    const count = Math.floor(WORLD_SIZE / step);
    for (const c of ROAD_CENTERS) {
      for (let i = 0; i < count; i++) {
        const start = -HALF + i * step + DASH_GAP / 2;
        const mid = start + DASH_LEN / 2;
        // Осевая улицы вдоль X
        meshes.push(makeSlab(markMat, mid, MARK_Y, c, DASH_LEN, 0.004, MARK_W));
        // Осевая улицы вдоль Z
        meshes.push(makeSlab(markMat, c, MARK_Y + ROAD_Y_LIFT, mid, MARK_W, 0.004, DASH_LEN));
      }
    }
  }

  // --- Участки под застройку: ячейки между соседними улицами ---
  // Границы, занятые улицей + тротуарами с каждой стороны центра
  const streetHalf = ROAD_W / 2 + WALK_W + PLOT_MARGIN;
  // Сортируем центры и считаем свободные пролёты между ними, включая края карты
  const sorted = [...ROAD_CENTERS].sort((a, b) => a - b);
  const edges = [-HALF, ...sorted, HALF];

  /** Свободные интервалы вдоль одной оси */
  const spans = [];
  for (let i = 0; i < edges.length - 1; i++) {
    const lo = i === 0 ? edges[i] : edges[i] + streetHalf;
    const hi = i === edges.length - 2 ? edges[i + 1] : edges[i + 1] - streetHalf;
    if (hi - lo > 4) spans.push({ lo, hi });
  }

  for (const sx of spans) {
    for (const sz of spans) {
      const w = sx.hi - sx.lo;
      const d = sz.hi - sz.lo;
      // Небольшой случайный отступ внутрь участка
      const jitter = detail ? rng() * 1.5 : 0;
      plots.push({
        x: (sx.lo + sx.hi) / 2,
        z: (sz.lo + sz.hi) / 2,
        w: w - jitter,
        d: d - jitter,
      });
    }
  }

  // --- Точки спауна: на проезжей части и на тротуарах ---
  for (const c of ROAD_CENTERS) {
    // На проезжей части: на перекрёстках и между ними
    for (const k of [-60, -20, 20, 60]) {
      spawnPoints.push({ x: k, y: 0.05, z: c });
      spawnPoints.push({ x: c, y: 0.05, z: k });
    }
    // На тротуарах
    const off = ROAD_W / 2 + WALK_W / 2;
    for (const side of [-1, 1]) {
      spawnPoints.push({ x: -60, y: CURB_H + 0.05, z: c + side * off });
      spawnPoints.push({ x: c + side * off, y: CURB_H + 0.05, z: 60 });
    }
  }

  return { meshes, colliders, spawnPoints, plots };
}
