// Радар-миникарта: отдельный canvas 2D, карта вращается вместе с игроком.

// --- Константы отрисовки ---
const DEFAULT_SIZE = 180;          // размер канваса, px
const DEFAULT_WORLD_SIZE = 200;    // размер мира (для справки/границ), м
const RADAR_RANGE_METERS = 60;     // радиус покрытия радара в мире
const EDGE_PADDING_PX = 5;         // отступ от окантовки для прижатых точек
const BORDER_WIDTH_PX = 1.5;

const BOT_DOT_RADIUS = 3;          // радиус точки живого бота в зоне радара
const BOT_DOT_RADIUS_EDGE = 2;     // радиус прижатой к краю точки
const PLAYER_TRI_SIZE = 6;         // полуразмер треугольника игрока

const COLOR_BG = 'rgba(10, 14, 18, 0.62)';
const COLOR_BORDER = 'rgba(220, 230, 240, 0.85)';
const COLOR_BUILDING = 'rgba(190, 195, 200, 0.55)';
const COLOR_PLAYER = '#ffffff';
const COLOR_BOT = '#ff4444';

/**
 * Создаёт радар-миникарту.
 * @param {{size?: number, worldSize?: number, container?: HTMLElement}} options
 * @returns {{element: HTMLCanvasElement, update(dt: number, view: object): void, dispose(): void}}
 */
export function createMinimap(options = {}) {
  const size = options.size ?? DEFAULT_SIZE;
  const half = size / 2;
  const radius = half - EDGE_PADDING_PX; // радиус рабочей зоны радара, px
  // масштаб: radius px соответствует RADAR_RANGE_METERS метрам
  const scale = radius / RADAR_RANGE_METERS;

  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  const canvas = document.createElement('canvas');
  canvas.width = size * dpr;
  canvas.height = size * dpr;
  canvas.style.cssText =
    `position:absolute;left:16px;top:16px;width:${size}px;height:${size}px;` +
    `z-index:20;pointer-events:none;border-radius:50%;` +
    `box-shadow:0 2px 10px rgba(0,0,0,0.45);`;
  (options.container ?? document.body).appendChild(canvas);

  const ctx = canvas.getContext('2d');

  // --- Статичный путь зданий в мировых координатах (кэш Path2D) ---
  /** @type {Path2D|null} */
  let buildingsPath = null;
  let buildingsBuilt = false;

  /**
   * Строит Path2D зданий один раз, по первому update с непустым списком.
   * @param {Array<{x:number, z:number, w:number, d:number}>} buildings
   */
  function buildBuildingsPath(buildings) {
    buildingsPath = new Path2D();
    for (let i = 0; i < buildings.length; i++) {
      const b = buildings[i];
      buildingsPath.rect(b.x - b.w / 2, b.z - b.d / 2, b.w, b.d);
    }
    buildingsBuilt = true;
  }

  /**
   * Перерисовывает радар.
   * @param {number} dt время кадра, с (не используется, интерфейс общий)
   * @param {{playerPos: {x:number, z:number}, playerYaw: number,
   *          bots: Array<{position:{x:number,z:number}, alive:boolean}>,
   *          buildings: Array<{x:number, z:number, w:number, d:number}>}} view
   */
  function update(dt, view) {
    if (!view || !view.playerPos) return;

    if (!buildingsBuilt && view.buildings && view.buildings.length > 0) {
      buildBuildingsPath(view.buildings);
    }

    const px = view.playerPos.x;
    const pz = view.playerPos.z;
    const yaw = view.playerYaw;

    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, size, size);

    // Круглая маска: всё вне круга отсекается
    ctx.save();
    ctx.beginPath();
    ctx.arc(half, half, half - BORDER_WIDTH_PX, 0, Math.PI * 2);
    ctx.clip();

    // Фон
    ctx.fillStyle = COLOR_BG;
    ctx.fillRect(0, 0, size, size);

    // --- Слой, вращающийся вместе с картой: центр = игрок, вверх = взгляд ---
    ctx.save();
    ctx.translate(half, half);
    ctx.rotate(yaw);
    ctx.scale(scale, scale);
    ctx.translate(-px, -pz);

    if (buildingsPath) {
      ctx.fillStyle = COLOR_BUILDING;
      ctx.fill(buildingsPath);
    }
    ctx.restore();

    // --- Боты (считаются вручную, чтобы прижимать к краю круга) ---
    const bots = view.bots;
    if (bots) {
      const cosY = Math.cos(yaw);
      const sinY = Math.sin(yaw);
      const maxR = radius - BOT_DOT_RADIUS_EDGE;
      for (let i = 0; i < bots.length; i++) {
        const bot = bots[i];
        if (!bot.alive) continue;
        const dx = bot.position.x - px;
        const dz = bot.position.z - pz;
        // Поворот мирового смещения в пространство экрана радара
        // (против часовой — тот же порядок, что и у ctx.rotate выше)
        const rx = dx * cosY - dz * sinY;
        const rz = dx * sinY + dz * cosY;

        let sx = rx * scale;
        let sy = rz * scale;
        const distPx = Math.sqrt(sx * sx + sy * sy);
        const dotR = distPx > maxR ? BOT_DOT_RADIUS_EDGE : BOT_DOT_RADIUS;
        if (distPx > maxR) {
          // Бот за пределами радара — точка прижимается к краю круга
          const k = maxR / distPx;
          sx *= k;
          sy *= k;
        }

        ctx.fillStyle = COLOR_BOT;
        ctx.beginPath();
        ctx.arc(half + sx, half + sy, dotR, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    // --- Игрок: белый треугольник в центре, вершиной вверх ---
    const t = PLAYER_TRI_SIZE;
    ctx.fillStyle = COLOR_PLAYER;
    ctx.beginPath();
    ctx.moveTo(half, half - t);            // нос вверх
    ctx.lineTo(half - t * 0.75, half + t); // левый край
    ctx.lineTo(half + t * 0.75, half + t); // правый край
    ctx.closePath();
    ctx.fill();

    ctx.restore(); // снять круглую маску

    // Окантовка поверх всего
    ctx.strokeStyle = COLOR_BORDER;
    ctx.lineWidth = BORDER_WIDTH_PX;
    ctx.beginPath();
    ctx.arc(half, half, half - BORDER_WIDTH_PX / 2, 0, Math.PI * 2);
    ctx.stroke();
  }

  /** Снимает обработчики и удаляет canvas из DOM. */
  function dispose() {
    canvas.remove();
    buildingsPath = null;
  }

  return { element: canvas, update, dispose };
}
