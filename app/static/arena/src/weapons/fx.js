// ============================================================
// fx.js — визуальные эффекты оружия: трассеры, вспышки, декали,
// гильзы, искры. Всё на пулах объектов, ноль аллокаций в рантайме.
// ============================================================

import * as THREE from 'three';
import { EventBus, bus } from '../core/events.js';

// --- Константы, недостающие в исходной генерации ---
const AXIS_Y = new THREE.Vector3(0, 1, 0);   // опорная ось для ориентации трассера
const _e1 = new THREE.Euler();               // временный поворот для гильз
const AXIS_Z = new THREE.Vector3(0, 0, 1);   // опорная ось для декали по нормали
const GRAVITY = 9.8;                          // ускорение для гильз и искр, м/с^2
const TRACER_MIN_LEN = 1.2;                   // короче этого трассер не рисуем, м
const SHELL_EJECT_SPEED = 2.4;                // скорость вылета гильзы, м/с
const SHELL_FADE = 0.5;                       // за сколько секунд гильза гаснет
const SPARKS_PER_IMPACT = 10;                 // искр на попадание при высоком качестве
const SPARK_SPEED = 3.5;                      // разлёт искр, м/с
const MUZZLE_LIGHT_INTENSITY = 6.0;           // яркость вспышки у ствола

// ------------------------- Константы -------------------------

/** Время жизни трассера (с) */
// Трассер жил 0.08 с и был почти невидим: при 60 кадрах это 5 кадров,
// а при просадке — один. Держим дольше, чтобы трасса реально читалась.
const TRACER_LIFE = 0.22;
/** Число трассеров в пуле */
const TRACER_POOL_SIZE = 32;
/** Толщина/длина единичной геометрии трассера */
const TRACER_RADIUS = 0.022;   // толще: тонкую нить не видно на дистанции

/** Число искр в пуле (точек) */
const SPARK_POOL_SIZE = 256;
/** Число искр на одно попадание */
const SPARKS_PER_HIT = 8;
/** Время жизни искры (с) */
const SPARK_LIFE = 0.35;
/** Гравитация искр (м/с^2) */
const SPARK_GRAVITY = 9.8;

/** Кольцевой буфер декалей */
const DECAL_POOL_SIZE = 64;
/** Размер декали (м) */
const DECAL_SIZE = 0.22;
/** Отступ декали от поверхности (во избежание z-fighting) */
const DECAL_OFFSET = 0.012;

/** Число гильз в пуле */
const SHELL_POOL_SIZE = 48;
/** Время жизни гильзы (с) */
const SHELL_LIFE = 3.0;

/** Дипазон мигания вспышки у ствола (с) */
const MUZZLE_LIFE = 0.05;
/** Размер спрайта вспышки */
const MUZZLE_SIZE = 0.55;
/** Число вспышек в пуле */
const MUZZLE_POOL_SIZE = 6;
/** Число источников света вспышек (только high) */
const MUZZLE_LIGHT_POOL = 3;

// Цвета
const COLOR_TRACER = 0xffd27a;
const COLOR_SPARK = 0xffb347;
const COLOR_MUZZLE = 0xffe0a0;
const COLOR_MUZZLE_LIGHT = 0xffc873;

// ------------------------ Генерация текстур ------------------------

/** Радиальная текстура вспышки/эксцентрика */
function makeFlashTexture() {
    const size = 64;
    const cv = document.createElement('canvas');
    cv.width = cv.height = size;
    const ctx = cv.getContext('2d');
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0.0, 'rgba(255,255,240,1)');
    g.addColorStop(0.25, 'rgba(255,220,140,0.9)');
    g.addColorStop(0.6, 'rgba(255,160,60,0.35)');
    g.addColorStop(1.0, 'rgba(255,120,20,0)');
    ctx.fillStyle = g;
    // «лепестки» вспышки
    ctx.translate(size / 2, size / 2);
    for (let i = 0; i < 4; i++) {
        ctx.rotate(Math.PI / 2);
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(size * 0.5, size * 0.045);
        ctx.lineTo(size * 0.5, -size * 0.045);
        ctx.closePath();
        ctx.fill();
    }
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
}

