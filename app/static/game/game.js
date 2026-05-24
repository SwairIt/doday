/**
 * Беллстрой ТВ — walking мем-игра на Three.js
 *
 * Геймплей:
 * - Третий-person вид, ходишь по карте от лица Беллстроя
 * - По карте разбросаны мем-пикапы (67, кокос воды, скибиди, ризз, гойда, ...)
 * - Подходишь к пикапу — auto-collect, +score, мем-popup с описанием
 * - 17 уникальных мемов всего. Собери все.
 *
 * Управление:
 * - Desktop: WASD = движение, mouse-drag = поворот камеры
 * - Mobile: левая половина экрана = виртуальный джойстик, правая = поворот камеры
 *
 * Архитектура: один файл, vanilla Three.js через ESM import.
 */

import * as THREE from 'three';

// ─── Состояние игры ──────────────────────────────────────────────────────

const state = {
  score: 0,
  collected: new Set(JSON.parse(localStorage.getItem('belstroy-collected') || '[]')),
  highScore: parseInt(localStorage.getItem('belstroy-high-score') || '0', 10),
  sixSevenShown: localStorage.getItem('belstroy-67-shown') === '1',
  pickups: [],
  player: null,
};

// ─── Three.js core ───────────────────────────────────────────────────────

const canvas = document.getElementById('game-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x1a0f3d, 25, 60);
scene.background = new THREE.Color(0x0d0820);

const camera = new THREE.PerspectiveCamera(
  65,
  window.innerWidth / window.innerHeight,
  0.1,
  200
);

// ─── Освещение ───────────────────────────────────────────────────────────

scene.add(new THREE.AmbientLight(0x6d28d9, 0.4));

const sun = new THREE.DirectionalLight(0xffffff, 1.2);
sun.position.set(15, 30, 15);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -40;
sun.shadow.camera.right = 40;
sun.shadow.camera.top = 40;
sun.shadow.camera.bottom = -40;
sun.shadow.camera.far = 80;
scene.add(sun);

const rimLight = new THREE.DirectionalLight(0xd946ef, 0.6);
rimLight.position.set(-10, 5, -10);
scene.add(rimLight);

// ─── Мир ─────────────────────────────────────────────────────────────────

function buildWorld() {
  const worldSize = 40;

  // Земля — большая плоскость с фиолетовым floor
  const groundGeom = new THREE.PlaneGeometry(worldSize, worldSize, 4, 4);
  const groundMat = new THREE.MeshStandardMaterial({
    color: 0x2e1065,
    metalness: 0.1,
    roughness: 0.9,
  });
  const ground = new THREE.Mesh(groundGeom, groundMat);
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // Сетка-grid на полу (RGB-стиль стримерской комнаты)
  const grid = new THREE.GridHelper(worldSize, 20, 0xd946ef, 0x4c1d95);
  grid.position.y = 0.01;
  scene.add(grid);

  // Стены по периметру (невидимые collision-боксы + видимые декорации)
  const wallMat = new THREE.MeshStandardMaterial({
    color: 0x4c1d95,
    metalness: 0.5,
    roughness: 0.4,
    emissive: 0x6d28d9,
    emissiveIntensity: 0.2,
  });
  const wallHeight = 3;
  const wallThickness = 0.5;
  const halfSize = worldSize / 2;

  // 4 стены
  const walls = [
    { x: 0, z: halfSize, w: worldSize, h: wallThickness },
    { x: 0, z: -halfSize, w: worldSize, h: wallThickness },
    { x: halfSize, z: 0, w: wallThickness, h: worldSize },
    { x: -halfSize, z: 0, w: wallThickness, h: worldSize },
  ];
  walls.forEach((w) => {
    const wallGeom = new THREE.BoxGeometry(w.w, wallHeight, w.h);
    const wall = new THREE.Mesh(wallGeom, wallMat);
    wall.position.set(w.x, wallHeight / 2, w.z);
    wall.castShadow = true;
    wall.receiveShadow = true;
    scene.add(wall);
  });

  // Декорации — random «здания» (boxes разных размеров) для атмосферы
  const buildingMat = new THREE.MeshStandardMaterial({
    color: 0x1e1b4b,
    metalness: 0.4,
    roughness: 0.6,
    emissive: 0x4c1d95,
    emissiveIntensity: 0.15,
  });
  const obstacles = [];
  for (let i = 0; i < 12; i++) {
    const w = 2 + Math.random() * 3;
    const h = 2 + Math.random() * 4;
    const d = 2 + Math.random() * 3;
    const x = (Math.random() - 0.5) * (worldSize - 6);
    const z = (Math.random() - 0.5) * (worldSize - 6);
    // не ставим близко к центру (точка спавна игрока)
    if (Math.abs(x) < 4 && Math.abs(z) < 4) continue;
    const bldg = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), buildingMat);
    bldg.position.set(x, h / 2, z);
    bldg.castShadow = true;
    bldg.receiveShadow = true;
    scene.add(bldg);
    // Добавим неон-полоску сверху для cyberpunk-вайба
    const stripGeom = new THREE.BoxGeometry(w, 0.05, d);
    const stripMat = new THREE.MeshBasicMaterial({
      color: [0xd946ef, 0xfbbf24, 0x06b6d4][i % 3],
    });
    const strip = new THREE.Mesh(stripGeom, stripMat);
    strip.position.set(x, h + 0.05, z);
    scene.add(strip);
    obstacles.push({ x, z, halfW: w / 2 + 0.5, halfD: d / 2 + 0.5 });
  }
  return { obstacles, halfSize };
}

