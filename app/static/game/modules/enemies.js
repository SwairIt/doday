/**
 * Italian Brainrot враги — procedural-модели в Three.js.
 *
 * 5 типов:
 *   - Tralalero Tralala — акула в синих кроссовках Nike (3 ноги)
 *   - Bombardiro Crocodilo — крокодил-самолёт-бомбардировщик
 *   - Tung Tung Tung Sahur — деревянный человечек с битой
 *   - Brr Brr Patapim — обезьяна-лес (тело-куст с лицом)
 *   - Lirili Larila — кактус-слон с часами
 *
 * AI: chase-player, при коллизии — наносят урон, при stomp сверху — умирают.
 */
import * as THREE from 'three';

const ENEMY_TYPES = ['tralalero', 'bombardiro', 'tung', 'patapim', 'lirili'];

export class Enemy {
  constructor(type, position) {
    this.type = type;
    this.position = position.clone();
    this.velocity = new THREE.Vector3();
    this.mesh = makeMeshFor(type);
    this.mesh.position.copy(position);
    this.alive = true;
    this.speed = enemySpeed(type);
    this.hitRadius = 1.0;
    this.killRadius = 1.4;
    this.deathTime = null;
    this.bobPhase = Math.random() * Math.PI * 2;
  }

  update(dt, playerPos, playerY) {
    if (!this.alive) {
      // Death animation — falls down + spins out then fades
      this.position.y -= dt * 4;
      this.mesh.rotation.x += dt * 6;
      this.mesh.rotation.z += dt * 4;
      this.mesh.position.copy(this.position);
      this.mesh.scale.multiplyScalar(1 - dt * 1.5);
      if (this.mesh.scale.x < 0.05) return 'remove';
      return null;
    }

    // Chase player (XZ only)
    const dx = playerPos.x - this.position.x;
    const dz = playerPos.z - this.position.z;
    const dist = Math.sqrt(dx * dx + dz * dz);
    if (dist > 0.1) {
      this.position.x += (dx / dist) * this.speed * dt;
      this.position.z += (dz / dist) * this.speed * dt;
      // Face player
      this.mesh.rotation.y = Math.atan2(dx, dz);
    }
    // Idle bob
    this.bobPhase += dt * 6;
    const bob = Math.sin(this.bobPhase) * 0.15;
    this.mesh.position.set(this.position.x, this.position.y + bob + 0.5, this.position.z);

    return null;
  }

  // Returns 'stomp' if player landed on top (kill enemy), 'hit' if side-collision (damage player), null otherwise.
  checkCollision(playerPos, playerVelocityY) {
    if (!this.alive) return null;
    const dx = playerPos.x - this.position.x;
    const dz = playerPos.z - this.position.z;
    const dist2 = dx * dx + dz * dz;
    if (dist2 > this.killRadius * this.killRadius) return null;
    // Stomp: player above + falling
    if (playerPos.y > 1.0 && playerVelocityY < -1) {
      this.alive = false;
      this.deathTime = performance.now();
      return 'stomp';
    }
    // Side collision
    if (dist2 < this.hitRadius * this.hitRadius) {
      return 'hit';
    }
    return null;
  }
}

export function getEnemyTypes() { return [...ENEMY_TYPES]; }

export function getEnemyDisplay(type) {
  return ENEMY_INFO[type] || { name: type, desc: '' };
}

const ENEMY_INFO = {
  tralalero: { name: 'Tralalero Tralala', desc: 'Акула в синих Nike. Tralalero tralala porco dio.' },
  bombardiro: { name: 'Bombardiro Crocodilo', desc: 'Крокодил-бомбардировщик. Сбрасывает на детей.' },
  tung:       { name: 'Tung Tung Sahur',    desc: 'Деревянный человечек с битой. Sahur sahur.' },
  patapim:    { name: 'Brr Brr Patapim',    desc: 'Обезьяна-лес. Hump-bump-tatatata.' },
  lirili:     { name: 'Lirili Larila',      desc: 'Слон-кактус с часами. Lirili larila.' },
};

function enemySpeed(type) {
  return ({
    tralalero:  3.5,
    bombardiro: 4.5,  // самый быстрый (летает)
    tung:       2.5,  // медленный с битой
    patapim:    3.0,
    lirili:     2.8,
  })[type] || 3;
}

// ─── Models ──────────────────────────────────────────────────────────────

function makeMeshFor(type) {
  switch (type) {
    case 'tralalero':  return makeTralalero();
    case 'bombardiro': return makeBombardiro();
    case 'tung':       return makeTung();
    case 'patapim':    return makePatapim();
    case 'lirili':     return makeLirili();
    default:           return makeTralalero();
  }
}

