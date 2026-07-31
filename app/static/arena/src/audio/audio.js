/**
 * Звуковая система Doday Arena.
 * Весь звук синтезируется WebAudio API на лету — без единого файла.
 * Позиционирование через PannerNode (HRTF), пул источников ограничен,
 * контекст автоматически резюмится после первого взаимодействия пользователя.
 */

/** Максимум одновременно звучащих источников (защита мобильных CPU). */
const MAX_VOICES = 24;

/** Дистанционная модель паннеров. */
const PANNER_MODEL = 'inverse';
/** Опорная дистанция позиционных источников, м. */
const PANNER_REF_DIST = 2;
/** Полная тишина за этой дистанцией при генерации источников, м. */
const CULL_DISTANCE = 80;

/** Длительность нойз-буфера, с. */
const NOISE_BUFFER_SECONDS = 1.0;

/** Период пульса эмбиента города, с. */
const AMBIENT_LFO_FREQ = 0.08;

// ---------- Модульные временные объекты (без аллокаций в цикле) ----------

const _panDefaults = {
  panningModel: 'HRTF',
  distanceModel: PANNER_MODEL,
  refDistance: PANNER_REF_DIST,
  rolloffFactor: 1,
};

/**
 * Создаёт генератор белого шума в виде AudioBuffer (один на весь контекст).
 * @param {AudioContext} ctx
 * @returns {AudioBuffer}
 */
function makeNoiseBuffer(ctx) {
  const len = Math.floor(ctx.sampleRate * NOISE_BUFFER_SECONDS);
  const buf = ctx.createBuffer(1, len, ctx.sampleRate);
  const data = buf.getChannelData(0);
  for (let i = 0; i < len; i++) data[i] = Math.random() * 2 - 1;
  return buf;
}

/**
 * Создаёт звуковую подсистему.
 * @param {object} listener — совместимый слушатель (не используется напрямую,
 *   ориентация задаётся через setListener; параметр оставлен по контракту).
 * @returns {{
 *   play: (name: string, position?: object|null, volume?: number) => void,
 *   setListener: (pos: {x:number,y:number,z:number}, forward: {x:number,y:number,z:number}) => void,
 *   setMasterVolume: (v: number) => void,
 *   resume: () => void
 * }}
 */
