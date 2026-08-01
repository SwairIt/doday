/**
 * src/weapons/weapon.js
 * Логика оружия в руках: стрельба, отдача, разброс, перезарядка,
 * вью-модель из примитивов, покачивание при ходьбе, хитмаркер.
 * Сам не реализует баллистику и эффекты — дёргает fireHitscan и fx.
 */

import * as THREE from 'three';
import { buildRifleViewModel } from './viewmodel.js';

/** Слой вью-модели: её освещает отдельный свет, не влияющий на мир. */
const VIEWMODEL_LAYER = 1;
import { bus } from '../core/events.js';
import { fireHitscan } from './ballistics.js';
import { getWeapon } from './registry.js';

// --- Константы, недостающие в исходной генерации ---
const KICK_RETURN = 14.0;
/** Докуда тянуть трассер, если пуля никуда не попала, метры. */
const TRACER_RANGE = 90;      // скорость возврата ствола после отдачи, 1/с
// Модель крупная и близко к камере, поэтому даже небольшой подброс
// читается как сильная тряска. Ход отдачи уменьшен втрое.
const VMODEL_KICK = 0.015;    // подброс модели оружия при выстреле, м
const BOB_AMP = 1.0;          // общий множитель покачивания при ходьбе

// ---------------------------------------------------------------------------
// Константы настройки ощущения оружия
// ---------------------------------------------------------------------------

/** Глубина и ширина покачивания вью-модели при ходьбе (метры). */
const BOB_AMPLITUDE_X = 0.012;
const BOB_AMPLITUDE_Y = 0.009;
/** Частота покачивания при полной скорости ходьбы (рад/с). */
const BOB_SPEED = 9.0;
/** Скорость возврата позы вью-модели к нейтрали. */
const POSE_LERP = 12.0;
/** Скорость перехода в режим прицеливания (ADS) и обратно. */
const ADS_LERP = 14.0;
/** Скорость восстановления камеры после отдачи (рад/с) и её затухание у прицеливания. */
const RECOIL_RECOVER = 9.0;
const RECOIL_ADS_DAMPING = 0.55;
/** Множитель возврата отдачи: доля, которая «возвращается» после выстрела. */
const RECOIL_RETURN = 0.6;
/** Порог скорости игрока, ниже которого покачивания нет. */
const MOVE_EPSILON = 0.25;
/** Масштаб случайного разброса вью-модели при выстреле. */
const KICK_POS_Z = 0.06;
const KICK_ROT_X = 0.05;

const _vA = new THREE.Vector3();
const _vB = new THREE.Vector3();
const _euler = new THREE.Euler(0, 0, 0, 'YXZ');
// Временные объекты, недостающие в исходной генерации (пул, без аллокаций в кадре)
const _pos = new THREE.Vector3();
const _right = new THREE.Vector3();
const _up = new THREE.Vector3();
const _v1 = new THREE.Vector3();
const _v2 = new THREE.Vector3();
const _v3 = new THREE.Vector3();

// ---------------------------------------------------------------------------
// Поза вью-модели
// ---------------------------------------------------------------------------

/** Итоговая поза: смесь hip/ads + покачивание + кик. */
function _applyPose(vm, pose, t) {
    vm.group.position.set(
        pose.posX + pose.bobX,
        pose.posY + pose.bobY,
        pose.posZ + pose.kickZ
    );
    vm.group.rotation.set(
        pose.rotX + pose.kickRotX,
        pose.rotY,
        pose.rotZ + Math.sin(t) * pose.roll
    );
}

/** Поза вью-модели «от бедра» и «в прицеле»: позиция + поворот. */
function _lerp(a, b, t) { return a + (b - a) * t; }

// ---------------------------------------------------------------------------
// Вью-модель: сборка из примитивов
// ---------------------------------------------------------------------------

/**
 * Собирает вью-модель оружия из примитивов: ствольная коробка, ствол,
 * магазин, приклад, рукоять и прицельные приспособления.
 * @param {string} id идентификатор оружия из реестра
 * @returns {{group: THREE.Group, parts: Object<string, THREE.Mesh>}}
 */
