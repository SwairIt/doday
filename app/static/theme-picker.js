(() => {
  const dialog = document.getElementById('appearance-dialog');
  const form = document.getElementById('appearance-form');
  const api = window.dodayAppearance;
  if (!dialog || !form || !api) return;
  const light = form.querySelector('[name="light-start"]');
  const dark = form.querySelector('[name="dark-start"]');
  const schedule = document.getElementById('appearance-schedule');
  const error = document.getElementById('appearance-error');
  let opener;
  const syncSchedule = () => {
    const active = form.elements.namedItem('appearance-mode').value === 'schedule';
    schedule.hidden = !active;
    light.disabled = dark.disabled = !active;
    error.hidden = true;
  };
  const fill = () => {
    const config = api.read();
    form.elements.namedItem('appearance-mode').value = config.mode;
    light.value = config.lightStart;
    dark.value = config.darkStart;
    syncSchedule();
  };
  const updateButtons = () => {
    const names = {schedule:'по расписанию',system:'как на устройстве',light:'светлая',dark:'тёмная'};
    const icons = {
      schedule:'<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
      system:'<rect x="3" y="4" width="18" height="13" rx="2"/><path d="M8 21h8m-4-4v4"/>',
      light:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
      dark:'<path d="M20.5 15.5A9 9 0 0 1 8.5 3.5a9 9 0 1 0 12 12Z"/>'
    };
    const mode = api.read().mode;
    document.querySelectorAll('[data-theme-open]').forEach(button => {
      button.title = `Тема: ${names[mode]}`;
      const icon = button.querySelector('svg');
      if (icon) icon.innerHTML = icons[mode];
    });
  };
  const close = () => dialog.close();
  document.addEventListener('click',event => {
    const button = event.target.closest('[data-theme-open]');
    if (button) { opener = button; fill(); dialog.showModal(); }
    if (event.target.closest('[data-theme-close]')) close();
    if (event.target.closest('[data-theme-reset]')) { light.value = '09:00'; dark.value = '19:00'; error.hidden = true; }
  });
  dialog.addEventListener('click',event => { if (event.target === dialog && (event.offsetX < 0 || event.offsetX > dialog.clientWidth || event.offsetY < 0 || event.offsetY > dialog.clientHeight)) close(); });
  dialog.addEventListener('close',() => opener?.focus({preventScroll:true}));
  form.addEventListener('change',syncSchedule);
  form.addEventListener('submit',event => {
    event.preventDefault();
    const mode = form.elements.namedItem('appearance-mode').value;
    const times = mode === 'schedule' ? {lightStart:light.value,darkStart:dark.value} : api.read();
    if (mode === 'schedule' && times.lightStart === times.darkStart) { error.hidden = false; light.focus(); return; }
    if (api.set({...times,mode})) close();
  });
  document.addEventListener('doday:themechange',updateButtons);
  updateButtons();
})();
