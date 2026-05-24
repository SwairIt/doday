/**
 * Кокос Воды — мем-кликер на Three.js
 *
 * Архитектура:
 * - Один canvas, одна Three.Scene
 * - В центре — character (procedural placeholder; заменишь на .glb от Tripo3D)
 * - С неба падают coconuts (3D sphere)
 * - Тап по character → +1, маленькая анимация прыжка, particle с надписью «+1»
 * - Тап по coconut (ray-cast) → +5, coconut splash-distroy
 * - При score === 67 → fullscreen-overlay «67 SIX SEVEN»
 * - Прогресс сохраняется в localStorage между сессиями
 *
 * Когда у тебя будут .glb-модели от Tripo3D — найди функцию `loadCharacter()`
 * и подмени procedural-куб на GLTFLoader. Loader уже импортнут.
 */

import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

// ─── Глобал состояние ─────────────────────────────────────────────────────

const state = {
  score: 0,
  highScore: parseInt(localStorage.getItem('kokos-high-score') || '0', 10),
  unlockedAchievements: new Set(
    JSON.parse(localStorage.getItem('kokos-achievements') || '[]')
  ),
  sixSevenShown: localStorage.getItem('kokos-67-shown') === '1',
  coconuts: [],
  character: null,
  characterBaseY: 0,
};

// ─── Three.js scene ───────────────────────────────────────────────────────

const canvas = document.getElementById('game-canvas');
const renderer = new THREE.WebGLRenderer({
  canvas,
  antialias: true,
  alpha: true,
});
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;

const scene = new THREE.Scene();
scene.fog = new THREE.Fog(0x1a0f3d, 12, 28);

const camera = new THREE.PerspectiveCamera(
  60,
  window.innerWidth / window.innerHeight,
  0.1,
  100
);
camera.position.set(0, 3, 7);
camera.lookAt(0, 1, 0);

// Освещение — фиолетовый rim light для стримерского fil
const ambient = new THREE.AmbientLight(0x6d28d9, 0.5);
scene.add(ambient);

const keyLight = new THREE.DirectionalLight(0xffffff, 1.2);
keyLight.position.set(5, 8, 5);
keyLight.castShadow = true;
keyLight.shadow.mapSize.set(1024, 1024);
keyLight.shadow.camera.left = -10;
keyLight.shadow.camera.right = 10;
keyLight.shadow.camera.top = 10;
keyLight.shadow.camera.bottom = -10;
scene.add(keyLight);

const rimLight = new THREE.DirectionalLight(0xd946ef, 0.8);
rimLight.position.set(-5, 3, -5);
scene.add(rimLight);

// Пол — стилизованная фиолетовая «сцена» с лёгкой подсветкой по краям
const groundGeom = new THREE.CircleGeometry(8, 32);
const groundMat = new THREE.MeshStandardMaterial({
  color: 0x2e1065,
  metalness: 0.3,
  roughness: 0.6,
});
const ground = new THREE.Mesh(groundGeom, groundMat);
ground.rotation.x = -Math.PI / 2;
ground.position.y = 0;
ground.receiveShadow = true;
scene.add(ground);

// Подложка с rgb-свечением по периметру (просто кольцо)
const ringGeom = new THREE.RingGeometry(7.8, 8.2, 64);
const ringMat = new THREE.MeshBasicMaterial({
  color: 0xd946ef,
  side: THREE.DoubleSide,
});
const ring = new THREE.Mesh(ringGeom, ringMat);
ring.rotation.x = -Math.PI / 2;
ring.position.y = 0.01;
scene.add(ring);

// ─── Character (procedural placeholder — заменится на .glb от Tripo3D) ─