function _buildViewModel(id) {
    const group = new THREE.Group();
    group.name = 'viewmodel_' + id;

    // Вью-модель светлее и с лёгким самосвечением: сцена вечерняя, и обычный
    // тёмный металл в руках превращается в чёрное пятно.
    const metal = new THREE.MeshStandardMaterial({
        color: 0x8b9099, roughness: 0.42, metalness: 0.65,
        emissive: 0x2a2f36, emissiveIntensity: 0.9,
    });
    const dark  = new THREE.MeshStandardMaterial({ color: 0x4a4d52, roughness: 0.6, metalness: 0.4,
        emissive: 0x1c1f23, emissiveIntensity: 0.8 });
    // Цевьё и приклад — тёплое дерево, как на AK: контраст с металлом.
    const grip  = new THREE.MeshStandardMaterial({ color: 0x8a5a2e, roughness: 0.85, metalness: 0.02,
        emissive: 0x2a1a0c, emissiveIntensity: 0.8 });

    const parts = {};

    // Ствольная коробка
    const receiver = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.07, 0.34), metal);
    receiver.position.set(0, 0, -0.02);
    group.add(receiver);
    parts.receiver = receiver;

    // Ствол
    const barrelLen = id === 'pistol' ? 0.12 : 0.28;
    const barrel = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.014, barrelLen, 10), dark);
    barrel.rotation.x = Math.PI / 2;
    barrel.position.set(0, 0.012, -0.19 - barrelLen * 0.5 + 0.05);
    group.add(barrel);
    parts.barrel = barrel;

    // Дульный срез — точка вылета для вспышки
    const muzzle = new THREE.Object3D();
    muzzle.name = 'muzzle';
    muzzle.position.set(0, 0.012, barrel.position.z - barrelLen * 0.5);
    group.add(muzzle);
    parts.muzzle = muzzle;

    // Магазин
    const mag = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.12, 0.07), dark);
    mag.position.set(0, -0.085, -0.05);
    mag.rotation.x = 0.12;
    group.add(mag);
    parts.magazine = mag;

    // Пистолетная рукоять
    const handle = new THREE.Mesh(new THREE.BoxGeometry(0.045, 0.11, 0.055), grip);
    handle.position.set(0, -0.075, 0.09);
    handle.rotation.x = 0.28;
    group.add(handle);
    parts.handle = handle;

    // Приклад (у длинноствольного оружия)
    if (id !== 'pistol') {
        const stock = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.06, 0.16), grip);
        stock.position.set(0, -0.01, 0.22);
        group.add(stock);
        parts.stock = stock;

        // Цевье
        const handguard = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.05, 0.14), metal);
        handguard.position.set(0, -0.005, -0.24);
        group.add(handguard);
        parts.handguard = handguard;
    } else {
        // У пистолета — затвор
        const slide = new THREE.Mesh(new THREE.BoxGeometry(0.055, 0.045, 0.22), metal);
        slide.position.set(0, 0.035, -0.04);
        group.add(slide);
        parts.slide = slide;
    }

    // Мушка
    const frontPost = new THREE.Mesh(new THREE.BoxGeometry(0.006, 0.03, 0.006), dark);
    frontPost.position.set(0, 0.055, -0.18);
    group.add(frontPost);

    // Целик
    const rearSight = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.025, 0.01), dark);
    rearSight.position.set(0, 0.05, 0.06);
    group.add(rearSight);

    // Свечение для прицельной точки в ADS у автоматики — упрощённо,
    // прицеливание сводится к смещению позы под линию прицела.

    group.traverse((o) => {
        if (o.isMesh) {
            o.frustumCulled = false; // вью-модель всегда у камеры
            o.castShadow = false;
            o.receiveShadow = false;
        }
    });

    return { group, parts };
}

// ---------------------------------------------------------------------------
// Хитмаркер
// ---------------------------------------------------------------------------

