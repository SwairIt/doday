// The page and native video controls work without the animation package.
const menuButton = document.getElementById('landing-menu-toggle');
const menu = document.getElementById('landing-mobile-menu');
if (menuButton && menu) {
  const closeMenu = () => {
    menu.hidden = true;
    menuButton.setAttribute('aria-expanded', 'false');
    menuButton.setAttribute('aria-label', 'Открыть меню');
  };
  menuButton.addEventListener('click', () => {
    const opening = menu.hidden;
    menu.hidden = !opening;
    menuButton.setAttribute('aria-expanded', String(opening));
    menuButton.setAttribute('aria-label', opening ? 'Закрыть меню' : 'Открыть меню');
  });
  menu.addEventListener('click', event => { if (event.target.closest('a')) closeMenu(); });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !menu.hidden) { closeMenu(); menuButton.focus(); }
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.lp-header')) closeMenu();
  });
  matchMedia('(min-width:961px)').addEventListener('change', closeMenu);
  menuButton.hidden = false;
}

document.querySelectorAll('[data-gallery-theme]').forEach(button => {
  button.addEventListener('click', () => {
    const theme = button.dataset.galleryTheme;
    document.querySelectorAll('[data-gallery-theme]').forEach(control => {
      control.setAttribute('aria-pressed', String(control === button));
    });
    ['light', 'dark'].forEach(name => { document.getElementById(`gallery-${name}`).hidden = theme !== name; });
  });
});

const video = document.getElementById('landing-video');
const playButton = document.getElementById('landing-video-start');
if (video && playButton) {
  playButton.addEventListener('click', async () => {
    try {
      if (!video.getAttribute('src')) {
        // Safari may ignore preload=none. No source means no eager media load.
        video.src = video.dataset.src;
        video.tabIndex = 0;
        video.load();
      }
      await video.play();
      playButton.hidden = true;
      video.focus({ preventScroll: true });
    } catch (_) {
      // Keep the browser's own controls available if playback is refused.
      playButton.hidden = true;
      video.focus();
    }
  });
  video.addEventListener('play', () => { playButton.hidden = true; });
  video.addEventListener('ended', () => { playButton.hidden = false; });
  video.addEventListener('error', () => { playButton.hidden = true; });
  playButton.hidden = false;
}

// Enhancement only: no initially invisible content or scroll interception.
if (!matchMedia('(prefers-reduced-motion:reduce)').matches && !navigator.connection?.saveData) {
  import('./vendor/motion-14.8.0.min.js').then(({ animate, inView }) => {
    inView('[data-landing-reveal]', element => {
      animate(element, { opacity: [0.78, 1], y: [10, 0] }, { duration: 0.45, ease: [0.22, 1, 0.36, 1] });
    }, { amount: 0.12 });
  }).catch(() => { /* The complete static layout remains visible. */ });
}
