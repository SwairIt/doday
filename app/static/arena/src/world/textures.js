/**
 * Процедурные PBR-текстуры для Doday Arena.
 * Все текстуры генерируются на canvas, без внешних ассетов.
 * Каждая фабрика возвращает { map, normalMap, roughnessMap }.
 * Результаты кэшируются по имени, повторные вызовы возвращают один и тот же набор.
 */

import * as THREE from 'three';

/** Размер генерируемых текстур в пикселях. */
const TEXTURE_SIZE = 512;

/** Сила перевода карты высот в карту нормалей. */
const NORMAL_STRENGTH = 2.0;

/** Кэш сгенерированных наборов текстур по имени. */
const cache = new Map();

/** Модульный временный canvas (переиспользуется между генерациями). */
const tmpCanvas = document.createElement('canvas');
tmpCanvas.width = TEXTURE_SIZE;
tmpCanvas.height = TEXTURE_SIZE;
const tmpCtx = tmpCanvas.getContext('2d', { willReadFrequently: true });

/**
 * Детерминированный PRNG (mulberry32), чтобы текстуры были стабильны между запусками.
 * @param {number} seed
 * @returns {() => number}
 */
function makeRng(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6D2B79F5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Создаёт канвас заданного размера с контекстом.
 * @param {number} size
 * @returns {{canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D}}
 */
function createCanvas(size) {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d', { willReadFrequently: true });
  return { canvas, ctx };
}

/**
 * Возвращает значение высоты из ImageData по координатам с зацикливанием (tiling-safe).
 * Берётся красный канал, нормализованный в [0, 1].
 * @param {Uint8ClampedArray} data
 * @param {number} size
 * @param {number} x
 * @param {number} y
 * @returns {number}
 */
function sampleHeight(data, size, x, y) {
  const ix = ((x % size) + size) % size;
  const iy = ((y % size) + size) % size;
  return data[(iy * size + ix) * 4] / 255;
}

/**
 * Строит карту нормалей из карты высот методом Собеля по соседним пикселям.
 * Зацикливание по краям — чтобы тайл не давал швов при RepeatWrapping.
 * @param {HTMLCanvasElement} heightCanvas
 * @returns {HTMLCanvasElement}
 */
function heightToNormal(heightCanvas) {
  const size = heightCanvas.width;
  const src = heightCanvas.getContext('2d').getImageData(0, 0, size, size).data;
  const { canvas, ctx } = createCanvas(size);
  const out = ctx.createImageData(size, size);
  const dst = out.data;

  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const hl = sampleHeight(src, size, x - 1, y);
      const hr = sampleHeight(src, size, x + 1, y);
      const hd = sampleHeight(src, size, x, y - 1);
      const hu = sampleHeight(src, size, x, y + 1);

      let nx = (hl - hr) * NORMAL_STRENGTH;
      let ny = (hd - hu) * NORMAL_STRENGTH;
      let nz = 1.0;
      const len = Math.sqrt(nx * nx + ny * ny + nz * nz);
      nx /= len;
      ny /= len;
      nz /= len;

      const i = (y * size + x) * 4;
      dst[i] = Math.round((nx * 0.5 + 0.5) * 255);
      dst[i + 1] = Math.round((ny * 0.5 + 0.5) * 255);
      dst[i + 2] = Math.round((nz * 0.5 + 0.5) * 255);
      dst[i + 3] = 255;
    }
  }
  ctx.putImageData(out, 0, 0);
  return canvas;
}

/**
 * Оборачивает canvas в THREE.Texture с RepeatWrapping и правильным colorSpace.
 * @param {HTMLCanvasElement} canvas
 * @param {boolean} isColor true — sRGB для albedo, false — linear для data-карт
 * @returns {THREE.Texture}
 */
function canvasToTexture(canvas, isColor) {
  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.colorSpace = isColor ? THREE.SRGBColorSpace : THREE.NoColorSpace;
  texture.anisotropy = 4;
  texture.needsUpdate = true;
  return texture;
}

/**
 * Собирает готовый набор текстур из трёх канвасов.
 * @param {HTMLCanvasElement} colorCanvas
 * @param {HTMLCanvasElement} heightCanvas
 * @param {HTMLCanvasElement} roughCanvas
 * @returns {{map: THREE.Texture, normalMap: THREE.Texture, roughnessMap: THREE.Texture}}
 */