// ─── Tralalero Tralala — акула в синих Nike (3 ноги) ────────────────────
function makeTralalero() {
  const g = new THREE.Group();
  // Тело-акула
  const sharkBody = new THREE.Mesh(
    new THREE.ConeGeometry(0.5, 1.6, 16),
    new THREE.MeshStandardMaterial({ color: 0x6b7280, roughness: 0.6 })
  );
  sharkBody.rotation.z = Math.PI / 2;
  sharkBody.position.y = 1.5;
  sharkBody.castShadow = true;
  g.add(sharkBody);
  // Хвост
  const tail = new THREE.Mesh(
    new THREE.ConeGeometry(0.3, 0.6, 8),
    new THREE.MeshStandardMaterial({ color: 0x4b5563 })
  );
  tail.rotation.z = -Math.PI / 2;
  tail.position.set(-0.95, 1.5, 0);
  g.add(tail);
  // Зубастый рот — белый conус
  const teeth = new THREE.Mesh(
    new THREE.ConeGeometry(0.25, 0.4, 8),
    new THREE.MeshStandardMaterial({ color: 0xffffff })
  );
  teeth.rotation.z = Math.PI / 2;
  teeth.position.set(0.65, 1.5, 0);
  g.add(teeth);
  // Глаз
  const eye = new THREE.Mesh(
    new THREE.SphereGeometry(0.1, 12, 12),
    new THREE.MeshStandardMaterial({ color: 0xffffff })
  );
  eye.position.set(0.4, 1.7, 0.3);
  g.add(eye);
  const pupil = new THREE.Mesh(
    new THREE.SphereGeometry(0.04, 8, 8),
    new THREE.MeshStandardMaterial({ color: 0x000000 })
  );
  pupil.position.set(0.45, 1.7, 0.35);
  g.add(pupil);
  // 3 синих кроссовка Nike
  const shoeMat = new THREE.MeshStandardMaterial({ color: 0x1d4ed8, roughness: 0.5 });
  const swooshMat = new THREE.MeshBasicMaterial({ color: 0xffffff });
  for (let i = 0; i < 3; i++) {
    const shoe = new THREE.Mesh(
      new THREE.BoxGeometry(0.5, 0.25, 0.25),
      shoeMat
    );
    shoe.position.set(-0.3 + i * 0.3, 0.13, 0);
    shoe.castShadow = true;
    g.add(shoe);
    // Nike swoosh — простая запятая
    const swoosh = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.02, 6, 12, Math.PI / 2), swooshMat);
    swoosh.position.set(-0.3 + i * 0.3, 0.18, 0.13);
    swoosh.rotation.x = Math.PI / 2;
    g.add(swoosh);
    // Ноги — маленькие cylinder
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.08, 0.08, 0.7, 8),
      new THREE.MeshStandardMaterial({ color: 0x6b7280 })
    );
    leg.position.set(-0.3 + i * 0.3, 0.6, 0);
    g.add(leg);
  }
  return g;
}

// ─── Bombardiro Crocodilo — крокодил-самолёт ───────────────────────────
function makeBombardiro() {
  const g = new THREE.Group();
  // Корпус-фюзеляж (зелёный)
  const fuselage = new THREE.Mesh(
    new THREE.CylinderGeometry(0.4, 0.3, 2.0, 16),
    new THREE.MeshStandardMaterial({ color: 0x166534, roughness: 0.5 })
  );
  fuselage.rotation.z = Math.PI / 2;
  fuselage.position.y = 1.5;
  fuselage.castShadow = true;
  g.add(fuselage);
  // Голова крокодила
  const head = new THREE.Mesh(
    new THREE.BoxGeometry(0.7, 0.45, 0.55),
    new THREE.MeshStandardMaterial({ color: 0x166534 })
  );
  head.position.set(1.0, 1.5, 0);
  head.castShadow = true;
  g.add(head);
  // Челюсть
  const jaw = new THREE.Mesh(
    new THREE.BoxGeometry(0.6, 0.15, 0.5),
    new THREE.MeshStandardMaterial({ color: 0xfde047 })
  );
  jaw.position.set(1.1, 1.32, 0);
  g.add(jaw);
  // Глаза
  for (const x of [0.85, 0.85]) {
    const eye = new THREE.Mesh(
      new THREE.SphereGeometry(0.08, 12, 12),
      new THREE.MeshStandardMaterial({ color: 0xfbbf24 })
    );
    eye.position.set(0.9, 1.7, x === 0.85 ? 0.2 : -0.2);
    g.add(eye);
  }
  // Крылья — большие плоские box
  const wingMat = new THREE.MeshStandardMaterial({ color: 0x4b5563 });
  const wingL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.06, 1.6), wingMat);
  wingL.position.set(-0.1, 1.5, 0.9);
  wingL.castShadow = true;
  g.add(wingL);
  const wingR = wingL.clone();
  wingR.position.z = -0.9;
  g.add(wingR);
  // Пропеллер
  const prop = new THREE.Mesh(
    new THREE.BoxGeometry(0.04, 0.04, 1.0),
    new THREE.MeshStandardMaterial({ color: 0x111111 })
  );
  prop.position.set(-1.05, 1.5, 0);
  g.add(prop);
  prop.userData.spinning = true;
  // Бомба под фюзеляжем
  const bomb = new THREE.Mesh(
    new THREE.SphereGeometry(0.2, 16, 16),
    new THREE.MeshStandardMaterial({ color: 0x1f2937, metalness: 0.6 })
  );
  bomb.position.set(0, 1.1, 0);
  bomb.scale.x = 1.5;
  g.add(bomb);
  return g;
}