export function createAudio(listener) {
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const noiseBuffer = makeNoiseBuffer(ctx);

  // Мастер-шина: все звуки -> master -> destination
  const master = ctx.createGain();
  master.gain.value = 1;
  master.connect(ctx.destination);

  // Пул активных голосов для ограничения нагрузки
  const voices = new Set();

  // ---------- Служебные ----------

  /**
   * Регистрирует источник в пуле голосов; при переполнении — отказ.
   * @param {AudioScheduledSourceNode} node
   * @returns {boolean} false, если пул переполнен
   */
  function addVoice(node) {
    if (voices.size >= MAX_VOICES) return false;
    voices.add(node);
    node.onended = () => { voices.delete(node); };
    return true;
  }

  /**
   * Создаёт цепочку вывода: [panner?] -> gain(volume) -> master.
   * Возвращает входную точку цепочки (куда подключать источник).
   * @param {object|null} position {x,y,z} или null для непозиционного звука
   * @param {number} volume 0..1
   * @returns {AudioNode|null} null, если источник за дистанцией отсечения
   */
  function makeOutput(position, volume) {
    let head = null;
    if (position) {
      const l = ctx.listener;
      const dx = position.x - _listenerPos.x;
      const dy = position.y - _listenerPos.y;
      const dz = position.z - _listenerPos.z;
      if (dx * dx + dy * dy + dz * dz > CULL_DISTANCE * CULL_DISTANCE) return null;
      head = ctx.createPanner();
      Object.assign(head, _panDefaults);
      head.positionX.value = position.x;
      head.positionY.value = position.y;
      head.positionZ.value = position.z;
    }
    const gain = ctx.createGain();
    gain.gain.value = volume;
    if (head) head.connect(gain);
    gain.connect(master);
    return head || gain;
  }

  // Кэш позиции слушателя для дистанционного отсечения
  const _listenerPos = { x: 0, y: 0, z: 0 };

  /**
   * Непозиционный источник шума через фильтр с огибающей.
   */
  function spawnNoise(position, volume, filterType, filterFreq, attack, decay, peak, q = 1) {
    const out = makeOutput(position, volume);
    if (!out) return;
    const src = ctx.createBufferSource();
    src.buffer = noiseBuffer;
    src.loop = true;
    if (!addVoice(src)) return;
    const flt = ctx.createBiquadFilter();
    flt.type = filterType;
    flt.frequency.value = filterFreq;
    flt.Q.value = q;
    const env = ctx.createGain();
    const t = ctx.currentTime;
    env.gain.setValueAtTime(0.0001, t);
    env.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0001), t + attack);
    env.gain.exponentialRampToValueAtTime(0.0001, t + attack + decay);
    src.connect(flt);
    flt.connect(env);
    env.connect(out);
    src.start(t);
    src.stop(t + attack + decay + 0.05);
  }

  /**
   * Осциллятор с экспоненциальной огибающей громкости и скольжением частоты.
   */
  function spawnTone(position, volume, type, f0, f1, attack, decay, peak, delay = 0) {
    const out = makeOutput(position, volume);
    if (!out) return;
    const osc = ctx.createOscillator();
    if (!addVoice(osc)) return;
    osc.type = type;
    const t = ctx.currentTime + delay;
    osc.frequency.setValueAtTime(f0, t);
    osc.frequency.exponentialRampToValueAtTime(Math.max(f1, 1), t + attack + decay);
    const env = ctx.createGain();
    env.gain.setValueAtTime(0.0001, t);
    env.gain.exponentialRampToValueAtTime(Math.max(peak, 0.0001), t + attack);
    env.gain.exponentialRampToValueAtTime(0.0001, t + attack + decay);
    osc.connect(env);
    env.connect(out);
    osc.start(t);
    osc.stop(t + attack + decay + 0.05);
  }

  // ---------- Звуки ----------

  const synth = {
    /** Выстрел: резкий шум + низкочастотный удар. */
    shot(position, volume) {
      spawnNoise(position, volume, 'highpass', 800, 0.002, 0.12, 1.0);
      spawnTone(position, volume, 'sine', 120, 40, 0.002, 0.14, 0.9);
    },
    /** Попадание в цель: короткий металлический тук. */
    hit(position, volume) {
      spawnTone(position, volume, 'square', 900, 500, 0.001, 0.07, 0.6);
      spawnNoise(position, volume * 0.6, 'bandpass', 2500, 0.001, 0.05, 0.5, 2);
    },
    /** Рикошет: звон с падающим тоном. */
    ricochet(position, volume) {
      const f = 1800 + Math.random() * 1200;
      spawnTone(position, volume, 'sine', f, f * 0.4, 0.001, 0.25, 0.5);
    },
    /** Шаг: фильтрованный шум со случайной вариацией тона. */
    step(position, volume) {
      const f = 300 + Math.random() * 250;
      spawnNoise(position, volume, 'bandpass', f, 0.004, 0.09, 0.8, 1.5);
    },
    /** Перезарядка: три щелчка. */
    reload(position, volume) {
      spawnTone(position, volume, 'square', 2200, 1600, 0.001, 0.03, 0.35, 0);
      spawnTone(position, volume, 'square', 1400, 1000, 0.001, 0.04, 0.4, 0.22);
      spawnTone(position, volume, 'square', 2600, 1900, 0.001, 0.03, 0.35, 0.5);
    },
  };

  // ---------- Эмбиент города ----------

  let ambientStarted = false;

  /** Запускает постоянный низкочастотный гул города (однократно). */
  function startAmbient() {
    if (ambientStarted) return;
    ambientStarted = true;
    const gain = ctx.createGain();
    gain.gain.value = 0.06;
    // Медленная пульсация гула
    const lfo = ctx.createOscillator();
    lfo.frequency.value = AMBIENT_LFO_FREQ;
    const lfoGain = ctx.createGain();
    lfoGain.gain.value = 0.025;
    lfo.connect(lfoGain);
    lfoGain.connect(gain.gain);
    // Низкочастотный шум
    const noise = ctx.createBufferSource();
    noise.buffer = noiseBuffer;
    noise.loop = true;
    const lp = ctx.createBiquadFilter();
    lp.type = 'lowpass';
    lp.frequency.value = 140;
    noise.connect(lp);
    lp.connect(gain);
    // Медленный гудящий саб-тон
    const sub = ctx.createOscillator();
    sub.type = 'sine';
    sub.frequency.value = 55;
    const subGain = ctx.createGain();
    subGain.gain.value = 0.5;
    sub.connect(subGain);
    subGain.connect(gain);
    gain.connect(master);
    noise.start();
    sub.start();
    lfo.start();
    // Эмбиент — постоянные узлы, голоса не считаем
  }

  // ---------- Авто-резюм по первому взаимодействию ----------

  /** Гарантированно активирует контекст (вызывается и по событию, и вручную). */
  function resume() {
    if (ctx.state === 'suspended') ctx.resume();
    startAmbient();
  }
  const onGesture = () => resume();
  window.addEventListener('pointerdown', onGesture);
  window.addEventListener('keydown', onGesture);

  // ---------- Публичный API ----------

  return {
    /**
     * Проигрывает звук по имени.
     * @param {'shot'|'hit'|'ricochet'|'step'|'reload'} name
     * @param {object|null} [position] — {x,y,z} мировой позиции, null = UI-звук
     * @param {number} [volume]
     */
    play(name, position = null, volume = 1) {
      if (ctx.state !== 'running') return;
      const fn = synth[name];
      if (fn) fn(position, Math.min(Math.max(volume, 0), 1));
    },
    /**
     * Обновляет позицию и ориентацию слушателя.
     * @param {{x:number,y:number,z:number}} pos
     * @param {{x:number,y:number,z:number}} forward — направление взгляда (нормированное)
     */
    setListener(pos, forward) {
      _listenerPos.x = pos.x;
      _listenerPos.y = pos.y;
      _listenerPos.z = pos.z;
      const l = ctx.listener;
      if (l.positionX) {
        l.positionX.value = pos.x;
        l.positionY.value = pos.y;
        l.positionZ.value = pos.z;
        l.forwardX.value = forward.x;
        l.forwardY.value = forward.y;
        l.forwardZ.value = forward.z;
        l.upX.value = 0;
        l.upY.value = 1;
        l.upZ.value = 0;
      } else {
        l.setPosition(pos.x, pos.y, pos.z);
        l.setOrientation(forward.x, forward.y, forward.z, 0, 1, 0);
      }
    },
    /**
     * Мастер-громкость 0..1.
     * @param {number} v
     */
    setMasterVolume(v) {
      master.gain.value = Math.min(Math.max(v, 0), 1);
    },
    /** Вручную реанимирует контекст (если жест уже был). */
    resume,
  };
}
