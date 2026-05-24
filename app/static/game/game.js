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
  // Группа из 4 частей: body, head, наушники, рот
  const group = new THREE.Group();

  // Body — пурпурный капсуло-куб
  const bodyGeom = new THREE.CylinderGeometry(0.5, 0.7, 1.4, 16);
  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0xa855f7,
    metalness: 0.2,
    roughness: 0.4,
  });
  const body = new THREE.Mesh(bodyGeom, bodyMat);
  body.position.y = 0.7;
  body.castShadow = true;
  group.add(body);

  // Head — sphere с лёгкой деформацией
  const headGeom = new THREE.SphereGeometry(0.55, 32, 32);
  const headMat = new THREE.MeshStandardMaterial({
    color: 0xfbbf24,
    metalness: 0.1,
    roughness: 0.7,
  });
  const head = new THREE.Mesh(headGeom, headMat);
  head.position.y = 1.95;
  head.castShadow = true;
  group.add(head);

  // Глаза — два мелких шарика
  const eyeMat = new THREE.MeshStandardMaterial({ color: 0x0d0820 });
  const eyeGeom = new THREE.SphereGeometry(0.08, 16, 16);
  const eyeL = new THREE.Mesh(eyeGeom, eyeMat);
  eyeL.position.set(-0.18, 2.05, 0.5);
  group.add(eyeL);
  const eyeR = eyeL.clone();
  eyeR.position.x = 0.18;
  group.add(eyeR);

  // Наушники — torus сверху
  const headphoneGeom = new THREE.TorusGeometry(0.6, 0.08, 12, 32, Math.PI);
  const headphoneMat = new THREE.MeshStandardMaterial({
    color: 0x1a0f3d,
    metalness: 0.8,
    roughness: 0.2,
  });
  const headphones = new THREE.Mesh(headphoneGeom, headphoneMat);
  headphones.position.y = 2.05;
  headphones.rotation.z = Math.PI / 2;
  headphones.rotation.x = Math.PI / 2;
  group.add(headphones);

  // Микрофон — маленький cylinder перед лицом
  const micGeom = new THREE.CylinderGeometry(0.05, 0.05, 0.3, 8);
  const micMat = new THREE.MeshStandardMaterial({
    color: 0xef4444,
    metalness: 0.6,
    roughness: 0.3,
  });
  const mic = new THREE.Mesh(micGeom, micMat);
  mic.position.set(0.35, 1.9, 0.5);
  mic.rotation.z = Math.PI / 4;
  group.add(mic);

  // Useful tag for ray-casting
  group.userData = { type: 'character', clickable: true };
  body.userData = head.userData = { ...group.userData };
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
  { score: 10, emoji: '🥥', title: 'Десяточка', desc: '10 кокосов? Только начало' },
  { score: 67, emoji: '🤘', title: 'SIX SEVEN', desc: 'Ты в моменте, бро' },
  { score: 100, emoji: '💯', title: 'Сотка', desc: 'Серьёзный кокосер' },
  { score: 250, emoji: '🔥', title: 'В моменте', desc: 'Стримерский флоу' },
  { score: 500, emoji: '👑', title: 'Кокос-король', desc: 'А Doday уже открывал?' },
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
    `Я набил ${state.score} кокосов в Doday Games. Sixsevenseven 🤘 ` +
    `Попробуй: https://getdoday.ru/game`;
  const shareData = {
    title: 'Кокос Воды',
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