function buildSet(colorCanvas, heightCanvas, roughCanvas) {
  return {
    map: canvasToTexture(colorCanvas, true),
    normalMap: canvasToTexture(heightToNormal(heightCanvas), false),
    roughnessMap: canvasToTexture(roughCanvas, false),
  };
}

/**
 * Заполняет переданные канвас монохромным значением с шумом.
 * Используется для roughness-карт.
 * @param {CanvasRenderingContext2D} ctx
 * @param {number} size
 * @param {number} base базовая шероховатость [0..1]
 * @param {number} amp амплитуда шума [0..1]
 * @param {() => number} rng
 */
function fillRoughness(ctx, size, base, amp, rng) {
  const img = ctx.createImageData(size, size);
  const d = img.data;
  for (let i = 0; i < size * size; i++) {
    const v = Math.max(0, Math.min(1, base + (rng() - 0.5) * amp));
    const b = Math.round(v * 255);
    const p = i * 4;
    d[p] = b;
    d[p + 1] = b;
    d[p + 2] = b;
    d[p + 3] = 255;
  }
  ctx.putImageData(img, 0, 0);
}

/**
 * Рисует тёмные пятна/трещины на канвасе (случайные полупрозрачные эллипсы).
 * @param {CanvasRenderingContext2D} ctx
 * @param {() => number} rng
 * @param {number} count
 * @param {number} maxRadius
 * @param {string} color
 * @param {number} alphaMax
 */