const world = buildWorld();

// ─── Персонаж Беллстрой (procedural) ────────────────────────────────────

function makeProceduralCharacter() {
  const group = new THREE.Group();

  const bodyGeom = new THREE.CylinderGeometry(0.55, 0.65, 1.3, 16);
  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x0d0d0d, metalness: 0.1, roughness: 0.85,
  });
  const body = new THREE.Mesh(bodyGeom, bodyMat);
  body.position.y = 0.65;
  body.castShadow = true;
  group.add(body);

  // Принт «Б» на футболке
  const emblemCanvas = document.createElement('canvas');
  emblemCanvas.width = 128;
  emblemCanvas.height = 128;
  const ctx = emblemCanvas.getContext('2d');
  ctx.font = 'bold 80px sans-serif';
  ctx.fillStyle = 'white';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText('Б', 64, 64);
  const emblemTex = new THREE.CanvasTexture(emblemCanvas);
  const emblem = new THREE.Mesh(
    new THREE.PlaneGeometry(0.4, 0.4),
    new THREE.MeshStandardMaterial({ map: emblemTex, transparent: true })
  );
  emblem.position.set(0, 0.8, 0.66);
  group.add(emblem);

  const skinMat = new THREE.MeshStandardMaterial({ color: 0xffd4a8, roughness: 0.6 });
  const neck = new THREE.Mesh(new THREE.CylinderGeometry(0.18, 0.22, 0.2, 12), skinMat);
  neck.position.y = 1.4;
  neck.castShadow = true;
  group.add(neck);

  const head = new THREE.Mesh(new THREE.SphereGeometry(0.45, 32, 32), skinMat);
  head.position.y = 1.85;
  head.scale.y = 1.05;
  head.castShadow = true;
  group.add(head);

  // Блонд-волосы (чёлка + боковые)
  const hairMat = new THREE.MeshStandardMaterial({ color: 0xead49a, roughness: 0.85 });
  for (let i = -2; i <= 2; i++) {
    const tuft = new THREE.Mesh(new THREE.ConeGeometry(0.06, 0.18, 6), hairMat);
    tuft.position.set(i * 0.08, 2.05, 0.4);
    tuft.rotation.x = -Math.PI / 6;
    tuft.rotation.z = i * 0.1;
    group.add(tuft);
  }
  const sideHairGeom = new THREE.SphereGeometry(0.12, 12, 12);
  const sideHairL = new THREE.Mesh(sideHairGeom, hairMat);
  sideHairL.position.set(-0.42, 1.75, 0.1);
  sideHairL.scale.set(0.5, 1, 0.7);
  group.add(sideHairL);
  const sideHairR = sideHairL.clone();
  sideHairR.position.x = 0.42;
  group.add(sideHairR);

  // Глаза-прищур
  for (const xSign of [-1, 1]) {
    const white = new THREE.Mesh(
      new THREE.SphereGeometry(0.07, 16, 16),
      new THREE.MeshStandardMaterial({ color: 0xffffff })
    );
    white.position.set(0.16 * xSign, 1.92, 0.4);
    white.scale.y = 0.6;
    group.add(white);
    const pupil = new THREE.Mesh(
      new THREE.SphereGeometry(0.035, 12, 12),
      new THREE.MeshStandardMaterial({ color: 0x1a4080 })
    );
    pupil.position.set(0.16 * xSign, 1.92, 0.45);
    group.add(pupil);
  }
  // Брови
  for (const xSign of [-1, 1]) {
    const brow = new THREE.Mesh(
      new THREE.BoxGeometry(0.12, 0.025, 0.025),
      new THREE.MeshStandardMaterial({ color: 0xc8a070 })
    );
    brow.position.set(0.17 * xSign, 2.01, 0.42);
    brow.rotation.z = -xSign * 0.15;
    group.add(brow);
  }
  // Ухмылка
  const smile = new THREE.Mesh(
    new THREE.TorusGeometry(0.12, 0.018, 8, 16, Math.PI * 0.7),
    new THREE.MeshStandardMaterial({ color: 0x802020 })
  );
  smile.position.set(0.02, 1.74, 0.43);
  smile.rotation.z = -0.25;
  smile.rotation.x = Math.PI;
  group.add(smile);

  // Кепка задом-наперёд
  const capMat = new THREE.MeshStandardMaterial({ color: 0x141414, metalness: 0.2, roughness: 0.7 });
  const capCrown = new THREE.Mesh(
    new THREE.SphereGeometry(0.5, 32, 32, 0, Math.PI * 2, 0, Math.PI / 2),
    capMat
  );
  capCrown.position.y = 2.1;
  capCrown.castShadow = true;
  group.add(capCrown);
  const band = new THREE.Mesh(
    new THREE.CylinderGeometry(0.5, 0.5, 0.08, 32, 1, true),
    capMat
  );
  band.position.y = 2.08;
  group.add(band);
  const visor = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.04, 0.35), capMat);
  visor.position.set(0, 2.05, -0.45);
  visor.rotation.x = -0.12;
  visor.castShadow = true;
  group.add(visor);

  // Snapback patch
  const logoCanvas = document.createElement('canvas');
  logoCanvas.width = 64;
  logoCanvas.height = 32;
  const lctx = logoCanvas.getContext('2d');
  lctx.fillStyle = 'white';
  lctx.fillRect(0, 0, 64, 32);
  lctx.fillStyle = '#0d0d0d';
  lctx.font = 'bold 16px sans-serif';
  lctx.textAlign = 'center';
  lctx.textBaseline = 'middle';
  lctx.fillText('БЕЛЛ', 32, 16);
  const logoTex = new THREE.CanvasTexture(logoCanvas);
  const logoPatch = new THREE.Mesh(
    new THREE.PlaneGeometry(0.28, 0.12),
    new THREE.MeshStandardMaterial({ map: logoTex })
  );
  logoPatch.position.set(0, 2.18, -0.32);
  logoPatch.rotation.x = -0.1;
  logoPatch.rotation.y = Math.PI;
  group.add(logoPatch);

  // Уши
  for (const xSign of [-1, 1]) {
    const ear = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 12), skinMat);
    ear.position.set(0.42 * xSign, 1.85, 0);
    ear.scale.set(0.6, 1, 0.4);
    group.add(ear);
  }
  // Руки
  for (const xSign of [-1, 1]) {
    const arm = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.1, 0.9, 12), bodyMat);
    arm.position.set(0.58 * xSign, 0.9, 0);
    arm.rotation.z = -xSign * 0.15;
    arm.castShadow = true;
    arm.userData.armSide = xSign;
    group.add(arm);
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 12), skinMat);
    hand.position.set(0.7 * xSign, 0.4, 0);
    group.add(hand);
  }

  return group;
}

