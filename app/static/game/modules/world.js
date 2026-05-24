/**
 * Мир: пол, sky-gradient, солнце, неоновые здания.
 * Размер карты 120×120, видимость ~80 метров.
 */
import * as THREE from 'three';

export const WORLD_SIZE = 120;
export const HALF_WORLD = WORLD_SIZE / 2;

export function buildWorld(scene) {
  // ─── Skybox: vertical gradient через large inverted sphere ──────────
  const skyGeo = new THREE.SphereGeometry(150, 32, 16);
  // ShaderMaterial с градиентом фиолетово-розовый закат
  const skyMat = new THREE.ShaderMaterial({
    uniforms: {
      topColor:    { value: new THREE.Color(0x0d0820) },
      midColor:    { value: new THREE.Color(0x7c1d6f) },
      bottomColor: { value: new THREE.Color(0xff7e5f) },
    },
    vertexShader: `
      varying vec3 vWorldPos;
      void main() {
        vec4 worldPosition = modelMatrix * vec4(position, 1.0);
        vWorldPos = worldPosition.xyz;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform vec3 topColor;
      uniform vec3 midColor;
      uniform vec3 bottomColor;
      varying vec3 vWorldPos;
      void main() {
        float h = normalize(vWorldPos).y;
        // -1 (низ) → 0 (середина) → 1 (верх)
        vec3 col;
        if (h > 0.0) {
          col = mix(midColor, topColor, smoothstep(0.0, 0.7, h));
        } else {
          col = mix(midColor, bottomColor, smoothstep(0.0, -0.5, h));
        }
        gl_FragColor = vec4(col, 1.0);
      }
    `,
    side: THREE.BackSide,
    depthWrite: false,
  });
  const sky = new THREE.Mesh(skyGeo, skyMat);
  scene.add(sky);
  scene.fog = new THREE.Fog(0x4c1d95, 50, 130);

  // ─── Солнце — большой светящийся диск на горизонте ──────────────────
  const sunSphere = new THREE.Mesh(
    new THREE.SphereGeometry(6, 32, 32),
    new THREE.MeshBasicMaterial({ color: 0xfde047 })
  );
  sunSphere.position.set(0, 25, -100);
  scene.add(sunSphere);
  // Свечение вокруг солнца
  const sunGlow = new THREE.Mesh(
    new THREE.SphereGeometry(10, 32, 32),
    new THREE.MeshBasicMaterial({
      color: 0xfbbf24,
      transparent: true,
      opacity: 0.3,
    })
  );
  sunGlow.position.copy(sunSphere.position);
  scene.add(sunGlow);

  // ─── Свет ───────────────────────────────────────────────────────────
  scene.add(new THREE.AmbientLight(0x6d28d9, 0.45));

  const sun = new THREE.DirectionalLight(0xfffbeb, 1.4);
  sun.position.set(20, 40, -30);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = -60;
  sun.shadow.camera.right = 60;
  sun.shadow.camera.top = 60;
  sun.shadow.camera.bottom = -60;
  sun.shadow.camera.far = 120;
  scene.add(sun);

  const rimLight = new THREE.DirectionalLight(0xff7eb9, 0.5);
  rimLight.position.set(-20, 10, 20);
  scene.add(rimLight);

  // ─── Пол: текстурированная плоскость ───────────────────────────────
  const floorTexture = makeFloorTexture();
  const groundMat = new THREE.MeshStandardMaterial({
    map: floorTexture,
    metalness: 0.15,
    roughness: 0.85,
  });
  const ground = new THREE.Mesh(
    new THREE.PlaneGeometry(WORLD_SIZE, WORLD_SIZE, 4, 4),
    groundMat
  );
  ground.rotation.x = -Math.PI / 2;
  ground.receiveShadow = true;
  scene.add(ground);

  // ─── Стены по периметру ─────────────────────────────────────────────
  const wallMat = new THREE.MeshStandardMaterial({
    color: 0x4c1d95,
    metalness: 0.5,
    roughness: 0.4,
    emissive: 0x6d28d9,
    emissiveIntensity: 0.3,
  });
  const wallHeight = 4;
  const wallThickness = 1;
  const walls = [
    { x: 0, z: HALF_WORLD, w: WORLD_SIZE, h: wallThickness },
    { x: 0, z: -HALF_WORLD, w: WORLD_SIZE, h: wallThickness },
    { x: HALF_WORLD, z: 0, w: wallThickness, h: WORLD_SIZE },
    { x: -HALF_WORLD, z: 0, w: wallThickness, h: WORLD_SIZE },
  ];
  walls.forEach((w) => {
    const wallGeom = new THREE.BoxGeometry(w.w, wallHeight, w.h);
    const wall = new THREE.Mesh(wallGeom, wallMat);
    wall.position.set(w.x, wallHeight / 2, w.z);
    wall.castShadow = true;
    wall.receiveShadow = true;
    scene.add(wall);
  });

  // ─── Здания: разные размеры + текстура «окон в ночи» ────────────────
  const obstacles = [];
  const buildingTexture = makeBuildingTexture();
  for (let i = 0; i < 30; i++) {
    const w = 3 + Math.random() * 5;
    const h = 4 + Math.random() * 10;
    const d = 3 + Math.random() * 5;
    const x = (Math.random() - 0.5) * (WORLD_SIZE - 10);
    const z = (Math.random() - 0.5) * (WORLD_SIZE - 10);
    // не ставим близко к точке спавна
    if (Math.abs(x) < 6 && Math.abs(z) < 6) continue;
    const tex = buildingTexture.clone();
    tex.needsUpdate = true;
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.repeat.set(w / 2, h / 4);
    const bldgMat = new THREE.MeshStandardMaterial({
      map: tex,
      metalness: 0.5,
      roughness: 0.6,
    });
    const bldg = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), bldgMat);
    bldg.position.set(x, h / 2, z);
    bldg.castShadow = true;
    bldg.receiveShadow = true;
    scene.add(bldg);
    // Неон-полоска сверху
    const stripColors = [0xd946ef, 0xfbbf24, 0x06b6d4, 0xef4444, 0x10b981];
    const strip = new THREE.Mesh(
      new THREE.BoxGeometry(w, 0.15, d),
      new THREE.MeshBasicMaterial({ color: stripColors[i % stripColors.length] })
    );
    strip.position.set(x, h + 0.07, z);
    scene.add(strip);
    // Бонус — point-light внутри здания для атмосферы (только у каждого 4-го)
    if (i % 4 === 0) {
      const pointLight = new THREE.PointLight(stripColors[i % stripColors.length], 1.5, 10);
      pointLight.position.set(x, h + 1, z);
      scene.add(pointLight);
    }
    obstacles.push({ x, z, halfW: w / 2 + 0.4, halfD: d / 2 + 0.4, top: h });
  }

  return { obstacles, halfSize: HALF_WORLD };
}