function drawSpots(ctx, rng, count, maxRadius, color, alphaMax) {
  const size = ctx.canvas.width;
  for (let i = 0; i < count; i++) {
    const x = rng() * size;
    const y = rng() * size;
    const r = 2 + rng() * maxRadius;
    ctx.globalAlpha = rng() * alphaMax;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.ellipse(x, y, r, r * (0.4 + rng() * 0.6), rng() * Math.PI, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

/**
 * Бетон: серый зернистый материал с пятнами и выбоинами.
 * @returns {{map: THREE.Texture, normalMap: THREE.Texture, roughnessMap: THREE.Texture}}
 */
export function makeConcrete() {
  const cached```javascript
 = cache.get('concrete');
  if (cached) return cached;

  const size = TEXTURE_SIZE;
  const rng = makeRng(0xC0C1E7E);

  // --- Карта высот: мелкое зерно + крупные выбоины ---
  const height = createCanvas(size);
  const hImg = height.ctx.createImageData(size, size);
  const hd = hImg.data;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      // двухоктавный шум: мелкий + средний
      const n1 = rng();
      const n2 = rng();
      const v = Math.round(150 + (n1 - 0.5) * 70 + (n2 - 0.5) * 40);
      hd[i] = v;
      hd[i + 1] = v;
      hd[i + 2] = v;
      hd[i + 3] = 255;
    }
  }
  height.ctx.putImageData(hImg, 0, 0);
  drawSpots(height.ctx, rng, 60, 22, '#404040', 0.35);

  // --- Альбедо: тёплый серый с вариациями ---
  const color = createCanvas(size);
  const cImg = color.ctx.createImageData(size, size);
  const cd = cImg.data;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const h = hd[i] / 255;
      const base = 120 + h * 60;
      cd[i] = Math.round(base * 1.02);
      cd[i + 1] = Math.round(base);
      cd[i + 2] = Math.round(base * 0.96);
      cd[i + 3] = 255;
    }
  }
  color.ctx.putImageData(cImg, 0, 0);
  drawSpots(color.ctx, rng, 40, 30, '#3a3a38', 0.25);
  drawSpots(color.ctx, rng, 24, 14, '#8a8880', 0.18);

  // --- Шероховатость: бетон почти матовый ---
  const rough = createCanvas(size);
  fillRoughness(rough.ctx, size, 0.9, 0.16, rng);

  const result = buildSet(color.canvas, height.canvas, rough.canvas);
  cache.set('concrete', result);
  return result;
}

/**
 * Асфальт: тёмное зерно с камешками и битумными пятнами.
 * @returns {{map: THREE.Texture, normalMap: THREE.Texture, roughnessMap: THREE.Texture}}
 */
export function makeAsphalt() {
  const cached = cache.get('asphalt');
  if (cached) return cached;

  const size = TEXTURE_SIZE;
  const rng = makeRng(0xA5F417);

  // --- Карта высот: агрессивное зерно ---
  const height = createCanvas(size);
  const hImg = height.ctx.createImageData(size, size);
  const hd = hImg.data;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const v = Math.round(120 + (rng() - 0.5) * 140);
      hd[i] = v;
      hd[i + 1] = v;
      hd[i + 2] = v;
      hd[i + 3] = 255;
    }
  }
  height.ctx.putImageData(hImg, 0, 0);

  // Трещины на карте высот — тонкие тёмные ломаные
  height.ctx.strokeStyle = 'rgba(30,30,30,0.8)';
  for (let t = 0; t < 14; t++) {
    height.ctx.lineWidth = 1 + rng() * 1.5;
    height.ctx.beginPath();
    let x = rng() * size;
    let y = rng() * size;
    height.ctx.moveTo(x, y);
    const segs = 4 + Math.floor(rng() * 5);
    for (let s = 0; s < segs; s++) {
      x += (rng() - 0.5) * 90;
      y += (rng() - 0.5) * 90;
      height.ctx.lineTo(x, y);
    }
    height.ctx.stroke();
  }

  // --- Альбедо: тёмно-серый + светлые камешки ---
  const color = createCanvas(size);
  const cImg = color.ctx.createImageData(size, size);
  const cd = cImg.data;
  const hData = height.ctx.getImageData(0, 0, size, size).data;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const h = hData[i] / 255;
      const base = 38 + h * 42;
      cd[i] = Math.round(base);
      cd[i + 1] = Math.round(base);
      cd[i + 2] = Math.round(base * 1.05);
      cd[i + 3] = 255;
    }
  }
  color.ctx.putImageData(cImg, 0, 0);

  // Светлые вкрапления щебня
  for (let k = 0; k < 900; k++) {
    const x = rng() * size;
    const y = rng() * size;
    const g = 90 + Math.floor(rng() * 90);
    color.ctx.globalAlpha = 0.25 + rng() * 0.5;
    color.ctx.fillStyle = `rgb(${g},${g},${g})`;
    color.ctx.fillRect(x, y, 1 + rng() * 2, 1 + rng() * 2);
  }
  color.ctx.globalAlpha = 1;
  drawSpots(color.ctx, rng, 30, 26, '#141414', 0.3);

  // --- Шероховатость ---
  const rough = createCanvas(size);
  fillRoughness(rough.ctx, size, 0.95, 0.12, rng);

  const result = buildSet(color.canvas, height.canvas, rough.canvas);
  cache.set('asphalt', result);
  return result;
}

/**
 * Кирпичная кладка: красно-коричневые кирпичи + светлый раствор.
 * @returns {{map: THREE.Texture, normalMap: THREE.Texture, roughnessMap: THREE.Texture}}
 */
export function makeBrick() {
  const cached = cache.get('brick');
  if (cached) return cached;

  const size = TEXTURE_SIZE;
  const rng = makeRng(0xB21C4);

  const BRICK_W = 128;
  const BRICK_H = 64;
  const MORTAR = 8;

  // --- Альбедо и высота рисуются параллельно ---
  const color = createCanvas(size);
  const height = createCanvas(size);

  // Раствор: светлый по цвету, низкий по высоте
  color.ctx```javascript
.fillStyle = '#9a938a';
  color.ctx.fillRect(0, 0, size, size);
  height.ctx.fillStyle = '#505050';
  height.ctx.fillRect(0, 0, size, size);

  // Кладка со смещением каждого второго ряда (в перевязку)
  const rows = size / BRICK_H;
  for (let row = 0; row < rows; row++) {
    const offset = (row % 2) * (BRICK_W / 2);
    const y = row * BRICK_H;
    for (let bx = -1; bx * BRICK_W < size + BRICK_W; bx++) {
      const x = bx * BRICK_W + offset;
      // Вариация оттенка кирпича
      const r = 128 + Math.floor(rng() * 52);
      const g = 52 + Math.floor(rng() * 26);
      const b = 40 + Math.floor(rng() * 18);
      color.ctx.fillStyle = `rgb(${r},${g},${b})`;
      color.ctx.fillRect(x + MORTAR / 2, y + MORTAR / 2, BRICK_W - MORTAR, BRICK_H - MORTAR);

      // Высота кирпича выше раствора, с лёгким перепадом по граням
      const hv = 175 + Math.floor(rng() * 40);
      height.ctx.fillStyle = `rgb(${hv},${hv},${hv})`;
      height.ctx.fillRect(x + MORTAR / 2, y + MORTAR / 2, BRICK_W - MORTAR, BRICK_H - MORTAR);

      // Сколы и потёки на отдельных кирпичах
      if (rng() < 0.3) {
        color.ctx.globalAlpha = 0.15 + rng() * 0.2;
        color.ctx.fillStyle = rng() < 0.5 ? '#2e2018' : '#c9b8a4';
        color.ctx.fillRect(
          x + MORTAR / 2 + rng() * (BRICK_W * 0.5),
          y + MORTAR / 2 + rng() * (BRICK_H * 0.5),
          4 + rng() * 20,
          3 + rng() * 12
        );
        color.ctx.globalAlpha = 1;
      }
    }
  }

  // Зернение поверх кладки
  const cImg = color.ctx.getImageData(0, 0, size, size);
  const cd = cImg.data;
  for (let i = 0; i < size * size; i++) {
    const n = (rng() - 0.5) * 18;
    const p = i * 4;
    cd[p] = Math.max(0, Math.min(255, cd[p] + n));
    cd[p + 1] = Math.max(0, Math.min(255, cd[p + 1] + n));
    cd[p + 2] = Math.max(0, Math.min(255, cd[p + 2] + n));
  }
  color.ctx.putImageData(cImg, 0, 0);

  // --- Шероховатость: кирпич шероховатый, раствор ещё грубее ---
  const rough = createCanvas(size);
  fillRoughness(rough.ctx, size, 0.86, 0.14, rng);

  const result = buildSet(color.canvas, height.canvas, rough.canvas);
  cache.set('brick', result);
  return result;
}

/**
 * Металл: рифлёные панели со швами, царапинами и потёртостями.
 * @returns {{map: THREE.Texture, normalMap: THREE.Texture, roughnessMap: THREE.Texture}}
 */
export function makeMetal() {
  const cached = cache.get('metal');
  if (cached) return cached;

  const size = TEXTURE_SIZE;
  const rng = makeRng(0x1E7A1);

  const PANEL = 128;
  const SEAM = 4;

  // --- Карта высот: панели + швы + рифлёная диагональ ---
  const height = createCanvas(size);
  height.ctx.fillStyle = '#b0b0b0';
  height.ctx.fillRect(0, 0, size, size);

  // Швы между панелями (углубления)
  height.ctx.fillStyle = '#2a2a2a';
  for (let s = 0; s <= size; s += PANEL) {
    height.ctx.fillRect(s - SEAM / 2, 0, SEAM, size);
    height.ctx.fillRect(0, s - SEAM / 2, size, SEAM);
  }

  // Диагональное рифление (rhombus pattern) повышением высоты полосами
  const hImg = height.ctx.getImageData(0, 0, size, size);
  const hd = hImg.data;
  const RIB_PERIOD = 16;
  const RIB_HEIGHT = 55;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      // Шеврон: чередующееся направление каждые полпанели
      const flip = (Math.floor(x / (PANEL / 2)) + Math.floor(y / (PANEL / 2))) % 2 === 0 ? 1 : -1;
      const phase = ((x * flip + y) % RIB_PERIOD + RIB_PERIOD) % RIB_PERIOD;
      const t = phase / RIB_PERIOD;
      const rib = t < 0.5 ? t * 2 : (1 - t) * 2; // треугольный профиль
      const v = Math.max(0, Math.min(255, hd[i] + rib * RIB_HEIGHT));
      hd[i] = v;
      hd[i + 1] = v;
      hd[i + 2] = v;
    }
  }
  height.ctx.putImageData(hImg, 0, 0);

  // --- Альбедо: холодный серый металл ---
  const color = createCanvas(size);
  const cImg = color.ctx.createImageData(size, size);
  const cd = cImg.data;
  const hData = height.ctx.getImageData(0, 0, size, size).data;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      const i = (y * size + x) * 4;
      const h = hData[i] / 255;
      const base = 96 + h * 78;
      cd[i] = Math.round(base * 0.97);
      cd[i + 1] = Math.round(base);
      cd[i + 2] = Math.round(base * 1.06);
      cd[i + 3] = 255;
    }
  }
  color.ctx.putImageData(cImg, 0, 0);

  // Царапины
  color.ctx.strokeStyle = 'rgba(210,215,220,0.35)';
  for (let s = 0; s < 40; s++) {
    color.ctx.lineWidth = 1;
    color.ctx.globalAlpha = 0.1 + rng() * 0.3;
    color.ctx.beginPath();
    const x = rng() * size;
    const y = rng() * size;
    const len = 20 + rng() * 120;
    const ang = rng() * Math.PI;
    color.ctx.moveTo(x, y);
    color.ctx.lineTo(x + Math.cos(ang) * len, y + Math.sin(ang) * len);
    color.ctx.stroke();
  }
  color.ctx.globalAlpha = 1;

  // Заклёпки по углам панелей
  for (let px = 0; px <= size; px += PANEL) {
    for (let py = 0; py <= size; py += PANEL) {
      const rx = (px + 10) % size;
      const ry = (py + 10) % size;
      color.ctx.fillStyle = '#6a6d72';
      color.ctx.beginPath();
      color.ctx.arc(rx, ry, 4, 0, Math.PI * 2);
      color.ctx.fill();
      color.ctx.fillStyle = '#cfd4d9';
      color.ctx.beginPath();
      color.ctx.arc(rx - 1, ry - 1, 1.6, 0, Math.PI * 2);
      color.ctx.fill();
      // заклёпка выпирает на карте высот
      height.ctx.fillStyle = '#e8e8e8';
      height.ctx.beginPath();
      height.ctx.arc(rx, ry, 4, 0, Math.PI * 2);
      height.ctx.fill();
    }
  }

  // Пятна ржавчины/грязи
  drawSpots(color.ctx, rng, 24, 20, '#4a3524', 0.22);
  // те же пятна понижают высоту (коррозия)
  drawSpots(height.ctx, rng, 24, 20, '#383838', 0.5);

  // --- Шероховатость: металл средней гладкости, вариации от```javascript
 ржавчины и царапин: швы и ржавчина — шероховатые, свежий металл — глаже.
  const rough = createCanvas(size);
  fillRoughness(rough.ctx, size, 0.42, 0.18, rng);

  // В швах и ржавых пятнах шероховатость выше
  rough.ctx.globalAlpha = 0.55;
  rough.ctx.fillStyle = '#e6e6e6';
  for (let s = 0; s <= size; s += PANEL) {
    rough.ctx.fillRect(s - SEAM / 2, 0, SEAM, size);
    rough.ctx.fillRect(0, s - SEAM / 2, size, SEAM);
  }
  rough.ctx.globalAlpha = 1;
  drawSpots(rough.ctx, rng, 24, 20, '#f0f0f0', 0.35);
  // Полированные царапины — гладкие
  rough.ctx.strokeStyle = 'rgba(70,70,70,0.5)';
  for (let s = 0; s < 40; s++) {
    rough.ctx.lineWidth = 1;
    rough.ctx.globalAlpha = 0.12 + rng() * 0.22;
    rough.ctx.beginPath();
    const x = rng() * size;
    const y = rng() * size;
    const len = 20 + rng() * 120;
    const ang = rng() * Math.PI;
    rough.ctx.moveTo(x, y);
    rough.ctx.lineTo(x + Math.cos(ang) * len, y + Math.sin(ang) * len);
    rough.ctx.stroke();
  }
  rough.ctx.globalAlpha = 1;

  const result = buildSet(color.canvas, height.canvas, rough.canvas);
  cache.set('metal', result);
  return result;
}