function makeProceduralCharacter() {
  // Беллстрой — stylized мем-стример. Атрибуты, узнаваемые как «жанр»:
  // блонд-волосы, кепка задом-наперёд, чёрная футболка, лёгкая ухмылка.
  // Никакого конкретного сходства — generic-vibe пародия.
  const group = new THREE.Group();

  // ─── Тело: чёрная футболка ───────────────────────────────────────
  const bodyGeom = new THREE.CylinderGeometry(0.55, 0.65, 1.3, 16);
  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x0d0d0d,
    metalness: 0.1,
    roughness: 0.85,
  });
  const body = new THREE.Mesh(bodyGeom, bodyMat);
  body.position.y = 0.65;
  body.castShadow = true;
  group.add(body);

  // Принт на футболке — белый «B» (chest emblem)
  const emblemCanvas = document.createElement('canvas');
  emblemCanvas.width = 128;
  emblemCanvas.height = 128;
  const ctx = emblemCanvas.getContext('2d');
  ctx.fillStyle = 'rgba(0,0,0,0)';
  ctx.fillRect(0, 0, 128, 128);
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

  // ─── Шея ─────────────────────────────────────────────────────────
  const neckGeom = new THREE.CylinderGeometry(0.18, 0.22, 0.2, 12);
  const skinMat = new THREE.MeshStandardMaterial({
    color: 0xffd4a8,
    metalness: 0.0,
    roughness: 0.6,
  });
  const neck = new THREE.Mesh(neckGeom, skinMat);
  neck.position.y = 1.4;
  neck.castShadow = true;
  group.add(neck);

  // ─── Голова: лицо ────────────────────────────────────────────────
  const headGeom = new THREE.SphereGeometry(0.45, 32, 32);
  const head = new THREE.Mesh(headGeom, skinMat);
  head.position.y = 1.85;
  head.castShadow = true;
  // Слегка сплющим голову для cartoon-эффекта
  head.scale.y = 1.05;
  group.add(head);

  // ─── Блонд-волосы по бокам (выглядывают из-под кепки) ────────────
  const hairMat = new THREE.MeshStandardMaterial({
    color: 0xead49a,
    metalness: 0.0,
    roughness: 0.85,
  });
  // Чёлка — несколько hair-tufts из-под козырька
  for (let i = -2; i <= 2; i++) {
    const tuftGeom = new THREE.ConeGeometry(0.06, 0.18, 6);
    const tuft = new THREE.Mesh(tuftGeom, hairMat);
    tuft.position.set(i * 0.08, 2.05, 0.4);
    tuft.rotation.x = -Math.PI / 6;
    tuft.rotation.z = i * 0.1;
    group.add(tuft);
  }
  // Боковые волосы за ушами
  const sideHairGeom = new THREE.SphereGeometry(0.12, 12, 12);
  const sideHairL = new THREE.Mesh(sideHairGeom, hairMat);
  sideHairL.position.set(-0.42, 1.75, 0.1);
  sideHairL.scale.set(0.5, 1, 0.7);
  group.add(sideHairL);
  const sideHairR = sideHairL.clone();
  sideHairR.position.x = 0.42;
  group.add(sideHairR);

  // ─── Глаза (мелкие, прищур) ──────────────────────────────────────
  const eyeWhite = new THREE.MeshStandardMaterial({ color: 0xffffff });
  const eyePupil = new THREE.MeshStandardMaterial({ color: 0x1a4080 });

  for (const xSign of [-1, 1]) {
    const whiteGeom = new THREE.SphereGeometry(0.07, 16, 16);
    const white = new THREE.Mesh(whiteGeom, eyeWhite);
    white.position.set(0.16 * xSign, 1.92, 0.4);
    white.scale.y = 0.6; // прищур
    group.add(white);

    const pupilGeom = new THREE.SphereGeometry(0.035, 12, 12);
    const pupil = new THREE.Mesh(pupilGeom, eyePupil);
    pupil.position.set(0.16 * xSign, 1.92, 0.45);
    group.add(pupil);
  }

  // ─── Брови (наклонены чтоб была ухмылка-attitude) ────────────────
  const browMat = new THREE.MeshStandardMaterial({ color: 0xc8a070 });
  for (const xSign of [-1, 1]) {
    const browGeom = new THREE.BoxGeometry(0.12, 0.025, 0.025);
    const brow = new THREE.Mesh(browGeom, browMat);
    brow.position.set(0.17 * xSign, 2.01, 0.42);
    brow.rotation.z = -xSign * 0.15;
    group.add(brow);
  }

  // ─── Ухмылка ─────────────────────────────────────────────────────
  // Простая дуга — линия mesh из BoxGeometry в полусогнутом виде
  const smileMat = new THREE.MeshStandardMaterial({ color: 0x802020 });
  const smileGeom = new THREE.TorusGeometry(0.12, 0.018, 8, 16, Math.PI * 0.7);
  const smile = new THREE.Mesh(smileGeom, smileMat);
  smile.position.set(0.02, 1.74, 0.43);
  smile.rotation.z = -0.25;
  smile.rotation.x = Math.PI;
  group.add(smile);

  // ─── Кепка задом-наперёд: купол + сзади-козырёк ──────────────────
  const capMat = new THREE.MeshStandardMaterial({
    color: 0x141414,
    metalness: 0.2,
    roughness: 0.7,
  });

  // Купол кепки — полусфера сверху головы
  const capCrownGeom = new THREE.SphereGeometry(
    0.5,
    32,
    32,
    0,
    Math.PI * 2,
    0,
    Math.PI / 2
  );
  const capCrown = new THREE.Mesh(capCrownGeom, capMat);
  capCrown.position.y = 2.1;
  capCrown.castShadow = true;
  group.add(capCrown);

  // Полоска вокруг (snapback band)
  const bandGeom = new THREE.CylinderGeometry(0.5, 0.5, 0.08, 32, 1, true);
  const band = new THREE.Mesh(bandGeom, capMat);
  band.position.y = 2.08;
  group.add(band);

  // Козырёк ЗАДОМ-наперёд (значит торчит на спине, не на лице)
  const visorGeom = new THREE.BoxGeometry(0.5, 0.04, 0.35);
  const visor = new THREE.Mesh(visorGeom, capMat);
  visor.position.set(0, 2.05, -0.45);
  visor.rotation.x = -0.12;
  visor.castShadow = true;
  group.add(visor);

  // Белый «logo-patch» на лбу — типичный snapback sticker
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
  logoPatch.rotation.y = Math.PI; // обратной стороной — задом-наперёд
  group.add(logoPatch);

  // ─── Уши ─────────────────────────────────────────────────────────
  const earGeom = new THREE.SphereGeometry(0.08, 12, 12);
  for (const xSign of [-1, 1]) {
    const ear = new THREE.Mesh(earGeom, skinMat);
    ear.position.set(0.42 * xSign, 1.85, 0);
    ear.scale.set(0.6, 1, 0.4);
    group.add(ear);
  }

  // ─── Руки — palki вдоль тела ─────────────────────────────────────
  const armGeom = new THREE.CylinderGeometry(0.12, 0.1, 0.9, 12);
  for (const xSign of [-1, 1]) {
    const arm = new THREE.Mesh(armGeom, bodyMat);
    arm.position.set(0.58 * xSign, 0.9, 0);
    arm.rotation.z = -xSign * 0.15;
    arm.castShadow = true;
    group.add(arm);

    // Кисть руки
    const hand = new THREE.Mesh(new THREE.SphereGeometry(0.12, 12, 12), skinMat);
    hand.position.set(0.7 * xSign, 0.4, 0);
    group.add(hand);
  }

  // ─── Tag for ray-casting ─────────────────────────────────────────
  group.userData = { type: 'character', clickable: true };
  group.traverse((n) => {
    if (n.isMesh) {
      n.userData = { type: 'character', clickable: true };
    }
  });
  return group;
}

