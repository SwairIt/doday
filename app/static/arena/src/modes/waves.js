// src/modes/waves.js — режим раундов: волны ботов поверх спавнера и HUD.

// Все длительности в секундах, размеры в константах
const PREPARE_TIME = 5; // пауза между раундами
const BANNER_TIME = 1.5; // показ крупной надписи
const BASE_BOTS = 3; // ботов в первом раунде
const BOTS_PER_ROUND = 2; // прирост за раунд
const HEALTH_SCALE_PER_ROUND = 0.12; // +12% здоровья за раунд
const INTERVAL_SCALE_PER_ROUND = 0.92; // интервал подспавна короче на 8%
const BANNER_FADE = 0.5; // длительность затухания надписи (хвост показа)

// Базовый стиль DOM-элементов (тёмная тема)
const OVERLAY_FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif';

/**
 * Создаёт DOM-подпись поверх canvas, ничего не перекрывает центр.
 * @param {HTMLElement} container
 * @param {string} top смещение сверху (CSS)
 */
function makeLabel(container, top) {
  const el = document.createElement('div');
  el.style.cssText =
    `position:absolute;left:50%;top:${top};transform:translateX(-50%);` +
    `font-family:${OVERLAY_FONT};color:#fff;background:rgba(10,12,16,0.55);` +
    'border-radius:10px;padding:6px 18px;pointer-events:none;' +
    'text-align:center;opacity:0;white-space:nowrap;' +
    'text-shadow:0 1px 3px rgba(0,0,0,0.7);';
  container.appendChild(el);
  return el;
}

/**
 * Создаёт режим волн.
 * @param {object} deps {spawner, hud, audio, player, settings, container}
 */