/** Текстура декали — рваная тёмная точка попадания */
function makeDecalTexture() {
    const size = 64;
    const cv = document.createElement('canvas');
    cv.width = cv.height = size;
    const ctx = cv.getContext('2d');
    const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    g.addColorStop(0.0, 'rgba(12,12,12,0.95)');
    g.addColorStop(0.3, 'rgba(18,16,14,0.85)');
    g.addColorStop(0.55, 'rgba(25,22,18,0.4)');
    g.addColorStop(1.0, 'rgba(30,28,24,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
    // трещины-лучи
    ctx.strokeStyle = 'rgba(15,14,12,0.75)';
    ctx.lineWidth = 1.6;
    let seed = 1337;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let i = 0; i < 7; i++) {
        const a = rnd() * Math.PI * 2;
        const len = size * (0.22 + rnd() * 0.2);
        ctx.beginPath();
        ctx.moveTo(size / 2, size / 2);
        ctx.lineTo(size / 2 + Math.cos(a) * len, size / 2 + Math.sin(a) * len);
        ctx.stroke();
    }
    const tex = new THREE.CanvasTexture(cv);
    tex.colorSpace = THREE.SRGBColorSpace;
    return tex;
}

// ------------------------ Модулярные временные ------------------------

const _v1 = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _v3 = new THREE.Vector3();
const _q1 = new THREE.Quaternion();
const _up = new THREE.Vector3(0, 1, 0);
const _fwd = new THREE.Vector3(0, 0, -1);
const _m1 = new THREE.Matrix4();
const _c1 = new THREE.Color();

// Ось геометрии трассера (цилиндр вытянут вдоль Y)
const _tracerBaseAxis = new THREE.Vector3(0, 1, 0);

// ------------------------ Фабрика ------------------------

/**
 * Создаёт систему визуальных эффектов оружия.
 * @param {THREE.Scene} scene
 * @param {object} world — физический мир Rapier (или null)
 * @param {import('../core/settings.js').Settings} settings
 * @returns {{tracer:Function, muzzleFlash:Function, impact:Function, ejectShell:Function, update:Function, dispose:Function}}
 */
