// Точка входа Doday Arena: загрузка, инициализация подсистем, главный цикл.
import * as THREE from 'three';

import { Settings } from './core/settings.js';
import { bus } from './core/events.js';
import { Loop } from './core/loop.js';
import { InputState } from './core/input-state.js';
import { createInput } from './core/input.js';

import { createRenderer } from './render/renderer.js';
import { createSky } from './render/sky.js';
import { createLighting } from './render/lighting.js';

import { buildCity } from './world/city.js';
import { initPhysics, buildStaticColliders, addGroundPlane } from './world/collision.js';

import { createPlayer } from './player/controller.js';
import { createPlayerCamera } from './player/camera.js';

import { createAudio } from './audio/audio.js';
import { createHud } from './ui/hud.js';
import { createTouchControls } from './ui/touch.js';
import { createTrackpadInput } from './core/input-trackpad.js';

import { createWeaponFx } from './weapons/fx.js';
import { createWeapon } from './weapons/weapon.js';
import { WEAPONS, getWeapon } from './weapons/registry.js';
import { createSpawner } from './ai/spawner.js';
import { createWaveMode } from './modes/waves.js';
import { createPerception } from './ai/perception.js';

/** Размер первой волны ботов. */
const FIRST_WAVE_SIZE = 5;
/** Индекс первого оружия в реестре. */
const DEFAULT_WEAPON_INDEX = 0;
/** Порог различения живой цели, HP. */
const ALIVE_HP = 0;

// --- Элементы экрана загрузки (разметка уже существует) ---
const canvas = document.getElementById('game');
const loadingScreen = document.getElementById('loading-screen');
const loadingBarFill = document.getElementById('loading-bar-fill');
const loadingPercent = document.getElementById('loading-percent');
const loadingStatus = document.getElementById('loading-status');

/**
 * Обновить полосу загрузки.
 * @param {number} fraction Прогресс от 0 до 1.
 * @param {string} status Подпись текущего шага.
 */
function setLoadingProgress(fraction, status) {
  const percent = Math.round(fraction * 100);
  loadingBarFill.style.width = `${percent}%`;
  loadingPercent.textContent = `${percent}%`;
  loadingStatus.textContent = status;
}

/** Проверить доступность WebGL2 на одноразовом холсте. */
function isWebGL2Available() {
  const probe = document.createElement('canvas');
  const gl = probe.getContext('webgl2');
  return gl !== null;
}

/**
 * Отрисовать сообщение об отсутствии WebGL2 вместо игры.
 */
function showWebGL2Unavailable() {
  loadingStatus.textContent =
    'Ваш браузер не поддерживает WebGL2. Обновите браузер или включите аппаратное ускорение.';
  loadingBarFill.style.width = '0%';
  canvas.style.display = 'none';
}

/**
 * Создать адаптер ввода: единый переиспользуемый объект для контроллера и камеры.
 * Источники: клавиатура/мышь (createInput) и тач-контролы, пишущие в тот же InputState.
 * @param {HTMLCanvasElement} domCanvas Игровой холст.
 * @param {Settings} settings Настройки.
 */
function createInputAdapter(domCanvas, settings) {
  // ЕДИНЫЙ InputState на все источники: createInput заводит его внутри себя,
  // поэтому берём именно его. Свой new InputState() здесь означал бы, что
  // клавиатура пишет в один объект, а игра читает другой — игрок не двигается.
  const keyboardMouse = createInput(domCanvas, settings);
  const state = keyboardMouse.state;

  const touch = createTouchControls(document.body, state);
  // Управление под трекпад Mac: обзор двухпальцевым свайпом без захвата
  // курсора, ADS переключателем, огонь на пробел и J.
  const trackpad = createTrackpadInput(domCanvas, settings, state);
  // Включаем безусловно: на Mac это основной способ играть без мыши, а на
  // остальных машинах слой просто добавляет запасные клавиши (J/Enter — огонь,
  // F — прицел, стрелки — обзор) и ничему не мешает.
  trackpad.setEnabled(true);

  // Один объект на всю игру, заполняется каждый кадр в onFixed.
  const adapter = {
    moveX: 0,
    moveZ: 0,
    lookX: 0,
    lookY: 0,
    mouseDX: 0,
    mouseDY: 0,
    aim: false,
    jump: false,
    crouch: false,
    sprint: false,
    fire: false,
    reload: false,
    weaponIndex: -1,
    wheelDelta: 0,
  };

  // Синхронизация адаптера из InputState (переиспользование, без аллокаций).
  const sync = () => {
    adapter.moveX = state.move.x;
    adapter.moveZ = state.move.y;
    // Камера читает mouseDX/mouseDY, контроллер — moveX/moveZ: держим оба вида.
    adapter.lookX = state.look.x;
    adapter.lookY = state.look.y;
    adapter.mouseDX = state.look.x;
    adapter.mouseDY = state.look.y;
    adapter.jump = state.buttons.jump.pressed;
    adapter.crouch = state.buttons.crouch.pressed;
    adapter.sprint = state.buttons.sprint.pressed;
    adapter.fire = state.buttons.fire.pressed;
    adapter.reload = state.buttons.reload.justPressed;
    adapter.aim = state.buttons.aim.pressed;
    adapter.wheelDelta = state.wheelDelta || 0;
    adapter.weaponIndex = state.weaponIndex !== undefined ? state.weaponIndex : -1;
  };

  return { state, adapter, keyboardMouse, touch, trackpad, sync };
}