// ─── Player + camera ────────────────────────────────────────────────────

const player = makeProceduralCharacter();
player.position.set(0, 0, 0);
scene.add(player);
state.player = player;

const playerState = {
  position: new THREE.Vector3(0, 0, 0),
  rotation: 0,  // yaw в радианах
  velocity: new THREE.Vector3(),
  walkPhase: 0,
};

// Camera mode: third-person, ~5 units behind player, ~3 up
const cameraState = {
  yaw: 0,   // поворот вокруг игрока
  pitch: -0.2,  // взгляд чуть сверху вниз
  distance: 7,
};

function updateCamera() {
  // Камера на orbit'ы вокруг игрока
  const offsetX = Math.sin(cameraState.yaw) * Math.cos(cameraState.pitch) * cameraState.distance;
  const offsetY = -Math.sin(cameraState.pitch) * cameraState.distance + 2.5;
  const offsetZ = Math.cos(cameraState.yaw) * Math.cos(cameraState.pitch) * cameraState.distance;
  camera.position.set(
    playerState.position.x + offsetX,
    playerState.position.y + offsetY,
    playerState.position.z + offsetZ
  );
  camera.lookAt(
    playerState.position.x,
    playerState.position.y + 1.5,
    playerState.position.z
  );
}

// ─── Каталог мемов ───────────────────────────────────────────────────────