export function createWeaponFx(scene, world, settings) {
    const RAPIER = world && world._rapier ? world._rapier : null;
    const physWorld
 = RAPIER && world._world ? world._world : (RAPIER ? world : null);

    const quality = settings.quality;
    const isHigh = quality === 'high';
    const isLow = quality === 'low';

    // Текстуры (создаются один раз)
    const flashTex = makeFlashTexture();
    const decalTex = makeDecalTexture();

    // ===================== Трассеры =====================
    // Один InstancedMesh на весь пул — один draw call.
    const tracerGeo = new THREE.CylinderGeometry(TRACER_RADIUS, TRACER_RADIUS, 1, 5, 1, true);
    const tracerMat = new THREE.MeshBasicMaterial({
        color: COLOR_TRACER,
        transparent: true,
        opacity: 0.9,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
    });
    const tracerMesh = new THREE.InstancedMesh(tracerGeo, tracerMat, TRACER_POOL_SIZE);
    tracerMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    tracerMesh.frustumCulled = false;
    scene.add(tracerMesh);

    /** @type {{life:number, length:number}} */
    const tracers = [];
    for (let i = 0; i < TRACER_POOL_SIZE; i++) {
        tracers.push({ life: 0 });
        // прячем: нулевой масштаб
        _m1.makeScale(0, 0, 0);
        tracerMesh.setMatrixAt(i, _m1);
    }
    tracerMesh.instanceMatrix.needsUpdate = true;
    let tracerCursor = 0;

    // ===================== Вспышка у ствола =====================
    const muzzleMat = new THREE.SpriteMaterial({
        map: flashTex,
        color: COLOR_MUZZLE,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        transparent: true,
    });
    const muzzles = [];
    for (let i = 0; i < MUZZLE_POOL_SIZE; i++) {
        const spr = new THREE.Sprite(muzzleMat.clone());
        spr.visible = false;
        spr.scale.setScalar(MUZZLE_SIZE);
        scene.add(spr);
        muzzles.push({ sprite: spr, life: 0 });
    }
    let muzzleCursor = 0;

    // Короткие PointLight только на high
    const muzzleLights = [];
    if (isHigh) {
        for (let i = 0; i < MUZZLE_LIGHT_POOL; i++) {
            const l = new THREE.PointLight(COLOR_MUZZLE_LIGHT, 0, 6, 2);
            l.visible = false;
            scene.add(l);
            muzzleLights.push({ light: l, life: 0 });
        }
    }
    let lightCursor = 0;

    // ===================== Декали (кольцевой буфер) =====================
    const decalGeo = new THREE.PlaneGeometry(DECAL_SIZE, DECAL_SIZE);
    const decalMat = new THREE.MeshBasicMaterial({
        map: decalTex,
        transparent: true,
        depthWrite: false,
        polygonOffset: true,
        polygonOffsetFactor: -2,
    });
    const decalMesh = new THREE.InstancedMesh(decalGeo, decalMat, DECAL_POOL_SIZE);
    decalMesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
    decalMesh.frustumCulled = false;
    scene.add(decalMesh);
    for (let i = 0; i < DECAL_POOL_SIZE; i++) {
        _m1.makeScale(0, 0, 0);
        decalMesh.setMatrixAt(i, _m1);
    }
    decalMesh.instanceMatrix.needsUpdate = true;
    let decalCursor = 0;
    // запоминаем масштаб с «рандомом» на слот — без аллокаций
    const decalScales = new Float32Array(DECAL_POOL_SIZE);
    decalScales.fill(1);

    // ===================== Гильзы =====================
    const shellGeo = new THREE.CapsuleGeometry(0.006, 0.028, 2, 6);
    const shellMat = new THREE.MeshStandardMaterial({
        color: 0xc9a227,
        metalness: 0.85,
        roughness: 0.3,
    });
    const shells = [];
    for (let i = 0; i < SHELL_POOL_SIZE; i++) {
        const mesh = new THREE.Mesh(shellGeo, shellMat);
        mesh.visible = false;
        scene.add(mesh);
        let body = null;
        if (RAPIER && physWorld && !isLow) {
            body = physWorld.createRigidBody(
                RAPIER.RigidBodyDesc.dynamic()
                    .setTranslation(0, -1000, 0)
                    .setCanSleep(true)
            );
            const colDesc = RAPIER.ColliderDesc.capsule(0.014, 0.006)
                .setRestitution(0.4)
                .setFriction(0.5)
                .setMass(0.015);
            physWorld.createCollider(colDesc, body);
            body.setEnabled(false);
        }
        shells.push({ mesh, body, life: 0, active: false });
    }
    let shellCursor = 0;

    // ===================== Искры (Points) =====================
    const sparkPos = new Float32Array(SPARK_POOL_SIZE * 3);
    const sparkVel = new Float32Array(SPARK_POOL_SIZE * 3);
    const sparkLife = new Float32Array(SPARK_POOL_SIZE); // оставшееся время
    // стартуем «под землёй», чтобы не светились
    for (let i = 0; i < SPARK_POOL_SIZE; i++) {
        sparkPos[i * 3 + 1] = -1000;
    }
    const sparkGeo = new THREE.BufferGeometry();
    sparkGeo.setAttribute('position', new THREE.BufferAttribute(sparkPos, 3));
    sparkGeo.attributes.position.setUsage(THREE.DynamicDrawUsage);
    const sparkMat = new THREE.PointsMaterial({
        color: COLOR_SPARK,
        size: 0.03,
        transparent: true,
        opacity: 0.95,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        sizeAttenuation: true,
    });
    const sparkPoints = new THREE.Points(sparkGeo, sparkMat);
    sparkPoints.frustumCulled = false;
    scene.add(sparkPoints);
    let sparkCursor = 0;
    let sparkSeed = 7;
    const sparkRnd = () => (sparkSeed = (sparkSeed * 48271) % 2147483647) / 2147483647;

    // =========================== API ===========================

    /**
     * Показывает трассер между двумя точками.
     * @param {THREE.Vector3} from — начало (дуло)
     * @param {THREE.Vector3} to — конец (точка попадания)
     */
    function tracer(from,        to) {
        _v1.subVectors(to, from);
        const len = _v1.length();
        if (len < TRACER_MIN_LEN) return;
        _v1.multiplyScalar(1 / len);

        // середина отрезка
        _v2.addVectors(from, to).multiplyScalar(0.5);

        // ось Y цилиндра вдоль направления
        _q1.setFromUnitVectors(AXIS_Y, _v1);

        const idx = tracerCursor;
        tracerCursor = (tracerCursor + 1) % TRACER_POOL_SIZE;

        _m1.compose(_v2, _q1, _v3.set(1, len, 1));
        tracerMesh.setMatrixAt(idx, _m1);
        tracerMesh.instanceMatrix.needsUpdate = true;
        tracers[idx].life = TRACER_LIFE;
    }

    /**
     * Вспышка у дула.
     * @param {THREE.Vector3} pos — мировая позиция дула
     * @param {THREE.Vector3} dir — направление выстрела (не обязателен к нормализации)
     */
    function muzzleFlash(pos, dir) {
        const m = muzzles[muzzleCursor];
        muzzleCursor = (muzzleCursor + 1) % MUZZLE_POOL_SIZE;

        // небольшой вынос вперёд по направлению, чтобы спрайт не тонул в стволе
        m.sprite.position.copy(pos).addScaledVector(dir, 0.12);
        // случайный поворот и размер — через материал спрайта
        m.sprite.material.rotation = sparkRnd() * 6.28318;
        const s = MUZZLE_SIZE * (0.8 + sparkRnd() * 0.5);
        m.sprite.scale.setScalar(s);
        m.sprite.visible = true;
        m.life = MUZZLE_LIFE;

        if (isHigh && muzzleLights.length > 0) {
            const ml = muzzleLights[lightCursor];
            lightCursor = (lightCursor + 1) % MUZZLE_LIGHT_POOL;
            ml.light.position.copy(m.sprite.position);
            ml.light.intensity = MUZZLE_LIGHT_INTENSITY;
            ml.light.visible = true;
            ml.life = MUZZLE_LIFE;
        }
    }

    /**
     * След попадания: декаль по нормали + веер искр.
     * @param {THREE.Vector3} point — точка попадания
     * @param {THREE.Vector3} normal — нормаль поверхности (должна быть нормализована)
     */
    function impact(point, normal) {
        // --- Декаль ---
        const di = decalCursor;
        decalCursor = (decalCursor + 1) % DECAL_POOL_SIZE;

        // слегка отодвигаем от поверхности во избежание z-fighting
        _v1.copy(point).addScaledVector(normal, DECAL_OFFSET);
        _q1.setFromUnitVectors(AXIS_Z, normal);
        const sc = 0.7 + sparkRnd() * 0.7;
        decalScales[di] = sc;
        _m1.compose(_v1, _q1, _v3.set(sc, sc, sc));
        decalMesh.setMatrixAt(di, _m1);
        decalMesh.instanceMatrix.needsUpdate = true;

        // --- Искры ---
        const count = isLow ? 4 : SPARKS_PER_IMPACT;
        for (let s = 0; s < count; s++) {
            const si = sparkCursor;
            sparkCursor = (sparkCursor + 1) % SPARK_POOL_SIZE;
            const o = si * 3;

            sparkPos[o] = point.x;
            sparkPos[o + 1] = point.y;
            sparkPos[o + 2] = point.z;

            // случайное направление в полусфере вокруг нормали
            const rx = sparkRnd() - 0.5;
            const ry = sparkRnd() - 0.5;
            const rz = sparkRnd() - 0.5;
            _v2.set(
                normal.x + rx * 1.4,
                normal.y + ry * 1.4 + 0.35,
                normal.z + rz * 1.4
            ).normalize().multiplyScalar(SPARK_SPEED * (0.5 + sparkRnd()));

            sparkVel[o] = _v2.x;
            sparkVel[o + 1] = _v2.y;
            sparkVel[o + 2] = _v2.z;

            sparkLife[si] = SPARK_LIFE * (0.5 + sparkRnd() * 0.8);
        }
        sparkGeo.attributes.position.needsUpdate = true;
    }

    /**
     * Выброс стреляной гильзы.
     * @param {THREE.Vector3} pos — мировая позиция окна выброса
     * @param {THREE.Vector3} right — правый вектор камеры/оружия
     * @param {THREE.Vector3} up — верхний вектор камеры/оружия
     */
    function ejectShell(pos, right, up) {
        const sh = shells[shellCursor];
        shellCursor = (shellCursor + 1) % SHELL_POOL_SIZE;

        sh.mesh.position.copy(pos);
        sh.mesh.quaternion.setFromEuler(_e1.set(
            sparkRnd() * 3, sparkRnd() * 3, sparkRnd() * 3
        ));
        sh.mesh.visible = true;
        sh.life = SHELL_LIFE;
        sh.active = true;

        if (sh.body) {
            sh.body.setEnabled(true);
            sh.body.setTranslation({ x: pos.x, y: pos.y, z: pos.z }, true);
            // импульс вправо-вверх со случайной составляющей
            _v1.copy(right).multiplyScalar(SHELL_EJECT_SPEED * (0.8 + sparkRnd() * 0.5));
            _v1.addScaledVector(up, SHELL_EJECT_SPEED * (0.45 + sparkRnd() * 0.35));
            sh.body.setLinvel({ x: _v1.x, y: _v1.y, z: _v1.z }, true);
            sh.body.setAngvel({
                x: (sparkRnd() - 0.5) * 20,
                y: (sparkRnd() - 0.5) * 20,
                z: (sparkRnd() - 0.5) * 20,
            }, true);
            sh.body.wakeUp();
        } else {
            // без физики: баллистика в update
            _v1.copy(right).multiplyScalar(SHELL_EJECT_SPEED);
            _v1.addScaledVector(up, SHELL_EJECT_SPEED * 0.5);
            sh.fallbackVel = sh.fallbackVel || new THREE.Vector3();
            sh.fallbackVel.copy(_v1);
        }
    }

    /**
     * Обновление эффектов. Вызывать каждый кадр.
     * @param {number} dt — секунды
     */
    function update(dt) {
        // --- Трассеры ---
        let tracerDirty = false;
        for (let i = 0; i < TRACER_POOL_SIZE; i++) {
            const t = tracers[i];
            if (t.life > 0) {
                t.life -= dt;
                if (t.life <= 0) {
                    _m1.makeScale(0, 0, 0);
                    tracerMesh.setMatrixAt(i, _m1);
                    tracerDirty = true;
                }
            }
        }
        if (tracerDirty) tracerMesh.instanceMatrix.needsUpdate = true;

        // --- Вспышки ---
        for (let i = 0; i < MUZZLE_POOL_SIZE; i++) {
            const m = muzzles[i];
            if (m.life > 0) {
                m.life -= dt;
                const k = m.life / MUZZLE_LIFE;
                m.sprite.material.opacity = k;
                if (m.life <= 0) m.sprite.visible = false;
            }
        }
        for (let i = 0; i < muzzleLights.length; i++) {
            const ml = muzzleLights[i];
            if (ml.life > 0) {
                ml.life -= dt;
                ml.light.intensity = MUZZLE_LIGHT_INTENSITY * (ml.life / MUZZLE_LIFE);
                if (ml.life <= 0) {
                    ml.light.visible = false;
                    ml.light.intensity = 0;
                }
            }
        }

        // --- Гильзы ---
        for (let i = 0; i < SHELL_POOL_SIZE; i++) {
            const sh = shells[i];
            if (!sh.active) continue;
            sh.life -= dt;
            if (sh.life <= 0) {
                sh.active = false;
                sh.mesh.visible = false;
                if (sh.body) {
                    sh.body.setEnabled(false);
                    sh.body.setTranslation({ x: 0, y: -1000, z: 0 }, false);
                }
                continue;
            }
            // плавное затухание в последнюю секунду — через масштаб (материал общий)
            const fade = sh.life < SHELL_FADE ? sh.life / SHELL_FADE : 1;
            sh.mesh.scale.setScalar(fade);
            if (sh.body) {
                const t = sh.body.translation();
                sh.mesh.position.set(t.x, t.y, t.z);
                const r = sh.body.rotation();
                sh.mesh.quaternion.set(r.x, r.y, r.z, r.w);
            } else {
                // простая баллистика без физики
                sh.fallbackVel.y -= GRAVITY * dt;
                sh.mesh.position.addScaledVector(sh.fallbackVel, dt);
                if (sh.mesh.position.y < 0.01) {
                    sh.mesh.position.y = 0.01;
                    sh.fallbackVel.set(0, 0, 0);
                }
                sh.mesh.rotation.x += dt * 12;
            }
        }

        // --- Искры ---
        let sparkDirty = false;
        for (let i = 0; i < SPARK_POOL_SIZE; i++) {
            if (sparkLife[i] <= 0) continue;
            sparkLife[i] -= dt;
            const o = i * 3;
            if (sparkLife[i] <= 0) {
                sparkPos[o + 1] = -1000;
                sparkDirty = true;
                continue;
            }
            sparkVel[o + 1] -= GRAVITY * dt;
            sparkPos[o] += sparkVel[o] * dt;
            sparkPos[o + 1] += sparkVel[o + 1] * dt;
            sparkPos[o + 2] += sparkVel[o + 2] * dt;
            if (sparkPos[o+ 1] < 0) {
                sparkPos[o + 1] = 0;
                sparkVel[o] *= 0.4;
                sparkVel[o + 1] *= -0.3;
                sparkVel[o + 2] *= 0.4;
            }
            sparkDirty = true;
        }
        if (sparkDirty) sparkGeo.attributes.position.needsUpdate = true;

        // затухание декалей по возрасту — общая прозрачность instanced-материала
        // (упрощение: материал один, глобальное затухание старых декалей не делаем,
        //  они просто перезаписываются по кольцу)
    }

    return { tracer, muzzleFlash, impact, ejectShell, update };
}
