/**
 * Создание и управление WebGL-рендерером, включая адаптивное разрешение.
 */

import * as THREE from 'three';

/** Пределы множителя разрешения. */
const RESOLUTION_MIN = 0.6;
const RESOLUTION_STEP_DOWN = 0.1;
const RESOLUTION_STEP_UP = 0.05;

/** Пороги FPS для адаптации. */
const FPS_LOW = 55;
const FPS_HIGH = 58;

/** Секунд стабильного FPS до повышения разрешения. */
const UP_SCALE_DELAY = 3;

/** Минимальный интервал между понижениями разрешения (сек). */
const DOWN_SCALE_DELAY = 1;

/** Максимальный devicePixelRatio по уровню качества. */
function maxPixelRatio(quality) {
  const dpr = window.devicePixelRatio || 1;
  switch (quality) {
    case 'low': return Math.min(dpr, 1);
    case 'medium': return Math.min(dpr, 1.5);
    default: return Math.min(dpr, 2);
  }
}

/**
 * Создаёт рендерер и привязанные к нему хелперы.
 * @param {HTMLCanvasElement} canvas целевой канвас
 * @param {object} settings настройки игры
 * @returns {{renderer: THREE.WebGLRenderer, resize: Function, updateAdaptiveResolution: Function}}
 */
export function createRenderer(canvas, settings) {
  const quality = settings.quality || 'high';

  const renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: quality !== 'low',
    powerPreference: 'high-performance',
    stencil: false,
  });

  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.0;
  renderer.outputColorSpace = THREE.SRGBColorSpace;

  renderer.shadowMap.enabled = quality !== 'low';
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  // Адаптивное разрешение: current / limit в долях devicePixelRatio
  const pixLimit = maxPixelRatio(quality);
  let pixCurrent = pixLimit;
  let stableTime = 0;   // накопленное время стабильного FPS
  let coolDown = 0;     // пауза после последнего изменения

  /**
   * Применяет текущий множитель и размеры канваса.
   */
  function applySize() {
    const width = canvas.clientWidth || window.innerWidth;
    const height = canvas.clientHeight || window.innerHeight;
    renderer.setPixelRatio(pixCurrent);
    renderer.setSize(width, height, false);
  }

  /**
   * Обработчик изменения размера окна с учётом devicePixelRatio.
   */
  function resize() {
    applySize();
  }

  /**
   * Адаптирует множитель разрешения по измеренному FPS.
   * Вызывать каждый кадр с усреднённым FPS.
   * @param {number} fps текущий усреднённый FPS
   */
  function updateAdaptiveResolution(fps) {
    const dt = Math.max(0.0001, 1 / Math.max(fps, 1));
    coolDown += dt;

    if (fps < FPS_LOW && pixCurrent > RESOLUTION_MIN && coolDown >= DOWN_SCALE_DELAY) {
      pixCurrent = Math.max(RESOLUTION_MIN, pixCurrent - RESOLUTION_STEP_DOWN);
      stableTime = 0;
      coolDown = 0;
      applySize();
    } else if (fps > FPS_HIGH && pixCurrent < pixLimit) {
      stableTime += dt;
      if (stableTime >= UP_SCALE_DELAY) {
        pixCurrent = Math.min(pixLimit, pixCurrent + RESOLUTION_STEP_UP);
        stableTime = 0;
        coolDown = 0;
        applySize();
      }
    } else {
      stableTime = 0;
    }
  }

  resize();

  return { renderer, resize, updateAdaptiveResolution };
}
