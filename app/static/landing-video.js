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
