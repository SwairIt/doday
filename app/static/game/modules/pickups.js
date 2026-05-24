/**
 * Meme pickups — floating диски с эмодзи, разбросанные по миру.
 * После сбора всех → respawn'аются на новых случайных позициях (бесконечно).
 */
import * as THREE from 'three';

export const MEMES = [
  { id: '67',          emoji: '6️⃣7️⃣', label: 'Six Seven',         desc: 'Тыщ-тыщ. Шесть-семь. Ты в моменте.', color: 0xfbbf24, points: 67, special: true },
  { id: 'coconut',     emoji: '🥥',     label: 'Кокос Воды',         desc: 'Главный coconut стрим-вайбов.',       color: 0x92400e, points: 10 },
  { id: 'sigma',       emoji: 'Σ',      label: 'Sigma',               desc: 'Грайндсет. Альфа-male energy.',       color: 0xfafafa, points: 10 },
  { id: 'skibidi',     emoji: '🚽',     label: 'Skibidi',             desc: 'Toilet. Brainrot grade 10.',           color: 0xd1d5db, points: 10 },
  { id: 'rizz',        emoji: '😎',     label: 'Rizz',                desc: 'W rizz. Pulled the baddies.',          color: 0xec4899, points: 10 },
  { id: 'cap',         emoji: '🧢',     label: 'No Cap',              desc: 'On god, no cap fr fr.',                 color: 0xef4444, points: 10 },
  { id: 'sus',         emoji: '🔺',     label: 'Sus',                 desc: 'Among us. Кто-то сус.',                color: 0xdc2626, points: 10 },
  { id: 'bruh',        emoji: '💀',     label: 'Bruh',                desc: 'Skull emoji. Я мёртв со смеху.',       color: 0xe5e7eb, points: 10 },
  { id: 'gyatt',       emoji: '🍑',     label: 'Gyatt',               desc: 'GYATT. Brainrot уровень дзен.',        color: 0xfdba74, points: 10 },
  { id: 'ohio',        emoji: '🌽',     label: 'Ohio',                desc: 'Only in Ohio. Только в Огайо.',        color: 0xeab308, points: 10 },
  { id: 'fanum',       emoji: '🍔',     label: 'Fanum Tax',           desc: 'Steal a bite. Это Fanum tax.',         color: 0xd97706, points: 10 },
  { id: 'mewing',      emoji: '🦴',     label: 'Mewing',              desc: 'Jawline maxxing. Закрой рот.',         color: 0xfafafa, points: 10 },
  { id: 'goida',       emoji: '⚔️',     label: 'Гойда',                desc: 'Старослав-боевой клич.',              color: 0xb91c1c, points: 10 },
  { id: 'vmomente',    emoji: '🔥',     label: 'В моменте',           desc: 'Стримерская концентрация.',            color: 0xf97316, points: 10 },
  { id: 'roll',        emoji: '🎰',     label: 'Roll',                desc: 'Крути слоты.',                         color: 0xa78bfa, points: 10 },
  { id: 'aura',        emoji: '✨',     label: 'Aura +1000',          desc: 'Massive aura points.',                color: 0xc4b5fd, points: 10 },
  { id: 'pookie',      emoji: '🐻',     label: 'Pookie',              desc: 'Delulu is the solulu.',                color: 0xf472b6, points: 10 },
];

export function spawnPickups(scene, halfSize, existingPickups = []) {
  const created = [];
  for (const meme of MEMES) {
    let x, z, tries = 0;
    do {
      x = (Math.random() - 0.5) * (halfSize * 2 - 6);
      z = (Math.random() - 0.5) * (halfSize * 2 - 6);
      tries++;
    } while ((Math.abs(x) < 4 && Math.abs(z) < 4) && tries < 20);

    const group = new THREE.Group();
    const baseMat = new THREE.MeshStandardMaterial({
      color: meme.color,
      emissive: meme.color,
      emissiveIntensity: 0.6,
      metalness: 0.5,
      roughness: 0.4,
    });
    const base = new THREE.Mesh(
      new THREE.CylinderGeometry(0.4, 0.5, 0.15, 16),
      baseMat
    );
    base.castShadow = true;
    group.add(base);

    const emojiCanvas = document.createElement('canvas');
    emojiCanvas.width = 256;
    emojiCanvas.height = 256;
    const ectx = emojiCanvas.getContext('2d');
    ectx.font = '170px sans-serif';
    ectx.textAlign = 'center';
    ectx.textBaseline = 'middle';
    ectx.fillText(meme.emoji, 128, 145);
    const emojiTex = new THREE.CanvasTexture(emojiCanvas);
    const billboard = new THREE.Mesh(
      new THREE.PlaneGeometry(0.9, 0.9),
      new THREE.MeshBasicMaterial({ map: emojiTex, transparent: true, depthWrite: false })
    );
    billboard.position.y = 1.2;
    group.add(billboard);

    group.position.set(x, 0.1, z);
    group.userData = { meme, billboard, baseY: 0.1, spawnTime: performance.now() };
    scene.add(group);
    created.push(group);
  }
  return created;
}

export function updatePickups(pickups, dt, cameraPos) {
  for (const p of pickups) {
    const t = (performance.now() - p.userData.spawnTime) * 0.001;
    p.position.y = p.userData.baseY + Math.sin(t * 2) * 0.15 + 0.5;
    p.rotation.y += dt * 0.8;
    if (p.userData.billboard) {
      p.userData.billboard.lookAt(cameraPos);
    }
  }
}
