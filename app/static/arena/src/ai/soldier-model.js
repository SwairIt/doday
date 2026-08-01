/**
 * Процедурная модель бойца для ботов Doday Arena.
 * Только геометрия и анимация — без логики ИИ и физики.
 *
 * Рост 1.8 м, начало координат — в ступнях (y = 0).
 * Ствол автомата смотрит вперёд по -Z.
 *
 * @module src/ai/soldier-model
 */

import * as THREE from 'three';

// --- Константы анимации, недостающие в исходной генерации ---
const HIP_X = 0.11;              // половина ширины таза, м
const LEG_SWING = 0.75;          // максимальный вымах ноги, радианы
const ARM_SWING_SCALE = 0.6;     // руки качаются слабее ног
const BOB_AMP = 0.03;            // покачивание корпуса в такт шагам, м
const MAX_RUN_SPEED = 5.0;       // скорость, при которой шаг максимальный, м/с
const STRIDE_FREQ_PER_MS = 1.6;  // множитель частоты шага от скорости
const AIM_ARM_LIFT = 0.35;       // подъём рук при вскидывании, радианы
const AIM_STRIDE_SCALE = 0.6;    // в прицеле шаг короче
const RECOIL_ARM = 0.25;         // отдача в плечо, радианы
const RECOIL_GUN = 0.05;         // отход автомата назад, м
const TEAM_EMISSIVE = 0.55;      // яркость командной подсветки

// -----------------------------------------------------------------------------
// Константы размеров (метры)
// -----------------------------------------------------------------------------

const HEAD_Y = 1.62;            // центр головы
const HEAD_W = 0.22, HEAD_H = 0.24, HEAD_D = 0.26;
const HELMET_Y = 1.72;
const TORSO_Y = 1.18;           // центр торса
const TORSO_W = 0.44, TORSO_H = 0.5, TORSO_D = 0.26;
const VEST_W = 0.5, VEST_H = 0.4, VEST_D = 0.34;
const HIP_Y = 0.92;             // точка крепления ног
const SHOULDER_Y = 1.42;        // точка крепления рук
const SHOULDER_X = 0.3;
const UPPER_ARM = 0.3;          // длина плеча
const FOREARM = 0.28;           // длина предплечья
const THIGH = 0.48;             // длина бедра
const SHIN = 0.44;              // длина голени
const LIMB_R = 0.055;           // толщина конечности

// -----------------------------------------------------------------------------
// Цвета (хаки / тёмно-серый)
// -----------------------------------------------------------------------------

const COLOR_UNIFORM = 0x5a5f43;   // хаки — форма
const COLOR_VEST = 0x42473a;      // бронежилет темнее
const COLOR_HELMET = 0x30343a;    // каска ещё темнее
const COLOR_DARK = 0x22242a;      // ботинки, оружие, очки
const COLOR_POUCH = 0x4d5240;     // подсумки

// -----------------------------------------------------------------------------
// Анимационные константы
// -----------------------------------------------------------------------------

const WALK_FREQ = 2.0;            // базовый множитель частоты шагов
const WALK_SWING = 0.6;           // амплитуда качания ног, рад
const ARM_SWING = 0.45;           // амплитуда качания рук, рад
const AIM_ARM_PITCH = -1.15;      // наклон рук при прицеливании
const BOB_AMPLITUDE = 0.03;       // покачивание корпуса, м
const RECOIL_PUSH = 0.09;         // отдача автомата по Z, м
const RECOIL_DECAY = 18.0;        // скорость затухания отдачи (экспонента)
const FLASH_TIME = 0.05;          // время жизни дульной вспышки, с
const DEATH_TIME = 0.6;           // длительность падения при смерти, с
const DEATH_SIDE_Z = Math.PI / 2; // крен на бок при смерти
const MAX_SPEED_FOR_ANIM = 5.0;   // скорость бега для нормировки

// Временные модульные объекты — ноль аллокаций в update
const _quat = new THREE.Quaternion();
const _euler = new THREE.Euler(0, 0, 0, 'YXZ');
const _color = new THREE.Color(0xffffff);