/**
 * Атлас окон 4x4: рамы, стёкла с разной степенью подсветки и загрязнения.
 * Подходит для зданий: ячейка атласа выбирается через offset/repeat UV.
 * @returns {{map: THREE.Texture, normalMap: THREE.Texture, roughnessMap: THREE.Texture}}
 */
export function makeWindowAtlas() {
  const cached = cache.get('windowAtlas');
  if (cached) return cached;

  const size = TEXTURE_SIZE;
  const rng = makeRng(0xA71A5);
  const CELLS = 4;
  const CELL = size / CELLS;
  const FRAME = Math.round(CELL * 0.11);

  const color = createCanvas(size);
  const height = createCanvas(size);
  const rough = createCanvas(size);

  // База: рамы высокие, стёкла утоплены
  height.ctx.fillStyle = '#d8d8d8';
  height.ctx.fillRect(0, 0, size, size);
  rough.ctx.fillStyle = '#5a5a5a';
  rough.ctx.fillRect(0, 0, size, size);

  for (let cy = 0; cy < CELLS; cy++) {
    for (let cx = 0; cx < CELLS; cx++) {
      const x0 = cx * CELL;
      const y0 = cy * CELL;

      // Рама
      const frameShade = 58 + Math.floor(rng() * 26);
      color.ctx.fillStyle = `rgb(${frameShade},${frameShade + 3},${frameShade + 6})`;
      color.ctx.fillRect(x0, y0, CELL, CELL);
      height.ctx.fillStyle = '#e2e2e2';
      height.ctx.fillRect(x0, y0, CELL, CELL);
      rough.ctx.fillStyle = '#7a7a7a';
      rough.ctx.fillRect(x0, y0, CELL, CELL);

      // Стекло
      const gx = x0 + FRAME;
      const gy = y0 + FRAME;
      const gw = CELL - FRAME * 2;
      const gh = CELL - FRAME * 2;
      const lit = rng() < 0.38;
      if (lit) {
        const warm = rng() < 0.7;
        const r = warm ? 240 : 190;
        const g = warm ? 190 : 215;
        const b = warm ? 120 : 235;
        const grad = color.ctx.createLinearGradient(gx, gy, gx, gy + gh);
        grad.addColorStop(0, `rgb(${r},${g},${b})`);
        grad.addColorStop(1, `rgb(${Math.max(0, r - 70)},${Math.max(0, g - 60)},${Math.max(0, b - 40)})`);
        color.ctx.fillStyle = grad;
      } else {
        const grad = color.ctx.createLinearGradient(gx, gy, gx + gw, gy + gh);
        grad.addColorStop(0, '#1a2430');
        grad.addColorStop(0.5, '#2a3b4d');
        grad.addColorStop(1, '#10161d');
        color.ctx.fillStyle = grad;
      }
      color.ctx.fillRect(gx, gy, gw, gh);

      // Стекло: ниже по высоте, гладкое
      height.ctx.fillStyle = '#585858';
      height.ctx.fillRect(gx, gy, gw, gh);
      rough.ctx.fillStyle = lit ? '#2e2e2e' : '#242424';
      rough.ctx.fillRect(gx, gy, gw, gh);

      // Горизонтальная перемычка у части окон
      if (rng() < 0.5) {
        const my = gy + Math.floor(gh * (0.35 + rng() * 0.3));
        color.ctx.fillStyle = `rgb(${frameShade},${frameShade + 3},${frameShade + 6})`;
        color.ctx.fillRect(gx, my - 2, gw, 4);
        height.ctx.fillStyle = '#e2e2e2';
        height.ctx.fillRect(gx, my - 2, gw, 4);
        rough.ctx.fillStyle = '#7a7a7a';
        rough.ctx.fillRect(gx, my - 2, gw, 4);
      }

      // Блик на стекле
      color.ctx.global```javascript
Alpha = 0.18;
      color.ctx.fillStyle = '#ffffff';
      color.ctx.beginPath();
      color.ctx.moveTo(gx, gy + gh);
      color.ctx.lineTo(gx + gw * 0.4, gy);
      color.ctx.lineTo(gx + gw * 0.6, gy);
      color.ctx.lineTo(gx + gw * 0.2, gy + gh);
      color.ctx.closePath();
      color.ctx.fill();
      color.ctx.globalAlpha = 1;

      // Загрязнение в нижней части стекла
      color.ctx.globalAlpha = 0.2 + rng() * 0.2;
      color.ctx.fillStyle = '#2f2b22';
      color.ctx.fillRect(gx, gy + gh * 0.8, gw, gh * 0.2);
      color.ctx.globalAlpha = 1;
      // грязь шероховатее стекла
      rough.ctx.globalAlpha = 0.5;
      rough.ctx.fillStyle = '#c8c8c8';
      rough.ctx.fillRect(gx, gy + gh * 0.8, gw, gh * 0.2);
      rough.ctx.globalAlpha = 1;
    }
  }

  const result = buildSet(color.canvas, height.canvas, rough.canvas);
  cache.set('windowAtlas', result);
  return result;
}