function loadCharacter() {
  // Если есть /static/game/models/character.glb — грузим из Tripo3D.
  // Иначе — используем procedural placeholder.
  const url = '/static/game/models/character.glb';
  const loader = new GLTFLoader();

  // Optimistic GET — если 404, fall back к процедурной модели.
  fetch(url, { method: 'HEAD' })
    .then((r) => {
      if (!r.ok) throw new Error('no model');
      loader.load(url, (gltf) => {
        const char = gltf.scene;
        char.scale.set(1.5, 1.5, 1.5);
        char.position.y = 0;
        char.traverse((node) => {
          if (node.isMesh) {
            node.castShadow = true;
            node.userData.clickable = true;
            node.userData.type = 'character';
          }
        });
        // Снимаем старый character (placeholder) если есть
        if (state.character) scene.remove(state.character);
        state.character = char;
        state.characterBaseY = char.position.y;
        scene.add(char);
      });
    })
    .catch(() => {
      // Procedural fallback — placeholder пока ты не сгенерил Tripo3D
      const placeholder = makeProceduralCharacter();
      state.character = placeholder;
      state.characterBaseY = placeholder.position.y;
      scene.add(placeholder);
    });
}

loadCharacter();

// ─── Coconuts — падают сверху, кликабельны ────────────────────────────────

