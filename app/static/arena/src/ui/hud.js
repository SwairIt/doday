/**
 * HUD поверх canvas: здоровье, патроны, прицел, hitmarker, killfeed,
 * счётчик фрагов, индикатор урона по направлению, экран смерти.
 * Обновляет DOM только при изменении значений.
 */

const KILLFEED_MAX = 5;
const KILLFEED_TTL = 5.0;         // секунды жизни строки лога
const HITMARKER_TTL = 0.18;
const DAMAGE_IND_TTL = 1.2;
const SPREAD_BASE_PX = 8;         // пиксели расхождения при нулевом разбросе
const SPREAD_SCALE_PX = 90;       // пиксели на радиан разброса
const SPREAD_LERP = 18;           // скорость подтяжки прицела (1/сек)
const HP_LOW_FRac = 0.3;

/**
 * Создаёт HUD и вставляет его в переданный контейнер.
 * @param {HTMLElement} container — блок-оверлей поверх canvas (position:absolute).
 * @returns {{
 *  setHealth(hp:number,max:number):void,
 *  setAmmo(mag:number,reserve:number):void,
 *  setSpread(radians:number, onEnemy:boolean):void,
 *  hitmarker(isKill?:boolean):void,
 *  killfeed(text:string):void,
 *  damageFrom(dirX:number,dirZ:number,yaw:number):void,
 *  addKill(count:number):void,
 *  showDeath():void,
 *  hideDeath():void,
 *  update(dt:number):void
 * }}
 */
