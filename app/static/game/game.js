/**
 * Беллстрой ТВ — бесконечная аркада.
 *
 * Геймплей:
 * - Ходишь по карте 120×120, прыгаешь (gravity + jump)
 * - Собираешь мемы (+score, popup)
 * - Враги (Italian brainrot) гонятся за тобой:
 *   - Side-collision → -1 HP (3 HP всего)
 *   - Stomp (прыжок сверху) → враг умирает + bonus score
 * - Каждые 25 сек спавн новой волны врагов, +1 враг каждая волна
 * - После сбора всех мемов — респаун + повторение бесконечно
 * - HP = 0 → game over → restart с волны 1
 */

import * as THREE from 'three';
import { buildWorld, HALF_WORLD } from './modules/world.js';
import { createPlayer } from './modules/player.js';
import { Enemy, getEnemyTypes, getEnemyDisplay } from './modules/enemies.js';
import { MEMES, spawnPickups, updatePickups } from './modules/pickups.js';

// ─── State ───────────────────────────────────────────────────────────────

const state = {
  score: 0,
  collected: 0,
  wave: 0,
  pickups: [],
  enemies: [],
  highScore: parseInt(localStorage.getItem('belstroy-high-score-v2') || '0', 10),
  bestWave: parseInt(localStorage.getItem('belstroy-best-wave') || '0', 10),
  paused: false,
  gameOver: false,
};

// ─── Three.js ────────────────────────────────────────────────────────────

const canvas = document.getElementById('game-canvas');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
renderer.toneMapping = THREE.ACESFilmicToneMapping;
renderer.toneMappingExposure = 1.1;

const scene = new THREE.Scene();
const world = buildWorld(scene);

const camera = new THREE.PerspectiveCamera(
  65,
  window.innerWidth / window.innerHeight,
  0.1,
  300
);
const cameraState = { yaw: 0, pitch: -0.25, distance: 8 };

// ─── Player ──────────────────────────────────────────────────────────────

const player = createPlayer();
scene.add(player.mesh);

// ─── Pickups ─────────────────────────────────────────────────────────────

state.pickups = spawnPickups(scene, HALF_WORLD);

// ─── Input ───────────────────────────────────────────────────────────────

const input = {
  forward: false, back: false, left: false, right: false,
  joyX: 0, joyY: 0, joystickActive: false,
  jumpPressed: false,
};

window.addEventListener('keydown', (e) => {
  const k = e.key.toLowerCase();
  if (['w', 'ц', 'arrowup'].includes(k)) input.forward = true;
  if (['s', 'ы', 'arrowdown'].includes(k)) input.back = true;
  if (['a', 'ф', 'arrowleft'].includes(k)) input.left = true;
  if (['d', 'в', 'arrowright'].includes(k)) input.right = true;
  if (k === ' ' || k === 'spacebar') {
    e.preventDefault();
    input.jumpPressed = true;
    player.jump();
  }
  if (k === 'r' && state.gameOver) restartGame();
});
window.addEventListener('keyup', (e) => {
  const k = e.key.toLowerCase();
  if (['w', 'ц', 'arrowup'].includes(k)) input.forward = false;
  if (['s', 'ы', 'arrowdown'].includes(k)) input.back = false;
  if (['a', 'ф', 'arrowleft'].includes(k)) input.left = false;
  if (['d', 'в', 'arrowright'].includes(k)) input.right = false;
  if (k === ' ') input.jumpPressed = false;
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
  cameraState.pitch = Math.max(-1.1, Math.min(0.3, cameraState.pitch + dy * 0.005));
});

// Touch: left half = joystick, right half = camera. Tap on jump button = jump.
const joystickEl = document.getElementById('virtual-joystick');
const joystickKnob = document.getElementById('joystick-knob');
const jumpBtn = document.getElementById('jump-btn');
let joystickTouchId = null;
let lookTouchId = null;
let joystickCenter = { x: 0, y: 0 };
let lastLookX = 0, lastLookY = 0;

function isJumpButton(target) {
  return target && (target === jumpBtn || target.closest?.('#jump-btn'));
}

function handleTouchStart(e) {
  for (const t of e.changedTouches) {
    if (isJumpButton(t.target)) {
      player.jump();
      continue;
    }
    if (t.clientX < window.innerWidth / 2) {
      if (joystickTouchId !== null) continue;
      joystickTouchId = t.identifier;
      joystickCenter = { x: t.clientX, y: t.clientY };
      joystickEl.style.left = (t.clientX - 60) + 'px';
      joystickEl.style.top = (t.clientY - 60) + 'px';
      joystickEl.classList.add('active');
      joystickKnob.style.transform = 'translate(0, 0)';
      input.joystickActive = true;
    } else {
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
      cameraState.pitch = Math.max(-1.1, Math.min(0.3, cameraState.pitch + dy * 0.008));
    }
  }
}