// ─── Tung Tung Tung Sahur — деревянный человечек с битой ───────────────
function makeTung() {
  const g = new THREE.Group();
  const woodMat = new THREE.MeshStandardMaterial({ color: 0xa16207, roughness: 0.7 });
  // Корпус — толстое полено
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.4, 0.4, 1.4, 12), woodMat);
  body.position.y = 1.0;
  body.castShadow = true;
  g.add(body);
  // Голова — большой куб
  const head = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 0.7), woodMat);
  head.position.y = 2.05;
  head.castShadow = true;
  g.add(head);
  // Огромные злые глаза
  for (const x of [-0.18, 0.18]) {
    const eye = new THREE.Mesh(
      new THREE.SphereGeometry(0.1, 12, 12),
      new THREE.MeshBasicMaterial({ color: 0xfde047 })
    );
    eye.position.set(x, 2.1, 0.36);
    g.add(eye);
    const pupil = new THREE.Mesh(
      new THREE.SphereGeometry(0.04, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0x000000 })
    );
    pupil.position.set(x, 2.1, 0.42);
    g.add(pupil);
  }
  // Открытый рот (чёрная щель)
  const mouth = new THREE.Mesh(
    new THREE.BoxGeometry(0.3, 0.06, 0.05),
    new THREE.MeshBasicMaterial({ color: 0x000000 })
  );
  mouth.position.set(0, 1.85, 0.36);
  g.add(mouth);
  // Руки — короткие палки
  for (const xSign of [-1, 1]) {
    const arm = new THREE.Mesh(
      new THREE.CylinderGeometry(0.1, 0.1, 0.8, 8),
      woodMat
    );
    arm.position.set(0.45 * xSign, 1.2, 0);
    arm.castShadow = true;
    g.add(arm);
  }
  // Бита в правой руке
  const bat = new THREE.Mesh(
    new THREE.CylinderGeometry(0.08, 0.13, 1.0, 10),
    new THREE.MeshStandardMaterial({ color: 0x57534e, roughness: 0.6 })
  );
  bat.position.set(0.65, 1.6, 0);
  bat.rotation.z = -Math.PI / 4;
  bat.castShadow = true;
  g.add(bat);
  // Ноги
  for (const xSign of [-1, 1]) {
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.13, 0.13, 0.6, 8),
      woodMat
    );
    leg.position.set(0.2 * xSign, 0.3, 0);
    leg.castShadow = true;
    g.add(leg);
  }
  return g;
}

// ─── Brr Brr Patapim — обезьяна-лес ─────────────────────────────────────
function makePatapim() {
  const g = new THREE.Group();
  // Тело — большой зелёный куст
  const bodyMat = new THREE.MeshStandardMaterial({ color: 0x166534, roughness: 0.9 });
  const body = new THREE.Mesh(new THREE.SphereGeometry(0.65, 16, 16), bodyMat);
  body.position.y = 1.0;
  body.scale.y = 0.9;
  body.castShadow = true;
  g.add(body);
  // Множество маленьких листочков
  for (let i = 0; i < 8; i++) {
    const angle = (i / 8) * Math.PI * 2;
    const leaf = new THREE.Mesh(
      new THREE.SphereGeometry(0.18, 8, 8),
      new THREE.MeshStandardMaterial({ color: 0x15803d })
    );
    leaf.position.set(
      Math.cos(angle) * 0.5,
      1.0 + Math.sin(i * 0.7) * 0.3,
      Math.sin(angle) * 0.5
    );
    g.add(leaf);
  }
  // Голова — коричневая обезьянья
  const headMat = new THREE.MeshStandardMaterial({ color: 0x713f12, roughness: 0.6 });
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.4, 16, 16), headMat);
  head.position.y = 1.85;
  head.castShadow = true;
  g.add(head);
  // Лицо — светлая морда
  const face = new THREE.Mesh(
    new THREE.SphereGeometry(0.28, 16, 16),
    new THREE.MeshStandardMaterial({ color: 0xfde68a })
  );
  face.position.set(0, 1.8, 0.2);
  face.scale.z = 0.5;
  g.add(face);
  // Глаза-сверкуны
  for (const x of [-0.12, 0.12]) {
    const eye = new THREE.Mesh(
      new THREE.SphereGeometry(0.07, 10, 10),
      new THREE.MeshBasicMaterial({ color: 0x000000 })
    );
    eye.position.set(x, 1.9, 0.36);
    g.add(eye);
  }
  // Длинные ноги-палки (тут босиком)
  const stickMat = new THREE.MeshStandardMaterial({ color: 0x57534e });
  for (const xSign of [-1, 1]) {
    const leg = new THREE.Mesh(
      new THREE.CylinderGeometry(0.05, 0.05, 0.8, 6),
      stickMat
    );
    leg.position.set(0.2 * xSign, 0.4, 0);
    leg.castShadow = true;
    g.add(leg);
    const foot = new THREE.Mesh(
      new THREE.BoxGeometry(0.2, 0.08, 0.4),
      new THREE.MeshStandardMaterial({ color: 0xfde68a })
    );
    foot.position.set(0.2 * xSign, 0.04, 0.1);
    g.add(foot);
  }
  return g;
}

