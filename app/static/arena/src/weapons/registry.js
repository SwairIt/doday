/**
 * Реестр оружия Doday Arena.
 * Чистые данные: описания стволов + простой доступ по идентификатору.
 * Единицы: метры, секунды, радианы, выстрелы в минуту.
 */

/** Угол отдачи по pitch — вверх (положительный), yaw — вправо (положительный), радианы */
const RIFLE_RECOIL_PATTERN = [
    [0.014, 0.000],
    [0.015, 0.004],
    [0.016, -0.005],
    [0.015, 0.006],
    [0.017, -0.003],
    [0.016, 0.005],
    [0.018, -0.006],
    [0.017, 0.002],
    [0.018, -0.004],
    [0.019, 0.005],
    [0.018, -0.002],
    [0.020, 0.004],
];

export const WEAPONS = {
    rifle: {
        id: 'rifle',
        name: 'Штурмовая винтовка',
        damage: 24,
        headshotMultiplier: 2.0,
        rpm: 640,
        magazine: 30,
        reserveAmmo: 120,
        reloadTime: 2.1,

        /** Базовый разброс (радианы) от бедра и в прицеле */
        spreadHip: 0.028,
        spreadAds: 0.004,

        /** Циклический паттерн отдачи: [pitch, yaw] на каждый выстрел */
        recoilPattern: RIFLE_RECOIL_PATTERN,
        /** Скорость возврата прицела после отдачи (рад/с) */
        recoilRecovery: 8.0,

        /** FOV камеры в режиме прицеливания и время входа/выхода (с) */
        adsFov: 50,
        adsTime: 0.18,

        /** Затухание урона по дистанции: от start до end (м), множитель падает до minFactor */
        rangeFalloff: {
            start: 25,
            end: 60,
            minFactor: 0.5,
        },

        /** Начальная скорость пули (м/с) для хитскан-симуляции полёта */
        muzzleVelocity: 850,

        /** Параметры примитивов для процедурной сборки модели в руках.
         *  Каждая деталь: тип, размеры, позиция и вращение в локальных координатах,
         *  color — цвет материала, metal/rough — параметры PBR. */
        model: {
            parts: [
                // Ствольная коробка
                { type: 'box', size: [0.55, 0.09, 0.11], position: [0, 0, 0], rotation: [0, 0, 0], color: 0x2a2d33, metal: 0.8, rough: 0.45 },
                // Ствол
                { type: 'cylinder', radiusTop: 0.022, radiusBottom: 0.022, height: 0.42, position: [0.45, 0.01, 0], rotation: [0, 0, -Math.PI / 2], color: 0x1c1e22, metal: 0.9, rough: 0.35 },
                // Цевье
                { type: 'box', size: [0.28, 0.07, 0.09], position: [0.32, -0.01, 0], rotation: [0, 0, 0], color: 0x3a3428, metal: 0.2, rough: 0.8 },
                // Дульный тормоз
                { type: 'cylinder', radiusTop: 0.03, radiusBottom: 0.034, height: 0.09, position: [0.7, 0.01, 0], rotation: [0, 0, -Math.PI / 2], color: 0x1c1e22, metal: 0.85, rough: 0.4 },
                // Приклад
                { type: 'box', size: [0.24, 0.1, 0.07], position: [-0.38, -0.01, 0], rotation: [0, 0, -0.08], color: 0x3a3428, metal: 0.2, rough: 0.8 },
                // Пистолетная рукоятка
                { type: 'box', size: [0.05, 0.13, 0.06], position: [-0.12, -0.11, 0], rotation: [0, 0, 0.25], color: 0x2a2d33, metal: 0.4, rough: 0.6 },
                // Магазин
                { type: 'box', size: [0.07, 0.18, 0.05], position: [0.08, -0.13, 0], rotation: [0, 0, 0.1], color: 0x33363c, metal: 0.6, rough: 0.5 },
                // Мушка
                { type: 'box', size: [0.02, 0.05, 0.015], position: [0.62, 0.075, 0], rotation: [0, 0, 0], color: 0x1c1e22, metal: 0.7, rough: 0.4 },
                // Целик
                { type: 'box', size: [0.03, 0.045, 0.05], position: [-0.2, 0.07, 0], rotation: [0, 0, 0], color: 0x1c1e22, metal: 0.7, rough: 0.4 },
                // Планка сверху
                { type: 'box', size: [0.3, 0.015, 0.03], position: [-0.02, 0.055, 0], rotation: [0, 0, 0], color: 0x22242a, metal: 0.75, rough: 0.45 },
            ],
            /** Позиция модели в руках относительно камеры: от бедра и в прицеле */
            hipOffset: [0.25, -0.22, -0.45],
            adsOffset: [0, -0.048, -0.28],
            /** Позиция дульного среза в локальных координатах (для вспышки и спавна пуль) */
            muzzlePosition: [0.76, 0.01, 0],
            /** Позиция окна выброса гильз */
            ejectPosition: [0.05, 0.03, 0.06],
            /** Общий масштаб модели */
            scale: 1.0,
        },
    },
};

/**
 * Возвращает описание оружия по идентификатору.
 * @param {string} id идентификатор оружия из WEAPONS
 * @returns {object} описание оружия
 * @throws {Error} если оружие с таким id не зарегистрировано
 */
export function getWeapon(id) {
    const weapon = WEAPONS[id];
    if (weapon === undefined) {
        throw new Error(`Неизвестное оружие: "${id}"`);
    }
    return weapon;
}