/** Главная асинхронная инициализация игры. */
async function init() {
  setLoadingProgress(0.05, 'Проверка WebGL2…');
  if (!isWebGL2Available()) {
    showWebGL2Unavailable();
    return null;
  }

  // Settings -> рендерер -> сцена.
  setLoadingProgress(0.10, 'Загрузка настроек…');
  const settings = new Settings();

  setLoadingProgress(0.15, 'Инициализация рендерера…');
  const { renderer, resize, updateAdaptiveResolution } = createRenderer(canvas, settings);
  resize();

  const scene = new THREE.Scene();

  setLoadingProgress(0.25, 'Создание неба…');
  const sky = createSky(scene, renderer, settings);

  setLoadingProgress(0.30, 'Настройка освещения…');
  const lighting = createLighting(scene, settings);

  // Город до физики: коллайдеры создаются после инициализации мира Rapier.
  setLoadingProgress(0.40, 'Генерация города…');
  const city = buildCity(scene, settings, settings.get('seed'));

  setLoadingProgress(0.55, 'Инициализация физики…');
  const world = await initPhysics();
  addGroundPlane(world);
  buildStaticColliders(world, city.colliders);

  // Ввод: один адаптер на все подсистемы.
  setLoadingProgress(0.65, 'Подключение управления…');
  const input = createInputAdapter(canvas, settings);

  setLoadingProgress(0.75, 'Создание игрока…');
  const player = createPlayer(world, city.spawnPoints[0]);

  // Здоровья в контроллере нет — модуль player/health.js не генерировался,
  // поэтому ведём его здесь: HUD и попадания ботов работают с этим объектом.
  const playerHealth = {
    max: 100,
    current: 100,
    /**
     * Наносит урон игроку.
     * @param {number} amount урон в единицах здоровья
     */
    damage(amount) {
      this.current = Math.max(0, this.current - amount);
    },
  };
  const playerCamera = createPlayerCamera(settings);

  setLoadingProgress(0.80, 'Загрузка звука…');
  const audio = createAudio(playerCamera.listener || playerCamera.camera);

  setLoadingProgress(0.85, 'Создание интерфейса…');
  const hud = createHud(document.body);

  const fx = createWeaponFx(scene, world, settings);

  setLoadingProgress(0.90, 'Подготовка ботов…');
  let bots = [];

  // Адаптер камеры не раскрывает своё состояние — азимут из направления взгляда.
  const camDir = new THREE.Vector3();
  const getCameraYaw = () => {
    playerCamera.camera.getWorldDirection(camDir);
    return Math.atan2(-camDir.x, -camDir.z);
  };

  const horizontalSpeed = new THREE.Vector3();
  const getMoveSpeed = () => {
    horizontalSpeed.copy(player.velocity);
    horizontalSpeed.y = 0;
    return horizontalSpeed.length();
  };

  const getTargets = () => bots.filter((bot) => bot.alive);

  const weaponDeps = {
    world,
    camera: playerCamera.camera,
    fx,
    settings,
    getTargets,
    getMoveSpeed,
  };

  const weaponIds = Object.keys(WEAPONS);
  let weaponIndex = DEFAULT_WEAPON_INDEX;
  let weapon = createWeapon(weaponIds[weaponIndex], weaponDeps);

  const switchWeapon = (index) => {
    const count = weaponIds.length;
    weaponIndex = ((index % count) + count) % count;
    weapon = createWeapon(weaponIds[weaponIndex], weaponDeps);
    hud.setAmmo(weapon.ammo, weapon.reserveAmmo);
  };

  // Восприятие общее на всех ботов: зрение конусом с рейкастом и слух.
  const perception = createPerception(world, { settings });

  // Что боты знают об игроке: позиция, направление взгляда для спавна вне
  // поля зрения и приём урона. Контроллер здоровьем не занимается.
  const botTarget = {
    position: player.position,
    fov: settings.fov,
    forward: new THREE.Vector3(),
    takeDamage(amount) {
      playerHealth.damage(amount);
    },
  };

  const spawner = createSpawner(scene, world, city.spawnPoints, {
    settings,
    // Спавном управляет режим раундов, иначе волна не кончается.
    autoRespawn: false,
    perception,
    fx,
    rng: Math.random,
    player,
    onBotSpawned: (bot) => bots.push(bot),
    onHit: (bot) => {
      hud.hitmarker();
      audio.play('hit');
    },
    onKill: (bot) => {
      hud.addKill();
      audio.play('kill');
    },
  });
  // Режим раундов: волны с паузой между ними, ростом сложности и
  // экранными надписями «РАУНД N» / «ЗАЧИЩЕН».
  const waves = createWaveMode({
    spawner,
    hud,
    audio,
    player: botTarget,
    settings,
    container: document.body,
  });

  // Спавнер списка не отдаёт: ведём его сами по событиям шины.
  bus.on('bot:spawned', ({ bot }) => bots.push(bot));
  bus.on('bot:killed', ({ bot }) => {
    const at = bots.indexOf(bot);
    if (at >= 0) bots.splice(at, 1);
    hud.addKill();
    audio.play('hit');
  });

  // Обработка выстрелов: попадания по ботам через fireHitscan уже внутри weapon.update.
  weapon.onHit = (bot, damage) => {
    bot.takeDamage(damage);
    hud.hitmarker();
    audio.play('hit');
    if (bot.hp <= ALIVE_HP) {
      hud.addKill();
      audio.play('kill');
    }
  };

  // Первая волна после загрузки.
  setLoadingProgress(1.0, 'Готово!');
  // spawnWave требует позицию и направление взгляда: она спавнит ботов вне
  // поля зрения игрока, без этих данных возвращает 0.
  waves.start();

  hud.setHealth(player.hp, player.maxHp);
  hud.setAmmo(weapon.ammo, weapon.reserveAmmo);
  hud.setSpread(0);

  // Главный цикл.
  // maxSubSteps по умолчанию 5: при 10 FPS на кадр нужно 6 шагов, остаток
  // отбрасывался и игра шла в замедленной съёмке. 15 хватает вплоть до 4 FPS.
  const loop = new Loop({ step: 1 / 60, maxSubSteps: 15 });

  loop.onFixed((dt) => {
    input.sync();

    player.update(dt, input.adapter, getCameraYaw());

    // Смена оружия: цифры 1–6 и колесо мыши.
    if (input.adapter.weaponIndex >= 0 && input.adapter.weaponIndex < weaponIds.length) {
      switchWeapon(input.adapter.weaponIndex);
      input.state.weaponIndex = -1;
    } else if (input.adapter.wheelDelta !== 0) {
      switchWeapon(weaponIndex + (input.adapter.wheelDelta > 0 ? 1 : -1));
    }

    weapon.update(dt, {
      fire: input.adapter.fire,
      reload: input.adapter.reload,
      origin: playerCamera.camera.position,
      direction: playerCamera.camera.getWorldDirection(camDir),
    });


    playerCamera.camera.getWorldDirection(botTarget.forward);
    spawner.update(dt, botTarget);
    waves.update(dt);
    world.step();
  });

  loop.onRender((dt, alpha) => {
    playerCamera.update(dt, player, input.adapter);
    lighting.update(player.position);

    hud.setHealth(playerHealth.current, playerHealth.max);
    hud.setAmmo(weapon.ammo, weapon.reserveAmmo);
    hud.setSpread(weapon.currentSpread);

    updateAdaptiveResolution(dt);
    renderer.render(scene, playerCamera.camera);

    input.state.endFrame();
  });

  loadingScreen.style.display = 'none';
  loop.start();

  return {
    settings, renderer, resize, updateAdaptiveResolution, scene, sky, lighting,
    city, world, input, player, playerCamera, audio, hud, fx,
    weapon, switchWeapon, spawner, waves, loop, camera: playerCamera.camera,
  };
}

/** Глобальный объект игры со всеми подсистемами. */
export const Game = await init();
