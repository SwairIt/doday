/**
 * src/main.js — точка входа Doday Arena.
 * Bootstrap: настройки → рендерер → сцена → небо → свет → текстуры →
 * город → физика → коллайдеры → орбитальная камера → главный цикл.
 */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

import { Settings } from './core/settings.js';
import { Loop } from './core/loop.js';
import { bus } from './core/events.js';

import { createRenderer } from './render/renderer.js';
import { createSky } from './render/sky.js';
import { createLighting } from './render/lighting.js';

import { makeConcrete, makeAsphalt, makeBrick, makeMetal, makeWindowAtlas } from './world/textures.js';
import { buildCity } from './world/city.js';
import { initPhysics, buildStaticColliders, addGroundPlane } from './world/collision.js';

/** Параметры временной орбитальной камеры для облёта карты. */
const ORBIT_TARGET = new THREE.Vector3(0, 0, 0);
const ORBIT_START_POSITION = new THREE.Vector3(80, 60, 80);
const ORBIT_MIN_DISTANCE = 10;
const ORBIT_MAX_DISTANCE = 400;

/** Идентификаторы DOM-элементов загрузочного экрана (уже есть в разметке). */
const LOADING_DELAY_MS = 50;

/** @type {HTMLCanvasElement} */
let canvas = null;
/** @type {HTMLElement} */
let loadingScreen = null;
/** @type {HTMLElement} */
let loadingBarFill = null;
/** @type {HTMLElement} */
let loadingPercent = null;
/** @type {HTMLElement} */
let loadingStatus = null;

/**
 * Обновляет индикатор загрузки.
 * @param {number} progress прогресс от 0 до 1
 * @param {string} status подпись этапа
 */
function setLoadingProgress(progress, status) {
  const percent = Math.round(Math.min(1, Math.max(0, progress)) * 100);
  if (loadingBarFill) loadingBarFill.style.width = `${percent}%`;
  if (loadingPercent) loadingPercent.textContent = `${percent}%`;
  if (loadingStatus) loadingStatus.textContent = status;
}

/**
 * Уступает кадр браузеру, чтобы индикатор загрузки успел отрисоваться.
 * @returns {Promise<void>}
 */
function nextFrame() {
  return new Promise((resolve) => setTimeout(resolve, LOADING_DELAY_MS));
}

/**
 * Показывает сообщение об ошибке вместо игры.
 * @param {string} message текст по-русски
 */
function showFatalError(message) {
  if (loadingScreen) {
    loadingScreen.classList.remove('hidden');
    loadingScreen.style.display = 'flex';
  }
  if (loadingBarFill) loadingBarFill.style.width = '0%';
  if (loadingPercent) loadingPercent.textContent = '';
  if (loadingStatus) {
    loadingStatus.textContent = message;
    loadingStatus.style.color = '#ff5a5a';
  }
}

/**
 * Проверяет доступность WebGL2 на существующем canvas.
 * @param {HTMLCanvasElement} targetCanvas канвас из разметки
 * @returns {boolean} true, если контекст WebGL2 доступен
 */
function isWebGL2Available(targetCanvas) {
  try {
    // Пробу делаем на ОДНОРАЗОВОМ холсте: контекст, взятый на игровом canvas,
    // остаётся за ним, и WebGLRenderer потом получает уже потерянный контекст
    // (проверено — падало на getMaxPrecision с gl === null).
    void targetCanvas;
    const probe = document.createElement('canvas').getContext('webgl2');
    return probe !== null;
  } catch {
    return false;
  }
}

/**
 * Основная последовательность инициализации игры.
 * @returns {Promise<void>}
 */