const MEMES = [
  { id: '67',          emoji: '6️⃣7️⃣', label: 'Six Seven',         desc: 'Тыщ-тыщ. Шесть-семь. Ты в моменте.', color: 0xfbbf24, points: 67, special: true },
  { id: 'coconut',     emoji: '🥥',     label: 'Кокос Воды',         desc: 'Главный coconut стрим-вайбов.',       color: 0x92400e, points: 10 },
  { id: 'sigma',       emoji: 'Σ',      label: 'Sigma',               desc: 'Грайндсет. Альфа-male energy.',       color: 0xfafafa, points: 10 },
  { id: 'skibidi',     emoji: '🚽',     label: 'Skibidi',             desc: 'Toilet. Brainrot grade 10.',           color: 0xd1d5db, points: 10 },
  { id: 'rizz',        emoji: '😎',     label: 'Rizz',                desc: 'W rizz. Pulled the baddies.',          color: 0xec4899, points: 10 },
  { id: 'cap',         emoji: '🧢',     label: 'No Cap',              desc: 'On god, no cap fr fr.',                 color: 0xef4444, points: 10 },
  { id: 'sus',         emoji: '🔺',     label: 'Sus',                 desc: 'Among us. Кто-то определённо сус.',    color: 0xdc2626, points: 10 },
  { id: 'bruh',        emoji: '💀',     label: 'Bruh',                desc: 'Skull emoji. Я мёртв со смеху.',       color: 0xe5e7eb, points: 10 },
  { id: 'gyatt',       emoji: '🍑',     label: 'Gyatt',               desc: 'GYATT. Brainrot уровень дзен.',        color: 0xfdba74, points: 10 },
  { id: 'ohio',        emoji: '🌽',     label: 'Ohio',                desc: 'Only in Ohio. Только в Огайо.',        color: 0xeab308, points: 10 },
  { id: 'fanum',       emoji: '🍔',     label: 'Fanum Tax',           desc: 'Steal a bite. Это Fanum tax, брат.',   color: 0xd97706, points: 10 },
  { id: 'mewing',      emoji: '🦴',     label: 'Mewing',              desc: 'Jawline maxxing. Закрой рот.',         color: 0xfafafa, points: 10 },
  { id: 'goida',       emoji: '⚔️',     label: 'Гойда',                desc: 'Старослав-боевой клич. Г-О-Й-Д-А.',  color: 0xb91c1c, points: 10 },
  { id: 'vmomente',    emoji: '🔥',     label: 'В моменте',           desc: 'Стримерская концентрация на максимум.', color: 0xf97316, points: 10 },
  { id: 'roll',        emoji: '🎰',     label: 'Roll',                desc: 'Крути слоты. Стримерская классика.',   color: 0xa78bfa, points: 10 },
  { id: 'aura',        emoji: '✨',     label: 'Aura +1000',          desc: 'Massive aura points. Не ты, точно.',   color: 0xc4b5fd, points: 10 },
  { id: 'pookie',      emoji: '🐻',     label: 'Pookie',              desc: 'Делулу is the solulu. Pookie bear.',   color: 0xf472b6, points: 10 },
];

// ─── Пикапы (расставляем по миру) ────────────────────────────────────────

