# Doday landing video and motion

Reproducible source for the 15 s, 1920 × 1080, silent landing demonstration.
Actual Doday screens were recorded in an isolated local database with fictional
tasks. Public assets contain no customer records or session cookies.

```powershell
npm ci
npm run check
npx hyperframes@0.8.220 snapshot --review
npx hyperframes@0.8.220 preview --background
npm run render -- --quality delivery --output ../../app/static/landing/doday-in-action.mp4
node build-motion.mjs
```

HyperFrames can discover system Chrome and FFmpeg. The project keeps the exact
CLI version; future upgrades must pass the full check and a frame review.

- [HyperFrames](https://github.com/heygen-com/hyperframes), 0.8.220: editable
  HTML compositions, deterministic GSAP timelines and MP4 rendering.
- [Motion](https://github.com/motiondivision/motion), 14.8.0, MIT: only `animate`
  and `inView` are bundled into the site's optional local ES module.
- [GSAP](https://gsap.com/): pinned 3.14.2 in `assets/gsap.min.js`, used in the
  authoring project, not loaded by the landing page.
- The installed `ui-focus-zoom` registry source is kept in
  `compositions/components/`; the tour adapts its single-world camera approach
  around a genuine recording rather than its default skeleton UI.
- Inter subsets are copied from the website, under the same OFL license.

`assets/product-flow.mp4` is the trimmed, lightly accelerated source recording.
`capture.webm` and `.hyperframes/` are local source/review artifacts and ignored.
`SPEC.md` and `REVIEW.md` record the chosen design and checks.

The installer advertised 0.8.221 but npm returned ETARGET, so this project pins
the available 0.8.220. A transitive Undici security fix is pinned with an override.
Node/video tooling is confined to this directory; the FastAPI deployment does
not install it. Only finished assets and the Motion browser bundle are served.