/**
 * Создаёт DOM-хитмаркер: четыре штриха, вспышка при попадании.
 * @returns {{show: (kill: boolean) => void, element: HTMLElement}}
 */
function _createHitmarker() {
    const element = document.createElement('div');
    element.className = 'hitmarker';
    element.style.cssText =
        'position:fixed;left:50%;top:50%;width:0;height:0;pointer-events:none;' +
        'opacity:0;z-index:40;transition:opacity 90ms linear;';

    const strokes = [];
    for (let i = 0; i < 4; i++) {
        const s = document.createElement('span');
        const rx = (i % 2 === 0) ? 1 : -1;
        const ry = (i < 2) ? 1 : -1;
        s.style.cssText =
            'position:absolute;width:2px;height:9px;background:#fff;' +
            'box-shadow:0 0 2px rgba(0,0,0,.8);' +
            'transform:translate(' + (rx * 6 - 1) + 'px,' + (ry * 6 - 4) + 'px) ' +
            'rotate(' + (45 * rx * ry) + 'deg);';
        element.appendChild(s);
        strokes.push(s);
    }
    document.body.appendChild(element);

    let hideTimer = 0;

    /**
     * Показывает хитмаркер. При убийстве штрихи становятся красными.
     * @param {boolean} kill
     */
    function show(kill) {
        const color = kill ? '#ff4444' : '#ffffff';
        for (const s of strokes) s.style.background = color;
        element.style.opacity = '1';
        window.clearTimeout(hideTimer);
        hideTimer = window.setTimeout(() => { element.style.opacity = '0'; }, 120);
    }

    return { show, element };
}

// ---------------------------------------------------------------------------
// createWeapon
// ---------------------------------------------------------------------------

/**
 * Создаёт оружие в руках игрока.
 *
 * @param {string} id идентификатор оружия из src/weapons/registry.js
 * @param {Object} deps внешние зависимости
 * @param {THREE.Camera} deps.camera камера игрока
 * @param {Object} deps.fx экземпляр эффектов (createWeaponFx)
 * @param {Function} deps.getTargets провайдер целей для хитскана: () => THREE.Object3D[]
 * @param {Function} [deps.getMoveSpeed] провайдер текущей скорости игрока, м/с
 * @param {Object} [deps.settings] настройки (Settings)
 * @returns {{
 *   update: (dt: number, input: Object, camera: THREE.Camera) => void,
 *   fire: () => boolean,
 *   reload: () => boolean,
 *   setAds: (on: boolean) => void,
 *   readonly ammo: number,
 *   readonly reserve: number,
 *   readonly state: string
 * }}
 */