function spawnPickups() {
  for (const meme of MEMES) {
    if (state.collected.has(meme.id)) continue;
    // Случайная позиция в пределах мира, не слишком близко к центру
    let x, z, tries = 0;
    do {
      x = (Math.random() - 0.5) * 30;
      z = (Math.random() - 0.5) * 30;
      tries++;
    } while ((Math.abs(x) < 3 && Math.abs(z) < 3) && tries < 20);

    // Сама модель пикапа: floating диск с эмодзи-текстурой
    const group = new THREE.Group();

    // Постамент — светящаяся плита
    const baseGeom = new THREE.CylinderGeometry(0.4, 0.5, 0.15, 16);
    const baseMat = new THREE.MeshStandardMaterial({
      color: meme.color,
      emissive: meme.color,
      emissiveIntensity: 0.6,
      metalness: 0.5,
      roughness: 0.4,
    });
    const base = new THREE.Mesh(baseGeom, baseMat);
    base.castShadow = true;
    group.add(base);

    // Текстовый billboard с эмодзи
    const emojiCanvas = document.createElement('canvas');
    emojiCanvas.width = 256;
    emojiCanvas.height = 256;
    const ectx = emojiCanvas.getContext('2d');
    ectx.font = '170px sans-serif';
    ectx.textAlign = 'center';
    ectx.textBaseline = 'middle';
    ectx.fillText(meme.emoji, 128, 145);
    const emojiTex = new THREE.CanvasTexture(emojiCanvas);
    const billboard = new THREE.Mesh(
      new THREE.PlaneGeometry(0.9, 0.9),
      new THREE.MeshBasicMaterial({ map: emojiTex, transparent: true, depthWrite: false })
    );
    billboard.position.y = 1.2;
    group.add(billboard);

    group.position.set(x, 0.1, z);
    group.userData = { meme, billboard, baseY: 0.1, spawnTime: performance.now() };
    scene.add(group);
    state.pickups.push(group);
  }
}
spawnPickups();

// ─── Input — клавиатура + touch joystick ─────────────────────────────────

const input = {
  forward: false, back: false, left: false, right: false,
  joyX: 0, joyY: 0,
  cameraDeltaYaw: 0, cameraDeltaPitch: 0,
};

// Keyboard (desktop)
window.addEventListener('keydown', (e) => {
  if (['w', 'ц', 'ц', 'ArrowUp'].includes(e.key.toLowerCase())) input.forward = true;
  if (['s', 'ы', 'ы', 'ArrowDown'].includes(e.key.toLowerCase())) input.back = true;
  if (['a', 'ф', 'ф', 'ArrowLeft'].includes(e.key.toLowerCase())) input.left = true;
  if (['d', 'в', 'в', 'ArrowRight'].includes(e.key.toLowerCase())) input.right = true;
});
window.addEventListener('keyup', (e) => {
  if (['w', 'ц', 'ц', 'ArrowUp'].includes(e.key.toLowerCase())) input.forward = false;
  if (['s', 'ы', 'ы', 'ArrowDown'].includes(e.key.toLowerCase())) input.back = false;
  if (['a', 'ф', 'ф', 'ArrowLeft'].includes(e.key.toLowerCase())) input.left = false;
  if (['d', 'в', 'в', 'ArrowRight'].includes(e.key.toLowerCase())) input.right = false;
});

// Mouse drag — поворот камеры (desktop)
let mouseDragging = false;
let lastMouseX = 0, lastMouseY = 0;
canvas.addEventListener('mousedown', (e) => {
  mouseDragging = true;
  lastMouseX = e.clientX;
  lastMouseY = e.clientY;
});
window.addEventListener('mouseup', () => { mouseDragging = false; });
window.addEventListener('mousemove', (e) => {
  if (!mouseDragging) return;
  const dx = e.clientX - lastMouseX;
  const dy = e.clientY - lastMouseY;
  lastMouseX = e.clientX;
  lastMouseY = e.clientY;
  cameraState.yaw -= dx * 0.005;
  cameraState.pitch = Math.max(-1, Math.min(0.3, cameraState.pitch + dy * 0.005));
});

// Touch — левая половина = виртуальный джойстик, правая = камера
const joystickEl = document.getElementById('virtual-joystick');
const joystickKnob = document.getElementById('joystick-knob');
let joystickActive = false;
let joystickCenter = { x: 0, y: 0 };
let joystickTouchId = null;
let lookTouchId = null;
let lastLookX = 0, lastLookY = 0;

function handleTouchStart(e) {
  for (const t of e.changedTouches) {
    if (t.clientX < window.innerWidth / 2) {
      // Левая половина — joystick
      if (joystickActive) continue;
      joystickActive = true;
      joystickTouchId = t.identifier;
      joystickCenter = { x: t.clientX, y: t.clientY };
      joystickEl.style.left = (t.clientX - 60) + 'px';
      joystickEl.style.top = (t.clientY - 60) + 'px';
      joystickEl.classList.add('active');
      joystickKnob.style.transform = 'translate(0, 0)';
    } else {
      // Правая половина — камера
      if (lookTouchId !== null) continue;
      lookTouchId = t.identifier;
      lastLookX = t.clientX;
      lastLookY = t.clientY;
    }
  }
}

