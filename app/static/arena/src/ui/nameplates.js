// Метки (никнеймы) над ботами — спрайты с текстурой из canvas.
// Спрайт честно тестируется по глубине: перекрывается стенами, не DOM.
import * as THREE from 'three';

const CANVAS_W = 256;
const CANVAS_H = 64;
const OUTLINE_PX = 3;
const PAD_X = 8;
const PAD_Y = 4;
const BG_ALPHA = 0.55;
const BG_RADIUS = 10;
const HEALTH_REDRAW_STEP = 0.05; // перерисовка при изменении HP больше 5%
const SHRINK_START = 20;         // с этой дистанции начинаем уменьшать
const MIN_SCALE_FACTOR = 0.6;    // минимум масштаба
const BASE_W = 0.6;
const BASE_H = 0.15;
const HEAD_OFFSET = 1.8 + 0.35;  // рост бота + смещение над макушкой

const FONT = 'bold 28px "Segoe UI", Arial, sans-serif';

/** @type {string[]} 24 коротких позывных кириллицей */
export const RU_CALLSIGNS = [
    'Волк', 'Ястреб', 'Гром', 'Крот', 'Сапёр', 'Барс',
    'Тайфун', 'Шторм', 'Кобра', 'Гепард', 'Бурый', 'Осот',
    'Шрам', 'Клык', 'Сокол', 'Туман', 'Росомаха', 'Ёрш',
    'Кедр', 'Лис', 'Гранит', 'Рейдер', 'Скат', 'Пёс'
];

let lastCallsignIndex = -1;

/**
 * Выбрать позывной без повтора подряд.
 * @param {() => number} rng генератор [0, 1)
 * @returns {string}
 */
export function pickCallsign(rng) {
    let i;
    do {
        i = Math.floor(rng() * RU_CALLSIGNS.length) % RU_CALLSIGNS.length;
    } while (i === lastCallsignIndex && RU_CALLSIGNS.length > 1);
    lastCallsignIndex = i;
    return RU_CALLSIGNS[i];
}

// Модульные временные — без аллокаций в update()
const _tmpPos = new THREE.Vector3();

/**
 * Рисует ник и полоску здоровья в canvas.
 * @param {CanvasRenderingContext2D} ctx
 * @param {string} name
 * @param {number} health 0..1
 */
function drawPlate(ctx, name, health) {
    ctx.clearRect(0, 0, CANVAS_W, CANVAS_H);

    // Подложка со скруглением
    ctx.font = FONT;
    const textW = Math.min(ctx.measureText(name).width, CANVAS_W - PAD_X * 2);
    const plateX = (CANVAS_W - textW) / 2 - PAD_X;
    const plateY = 2;
    const plateW = textW + PAD_X * 2;
    const plateH = 36 + PAD_Y * 2;

    ctx.fillStyle = `rgba(0,0,0,${BG_ALPHA})`;
    ctx.beginPath();
    if (ctx.roundRect) {
        ctx.roundRect(plateX, plateY, plateW, plateH, BG_RADIUS);
    } else {
        ctx.rect(plateX, plateY, plateW, plateH);
    }
    ctx.fill();

    // Ник: тёмная обводка + белая заливка
    ctx.font = FONT;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.lineWidth = OUTLINE_PX * 2;
    ctx.strokeStyle = 'rgba(10,10,10,0.9)';
    ctx.strokeText(name, CANVAS_W / 2, plateY + plateH / 2);
    ctx.fillStyle = '#ffffff';
    ctx.fillText(name, CANVAS_W / 2, plateY + plateH / 2);

    // Полоска здоровья шириной с ник (по тексту)
    const barW = textW + 10;
    const barH = 5;
    const barX = (CANVAS_W - barW) / 2;
    const barY = CANVAS_H - barH - 6;
    ctx.fillStyle = 'rgba(0,0,0,0.6)';
    ctx.fillRect(barX - 1, barY - 1, barW + 2, barH + 2);
    const h = Math.max(0, Math.min(1, health));
    // От зелёного к красному по мере потери HP
    ctx.fillStyle = `hsl(${Math.round(h * 120)},90%,45%)`;
    ctx.fillRect(barX, barY, barW * h, barH);
}

