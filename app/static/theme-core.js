(() => {
  const root = document.documentElement;
  const script = document.currentScript;
  const serverNow = Number(script?.dataset.serverNow);
  const started = Date.now();
  const now = () => (Number.isFinite(serverNow) && serverNow > 0 ? serverNow : started) + Date.now() - started;
  const modes = ['schedule', 'system', 'light', 'dark'];
  const keys = {mode:'doday-theme', lightStart:'doday-theme-light-start', darkStart:'doday-theme-dark-start'};
  const defaults = {mode:'schedule', lightStart:'09:00', darkStart:'19:00'};
  const cookies = () => Object.fromEntries(document.cookie.split(';').map(v => v.trim().split('=')));
  const validTime = value => typeof value === 'string' && /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
  let memory = {};
  let timer;
  let reloading = false;
  const read = () => {
    const saved = cookies();
    const result = {};
    for (const [name, key] of Object.entries(keys)) {
      let value = memory[name] || saved[key];
      try { value = localStorage.getItem(key) || value; } catch (_) {}
      result[name] = (name === 'mode' ? modes.includes(value) : validTime(value)) ? value : defaults[name];
    }
    if (result.lightStart === result.darkStart) Object.assign(result, {lightStart:'09:00', darkStart:'19:00'});
    return result;
  };
  const writeCookie = (key, value) => {
    const secure = location.protocol === 'https:' ? '; Secure' : '';
    document.cookie = `${key}=${value}; Path=/; Max-Age=31536000; SameSite=Lax${secure}`;
  };
  const system = matchMedia('(prefers-color-scheme: dark)');
  const moscow = new Intl.DateTimeFormat('en-GB', {timeZone:'Europe/Moscow', hour:'2-digit', minute:'2-digit', hourCycle:'h23'});
  const minutes = value => Number(value.slice(0,2)) * 60 + Number(value.slice(3));
  const resolve = config => {
    if (config.mode === 'light' || config.mode === 'dark') return config.mode;
    if (config.mode === 'system') return system.matches ? 'dark' : 'light';
    const current = minutes(moscow.format(new Date(now())));
    const light = minutes(config.lightStart), dark = minutes(config.darkStart);
    const day = light < dark ? current >= light && current < dark : current >= light || current < dark;
    return day ? 'light' : 'dark';
  };
  const apply = () => {
    clearTimeout(timer);
    const config = read();
    const resolved = resolve(config);
    root.dataset.theme = resolved;
    root.dataset.themeMode = config.mode;
    root.style.colorScheme = resolved;
    for (const [name,key] of Object.entries(keys)) writeCookie(key,config[name]);
    writeCookie('doday-system-theme', system.matches ? 'dark' : 'light');
    document.dispatchEvent(new CustomEvent('doday:themechange',{detail:{...config,resolved}}));
    const variant = root.dataset.landingVariant;
    if (variant && (variant === 'day') !== (resolved === 'light') && !reloading && cookies()['doday-theme'] === config.mode) {
      reloading = true;
      location.reload();
    }
    if (config.mode === 'schedule') {
      const current = now();
      const minute = minutes(moscow.format(new Date(current)));
      const boundary = minutes(resolved === 'light' ? config.darkStart : config.lightStart);
      const remaining = ((boundary - minute + 1440) % 1440) * 60000 - (current % 60000);
      timer = setTimeout(apply, Math.max(100, remaining + 50));
    }
  };
  const set = config => {
    if (!modes.includes(config.mode) || !validTime(config.lightStart) || !validTime(config.darkStart) || config.lightStart === config.darkStart) return false;
    memory = {...config};
    for (const [name,key] of Object.entries(keys)) {
      try { localStorage.setItem(key,config[name]); } catch (_) {}
      writeCookie(key,config[name]);
    }
    apply();
    return true;
  };
  window.dodayAppearance = {read,set,apply,resolve};
  window.dodayApplyTheme = apply;
  system.addEventListener('change',apply);
  window.addEventListener('storage',event => { if (Object.values(keys).includes(event.key) || event.key === null) { memory = {}; apply(); } });
  window.addEventListener('pageshow',apply);
  document.addEventListener('visibilitychange',() => { if (!document.hidden) apply(); });
  apply();
})();