function spawnCoconut() {
  const geom = new THREE.SphereGeometry(0.35, 16, 16);
  const mat = new THREE.MeshStandardMaterial({
    color: 0x8b4513,
    metalness: 0.1,
    roughness: 0.9,
    bumpScale: 0.1,
  });
  const coconut = new THREE.Mesh(geom, mat);
  // Случайное X в пределах сцены, начальная Y высоко
  const x = (Math.random() - 0.5) * 8;
  coconut.position.set(x, 10, 0);
  coconut.castShadow = true;
  coconut.userData = {
    type: 'coconut',
    clickable: true,
    velocityY: -0.04 - Math.random() * 0.04,
    rotationSpeed: (Math.random() - 0.5) * 0.05,
  };
  scene.add(coconut);
  state.coconuts.push(coconut);
}

// Спавним один кокос каждые 1.5-3 сек
function scheduleNextCoconut() {
  const delay = 1500 + Math.random() * 1500;
  setTimeout(() => {
    spawnCoconut();
    scheduleNextCoconut();
  }, delay);
}
scheduleNextCoconut();

// ─── Click / tap handling — raycaster ─────────────────────────────────────

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();

function onPointerDown(event) {
  // Touch / mouse-uni: достаём координаты клика в NDC
  const x = event.touches ? event.touches[0].clientX : event.clientX;
  const y = event.touches ? event.touches[0].clientY : event.clientY;
  pointer.x = (x / window.innerWidth) * 2 - 1;
  pointer.y = -(y / window.innerHeight) * 2 + 1;

  raycaster.setFromCamera(pointer, camera);

  // Все «кликабельные» объекты на сцене
  const clickables = [];
  if (state.character) {
    state.character.traverse((n) => {
      if (n.isMesh && n.userData.clickable) clickables.push(n);
    });
  }
  state.coconuts.forEach((c) => clickables.push(c));

  const hits = raycaster.intersectObjects(clickables, false);
  if (hits.length === 0) return;

  const hit = hits[0].object;
  // Поднимаемся к родителю который маркирован тип
  let typeNode = hit;
  while (typeNode && !typeNode.userData.type) typeNode = typeNode.parent;
  const type = typeNode && typeNode.userData.type;

  if (type === 'character') {
    handleCharacterClick(x, y);
  } else if (type === 'coconut') {
    handleCoconutClick(hit, x, y);
  }
}

canvas.addEventListener('pointerdown', onPointerDown);
canvas.addEventListener('touchstart', onPointerDown, { passive: true });

// ─── Click effects ────────────────────────────────────────────────────────

function handleCharacterClick(screenX, screenY) {
  state.score += 1;
  updateScore();
  spawnParticle(screenX, screenY, '+1', '#fbbf24');
  bumpCharacter();
  checkAchievements();
}

function handleCoconutClick(coconut, screenX, screenY) {
  state.score += 5;
  updateScore();
  spawnParticle(screenX, screenY, '+5 🥥', '#10b981');
  scene.remove(coconut);
  state.coconuts = state.coconuts.filter((c) => c !== coconut);
  checkAchievements();
}

function spawnParticle(x, y, text, color) {
  const el = document.createElement('div');
  el.className = 'particle';
  el.textContent = text;
  el.style.left = x + 'px';
  el.style.top = y + 'px';
  el.style.color = color;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), 1000);
}

function bumpCharacter() {
  if (!state.character) return;
  // Быстрый прыжок вверх и обратно
  const start = performance.now();
  const duration = 250;
  function frame() {
    const t = (performance.now() - start) / duration;
    if (t >= 1) {
      state.character.position.y = state.characterBaseY;
      state.character.scale.set(1, 1, 1);
      return;
    }
    // ease-out параболой
    const k = Math.sin(t * Math.PI);
    state.character.position.y = state.characterBaseY + k * 0.4;
    state.character.scale.set(1 + k * 0.1, 1 - k * 0.05, 1 + k * 0.1);
    requestAnimationFrame(frame);
  }
  frame();
}