function handleTouchMove(e) {
  for (const t of e.changedTouches) {
    if (t.identifier === joystickTouchId) {
      const dx = t.clientX - joystickCenter.x;
      const dy = t.clientY - joystickCenter.y;
      const dist = Math.min(50, Math.sqrt(dx * dx + dy * dy));
      const angle = Math.atan2(dy, dx);
      const knobX = Math.cos(angle) * dist;
      const knobY = Math.sin(angle) * dist;
      joystickKnob.style.transform = `translate(${knobX}px, ${knobY}px)`;
      input.joyX = knobX / 50;
      input.joyY = knobY / 50;
    } else if (t.identifier === lookTouchId) {
      const dx = t.clientX - lastLookX;
      const dy = t.clientY - lastLookY;
      lastLookX = t.clientX;
      lastLookY = t.clientY;
      cameraState.yaw -= dx * 0.008;
      cameraState.pitch = Math.max(-1, Math.min(0.3, cameraState.pitch + dy * 0.008));
    }
  }
}

function handleTouchEnd(e) {
  for (const t of e.changedTouches) {
    if (t.identifier === joystickTouchId) {
      joystickActive = false;
      joystickTouchId = null;
      input.joyX = 0;
      input.joyY = 0;
      joystickEl.classList.remove('active');
    } else if (t.identifier === lookTouchId) {
      lookTouchId = null;
    }
  }
}

window.addEventListener('touchstart', handleTouchStart, { passive: true });
window.addEventListener('touchmove', handleTouchMove, { passive: true });
window.addEventListener('touchend', handleTouchEnd, { passive: true });
window.addEventListener('touchcancel', handleTouchEnd, { passive: true });

// ─── Игровой цикл ────────────────────────────────────────────────────────

function checkObstacleCollision(x, z) {
  for (const o of world.obstacles) {
    if (Math.abs(x - o.x) < o.halfW && Math.abs(z - o.z) < o.halfD) return true;
  }
  return false;
}

function updatePlayer(dt) {
  // Десктоп input → направление
  let dx = 0, dz = 0;
  if (input.forward) dz -= 1;
  if (input.back) dz += 1;
  if (input.left) dx -= 1;
  if (input.right) dx += 1;
  // Touch joystick перебивает (если кто-то на тачскрине)
  if (joystickActive) {
    dx = input.joyX;
    dz = input.joyY;
  }
  const len = Math.sqrt(dx * dx + dz * dz);
  if (len > 0) {
    dx /= len;
    dz /= len;
    // Поворачиваем по yaw камеры — двигаемся относительно того куда смотрим
    const cosY = Math.cos(cameraState.yaw);
    const sinY = Math.sin(cameraState.yaw);
    const worldDx = dx * cosY + dz * sinY;
    const worldDz = -dx * sinY + dz * cosY;
    const speed = 6;
    const newX = playerState.position.x + worldDx * speed * dt;
    const newZ = playerState.position.z + worldDz * speed * dt;
    // Bounding-box + obstacle collision
    if (Math.abs(newX) < world.halfSize - 1 && !checkObstacleCollision(newX, playerState.position.z)) {
      playerState.position.x = newX;
    }
    if (Math.abs(newZ) < world.halfSize - 1 && !checkObstacleCollision(playerState.position.x, newZ)) {
      playerState.position.z = newZ;
    }
    // Поворачиваем модельку по направлению движения (плавно)
    const targetYaw = Math.atan2(worldDx, worldDz);
    let diff = targetYaw - playerState.rotation;
    while (diff > Math.PI) diff -= Math.PI * 2;
    while (diff < -Math.PI) diff += Math.PI * 2;
    playerState.rotation += diff * Math.min(1, dt * 10);
    // Walk-bob — фаза для покачивания корпуса
    playerState.walkPhase += dt * 12;
  } else {
    // Затухание walk-bob
    playerState.walkPhase += dt * 4;
  }

  player.position.set(playerState.position.x, playerState.position.y, playerState.position.z);
  player.rotation.y = playerState.rotation;

  // Walk-bob: лёгкое up-down + покачивание корпуса
  const bobAmt = len > 0 ? 0.08 : 0;
  player.position.y = Math.abs(Math.sin(playerState.walkPhase)) * bobAmt;

  // Покачивание рук
  player.children.forEach((c) => {
    if (c.userData.armSide !== undefined) {
      c.rotation.x = Math.sin(playerState.walkPhase + (c.userData.armSide > 0 ? Math.PI : 0)) * 0.4 * (len > 0 ? 1 : 0);
    }
  });
}

