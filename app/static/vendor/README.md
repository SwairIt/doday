# Browser dependencies

Pinned, unmodified upstream files served locally so slow or blocked public CDNs
do not prevent the mobile interface from rendering or responding.

| File | Upstream source |
|---|---|
| tailwind-3.4.17.js | https://cdn.tailwindcss.com/3.4.17 |
| htmx-2.0.4.min.js | https://cdn.jsdelivr.net/npm/htmx.org@2.0.4/dist/htmx.min.js |
| alpine-3.14.7.min.js | https://cdn.jsdelivr.net/npm/alpinejs@3.14.7/dist/cdn.min.js |
| sortable-1.15.6.min.js | https://cdn.jsdelivr.net/npm/sortablejs@1.15.6/Sortable.min.js |
| qrcode-1.4.4.js | https://cdn.jsdelivr.net/npm/qrcode-generator@1.4.4/qrcode.js |
| confetti-1.9.2.min.js | https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.2/dist/confetti.browser.min.js |
| motion-14.8.0.min.js | https://github.com/motiondivision/motion (tree-shaken `animate` and `inView`, MIT) |

Licenses are stored alongside the files. Tailwind remains the existing runtime
compiler, preserving dynamically generated Jinja and Alpine classes without a
new frontend build requirement. When upgrading, use a new versioned filename,
update the relevant template references, and verify all product themes.

The Motion bundle is built by `media/landing-demo/build-motion.mjs` using pinned
dependencies. It is loaded as an optional enhancement by `landing.js`; menu,
gallery and video controls do not depend on it. The landing honors reduced
motion and save-data preferences and has no initially hidden content.

Inter font subsets and their license are in `../fonts/`. Only Latin and Cyrillic
subsets are included; weights 400–800 share the same three WOFF2 files.