// Procedural floor: шахматка с диагональю + светящиеся линии
function makeFloorTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 512;
  const ctx = canvas.getContext('2d');
  // Фон фиолетовый
  ctx.fillStyle = '#2e1065';
  ctx.fillRect(0, 0, 512, 512);
  // Шахматка
  ctx.fillStyle = '#4c1d95';
  const cell = 64;
  for (let y = 0; y < 512; y += cell) {
    for (let x = 0; x < 512; x += cell) {
      if (((x / cell) + (y / cell)) % 2 === 0) {
        ctx.fillRect(x, y, cell, cell);
      }
    }
  }
  // Светящиеся ярко-розовые линии
  ctx.strokeStyle = '#d946ef';
  ctx.lineWidth = 3;
  for (let x = 0; x <= 512; x += cell) {
    ctx.beginPath();
    ctx.moveTo(x, 0); ctx.lineTo(x, 512); ctx.stroke();
  }
  for (let y = 0; y <= 512; y += cell) {
    ctx.beginPath();
    ctx.moveTo(0, y); ctx.lineTo(512, y); ctx.stroke();
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(10, 10);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

// Procedural building texture: окна светящиеся ночью
function makeBuildingTexture() {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#1e1b4b';
  ctx.fillRect(0, 0, 256, 256);
  // Случайные горящие окна
  for (let y = 16; y < 256; y += 32) {
    for (let x = 16; x < 256; x += 32) {
      ctx.fillStyle = Math.random() > 0.4 ? '#fbbf24' : '#1a1430';
      ctx.fillRect(x, y, 18, 22);
    }
  }
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}