function checkPickups() {
  const px = playerState.position.x;
  const pz = playerState.position.z;
  for (let i = state.pickups.length - 1; i >= 0; i--) {
    const p = state.pickups[i];
    const dx = p.position.x - px;
    const dz = p.position.z - pz;
    const dist2 = dx * dx + dz * dz;
    if (dist2 < 1.4 * 1.4) {
      collectPickup(p);
    }
  }
}

function updatePickups(dt) {
  for (const p of state.pickups) {
    // Floating up-down + spin
    const t = (performance.now() - p.userData.spawnTime) * 0.001;
    p.position.y = p.userData.baseY + Math.sin(t * 2) * 0.15 + 0.5;
    p.rotation.y += dt * 0.8;
    // Billboard всегда смотрит на камеру
    if (p.userData.billboard) {
      p.userData.billboard.lookAt(camera.position);
    }
  }
}

function collectPickup(p) {
  const meme = p.userData.meme;
  state.collected.add(meme.id);
  state.score += meme.points;
  localStorage.setItem('belstroy-collected', JSON.stringify([...state.collected]));
  if (state.score > state.highScore) {
    state.highScore = state.score;
    localStorage.setItem('belstroy-high-score', String(state.highScore));
  }
  // Удалить из сцены
  scene.remove(p);
  state.pickups = state.pickups.filter((x) => x !== p);
  updateScore();
  if (meme.special && meme.id === '67') {
    showSixSeven();
  } else {
    showMemePopup(meme);
  }
}

// ─── UI ──────────────────────────────────────────────────────────────────

const scoreEl = document.getElementById('score');
const collectedEl = document.getElementById('collected');
const hintEl = document.getElementById('hint');
let hintFaded = false;

function updateScore() {
  scoreEl.textContent = state.score;
  if (collectedEl) {
    collectedEl.textContent = `${state.collected.size} / ${MEMES.length}`;
  }
  if (!hintFaded) {
    hintEl.classList.add('fade');
    hintFaded = true;
  }
}
updateScore();

function showMemePopup(meme) {
  const popup = document.getElementById('ach-popup');
  document.getElementById('ach-emoji').textContent = meme.emoji;
  document.getElementById('ach-title').textContent = meme.label;
  document.getElementById('ach-desc').textContent = meme.desc;
  popup.classList.add('show');
  clearTimeout(popup._t);
  popup._t = setTimeout(() => popup.classList.remove('show'), 3000);
}

function showSixSeven() {
  const overlay = document.getElementById('mem-overlay');
  overlay.classList.add('show');
  localStorage.setItem('belstroy-67-shown', '1');
  state.sixSevenShown = true;
}
document.getElementById('mem-close').addEventListener('click', () => {
  document.getElementById('mem-overlay').classList.remove('show');
});

// Share
document.getElementById('share-btn').addEventListener('click', async () => {
  const text =
    `Собрал ${state.collected.size}/${MEMES.length} мемов в Беллстрой ТВ. ` +
    `Sixsevenseven 🤘 Попробуй: https://getdoday.ru/game`;
  const shareData = { title: 'Беллстрой ТВ', text, url: 'https://getdoday.ru/game' };
  if (navigator.share) {
    try { await navigator.share(shareData); return; } catch (e) { /* user cancel */ }
  }
  const tgUrl =
    'https://t.me/share/url?url=' + encodeURIComponent(shareData.url) +
    '&text=' + encodeURIComponent(text);
  window.open(tgUrl, '_blank');
});

// ─── Resize ──────────────────────────────────────────────────────────────

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ─── Main loop ───────────────────────────────────────────────────────────

const clock = new THREE.Clock();
function animate() {
  const dt = Math.min(0.05, clock.getDelta()); // cap dt to avoid teleport on tab-switch

  updatePlayer(dt);
  updatePickups(dt);
  updateCamera();
  checkPickups();

  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();