export function createWeapon(id, deps) {
    // --- Конфиг из реестра ---------------------------------------------------
    const def = getWeapon(id);
    const cfg = Object.assign({
        rpm: 400,
        auto: true,
        damage: 25,
        headshotMult: 2.0,
        magazine: 30,
        reserveAmmo: 120,
        reloadTime: 2.0,
        // Разброс: радианы конуса от бедра и в прицеле
        spreadHip: 0.022,
        spreadAds: 0.005,
        // Отдача: паттерн отклонения камеры на выстрел [pitch, yaw]
        recoilPattern: [[0.012, 0.0]],
        // Позы вью-модели
        hipPos: new THREE.Vector3(0.24, -0.19, -0.34),
        adsPos: new THREE.Vector3(0.0, -0.115, -0.22),
    }, def);

    const camera = deps.camera;
    const fx = deps.fx;
    const getTargets = deps.getTargets;
    const getMoveSpeed = deps.getMoveSpeed || (() => 0);

    // --- Внутреннее состояние ------------------------------------------------
    let ammo = cfg.magazine;
    let reserve = cfg.reserveAmmo;
    let state = 'ready'; // 'ready' | 'reloading';

    /** время до следующего выстрела */
    let fireCooldown = 0;
    /** таймер перезарядки */
    let reloadTimer = 0;
    /** была ли отпущена кнопка огня (для полуавтоматики) */
    let triggerReleased = true;
    /** индекс текущего шага паттерна отдачи */
    let recoilIndex = 0;
    /** накопленная визуальная отдача вью-модели (отскок назад) */
    let kick = 0;
    /** флаг прицеливания */
    let adsOn = false;
    /** сглаженный параметр прицеливания 0..1 */
    let adsBlend = 0;
    /** время жизни оружия для покачивания */
    let bobTime = 0;
    /** накопленный поворот камеры от отдачи с возвратом */
    const recoilOffset = { pitch: 0, yaw: 0 };

    // --- Вью-модель ---------------------------------------------------------
    // Винтовка получает детальную модель с руками в перчатках; остальные
    // стволы пока собираются прежним простым конструктором.
    const view = id === 'rifle'
        ? buildRifleViewModel({ quality: deps?.settings?.quality })
        : _buildViewModel(id, cfg);
    const model = view.group;
    // Старый конструктор кладёт точку дула в parts.muzzle, новый отдаёт
    // её как muzzlePoint. Берём то, что есть, иначе выстрел падает.
    const muzzle = view.muzzlePoint || view.parts.muzzle || view.group;
    camera.add(model);

    // Собственный свет вью-модели: сцена вечерняя, и без подсветки ствол
    // в руках сливается в чёрное пятно. Свет висит на камере, поэтому
    // на освещение мира не влияет.
    // Слой 1 — только вью-модель. Иначе свет, висящий на камере, засвечивает
    // весь мир: камера теперь в графе сцены, и её потомки-источники светят всем.
    model.traverse((node) => node.layers.set(VIEWMODEL_LAYER));
    camera.layers.enable(VIEWMODEL_LAYER);

    if (!camera.userData.viewmodelLight) {
        const key = new THREE.DirectionalLight(0xfff0dd, 2.6);
        key.position.set(0.6, 0.9, 0.4);
        key.layers.set(VIEWMODEL_LAYER);
        camera.add(key);
        const fill = new THREE.HemisphereLight(0xbfd4ff, 0x2b2620, 1.4);
        fill.layers.set(VIEWMODEL_LAYER);
        camera.add(fill);
        camera.userData.viewmodelLight = key;
    }
    model.position.copy(cfg.hipPos);
    // Ствол у самой камеры занимал пол-экрана: уменьшаем и отодвигаем.
    // Крупная модель у правого нижнего угла: дуло намеренно уходит за кадр,
    // как в CS — виден ресивер, магазин и рукоять, а не весь ствол.
    // Детальная винтовка собрана в других габаритах, поэтому масштаб свой.
    model.scale.setScalar(id === 'rifle' ? 0.95 : 1.45);
    model.rotation.y = 0.06;

    const muzzleWorld = new THREE.Vector3();
    const hitmarker = _createHitmarker();

    // --- Вспомогательные приватные функции ----------------------------------

    /**
     * Текущий разброс с учётом прицеливания.
     * @returns {number} радианы полуконуса
     */
    function currentSpread() {
        return cfg.spreadHip + (cfg.spreadAds - cfg.spreadHip) * adsBlend;
    }

    /**
     * Продлевает/прерывает перезарядку при выстреле.
     */
    function interruptReload() {
        if (state === 'reloading') {
            state = 'ready';
            reloadTimer = 0;
            bus.emit('weapon:reloadCancel', { id });
        }
    }

    /**
     * Применяет шаг отдачи к накопленному смещению камеры и вью-модели.
     */
    function applyRecoil() {
        const step = cfg.recoilPattern[recoilIndex % cfg.recoilPattern.length];
        recoilIndex++;
        recoilOffset.pitch += step[0];
        recoilOffset.yaw += step[1];
        kick = VMODEL_KICK;
    }

    /**
     * Выполняет один выстрел хитсканом и обработку попаданий.
     * @param {THREE.Camera} cam
     */
    function shootOnce(cam) {
        // направление с разбросом вокруг оси камеры
        cam.getWorldDirection(_v1);
        _v2.copy(_v1);
        const spread = currentSpread();
        const a = Math.random() * Math.PI * 2;
        const r = Math.sqrt(Math.random()) * spread;
        _right.set(1, 0, 0).applyQuaternion(cam.quaternion);
        _up.set(0, 1, 0).applyQuaternion(cam.quaternion);
        _v2.addScaledVector(_right, Math.cos(a) * r)
           .addScaledVector(_up, Math.sin(a) * r)
           .normalize();

        const result = fireHitscan({
            // Без мира рейкаст по геометрии невозможен — стрельба била бы
            // только по ботам и проходила сквозь стены.
            world: deps.world,
            origin: cam.getWorldPosition(_v3),
            direction: _v2,
            damage: cfg.damage,
            headshotMult: cfg.headshotMult,
            targets: getTargets(),
            maxDistance: 300,
        });

        muzzle.getWorldPosition(muzzleWorld);
        // muzzleFlash(pos, dir): без направления спрайт тонет в стволе.
        fx.muzzleFlash(muzzleWorld, _v2);
        // Звук выстрела: без него стрельба ощущается мёртвой.
        deps.audio?.play?.('shot', muzzleWorld);
        // Трассер рисуем ВСЕГДА, а не только при попадании: иначе выстрел
        // в небо или мимо цели не оставляет никакого следа, и кажется,
        // что пули не летят.
        if (result && result.point) {
            _v3.copy(result.point);
        } else {
            _v3.copy(muzzleWorld).addScaledVector(_v2, TRACER_RANGE);
        }
        fx.tracer(muzzleWorld, _v3);

        if (result && result.point) {
            fx.impact(result.point, result.normal || result.face && result.face.normal || _up, result.target ? 'flesh' : 'concrete');
        }

        if (result && result.hit) {
            hitmarker.show(Boolean(result.kill));
            bus.emit('weapon:hit', {
                id, damage: result.damage, kill: Boolean(result.kill),
                headshot: Boolean(result.headshot), point: result.point,
            });
        }

        bus.emit('weapon:shot', { id, ammo, reserve });
        applyRecoil();
    }

    // --- Публичный API -------------------------------------------------------

    /**
     * Пытается произвести выстрел (один, с учётом скорострельности управляет update/fire).
     * @returns {boolean} произошёл ли выстрел
     */
    function fire() {
        // Пустой магазин при нажатии — сразу перезаряжаемся, иначе выглядит
        // так, будто оружие сломалось: щелчков нет, выстрелов нет.
        if (ammo <= 0 && state !== 'reloading') {
            reload();
            return false;
        }
        if (state !== 'ready') return false;
        if (fireCooldown > 0) return false;
        if (ammo <= 0) {
            bus.emit('weapon:dry', { id });
            reload();
            return false;
        }
        interruptReload();
        ammo--;
        fireCooldown = 60 / cfg.rpm;
        shootOnce(camera);
        return true;
    }

    /**
     * Начинает перезарядку, если есть смысл и резерв.
     * @returns {boolean} началась ли перезарядка
     */
    function reload() {
        if (state === 'reloading') return false;
        if (ammo >= cfg.magazine) return false;
        if (reserve <= 0) return false;
        state = 'reloading';
        reloadTimer = cfg.reloadTime;
        bus.emit('weapon:reloadStart', { id, time: cfg.reloadTime });
        return true;
    }

    /**
     * Включает/выключает прицеливание.
     * @param {boolean} on
     */
    function setAds(on) {
        adsOn = Boolean(on) && state !== 'reloading';
    }

    /**
     * Обновление оружия: таймеры, автоогонь, отдача, поза вью-модели.
     * @param {number} dt секунды
     * @param {Object} input ввод игрока: {fire:boolean, reload:boolean, ads:boolean}
     * @param {THREE.Camera} cam камера для коррекции выстрела/позы
     */
    function update(dt, input, cam) {
        if (dt <= 0) return;

        // Таймеры
        if (fireCooldown > 0) fireCooldown -= dt;

        if (input && input.ads !== undefined) setAds(input.ads);
        adsBlend += ((adsOn ? 1 : 0) - adsBlend) * (1 - Math.exp(-ADS_LERP * dt));

        // Перезарядка
        if (state === 'reloading') {
            reloadTimer -= dt;
            if (input && input.fire) interruptReload();
            if (reloadTimer <= 0 && state === 'reloading') {
                const need = cfg.magazine - ammo;
                const take = Math.min(need, reserve);
                ammo += take;
                reserve -= take;
                state = 'ready';
                bus.emit('weapon:reloadEnd', { id, ammo, reserve });
            }
        }

        // Огонь по вводу
        const wantFire = Boolean(input && input.fire);
        if (wantFire) {
            if (cfg.auto) {
                fire();
            } else if (triggerReleased) {
                if (fire()) triggerReleased = false;
            }
        }
        if (!wantFire) triggerReleased = true;

        // Ручная перезарядка по вводу
        if (input && input.reload) {
            reload();
            if (input.reloadOnce !== undefined) input.reload = false;
        }

        // Отдача камеры: возврат к нулю
        recoilOffset.pitch += (0 - recoilOffset.pitch) * (1 - Math.exp(-RECOIL_RETURN * dt));
        recoilOffset.yaw += (0 - recoilOffset.yaw) * (1 - Math.exp(-RECOIL_RETURN * dt));
        if (cam && cam.rotation) {
            // применяем как добавку — контроллер камеры читает weapon.recoil
            cam.rotation.x += recoilOffset.pitch * dt * 60 * 0;
        }

        // Вью-модель: отскок и покачивание
        kick += (0 - kick) * (1 - Math.exp(-KICK_RETURN * dt));
        const speed = getMoveSpeed();
        bobTime += dt * (BOB_SPEED + speed * 0.9) * (1 - adsBlend * 0.85);
        // Покачивание оставлено едва заметным: в CS ствол при ходьбе
        // практически не гуляет, крупная модель усиливает любое смещение.
        const bobAmp = BOB_AMP * 0.18 * Math.min(speed / 6, 1) * (1 - adsBlend * 0.9);
        const bx = Math.cos(bobTime) * bobAmp;
        const by = Math.abs(Math.sin(bobTime)) * bobAmp * 1.4;

        _pos.copy(cfg.hipPos).lerp(cfg.adsPos, adsBlend);
        _pos.x += bx;
        _pos.y += by;
        _pos.z += kick * (1 - adsBlend * 0.7);
        model.position.copy(_pos);
        model.rotation.x = kick * 0.9;
        model.rotation.z = 0.06 + bx * 0.4;

        // Перезарядка: ствол уходит вниз и вбок с наклоном, магазин выпадает
        // и встаёт на место. Без этого перезарядка никак не читается на экране.
        if (state === 'reloading') {
            const t = 1 - reloadTimer / cfg.reloadTime;      // 0..1 по ходу
            const arc = Math.sin(t * Math.PI);               // плавно туда и обратно
            model.position.y -= arc * 0.10;
            model.position.x += arc * 0.04;
            model.position.z += arc * 0.05;
            model.rotation.x += arc * 0.55;
            model.rotation.z += arc * 0.35;
            if (view.parts.magazine) {
                // Магазин уходит вниз в первой половине и возвращается во второй.
                const drop = t < 0.5 ? t * 2 : (1 - t) * 2;
                view.parts.magazine.position.y = -0.085 - drop * 0.11;
                view.parts.magazine.rotation.z = drop * 0.5;
            }
        } else if (view.parts.magazine) {
            view.parts.magazine.position.y = -0.085;
            view.parts.magazine.rotation.z = 0;
        }
    }

    return {
        update,
        fire,
        reload,
        setAds,
        /** накопленная отдача для контроллера камеры */
        recoilOffset,
        get ammo() { return ammo; },
        get reserve() { return reserve; },
        get state() { return state; },
        get ads() { return adsOn; },
        get definition() { return cfg; },
        get model() { return model; },
    };
}