export function createWaveMode(deps) {
  const { spawner, hud, audio, player, container } = deps;

  // DOM-слой режима
  const banner = makeLabel(container, '22%'); // крупная надпись выше прицела
  banner.style.fontSize = 'clamp(28px, 6vw, 56px)';
  banner.style.fontWeight = '800';
  banner.style.padding = '14px 34px';

  const countdown = makeLabel(container, '36%'); // отсчёт под надписью
  countdown.style.fontSize = 'clamp(16px, 3vw, 26px)';
  countdown.style.fontWeight = '600';

  const statusLine = makeLabel(container, '8px'); // постоянная строка сверху
  statusLine.style.fontSize = 'clamp(13px, 2vw, 18px)';
  statusLine.style.fontWeight = '500';

  // Состояние режима
  const state = {
    phase: 'prepare', // 'prepare' | 'fighting' | 'cleared'
    round: 0, // текущий раунд (будет 1 на старте первого)
    enemiesLeft: 0, // ещё не заспавнено/не убито
    phaseTime: 0, // время внутри текущей фазы
    toSpawn: 0, // сколько ботов раунда осталось выпустить
    difficulty: 1, // множитель здоровья ботов
    spawnInterval: 0, // текущий интервал подспавна
    spawnTimer: 0, // накопленное время с последнего подспавна
    running: false,
  };

  /** Число ботов в раунде N. */
  function botsForRound(round) {
    return BASE_BOTS + round * BOTS_PER_ROUND;
  }

  /** Показать DOM-элемент с текстом и прозрачностью. */
  function showLabel(el, text, opacity) {
    el.textContent = text;
    el.style.opacity = opacity.toFixed(3);
  }

  function hideLabel(el) {
    el.style.opacity = '0';
    // Чистим и текст: иначе он остаётся в дереве и читается скринридером.
    if (el.textContent) el.textContent = '';
  }

  /** Прозрачность баннера: полная, затем плавное затухание в конце показа. */
  function bannerOpacity(t) {
    const fadeStart = BANNER_TIME - BANNER_FADE;
    if (t <= fadeStart) return 1;
    return Math.max(0, 1 - (t - fadeStart) / BANNER_FADE);
  }

  /** Прокинуть сложность в спавнер, если он её принимает. */
  function applyDifficulty() {
    state.difficulty = 1 + (state.round - 1) * HEALTH_SCALE_PER_ROUND;
    state.spawnInterval = 1.5 * Math.pow(INTERVAL_SCALE_PER_ROUND, state.round - 1);
    if (typeof spawner.setDifficulty === 'function') {
      spawner.setDifficulty(state.difficulty, state.spawnInterval);
    }
  }

  /** Переход в фазу prepare (конец предыдущего раунда или старт игры). */
  function enterPrepare() {
    state.phase = 'prepare';
    state.phaseTime = 0;
    state.round += 1;
    applyDifficulty();
    hideLabel(statusLine);
    hideLabel(countdown);
  }

  /** Начало боя: спавним всю волну сразу первым вызовом, дальше добиваем по таймеру. */
  function enterFighting() {
    state.phase = 'fighting';
    state.phaseTime = 0;
    state.toSpawn = botsForRound(state.round);
    state.enemiesLeft = state.toSpawn;
    state.spawnTimer = state.spawnInterval; // первый заход сразу
    if (audio && typeof audio.play === 'function') audio.play('wave-start');
    hideLabel(banner);
    hideLabel(countdown);
  }

  /** Раунд зачищен. */
  function enterCleared() {
    state.phase = 'cleared';
    state.phaseTime = 0;
    if (audio && typeof audio.play === 'function') audio.play('wave-clear');
    showLabel(banner, `РАУНД ${state.round} ЗАЧИЩЕН`, 1);
    hideLabel(statusLine);
  }

  /** Выпускаем ботов, сколько позволяет спавнер. Возвращает, сколько осталось. */
  function trySpawn(count) {
    const playerPos = player && player.position ? player.position : player;
    const fov = deps.settings ? deps.settings.fov : 90;
    const forward = player && player.forward ? player.forward : null;
    // Сигнатура строгая: spawnWave(count, playerPos, fov, forward)
    const spawned = spawner.spawnWave(count, playerPos, fov, forward);
    return count - spawned;
  }

  /**
   * Запуск режима с первого раунда.
   */
  function start() {
    state.round = 0;
    state.running = true;
    enterPrepare();
  }

  /**
   * Полный сброс режима и интерфейса.
   */
  function reset() {
    state.phase = 'prepare';
    state.round = 0;
    state.enemiesLeft = 0;
    state.phaseTime = 0;
    state.toSpawn = 0;
    state.difficulty = 1;
    state.spawnInterval = 1.5;
    state.spawnTimer = 0;
    state.running = false;
    hideLabel(banner);
    hideLabel(countdown);
    hideLabel(statusLine);
  }

  /**
   * Обновление режима. Все времена — накопленный dt, без setInterval.
   * @param {number} dt секунды
   */
  function update(dt) {
    if (!state.running) return;
    state.phaseTime += dt;

    if (state.phase === 'prepare') {
      // Баннер «РАУНД N» первые 1.5 секунды, затем гаснет
      if (state.phaseTime <= BANNER_TIME) {
        showLabel(banner, `РАУНД ${state.round}`, bannerOpacity(state.phaseTime));
      } else {
        hideLabel(banner);
      }
      // Обратный отсчёт до боя
      const left = Math.max(0, Math.ceil(PREPARE_TIME - state.phaseTime));
      showLabel(countdown, `Бой начнётся через ${left}`, 0.95);
      if (state.phaseTime >= PREPARE_TIME) {
        enterFighting();
      }
      return;
    }

    if (state.phase === 'fighting') {
      // Доспавн остатка волны с убывающим интервалом
      if (state.toSpawn > 0) {
        state.spawnTimer += dt;
        if (state.spawnTimer >= state.spawnInterval) {
          state.spawnTimer = 0;
          state.toSpawn = trySpawn(state.toSpawn);
        }
      }
      // Живые боты + ещё не выпущенные = осталось в раунде
      state.enemiesLeft = spawner.alive + state.toSpawn;
      showLabel(statusLine, `Раунд ${state.round} · осталось ${state.enemiesLeft}`, 0.95);
      // Зачистка: все выпущены и все мертвы
      if (state.toSpawn === 0 && spawner.alive === 0) {
        enterCleared();
      }
      return;
    }

    if (state.phase === 'cleared') {
      // Баннер зачистки 1.5 секунды с затуханием
      if (state.phaseTime <= BANNER_TIME) {
        showLabel(banner, `РАУНД ${state.round} ЗАЧИЩЕН`, bannerOpacity(state.phaseTime));
      } else if (state.phaseTime >= PREPARE_TIME) {
        enterPrepare(); // следующий раунд
      } else {
        hideLabel(banner);
      }
    }
  }

  return {
    update,
    start,
    reset,
    get round() { return state.round; },
    get enemiesLeft() { return state.enemiesLeft; },
    get phase() { return state.phase; },
    get difficulty() { return state.difficulty; },
  };
}