async function boot() {
  setLoadingProgress(0.05, 'Загрузка настроек…');
  await nextFrame();

  // Настройки — до рендерера, т.к. он зависит от пресета качества.
  const settings = new Settings();

  setLoadingProgress(0.1, 'Создание рендерера…');
  await nextFrame();

  // createRenderer отдаёт обёртку {renderer, resize, updateAdaptiveResolution};
  // ниже нужен сам WebGLRenderer — его ждут и PMREMGenerator в небе, и OrbitControls.
  const { renderer, resize, updateAdaptiveResolution } = createRenderer(canvas, settings);
  resize(); // иначе холст остаётся 300x150 до первого события resize
  const scene = new THREE.Scene();

  setLoadingProgress(0.2, 'Настройка неба и освещения…');
  await nextFrame();

  const sky = createSky(scene, renderer, settings);
  const lighting = createLighting(scene, settings);

  setLoadingProgress(0.3, 'Генерация текстур…');
  await nextFrame();

  // Буферы текстур: прогреваем кэш генераторов до постройки города.
  const textures = {
    concrete: makeConcrete(),
    asphalt: makeAsphalt(),
    brick: makeBrick(),
    metal: makeMetal(),
    windowAtlas: makeWindowAtlas(),
  };
  Object.values(textures).forEach((texture) => {
    if (texture) renderer.initTexture(texture);
  });

  setLoadingProgress(0.45, 'Строительство города…');
  await nextFrame();

  const citySeed = 1337;
  const city = buildCity(scene, settings, citySeed);

  setLoadingProgress(0.65, 'Инициализация физики…');
  await nextFrame();

  const world = await initPhysics();
  addGroundPlane(world);

  setLoadingProgress(0.8, 'Постройка коллайдеров…');
  await nextFrame();

  buildStaticColliders(world, city.colliders);

  setLoadingProgress(0.9, 'Настройка камеры…');
  await nextFrame();

  // Временная орбитальная камера для облёта карты (до появления игрока).
  const aspect = window.innerWidth / Math.max(1, window.innerHeight);
  const camera = new THREE.PerspectiveCamera(settings.fov, aspect, 0.1, 2000);
  camera.position.copy(ORBIT_START_POSITION);
  camera.lookAt(ORBIT_TARGET);

  const orbitControls = new OrbitControls(camera, renderer.domElement);
  orbitControls.target.copy(ORBIT_TARGET);
  orbitControls.enableDamping = true;
  orbitControls.minDistance = ORBIT_MIN_DISTANCE;
  orbitControls.maxDistance = ORBIT_MAX_DISTANCE;
  orbitControls.update();

  // Главный цикл: физика в onFixed, рендер в onRender.
  const loop = new Loop();

  loop.onFixed((dt) => {
    world.timestep = dt;
    world.step();
    bus.emit('fixed', dt);
  });

  loop.onRender((dt, alpha) => {
    orbitControls.update(dt);
    renderer.render(scene, camera);
  });

  // Подгонка камеры и рендерера под размер окна.
  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / Math.max(1, window.innerHeight);
    camera.updateProjectionMatrix();
    resize();
  });

  setLoadingProgress(1, 'Готово');
  loop.start();

  // Скрываем загрузочный экран после старта цикла.
  if (loadingScreen) {
    loadingScreen.classList.add('hidden');
    loadingScreen.style.display = 'none';
  }

  return {
    settings,
    renderer,
    scene,
    camera,
    orbitControls,
    sky,
    lighting,
    textures,
    city,
    world,
    loop,
  };
}

/** Игровой контекст, доступный другим модулям и консоли отладки. */
export const Game = {
  settings: null,
  renderer: null,
  scene: null,
  camera: null,
  orbitControls: null,
  sky: null,
  lighting: null,
  textures: null,
  city: null,
  world: null,
  loop: null,
  ready: false,
};

/**
 * Старт приложения после готовности DOM.
 */
function main() {
  canvas = /** @type {HTMLCanvasElement|null} */ (document.getElementById('game'));
  loadingScreen = document.getElementById('loading-screen');
  loadingBarFill = document.getElementById('loading-bar-fill');
  loadingPercent = document.getElementById('loading-percent');
  loadingStatus = document.getElementById('loading-status');

  if (!canvas) {
    showFatalError('Ошибка: канвас #game не найден в разметке.');
    return;
  }

  if (!isWebGL2Available(canvas)) {
    showFatalError(
      'К сожалению, ваш браузер не поддерживает WebGL2. ' +
      'Обновите браузер или включите аппаратное ускорение, чтобы играть в Doday Arena.'
    );
    return;
  }

  boot()
    .then((context) => {
      Object.assign(Game, context, { ready: true });
      bus.emit('game:ready', Game);
    })
    .catch((err) => {
      console.error('[DodayArena] Ошибка инициализации:', err);
      showFatalError('Произошла ошибка при запуске игры. Попробуйте обновить страницу.');
    });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', main, { once: true });
} else {
  main();
}