// ─── Score / achievements ─────────────────────────────────────────────────

const scoreEl = document.getElementById('score');
const hintEl = document.getElementById('hint');
let hintFaded = false;

function updateScore() {
  scoreEl.textContent = state.score;
  if (state.score > state.highScore) {
    state.highScore = state.score;
    localStorage.setItem('kokos-high-score', String(state.highScore));
  }
  if (!hintFaded) {
    hintEl.classList.add('fade');
    hintFaded = true;
  }
}

const ACHIEVEMENTS = [
  { score: 10, emoji: '🥥', title: 'Кокос воды', desc: 'Беллстрой одобрил твой стрим' },
  { score: 67, emoji: '🤘', title: 'SIX SEVEN', desc: 'Ты в моменте, бро' },
  { score: 100, emoji: '💯', title: 'Сотка', desc: 'Серьёзный кокосер' },
  { score: 250, emoji: '🔥', title: 'В моменте', desc: 'Стримерский флоу' },
  { score: 500, emoji: '👑', title: 'Король стрима', desc: 'А Doday уже открывал?' },
];

function checkAchievements() {
  for (const a of ACHIEVEMENTS) {
    if (state.score >= a.score && !state.unlockedAchievements.has(a.score)) {
      state.unlockedAchievements.add(a.score);
      localStorage.setItem(
        'kokos-achievements',
        JSON.stringify([...state.unlockedAchievements])
      );
      if (a.score === 67) showSixSeven();
      else showAchievement(a);
    }
  }
}

function showAchievement(a) {
  const popup = document.getElementById('ach-popup');
  document.getElementById('ach-emoji').textContent = a.emoji;
  document.getElementById('ach-title').textContent = a.title;
  document.getElementById('ach-desc').textContent = a.desc;
  popup.classList.add('show');
  setTimeout(() => popup.classList.remove('show'), 3500);
}

function showSixSeven() {
  const overlay = document.getElementById('mem-overlay');
  overlay.classList.add('show');
  localStorage.setItem('kokos-67-shown', '1');
  state.sixSevenShown = true;
}
document.getElementById('mem-close').addEventListener('click', () => {
  document.getElementById('mem-overlay').classList.remove('show');
});

// ─── Share button — Web Share API + Telegram fallback ────────────────────

document.getElementById('share-btn').addEventListener('click', async () => {
  const text =
    `Я набил ${state.score} кокосов в Беллстрой ТВ. Sixsevenseven 🤘 ` +
    `Попробуй: https://getdoday.ru/game`;
  const shareData = {
    title: 'Беллстрой ТВ',
    text,
    url: 'https://getdoday.ru/game',
  };
  if (navigator.share) {
    try { await navigator.share(shareData); return; } catch (e) { /* user cancel */ }
  }
  // Fallback — Telegram share
  const tgUrl =
    'https://t.me/share/url?url=' +
    encodeURIComponent(shareData.url) +
    '&text=' +
    encodeURIComponent(text);
  window.open(tgUrl, '_blank');
});

// ─── Resize ───────────────────────────────────────────────────────────────

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

// ─── Main loop ────────────────────────────────────────────────────────────

const clock = new THREE.Clock();
function animate() {
  const dt = clock.getDelta();

  // Лёгкое idle-покачивание персонажа
  if (state.character) {
    state.character.rotation.y = Math.sin(performance.now() * 0.001) * 0.15;
  }

  // Падение кокосов
  for (let i = state.coconuts.length - 1; i >= 0; i--) {
    const c = state.coconuts[i];
    c.position.y += c.userData.velocityY;
    c.rotation.x += c.userData.rotationSpeed;
    c.rotation.z += c.userData.rotationSpeed;
    // Долетел до земли — убираем (без очков)
    if (c.position.y < 0) {
      scene.remove(c);
      state.coconuts.splice(i, 1);
    }
  }

  // Пульсация ring'а — RGB-стиль
  ring.material.color.setHSL(
    (performance.now() * 0.0003) % 1,
    0.7,
    0.6
  );

  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();
