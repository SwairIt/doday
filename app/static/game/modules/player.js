/**
 * Беллстрой — игрок. Procedural-character + физика прыжка.
 *
 * API:
 *   const p = createPlayer();
 *   scene.add(p.mesh);
 *   p.update(dt, input, cameraYaw, world);
 *   p.jump();
 *   p.takeDamage();
 *   p.position / p.velocity / p.hp / p.isGrounded
 */
import * as THREE from 'three';

const GRAVITY = -25;
const JUMP_VELOCITY = 9;
const MOVE_SPEED = 7;
const MAX_HP = 3;

export function createPlayer() {
  const mesh = buildCharacterMesh();
  return new Player(mesh);
}

class Player {
  constructor(mesh) {
    this.mesh = mesh;
    this.position = new THREE.Vector3(0, 0, 0);
    this.velocity = new THREE.Vector3(0, 0, 0);
    this.rotation = 0;
    this.walkPhase = 0;
    this.hp = MAX_HP;
    this.maxHp = MAX_HP;
    this.invincibleUntil = 0;
    this.alive = true;
    this.isGrounded = true;
  }

  jump() {
    if (this.isGrounded && this.alive) {
      this.velocity.y = JUMP_VELOCITY;
      this.isGrounded = false;
    }
  }

  takeDamage() {
    if (!this.alive) return false;
    const now = performance.now();
    if (now < this.invincibleUntil) return false;
    this.hp -= 1;
    this.invincibleUntil = now + 1200;
    if (this.hp <= 0) {
      this.alive = false;
    }
    return true;
  }

  reset() {
    this.position.set(0, 0, 0);
    this.velocity.set(0, 0, 0);
    this.rotation = 0;
    this.hp = this.maxHp;
    this.alive = true;
    this.invincibleUntil = 0;
    this.isGrounded = true;
  }

  update(dt, input, cameraYaw, world) {
    if (!this.alive) {
      // dead — падаем на землю с гравитацией, никакого input'а
      this.velocity.y += GRAVITY * dt;
      this.position.y += this.velocity.y * dt;
      if (this.position.y < 0) {
        this.position.y = 0;
        this.velocity.y = 0;
      }
      this.mesh.position.copy(this.position);
      this.mesh.rotation.y = this.rotation;
      // Падает на бок при смерти
      this.mesh.rotation.z = Math.min(Math.PI / 2, (this.mesh.rotation.z || 0) + dt * 3);
      return;
    }

    // ─── Movement input ─────────────────────────────────────────────
    let dx = 0, dz = 0;
    if (input.forward) dz -= 1;
    if (input.back) dz += 1;
    if (input.left) dx -= 1;
    if (input.right) dx += 1;
    if (input.joystickActive) {
      dx = input.joyX;
      dz = input.joyY;
    }
    const len = Math.sqrt(dx * dx + dz * dz);
    let moving = false;
    if (len > 0.05) {
      moving = true;
      if (len > 1) { dx /= len; dz /= len; }
      // Поворачиваем по yaw камеры
      const cosY = Math.cos(cameraYaw);
      const sinY = Math.sin(cameraYaw);
      const worldDx = dx * cosY + dz * sinY;
      const worldDz = -dx * sinY + dz * cosY;
      const newX = this.position.x + worldDx * MOVE_SPEED * dt;
      const newZ = this.position.z + worldDz * MOVE_SPEED * dt;
      if (Math.abs(newX) < world.halfSize - 1 && !checkObstacle(newX, this.position.z, world)) {
        this.position.x = newX;
      }
      if (Math.abs(newZ) < world.halfSize - 1 && !checkObstacle(this.position.x, newZ, world)) {
        this.position.z = newZ;
      }
      const targetYaw = Math.atan2(worldDx, worldDz);
      let diff = targetYaw - this.rotation;
      while (diff > Math.PI) diff -= Math.PI * 2;
      while (diff < -Math.PI) diff += Math.PI * 2;
      this.rotation += diff * Math.min(1, dt * 10);
      this.walkPhase += dt * 12;
    } else {
      this.walkPhase += dt * 4;
    }

    // ─── Vertical physics ───────────────────────────────────────────
    this.velocity.y += GRAVITY * dt;
    this.position.y += this.velocity.y * dt;
    if (this.position.y <= 0) {
      this.position.y = 0;
      this.velocity.y = 0;
      this.isGrounded = true;
    } else {
      this.isGrounded = false;
    }

    // ─── Apply to mesh ──────────────────────────────────────────────
    this.mesh.position.copy(this.position);
    this.mesh.rotation.y = this.rotation;
    this.mesh.rotation.z = 0; // на случай если был мёртв и оживили
    // Walk-bob (только если на земле и движется)
    const bobAmt = moving && this.isGrounded ? 0.08 : 0;
    this.mesh.position.y = this.position.y + Math.abs(Math.sin(this.walkPhase)) * bobAmt;

    // Покачивание рук
    this.mesh.children.forEach((c) => {
      if (c.userData.armSide !== undefined) {
        c.rotation.x = Math.sin(this.walkPhase + (c.userData.armSide > 0 ? Math.PI : 0)) * 0.4 * (moving ? 1 : 0);
      }
    });

    // Мигание во время invincibility
    const isInvinc = performance.now() < this.invincibleUntil;
    this.mesh.visible = !isInvinc || (Math.floor(performance.now() / 80) % 2 === 0);
  }
}

function checkObstacle(x, z, world) {
  for (const o of world.obstacles) {
    if (Math.abs(x - o.x) < o.halfW && Math.abs(z - o.z) < o.halfD) return true;
  }
  return false;
}

// ─── Procedural Беллстрой ─────────────────────────────────────────────

function buildCharacterMesh() {
  const group = new THREE.Group();

  const bodyMat = new THREE.MeshStandardMaterial({
    color: 0x0d0d0d, metalness: 0.1, roughness: 0.85,
  });
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.55, 0.65, 1.3, 16), bodyMat);
  body.position.y = 0.65;
  body.castShadow = true;
  group.add(body);

  // Принт «Б»
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
  for (const xSign of [-1, 1]) {
    const brow = new THREE.Mesh(
      new THREE.BoxGeometry(0.12, 0.025, 0.025),
      new THREE.MeshStandardMaterial({ color: 0xc8a070 })
    );
    brow.position.set(0.17 * xSign, 2.01, 0.42);
    brow.rotation.z = -xSign * 0.15;
    group.add(brow);
  }
  const smile = new THREE.Mesh(
    new THREE.TorusGeometry(0.12, 0.018, 8, 16, Math.PI * 0.7),
    new THREE.MeshStandardMaterial({ color: 0x802020 })
  );
  smile.position.set(0.02, 1.74, 0.43);
  smile.rotation.z = -0.25;
  smile.rotation.x = Math.PI;
  group.add(smile);

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

  for (const xSign of [-1, 1]) {
    const ear = new THREE.Mesh(new THREE.SphereGeometry(0.08, 12, 12), skinMat);
    ear.position.set(0.42 * xSign, 1.85, 0);
    ear.scale.set(0.6, 1, 0.4);
    group.add(ear);
  }
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