// ─── Lirili Larila — кактус-слон с часами ──────────────────────────────
function makeLirili() {
  const g = new THREE.Group();
  // Тело-кактус (зелёный с вертикальными полосами)
  const cactusMat = new THREE.MeshStandardMaterial({ color: 0x166534, roughness: 0.8 });
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.55, 1.6, 12), cactusMat);
  body.position.y = 1.1;
  body.castShadow = true;
  g.add(body);
  // Шипы
  for (let i = 0; i < 12; i++) {
    const angle = (i / 12) * Math.PI * 2;
    const spike = new THREE.Mesh(
      new THREE.ConeGeometry(0.04, 0.15, 6),
      new THREE.MeshStandardMaterial({ color: 0xfde68a })
    );
    spike.position.set(
      Math.cos(angle) * 0.55,
      1.1 + (i % 3 - 1) * 0.3,
      Math.sin(angle) * 0.55
    );
    spike.rotation.z = Math.PI / 2;
    spike.lookAt(spike.position.x * 2, spike.position.y, spike.position.z * 2);
    g.add(spike);
  }
  // Голова слона — серая
  const elephantMat = new THREE.MeshStandardMaterial({ color: 0x6b7280, roughness: 0.7 });
  const head = new THREE.Mesh(new THREE.SphereGeometry(0.5, 16, 16), elephantMat);
  head.position.y = 2.1;
  head.castShadow = true;
  g.add(head);
  // Уши слона
  for (const xSign of [-1, 1]) {
    const ear = new THREE.Mesh(
      new THREE.SphereGeometry(0.25, 12, 12),
      elephantMat
    );
    ear.position.set(0.5 * xSign, 2.15, 0);
    ear.scale.set(0.5, 1.2, 0.7);
    g.add(ear);
  }
  // Хобот
  const trunkSegments = 5;
  for (let i = 0; i < trunkSegments; i++) {
    const seg = new THREE.Mesh(
      new THREE.SphereGeometry(0.15 - i * 0.015, 12, 12),
      elephantMat
    );
    const t = i / trunkSegments;
    seg.position.set(
      Math.sin(t * Math.PI * 0.5) * 0.1,
      2.0 - t * 0.5,
      0.3 + t * 0.3
    );
    g.add(seg);
  }
  // Глаза
  for (const x of [-0.18, 0.18]) {
    const eye = new THREE.Mesh(
      new THREE.SphereGeometry(0.08, 10, 10),
      new THREE.MeshBasicMaterial({ color: 0xffffff })
    );
    eye.position.set(x, 2.2, 0.35);
    g.add(eye);
    const pupil = new THREE.Mesh(
      new THREE.SphereGeometry(0.04, 8, 8),
      new THREE.MeshBasicMaterial({ color: 0x000000 })
    );
    pupil.position.set(x, 2.2, 0.42);
    g.add(pupil);
  }
  // Часы на руке (большой циферблат)
  const clockBack = new THREE.Mesh(
    new THREE.CylinderGeometry(0.18, 0.18, 0.05, 16),
    new THREE.MeshStandardMaterial({ color: 0xfafafa })
  );
  clockBack.position.set(0.65, 1.2, 0);
  clockBack.rotation.z = Math.PI / 2;
  g.add(clockBack);
  // Часовая стрелка (canvas-text «12 3 6 9» опционально, упрощённо — кружок)
  const clockCenter = new THREE.Mesh(
    new THREE.SphereGeometry(0.03, 8, 8),
    new THREE.MeshBasicMaterial({ color: 0x000000 })
  );
  clockCenter.position.set(0.66, 1.2, 0);
  g.add(clockCenter);
  return g;
}