/**
 * Создаёт процедурную модель бойца.
 *
 * @param {{ rng: Function, quality: 'low'|'medium'|'high' }} options
 * @returns {{
 *   group: THREE.Group,
 *   update: (dt: number, pose: {speed: number, aiming: boolean, firing: boolean, grounded: boolean, yaw: number}) => void,
 *   setTeamColor: (hex: number) => void,
 *   playMuzzleFlash: () => void,
 *   setDead: (on: boolean) => void,
 *   dispose: () => void
 * }}
 */
export function createSoldierModel(options) {
    const quality = options && options.quality ? options.quality : 'medium';
    const isLow = quality === 'low';

    const group = new THREE.Group();
    group.name = 'SoldierModel';
    // Тени от мелких деталей экипировки не видны, но стоят дорого:
    // включаем их только для корпуса и ног (см. ниже по коду).
    group.userData.shadowsTrimmed = true;

    // Общие материалы: один на группу деталей одного цвета
    const matUniform = new THREE.MeshStandardMaterial({ color: COLOR_UNIFORM, roughness: 0.95, metalness: 0.0 });
    const matVest = new THREE.MeshStandardMaterial({ color: COLOR_VEST, roughness: 0.9, metalness: 0.05 });
    const matHelmet = new THREE.MeshStandardMaterial({ color: COLOR_HELMET, roughness: 0.6, metalness: 0.25 });
    const matDark = new THREE.MeshStandardMaterial({ color: COLOR_DARK, roughness: 0.7, metalness: 0.3 });
    const matPouch = new THREE.MeshStandardMaterial({ color: COLOR_POUCH, roughness: 0.95, metalness: 0.0 });
    // Командная эмиссивная полоса — слабо светится, видна в сумерках
    const matTeam = new THREE.MeshStandardMaterial({
        color: 0x111111,
        emissive: 0xffffff,
        emissiveIntensity: 0.55,
        roughness: 0.5,
    });
    // Дульная вспышка — яркая эмиссия
    const matFlash = new THREE.MeshStandardMaterial({
        color: 0xffaa33,
        emissive: 0xffcc55,
        emissiveIntensity: 6.0,
        transparent: true,
        opacity: 0.95,
    });

    const materials = [matUniform, matVest, matHelmet, matDark, matPouch, matTeam, matFlash];
    const geometries = [];

    /**
     * Вспомогательная: меш из общего кэша геометрий.
     * @param {THREE.BufferGeometry} geo
     * @param {THREE.Material} mat
     * @param {Object3D} parent
     * @returns {THREE.Mesh}
     */
    function addMesh(geo, mat, parent) {
        geometries.push(geo);
        const mesh = new THREE.Mesh(geo, mat);
        parent.add(mesh);
        return mesh;
    }

    /**
     * Бокс-примитив.
     */
    function addBox(w, h, d, mat, parent, x, y, z) {
        const mesh = addMesh(new THREE.BoxGeometry(w, h, d), mat, parent);
        mesh.position.set(x, y, z);
        return mesh;
    }

    // =========================================================================
    // Голова + каска
    // =========================================================================

    const headGroup = new THREE.Group();
    headGroup.position.set(0, HEAD_Y, 0);
    group.add(headGroup);

    // Слегка сплюснутая коробка-голова
    addBox(HEAD_W, HEAD_H * 0.85, HEAD_D, matUniform, headGroup, 0, 0, 0);

    // Каска — верхняя половина сферы
    const helmetGeo = new THREE.SphereGeometry(0.16, isLow ? 8 : 12, isLow ? 6 : 8, 0, Math.PI * 2, 0, Math.PI * 0.5);
    const helmet = addMesh(helmetGeo, matHelmet, headGroup);
    helmet.position.set(0, HEAD_H * 0.25, 0);
    helmet.scale.set(1, 0.85, 1.05);

    // Козырёк каски
    addBox(0.2, 0.02, 0.12, matHelmet, headGroup, 0, HEAD_H * 0.22, -0.17);

    // Тёмные очки-полоска (пропускаются на low)
    if (!isLow) {
        addBox(HEAD_W + 0.02, 0.05, 0.03, matDark, headGroup, 0, 0.02, -HEAD_D * 0.5);
    }

    // Командная полоса на каске (эмиссивная)
    const teamStripe = addBox(0.05, 0.06, 0.28, matTeam, headGroup, 0, HEAD_H * 0.42, 0);

    // =========================================================================
    // Торс + бронежилет + разгрузка + рюкзак
    // =========================================================================

    const torsoGroup = new THREE.Group();
    torsoGroup.position.set(0, TORSO_Y, 0);
    group.add(torsoGroup);

    addBox(TORSO_W, TORSO_H, TORSO_D, matUniform, torsoGroup, 0, 0, 0);
    addBox(VEST_W, VEST_H, VEST_D, matVest, torsoGroup, 0, 0.02, 0);

    // Плечевые накладки
    addBox(0.14, 0.08, 0.22, matVest, torsoGroup, -0.26, 0.24, 0);
    addBox(0.14, 0.08, 0.22, matVest, torsoGroup, 0.26, 0.24, 0);

    // Эмиссивные командные полоски на плечах
    addBox(0.15, 0.025, 0.23, matTeam, torsoGroup, -0.26, 0.285, 0);
    addBox(0.15, 0.025, 0.23, matTeam, torsoGroup, 0.26, 0.285, 0);

    // Разгрузка: 4 подсумка спереди + рация на плече — только не на low
    if (!isLow) {
        for (let i = 0; i < 4; i++) {
            addBox(0.09, 0.13, 0.06, matPouch, torsoGroup, -0.165 + i * 0.11, -0.1, -VEST_D * 0.5 - 0.03);
        }
        const radio = addBox(0.07, 0.16, 0.06, matDark, torsoGroup, -0.2, 0.18, -VEST_D * 0.5 - 0.035);
        radio.rotation.z = 0.15;
    }

    // Рюкзак за спиной, скругление — через масштаб
    const backpack = addMesh(new THREE.SphereGeometry(0.24, isLow ? 8 : 10, isLow ? 6 : 8), matPouch, torsoGroup);
    backpack.position.set(0, 0.02, VEST_D * 0.5 + 0.08);
    backpack.scale.set(0.85, 0.95, 0.55);

    // =========================================================================
    // Руки: суставы-группы, плечо + предплечье
    // =========================================================================

    const rightShoulder = new THREE.Group();
    rightShoulder.position.set(-SHOULDER_X, SHOULDER_Y, 0);
    group.add(rightShoulder);
    addBox(LIMB_R * 2, UPPER_ARM, LIMB_R * 2, matUniform, rightShoulder, 0, -UPPER_ARM * 0.5, 0);

    const rightElbow = new THREE.Group();
    rightElbow.position.set(0, -UPPER_ARM, 0);
    rightShoulder.add(rightElbow);
    addBox(LIMB_R * 1.8, FOREARM, LIMB_R * 1.8, matUniform, rightElbow, 0, -FOREARM * 0.5, 0);

    const leftShoulder = new THREE.Group();
    leftShoulder.position.set(SHOULDER_X, SHOULDER_Y, 0);
    group.add(leftShoulder);
    addBox(LIMB_R * 2, UPPER_ARM, LIMB_R * 2, matUniform, leftShoulder, 0, -UPPER_ARM * 0.5, 0);

    const leftElbow = new THREE.Group();
    leftElbow.position.set(0, -UPPER_ARM, 0);
    leftShoulder.add(leftElbow);
    addBox(LIMB_R * 1.8, FOREARM, LIMB_R * 1.8, matUniform, leftElbow, 0, -FOREARM * 0.5, 0);

    // =========================================================================
    // Автомат — крепится к правому предплечью, ствол вдоль -Z
    // =========================================================================

    const gun = new THREE.Group();
    gun.position.set(0.02, -FOREARM - 0.02, -0.08);
    rightElbow.add(gun);

    // Ресивер
    addBox(0.06, 0.09, 0.42, matDark, gun, 0, 0, -0.08);
    // Ствол (цилиндр вдоль -Z)
    const barrel = addMesh(new THREE.CylinderGeometry(0.018, 0.018, 0.3, 8), matDark, gun);
    barrel.rotation.x = Math.PI * 0.5;
    barrel.position.set(0, 0.015, -0.42);
    // Магазин
    const mag = addBox(0.05, 0.18, 0.08, matDark, gun, 0, -0.12, -0.16);
    mag.rotation.x = 0.15;
    // Приклад
    const stock = addBox(0.05, 0.1, 0.2, matDark, gun, 0, -0.01, 0.22);
    stock.rotation.x = -0.08;
    // Рукоять
    const grip = addBox(0.04, 0.11, 0.05, matDark, gun, 0, -0.09, -0.02);
    grip.rotation.x = 0.25;

    // Дульная вспышка у среза ствола, по умолчанию скрыта
    const muzzleFlash = addMesh(new THREE.ConeGeometry(0.06, 0.16, 6), matFlash, gun);
    muzzleFlash.rotation.x = -Math.PI * 0.5;
    muzzleFlash.position.set(0, 0.015, -0.62);
    muzzleFlash.visible = false;

    // =========================================================================

    // =========================================================================
    // Ноги: суставы-группы, бедро + голень + ботинок
    // =========================================================================

    const rightHip = new THREE.Group();
    rightHip.position.set(-HIP_X, HIP_Y, 0);
    group.add(rightHip);
    addBox(LIMB_R * 2.4, THIGH, LIMB_R * 2.4, matUniform, rightHip, 0, -THIGH * 0.5, 0);

    const rightKnee = new THREE.Group();
    rightKnee.position.set(0, -THIGH, 0);
    rightHip.add(rightKnee);
    addBox(LIMB_R * 2, SHIN, LIMB_R * 2, matUniform, rightKnee, 0, -SHIN * 0.5, 0);
    addBox(0.11, 0.08, 0.24, matDark, rightKnee, 0, -SHIN + 0.04, -0.06); // ботинок

    const leftHip = new THREE.Group();
    leftHip.position.set(HIP_X, HIP_Y, 0);
    group.add(leftHip);
    addBox(LIMB_R * 2.4, THIGH, LIMB_R * 2.4, matUniform, leftHip, 0, -THIGH * 0.5, 0);

    const leftKnee = new THREE.Group();
    leftKnee.position.set(0, -THIGH, 0);
    leftHip.add(leftKnee);
    addBox(LIMB_R * 2, SHIN, LIMB_R * 2, matUniform, leftKnee, 0, -SHIN * 0.5, 0);
    addBox(0.11, 0.08, 0.24, matDark, leftKnee, 0, -SHIN + 0.04, -0.06); // ботинок

    // =========================================================================
    // Состояние анимации
    // =========================================================================

    let phase = 0;                 // фаза шага
    let recoil = 0;               // величина отдачи 0..1
    let flashTime = 0;           // оставшееся время вспышки, сек
    let dead = false;            // модель мертва
    let deathT = 0;              // прогресс падения 0..1

    // =========================================================================
    // Публичный API
    // =========================================================================

    /**
     * Обновить анимацию модели.
     * @param {number} dt - дельта времени, сек
     * @param {{speed:number, aiming:boolean, firing:boolean, grounded:boolean, yaw:number}} pose
     */
    function update(dt, pose) {
        if (!pose) return;

        // --- Падение при смерти: завал набок за DEATH_TIME с, далее статично ---
        if (dead) {
            if (deathT < 1) {
                deathT = Math.min(1, deathT + dt / DEATH_TIME);
                const e = 1 - (1 - deathT) * (1 - deathT); // easeOutQuad
                group.rotation.z = e * (Math.PI * 0.5);
                group.position.y = e * 0.12; // лёг на бок, немного приподняли от земли по краю
            }
            if (flashTime > 0) {
                flashTime -= dt;
                if (flashTime <= 0) muzzleFlash.visible = false;
            }
            return;
        }

        const speed = pose.speed || 0;
        const aimingK = pose.aiming ? 1 : 0;

        // Фаза шага: частота пропорциональна скорости
        const normSpeed = Math.min(speed / MAX_RUN_SPEED, 1);
        phase += dt * speed * STRIDE_FREQ_PER_MS;

        const swing = normSpeed * LEG_SWING * (pose.aiming ? AIM_STRIDE_SCALE : 1);
        const sIn = Math.sin(phase);
        const cIn = Math.cos(phase);

        // Ноги противофазно; колени сгибаются на «оттянутой» ноге
        rightHip.rotation.x = sIn * swing;
        leftHip.rotation.x = -sIn * swing;
        rightKnee.rotation.x = Math.max(0, -cIn) * swing * 1.4;
        leftKnee.rotation.x = Math.max(0, cIn) * swing * 1.4;

        // Покачивание корпуса вверх-вниз, двойная частота шага
        const bob = Math.abs(Math.sin(phase)) * normSpeed * BOB_AMP;
        torsoGroup.position.y = TORSO_Y + bob;
        headGroup.position.y = HEAD_Y + bob;
        rightShoulder.position.y = SHOULDER_Y + bob;
        leftShoulder.position.y = SHOULDER_Y + bob;
        // Лёгкий наклон корпуса вперёд при беге
        torsoGroup.rotation.x = normSpeed * 0.12;
        headGroup.rotation.x = -normSpeed * 0.05;

        // Отдача: при firing прыгает в 1, затухает по экспоненте
        if (pose.firing) recoil = 1;
        recoil *= Math.exp(-dt * RECOIL_DECAY);
        if (recoil < 0.001) recoil = 0;

        // Руки: базовая поза держания автомата, кач при беге, подъём при прицеливании
        // Правая рука (с автоматом)
        const armSwing = -sIn * swing * ARM_SWING_SCALE;
        const aimLift = aimingK * AIM_ARM_LIFT;
        rightShoulder.rotation.x = -1.05 - aimLift + armSwing + recoil * RECOIL_ARM;
        rightElbow.rotation.x = -0.35 + aimLift * 0.5 + recoil * RECOIL_ARM * 0.5;
        // Левая рука — поддержка автомата спереди
        leftShoulder.rotation.x = -0.95 - aimLift - armSwing + recoil * RECOIL_ARM * 0.7;
        leftElbow.rotation.x = -0.5 + aimLift * 0.4 + recoil * RECOIL_ARM * 0.3;

        // Отдача автомата назад по +Z
        gun.position.z = -0.08 + recoil * RECOIL_GUN;

        // Вспышка: таймер 50 мс
        if (flashTime > 0) {
            flashTime -= dt;
            if (flashTime <= 0) {
                flashTime = 0;
                muzzleFlash.visible = false;
            }
        }
    }

    /**
     * Окрасить опознавательные полосы в командный цвет (слабое свечение).
     * @param {number|string} hex - цвет команды
     */
    function setTeamColor(hex) {
        matTeam.color.set(hex);
        matTeam.emissive.set(hex);
        matTeam.emissiveIntensity = TEAM_EMISSIVE;
    }

    /**
     * Показать дульную вспышку на FLASH_TIME секунд.
     */
    function playMuzzleFlash() {
        if (dead) return;
        muzzleFlash.visible = true;
        flashTime = FLASH_TIME;
    }

    /**
     * Перевести модель в состояние смерти / воскресить.
     * @param {boolean} on
     */
    function setDead(on) {
        if (dead === on) return;
        dead = on;
        if (!on) {
            // Воскрешение: мгновенно встаём, сбрасываем прогресс падения
            deathT = 0;
            group.rotation.z = 0;
            group.position.y = 0;
            phase = 0;
            recoil = 0;
            muzzleFlash.visible = false;
            flashTime = 0;
        } else {
            deathT = 0;
        }
    }

    /**
     * Освободить все ресурсы модели (геометрии, материалы).
     */
    function dispose() {
        if (group.parent) group.parent.remove(group);
        group.traverse((obj) => {
            if (obj.isMesh) {
                obj.geometry.dispose();
            }
        });
        matUniform.dispose();
        matVest.dispose();
        matHelmet.dispose();
        matDark.dispose();
        matTeam.dispose();
        matFlash.dispose();
    }

    return { group, update, setTeamColor, playMuzzleFlash, setDead, dispose };
}
