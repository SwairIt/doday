import { build } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';
await build({
  entryPoints: ['motion-entry.js'],
  outfile: '../../app/static/vendor/motion-14.8.0.min.js',
  bundle: true,
  format: 'esm',
  minify: true,
  target: ['es2020'],
  legalComments: 'eof',
});
const notices = [];
for (const name of ['motion', 'framer-motion', 'motion-dom', 'motion-utils']) {
  notices.push(`${name}\n${await readFile(`node_modules/${name}/LICENSE.md`, 'utf8')}`);
}
await writeFile('../../app/static/vendor/motion.LICENSE.txt', notices.join('\n\n'));