function handleTouchEnd(e) {
  for (const t of e.changedTouches) {
    if (t.identifier === joystickTouchId) {
      joystickTouchId = null;
      input.joyX = 0;
      input.joyY = 0;
      input.joystickActive = false;
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

// ─── Camera ──────────────────────────────────────────────────────────────

function updateCamera() {
  const offsetX = Math.sin(cameraState.yaw) * Math.cos(cameraState.pitch) * cameraState.distance;
  const offsetY = -Math.sin(cameraState.pitch) * cameraState.distance + 3;
  const offsetZ = Math.cos(cameraState.yaw) * Math.cos(cameraState.pitch) * cameraState.distance;
  camera.position.set(
    player.position.x + offsetX,
    player.position.y + offsetY,
    player.position.z + offsetZ
  );
  camera.lookAt(
    player.position.x,
    player.position.y + 1.5,
    player.position.z
  );
}

// ─── Wave system ─────────────────────────────────────────────────────────

let waveStartTime = performance.now();
let nextWaveAt = 0;
const WAVE_INTERVAL = 25000;  // 25 сек между волнами

function startNextWave() {
  state.wave += 1;
  // Кол-во врагов в волне: 2 + wave/2
  const enemyCount = Math.min(20, 2 + Math.floor(state.wave * 0.7));
  const enemyTypes = getEnemyTypes();
  for (let i = 0; i < enemyCount; i++) {
    const type = enemyTypes[Math.floor(Math.random() * enemyTypes.length)];
    // Spawn на краю карты, далеко от игрока
    const angle = Math.random() * Math.PI * 2;
    const dist = HALF_WORLD - 5 - Math.random() * 10;
    const pos = new THREE.Vector3(
      player.position.x + Math.cos(angle) * dist * (Math.random() > 0.5 ? 1 : -1),
      0,
      player.position.z + Math.sin(angle) * dist * (Math.random() > 0.5 ? 1 : -1)
    );
    pos.x = Math.max(-HALF_WORLD + 3, Math.min(HALF_WORLD - 3, pos.x));
    pos.z = Math.max(-HALF_WORLD + 3, Math.min(HALF_WORLD - 3, pos.z));
    const enemy = new Enemy(type, pos);
    scene.add(enemy.mesh);
    state.enemies.push(enemy);
  }
  if (state.wave > state.bestWave) {
    state.bestWave = state.wave;
    localStorage.setItem('belstroy-best-wave', String(state.wave));
  }
  nextWaveAt = performance.now() + WAVE_INTERVAL;
  flashWaveBanner();
}

function flashWaveBanner() {
  const banner = document.getElementById('wave-banner');
  banner.textContent = `🌊 Волна ${state.wave}`;
  banner.classList.add('show');
  clearTimeout(banner._t);
  banner._t = setTimeout(() => banner.classList.remove('show'), 2500);
}

// First wave starts after a small delay
setTimeout(startNextWave, 4000);

// ─── Game loop ───────────────────────────────────────────────────────────

function checkPickupCollisions() {
  const px = player.position.x;
  const pz = player.position.z;
  for (let i = state.pickups.length - 1; i >= 0; i--) {
    const p = state.pickups[i];
    const dx = p.position.x - px;
    const dz = p.position.z - pz;
    if (dx * dx + dz * dz < 1.6 * 1.6) {
      collectPickup(p, i);
    }
  }
  if (state.pickups.length === 0) {
    // Respawn все мемы (бесконечный цикл)
    state.pickups = spawnPickups(scene, HALF_WORLD);
  }
}

function collectPickup(p, idx) {
  const meme = p.userData.meme;
  state.score += meme.points;
  state.collected += 1;
  scene.remove(p);
  state.pickups.splice(idx, 1);
  updateHud();
  if (meme.special && meme.id === '67') {
    showSixSeven();
  } else {
    showMemePopup(meme);
  }
}

function checkEnemyCollisions() {
  for (let i = state.enemies.length - 1; i >= 0; i--) {
    const e = state.enemies[i];
    const result = e.checkCollision(player.position, player.velocity.y);
    if (result === 'stomp') {
      state.score += 50 * state.wave;  // награда растёт с волной
      showEnemyKilled(e);
      // Маленький отскок вверх после stomp
      player.velocity.y = 6;
      updateHud();
    } else if (result === 'hit') {
      if (player.takeDamage()) {
        // успешно нанесли урон
        updateHud();
        cameraShake(0.4);
        if (!player.alive) {
          triggerGameOver();
        }
      }
    }
  }
}

let cameraShakeAmt = 0;
function cameraShake(amt) { cameraShakeAmt = Math.max(cameraShakeAmt, amt); }
function applyCameraShake() {
  if (cameraShakeAmt > 0.01) {
    camera.position.x += (Math.random() - 0.5) * cameraShakeAmt;
    camera.position.y += (Math.random() - 0.5) * cameraShakeAmt;
    cameraShakeAmt *= 0.85;
  }
}

function triggerGameOver() {
  state.gameOver = true;
  if (state.score > state.highScore) {
    state.highScore = state.score;
    localStorage.setItem('belstroy-high-score-v2', String(state.score));
  }
  const overlay = document.getElementById('gameover-overlay');
  document.getElementById('gameover-score').textContent = state.score;
  document.getElementById('gameover-wave').textContent = state.wave;
  document.getElementById('gameover-collected').textContent = state.collected;
  document.getElementById('gameover-best-score').textContent = state.highScore;
  document.getElementById('gameover-best-wave').textContent = state.bestWave;
  overlay.classList.add('show');
}

function restartGame() {
  // Сбросить state
  state.score = 0;
  state.collected = 0;
  state.wave = 0;
  state.gameOver = false;
  // Убрать всех врагов
  for (const e of state.enemies) scene.remove(e.mesh);
  state.enemies = [];
  // Респаунить мемы
  for (const p of state.pickups) scene.remove(p);
  state.pickups = spawnPickups(scene, HALF_WORLD);
  // Сбросить игрока
  player.reset();
  // Скрыть game-over overlay
  document.getElementById('gameover-overlay').classList.remove('show');
  // Запланировать первую волну
  setTimeout(startNextWave, 4000);
  updateHud();
}

document.getElementById('restart-btn').addEventListener('click', restartGame);

// ─── UI ──────────────────────────────────────────────────────────────────

const scoreEl = document.getElementById('score');
const waveEl = document.getElementById('wave');
const hpEl = document.getElementById('hp');
const collectedEl = document.getElementById('collected');
const hintEl = document.getElementById('hint');
let hintFaded = false;

function updateHud() {
  scoreEl.textContent = state.score;
  if (waveEl) waveEl.textContent = state.wave;
  if (collectedEl) collectedEl.textContent = state.collected;
  if (hpEl) {
    const hearts = '❤️'.repeat(player.hp) + '🖤'.repeat(player.maxHp - player.hp);
    hpEl.textContent = hearts;
  }
  if (!hintFaded) {
    hintEl.classList.add('fade');
    hintFaded = true;
  }
}
updateHud();

function showMemePopup(meme) {
  const popup = document.getElementById('ach-popup');
  document.getElementById('ach-emoji').textContent = meme.emoji;
  document.getElementById('ach-title').textContent = meme.label;
  document.getElementById('ach-desc').textContent = meme.desc;
  popup.classList.add('show');
  clearTimeout(popup._t);
  popup._t = setTimeout(() => popup.classList.remove('show'), 2500);
}

function showEnemyKilled(enemy) {
  const popup = document.getElementById('ach-popup');
  const info = getEnemyDisplay(enemy.type);
  document.getElementById('ach-emoji').textContent = '💥';
  document.getElementById('ach-title').textContent = `${info.name} stomped!`;
  document.getElementById('ach-desc').textContent = `+${50 * state.wave} очков`;
  popup.classList.add('show');
  clearTimeout(popup._t);
  popup._t = setTimeout(() => popup.classList.remove('show'), 2000);
}

function showSixSeven() {
  document.getElementById('mem-overlay').classList.add('show');
}
document.getElementById('mem-close').addEventListener('click', () => {
  document.getElementById('mem-overlay').classList.remove('show');
});

document.getElementById('share-btn').addEventListener('click', async () => {
  const text =
    `Беллстрой ТВ: волна ${state.wave}, score ${state.score}. ` +
    `Sixsevenseven 🤘 https://getdoday.ru/game`;
  const shareData = { title: 'Беллстрой ТВ', text, url: 'https://getdoday.ru/game' };
  if (navigator.share) {
    try { await navigator.share(shareData); return; } catch (e) { /* user cancel */ }
  }
  window.open('https://t.me/share/url?url=' + encodeURIComponent(shareData.url) +
    '&text=' + encodeURIComponent(text), '_blank');
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
  const dt = Math.min(0.05, clock.getDelta());

  if (!state.gameOver) {
    player.update(dt, input, cameraState.yaw, world);

    // Update enemies
    for (let i = state.enemies.length - 1; i >= 0; i--) {
      const e = state.enemies[i];
      const result = e.update(dt, player.position, player.position.y);
      if (result === 'remove') {
        scene.remove(e.mesh);
        state.enemies.splice(i, 1);
      }
    }

    updatePickups(state.pickups, dt, camera.position);
    checkPickupCollisions();
    checkEnemyCollisions();

    // Wave timer
    if (performance.now() > nextWaveAt) {
      startNextWave();
    }
  }

  updateCamera();
  applyCameraShake();

  // Прокрутка пропеллеров у Bombardiro
  state.enemies.forEach((e) => {
    e.mesh.traverse((c) => {
      if (c.userData?.spinning) c.rotation.x += dt * 30;
    });
  });

  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}
animate();
