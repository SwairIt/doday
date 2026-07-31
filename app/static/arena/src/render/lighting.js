/**
 * Освещение арены: закатное солнце с тенями, следующими за игроком,
 * и полусферическая мягкая заливка небо/земля.
 */
import { DirectionalLight, HemisphereLight, Vector3, MathUtils } from 'three';

/** Пресеты качества: размер карты теней (0 — тени выключены). */
const QUALITY_PRESETS = {
  low:    { shadowMapSize: 0 },
  medium: { shadowMapSize: 1024 },
  high:   { shadowMapSize: 2048 },
};

/** Высота солнца над горизонтом (радианы от горизонта) — низкое закатное солнце. */
const SUN_ELEVATION = MathUtils.degToRad(14);
/** Азимут солнца (радианы). */
const SUN_AZIMUTH = MathUtils.degToRad(55);
/** Расстояние источника света от точки цели (влияет только на направление). */
const SUN_DISTANCE = 80;
/** Цвет закатного солнца. */
const SUN_COLOR = 0xffb36b;
/** Интенсивность солнца. */
const SUN_INTENSITY = 2.2;
/** Полуразмер ортографической зоны теней (метры). */
const SHADOW_EXTENT = 45;
/** Дальняя плоскость теневой камеры. */
const SHADOW_FAR = 220;
/** Цвет неба и земли для полусферического света. */
const HEMI_SKY_COLOR = 0x8fb4d8;
const HEMI_GROUND_COLOR = 0x4a3b2e;
/** Интенсивность полусферического света. */
const HEMI_INTENSITY = 0.55;

// Модульные временные векторы — без аллокаций в update.
const _sunDir = new Vector3();
const _snap = new Vector3();

/**
 * Создаёт освещение сцены.
 * @param {import('three').Scene} scene сцена
 * @param {{quality: 'low'|'medium'|'high', get: Function}} settings настройки
 * @returns {{sun: DirectionalLight, hemi: HemisphereLight, update: (playerPosition: Vector3) => void}}
 */
export function createLighting(scene, settings) {
  const preset = QUALITY_PRESETS[settings.quality] ?? QUALITY_PRESETS.medium;

  // Направление «к солнцу» из низкого угла над горизонтом.
  _sunDir.set(
    Math.cos(SUN_ELEVATION) * Math.cos(SUN_AZIMUTH),
    Math.sin(SUN_ELEVATION),
    Math.cos(SUN_ELEVATION) * Math.sin(SUN_AZIMUTH),
  ).normalize();

  const sun = new DirectionalLight(SUN_COLOR, SUN_INTENSITY);
  sun.castShadow = preset.shadowMapSize > 0;

  const cam = sun.shadow.camera;
  if (sun.castShadow) {
    sun.shadow.mapSize.set(preset.shadowMapSize, preset.shadowMapSize);
    cam.left = -SHADOW_EXTENT;
    cam.right = SHADOW_EXTENT;
    cam.top = SHADOW_EXTENT;
    cam.bottom = -SHADOW_EXTENT;
    cam.near = 1;
    cam.far = SHADOW_FAR;
    sun.shadow.bias = -0.0004;
    sun.shadow.normalBias = 0.02;
    cam.updateProjectionMatrix();
  }

  scene.add(sun);
  scene.add(sun.target);

  const hemi = new HemisphereLight(HEMI_SKY_COLOR, HEMI_GROUND_COLOR, HEMI_INTENSITY);
  scene.add(hemi);

  // Пиксельный размер теневой карты в мировых единицах — для снаппинга
  // теневой камеры, чтобы избежать мерцания краёв теней при движении.
  const texelSize = (SHADOW_EXTENT * 2) / Math.max(preset.shadowMapSize, 1);

  /**
   * Подвигает ортографическую теневую камеру вслед за игроком,
   * чтобы тени не обрывались вдали.
   * @param {import('three').Vector3} playerPosition позиция игрока
   */
  function update(playerPosition) {
    // Снаппим центр теневой области по размеру текселя карты теней.
    _snap.copy(playerPosition);
    if (sun.castShadow) {
      _snap.x = Math.round(_snap.x / texelSize) * texelSize;
      _snap.z = Math.round(_snap.z / texelSize) * texelSize;
      _snap.y = 0;
    }
    sun.target.position.copy(_snap);
    sun.position.copy(_sunDir).multiplyScalar(SUN_DISTANCE).add(_snap);
  }

  update(sun.target.position);

  return { sun, hemi, update };
}