export function createHud(container) {
  const root = document.createElement('div');
  root.id = 'hud';
  root.innerHTML = `
    <div class="hud-crosshair"><i class="ch-t"></i><i class="ch-b"></i><i class="ch-l"></i><i class="ch-r"></i><i class="ch-dot"></i></div>
    <div class="hud-hitmarker"><i></i><i></i><i></i><i></i></div>
    <div class="hud-dmg-ring"></div>
    <div class="hud-hp"><div class="hud-hp-bar"></div><span class="hud-hp-text"></span></div>
    <div class="hud-ammo"><span class="hud-ammo-mag"></span><span class="hud-ammo-sep">/</span><span class="hud-ammo-res"></span></div>
    <div class="hud-kills">☠ <span class="hud-kills-num">0</span></div>
    <ul class="hud-feed"></ul>
    <div class="hud-death">
      <div class="hud-death-title">ВЫ ПОГИБЛИ</div>
      <button class="hud-respawn" type="button">ВОЗРОДИТЬСЯ</button>
    </div>`;
  container.appendChild(root);

  const style = document.createElement('style');
  style.textContent = `
    #hud{position:absolute;inset:0;pointer-events:none;font-family:Segoe UI,Arial,sans-serif;color:#fff;user-select:none;overflow:hidden}
    .hud-crosshair{position:absolute;left:50%;top:50%;width:0;height:0}
    .hud-crosshair i{position:absolute;background:#fff;box-shadow:0 0 3px #000}
    .ch-t,.ch-b{width:2px;height:10px;left:-1px}
    .ch-l,.ch-r{width:10px;height:2px;top:-1px}
    .hud-crosshair.enemy i{background:#ff3b3b}
    .ch-dot{width:2px;height:2px;left:-1px;top:-1px;border-radius:50%}
    .hud-hitmarker{position:absolute;left:50%;top:50%;width:0;height:0;opacity:0}
    .hud-hitmarker i{position:absolute;width:12px;height:2px;background:#fff;box-shadow:0 0 4px #000}
    .hud-hitmarker i:nth-child(1){transform:rotate(45deg) translate(8px,0)}
    .hud-hitmarker i:nth-child(2){transform:rotate(135deg) translate(8px,0)}
    .hud-hitmarker i:nth-child(3){transform:rotate(225deg) translate(8px,0)}
    .hud-hitmarker i:nth-child(4){transform:rotate(315deg) translate(8px,0)}
    .hud-hitmarker.kill i{background:#ff2020}
    .hud-dmg-ring{position:absolute;left:50%;top:50%;width:120px;height:120px;margin:-60px 0 0 -60px;opacity:0;
      border-radius:50%;border:0 solid transparent;border-top:6px solid rgba(255,40,40,.9)}
    .hud-hp{position:absolute;left:24px;bottom:24px;width:240px}
    .hud-hp{height:18px;background:rgba(0,0,0,.5);border:1px solid rgba(255,255,255,.25);box-sizing:content-box}
    .hud-hp-bar{height:100%;width:100%;background:#39d353;transition:background .2s}
    .hud-hp-text{position:absolute;inset:0;text-align:center;font-size:13px;line-height:18px;text-shadow:0 1px 2px #000}
    .hud-ammo{position:absolute;right:24px;bottom:24px;font-size:28px;text-shadow:0 1px 3px #000}
    .hud-ammo-mag{font-size:38px;font-weight:700}
    .hud-ammo-mag.empty{color:#ff3b3b}
    .hud-ammo-res{opacity:.7;margin-left:6px}
    .hud-kills{position:absolute;right:24px;top:16px;font-size:22px;text-shadow:0 1px 3px #000}
    /* Килфид справа сверху, как в CS: строки прижаты к правому краю. */
    .hud-feed{position:absolute;right:16px;top:52px;margin:0;padding:0;list-style:none;
      font-size:14px;text-align:right;display:flex;flex-direction:column;align-items:flex-end}
    .hud-feed li{background:rgba(0,0,0,.55);padding:4px 10px;margin-bottom:4px;border-right:3px solid #d9a441;
      text-shadow:0 1px 2px #000;transition:opacity .4s}
    .hud-death{position:absolute;inset:0;display:none;flex-direction:column;align-items:center;justify-content:center;
      background:rgba(120,0,0,.35);backdrop-filter:blur(2px);pointer-events:auto}
    .hud-death-title{font-size:42px;font-weight:800;letter-spacing:4px;color:#ff4040;text-shadow:0 2px 8px #000;margin-bottom:24px}
    .hud-respawn{font-size:18px;padding:12px 36px;background:#222;color:#fff;border:2px solid #ff4040;cursor:pointer;letter-spacing:2px}
    .hud-respawn:hover{background:#ff4040}`;
  document.head.appendChild(style);

  // --- кэш узлов ---
  const ch = root.querySelector('.hud-crosshair');
  const chT = root.querySelector('.ch-t'), chB = root.querySelector('.ch-b');
  const chL = root.querySelector('.ch-l'), chR = root.querySelector('.ch-r');
  const hitEl = root.querySelector('.hud-hitmarker');
  const dmgEl = root.querySelector('.hud-dmg-ring');
  const hpBar = root.querySelector('.hud-hp-bar');
  const hpText = root.querySelector('.hud-hp-text');
  const ammoMag = root.querySelector('.hud-ammo-mag');
  const ammoRes = root.querySelector('.hud-ammo-res');
  const killsNum = root.querySelector('.hud-kills-num');
  const feedEl = root.querySelector('.hud-feed');
  const deathEl = root.querySelector('.hud-death');

  // --- состояние (чтобы не трогать DOM без изменений) ---
  let lastHp = -1, lastMax = -1, lastLow = false;
  let lastMag = -1, lastRes = -1, lastEmpty = false;
  let lastKills = -1;
  let spreadRad = 0, spreadPx = 0, lastGap = -1, lastEnemy = false;
  let hitTimer = 0, dmgTimer = 0;
  const feed = []; // {el, t}

  /** Установить полосу здоровья. */
  function setHealth(hp, max) {
    if (hp === lastHp && max === lastMax) return;
    lastHp = hp; lastMax = max;
    const frac = max > 0 ? Math.max(0, hp / max) : 0;
    hpBar.style.width = (frac * 100).toFixed(1) + '%';
    hpText.textContent = hp + ' / ' + max;
    const low = frac <= HP_LOW_FRac;
    if (low !== lastLow) {
      lastLow = low;
      hpBar.style.background = low ? '#ff3b3b' : '#39d353';
    }
  }

  /** Установить счётчик патронов. */
  function setAmmo(mag, reserve) {
    if (mag !== lastMag) {
      lastMag = mag;
      ammoMag.textContent = mag;
      const empty = mag === 0;
      if (empty !== lastEmpty) { lastEmpty = empty; ammoMag.classList.toggle('empty', empty); }
    }
    if (reserve !== lastRes) { lastRes = reserve; ammoRes.textContent = reserve; }
  }

  /**
   * Установить текущий разброс прицела.
   * @param {number} radians — разброс оружия, рад.
   * @param {boolean} [onEnemy=false] — прицел наведён на врага.
   */
  function setSpread(radians, onEnemy = false) {
    spreadRad = radians;
    if (onEnemy !== lastEnemy) { lastEnemy = onEnemy; ch.classList.toggle('enemy', onEnemy); }
  }

  /** Показать hitmarker. @param {boolean} [isKill=false] */
  function hitmarker(isKill = false) {
    hitTimer = HITMARKER_TTL;
    hitEl.classList.toggle('kill', isKill);
    hitEl.style.opacity = '1';
  }

  /** Добавить строку в killfeed. @param {string} text */
  function killfeed(text) {
    const li = document.createElement('li');
    li.textContent = text;
    feedEl.appendChild(li);
    feed.push({ el: li, t: KILLFEED_TTL });
    while (feed.length > KILLFEED_MAX) feed.shift().el.remove();
  }

  /**
   * Индикатор урона по направлению источника.
   * @param {number} dirX — мировой вектор к источнику (X).
   * @param {number} dirZ — мировой вектор к источнику (Z).
   * @param {number} yaw — курс камеры игрока, рад (0 = взгляд в -Z).
   */
  function damageFrom(dirX, dirZ, yaw) {
    const worldAng = Math.atan2(dirX, -dirZ);
    let rel = worldAng - yaw;
    dmgEl.style.transform = 'rotate(' + rel.toFixed(3) + 'rad)';
    dmgEl.style.opacity = '1';
    dmgTimer = DAMAGE_IND_TTL;
  }

  /** Обновить счётчик фрагов. @param {number} count */
  function addKill(count) {
    if (count === lastKills) return;
    lastKills = count;
    killsNum.textContent = count;
  }

  /** Показать экран смерти. onRespawn вызывается по кнопке. */
  function showDeath(onRespawn) {
    deathEl.style.display = 'flex';
    const btn = root.querySelector('.hud-respawn');
    btn.onclick = () => { hideDeath(); if (onRespawn) onRespawn(); };
  }

  /** Скрыть экран смерти. */
  function hideDeath() {
    deathEl.style.display = 'none';
  }

  /**
   * Кадровое обновление плавных элементов HUD.
   * @param {number} dt — секунды.
   */
  function update(dt) {
    // плавный развод прицела
    const target = SPREAD_BASE_PX + spreadRad * SPREAD_SCALE_PX;
    spreadPx += (target - spreadPx) * Math.min(1, SPREAD_LERP * dt);
    const gap = Math.round(spreadPx);
    if (gap !== lastGap) {
      lastGap = gap;
      chT.style.top = (-gap - 10) + 'px';
      chB.style.top = gap + 'px';
      chL.style.left = (-gap - 10) + 'px';
      chR.style.left = gap + 'px';
    }
    // hitmarker
    if (hitTimer > 0) {
      hitTimer -= dt;
      if (hitTimer <= 0) hitEl.style.opacity = '0';
    }
    // индикатор урона
    if (dmgTimer > 0) {
      dmgTimer -= dt;
      if (dmgTimer <= 0) dmgEl.style.opacity = '0';
    }
    // killfeed TTL
    for (let i = feed.length - 1; i >= 0; i--) {
      const f = feed[i];
      f.t -= dt;
      if (f.t <= 0) { f.el.remove(); feed.splice(i, 1); }
      else if (f.t < 0.4 && !f.fading) { f.fading = true; f.el.style.opacity = '0'; }
    }
  }

  return { setHealth, setAmmo, setSpread, hitmarker, killfeed, damageFrom, addKill, showDeath, hideDeath, update };
}
