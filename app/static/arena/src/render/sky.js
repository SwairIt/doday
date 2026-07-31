/**
 * src/render/sky.js
 * Процедурное закатное небо Doday Arena: скайдом на шейдере,
 * PMREM environment map, экспоненциальный туман в тон горизонта.
 */

import * as THREE from 'three';

/** Радиус скайдома, метры. */
const SKY_RADIUS = 900;

/** Направление на заходящее солнце (нормализуется в коде). */
const SUN_DIRECTION = new THREE.Vector3(-0.55, 0.18, -0.82).normalize();

/** Цвета палитры заката. */
const COLOR_ZENITH = new THREE.Color(0x1a2140);      // глубокий сине-фиолетовый зенит
const COLOR_HORIZON = new THREE.Color(0xff7a3c);     // оранжевый горизонт
const COLOR_GROUND = new THREE.Color(0x241a20);      // ниже горизонта — тёмная земля
const COLOR_SUN_DISK = new THREE.Color(0xfff2cc);    // диск солнца
const COLOR_SUN_HALO = new THREE.Color(0xff9a4d);    // ореол солнца
const COLOR_HAZE = new THREE.Color(0xd96a45);        // дымка у горизонта

/** Пресеты качества: плотность тумана и разрешение PMREM. */
const QUALITY_PRESETS = {
  low:    { fogDensity: 0.0035, pmremSize: 64 },
  medium: { fogDensity: 0.0028, pmremSize: 128 },
  high:   { fogDensity: 0.0022, pmremSize: 256 },
};

const VERTEX_SHADER = /* glsl */ `
varying vec3 vWorldDir;

void main() {
  // Позиция локальная — сфера всегда следует за камерой через frustumCulled=false
  // и центрированием по камере в update. Направление берём мировое.
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldDir = normalize(worldPos.xyz - cameraPosition);
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const FRAGMENT_SHADER = /* glsl */ `
uniform vec3 uSunDir;
uniform vec3 uZenith;
uniform vec3 uHorizon;
uniform vec3 uGround;
uniform vec3 uSunDisk;
uniform vec3 uSunHalo;
uniform vec3 uHaze;
uniform float uTime;

varying vec3 vWorldDir;

void main() {
  vec3 dir = normalize(vWorldDir);
  float height = dir.y;

  // Градиент зенит -> горизонт -> земля
  float skyT = pow(clamp(1.0 - height, 0.0, 1.0), 2.2);
  vec3 sky = mix(uZenith, uHorizon, skyT);
  float groundT = pow(clamp(1.0 + height, 0.0, 1.0), 3.0);
  vec3 col = mix(uGround, sky, smoothstep(-0.08, 0.02, height));

  // Солнце: диск + широкий ореол
  float cosSun = dot(dir, uSunDir);
  float disk = smoothstep(0.9993, 0.9997, cosSun);
  float halo = pow(clamp(cosSun, 0.0, 1.0), 24.0) * 0.55
             + pow(clamp(cosSun, 0.0, 1.0), 160.0) * 0.9;

  // Ореол усиливаем ближе к горизонту
  float horizonBoost = 1.0 - clamp(abs(height) * 2.5, 0.0, 1.0);
  col = mix(col, uSunHalo, halo * horizonBoost * 0.8);
  col = mix(col, uSunDisk, disk);

  // Лёгкая мерцающая дымка вдоль горизонта
  float hazeBand = exp(-abs(height) * 14.0);
  float wave = sin(dir.x * 9.0 + uTime * 0.07) * sin(dir.z * 7.0 - uTime * 0.05);
  col = mix(col, uHaze, hazeBand * (0.22 + 0.06 * wave));

  gl_FragColor = vec4(col, 1.0);
}
`;

/**
 * Создаёт скайдом, environment map и туман сцены.
 * @param {THREE.Scene} scene
 * @param {THREE.WebGLRenderer} renderer
 * @param {import('../core/settings.js').Settings} settings
 * @returns {{update: (dt: number) => void, envMap: THREE.Texture}}
 */
export function createSky(scene, renderer, settings) {
  const quality = settings.quality;
  const preset = QUALITY_PRESETS[quality] ?? QUALITY_PRESETS.medium;

  const material = new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
    uniforms: {
      uSunDir: { value: SUN_DIRECTION.clone() },
      uZenith: { value: COLOR_ZENITH.clone() },
      uHorizon: { value: COLOR_HORIZON.clone() },
      uGround: { value: COLOR_GROUND.clone() },
      uSunDisk: { value: COLOR_SUN_DISK.clone() },
      uSunHalo: { value: COLOR_SUN_HALO.clone() },
      uHaze: { value: COLOR_HAZE.clone() },
      uTime: { value: 0 },
    },
    vertexShader: VERTEX_SHADER,
    fragmentShader: FRAGMENT_SHADER,
  });

  const geometry = new THREE.SphereGeometry(SKY_RADIUS, 32, 16);
  const mesh = new THREE.Mesh(geometry, material);
  mesh.frustumCulled = false;
  mesh.renderOrder = -1000; // рисуем небо первым
  scene.add(mesh);

  // Туман в тон горизонту
  scene.fog = new THREE.FogExp2(COLOR_HAZE.getHex(), preset.fogDensity);

  // --- Environment map: прогоняем отдельную сцену со скайдомом через PMREM ---
  const pmrem = new THREE.PMREMGenerator(renderer);
  pmrem.compileEquirectangularShader();

  const envScene = new THREE.Scene();
  const envMesh = new THREE.Mesh(geometry, material);
  envScene.add(envMesh);

  const envRT = pmrem.fromScene(envScene, 0.04, 0.1, SKY_RADIUS * 0.9);
  const envMap = envRT.texture;
  scene.environment = envMap;

  pmrem.dispose();
  envScene.remove(envMesh); // геометрия/материал общие с основным скайдомом — не диспоузим

  // Солнце задаёт и ключевое направленное освещение сцены
  const sunLight = new THREE.DirectionalLight(COLOR_SUN_DISK, 2.2);
  sunLight.position.copy(SUN_DIRECTION).multiplyScalar(300);
  scene.add(sunLight);
  scene.add(sunLight.target);

  const ambient = new THREE.HemisphereLight(COLOR_ZENITH, COLOR_GROUND, 0.35);
  scene.add(ambient);

  let time = 0;

  /**
   * Обновление неба: время униформы, следование за камерой.
   * @param {number} dt секунды
   */
  function update(dt) {
    time += dt;
    material.uniforms.uTime.value = time;

    // Скайдом держим центрированным на активной камере,
    // чтобы игрок никогда не «дошёл» до края сферы.
    const cam = scene.userData.camera;
    if (cam) {
      mesh.position.copy(cam.position);
      sunLight.target.position.copy(cam.position);
      sunLight.position.copy(cam.position).addScaledVector(SUN_DIRECTION, 300);
      sunLight.target.updateMatrixWorld();
    }
  }

  return { update, envMap };
}