/**
 * Создать менеджер меток над ботами.
 * @param {THREE.Scene} scene
 * @param {THREE.Camera} camera
 * @param {{maxDistance?: number, container?: HTMLElement}} [options]
 * @returns {{add(bot: object, name: string): void, remove(bot: object): void,
 *   update(dt: number): void, dispose(): void}}
 */
export function createNameplates(scene, camera, options = {}) {
    const maxDistance = options.maxDistance ?? 60;
    const maxDistSq = maxDistance * maxDistance;
    /** @type {Map<object, {sprite: THREE.Sprite, texture: THREE.Texture,
     *   canvas: HTMLCanvasElement, ctx: CanvasRenderingContext2D,
     *   name: string, lastHealth: number}>} */
    const entries = new Map();

    function add(bot, name) {
        if (entries.has(bot)) return;
        const canvas = document.createElement('canvas');
        canvas.width = CANVAS_W;
        canvas.height = CANVAS_H;
        const ctx = canvas.getContext('2d');

        const health = bot.health ?? 1;
        const norm = health > 1 ? health / (bot.maxHealth ?? 100) : health;
        drawPlate(ctx, name, norm);

        const texture = new THREE.CanvasTexture(canvas);
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.minFilter = THREE.LinearFilter;
        const material = new THREE.SpriteMaterial({
            map: texture,
            sizeAttenuation: true,
            depthTest: true,
            transparent: true
        });
        const sprite = new THREE.Sprite(material);
        sprite.scale.set(BASE_W, BASE_H, 1);
        sprite.position.y = HEAD_OFFSET;
        sprite.renderOrder = 10;

        const parent = bot.object3D ?? bot.model ?? null;
        if (parent) {
            parent.add(sprite);
        } else {
            scene.add(sprite);
        }
        entries.set(bot, {
            sprite, texture, canvas, ctx, name,
            lastHealth: norm,
            worldObj: parent ? null : bot
        });
    }

    function remove(bot) {
        const e = entries.get(bot);
        if (!e) return;
        e.sprite.parent?.remove(e.sprite);
        e.sprite.material.dispose();
        e.texture.dispose();
        entries.delete(bot);
    }

    function update() {
        if (entries.size === 0) return;
        const camPos = camera.position;
        for (const [bot, e] of entries) {
            // Мёртвый бот — метку сразу убираем
            const hp = bot.health ?? 1;
            if (hp <= 0 || bot.dead) {
                remove(bot);
                continue;
            }
            const sprite = e.sprite;
            let worldPos = _tmpPos;
            if (e.worldObj) {
                const p = e.worldObj.position ?? e.worldObj;
                worldPos.set(p.x ?? 0, (p.y ?? 0) + HEAD_OFFSET, p.z ?? 0);
                sprite.position.copy(worldPos);
            } else {
                sprite.getWorldPosition(worldPos);
            }
            const distSq = worldPos.distanceToSquared(camPos);
            if (distSq > maxDistSq) {
                sprite.visible = false;
                continue;
            }
            sprite.visible = true;

            // Плавное уменьшение масштаба дальше SHRINK_START метров
            const dist = Math.sqrt(distSq);
            let k = 1;
            if (dist > SHRINK_START) {
                const t = Math.min((dist - SHRINK_START) / (maxDistance - SHRINK_START), 1);
                k = 1 + (MIN_SCALE_FACTOR - 1) * t;
            }
            sprite.scale.set(BASE_W * k, BASE_H * k, 1);

            // Перерисовка полоски здоровья только при изменении > 5%
            const norm = hp > 1 ? hp / (bot.maxHealth ?? 100) : hp;
            if (Math.abs(norm - e.lastHealth) > HEALTH_REDRAW_STEP) {
                e.lastHealth = norm;
                drawPlate(e.ctx, e.name, norm);
                e.texture.needsUpdate = true;
            }
        }
    }

    function dispose() {
        for (const bot of Array.from(entries.keys())) remove(bot);
    }

    return { add, remove, update, dispose };
}
