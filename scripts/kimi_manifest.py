"""Манифест игры Doday Arena: какие файлы генерировать и что в каждом должно быть.

Гранулярность «один файл — один запрос» выбрана не от красоты: у Kimi K3 через
TokenRouter соединение живёт ~300 секунд, за которые при reasoning_effort=low
выходит около 5 КБ кода. Более крупные задания модель не успевает дописать.

CONTRACT — общий кусок контекста, который идёт в каждый запрос: без него файлы
не состыкуются по именам и сигнатурам.
"""

from __future__ import annotations

CONTRACT = """
Проект: браузерный FPS «Doday Arena» на Three.js, отдаётся статикой с /game/.
Сборщика нет — только нативные ES-модули. Зависимости через importmap:
  three            -> https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js
  three/addons/    -> https://cdn.jsdelivr.net/npm/three@0.180.0/examples/jsm/
  rapier           -> https://cdn.jsdelivr.net/npm/@dimforge/rapier3d-compat@0.19.3/rapier.mjs

Общие соглашения (соблюдать строго, файлы обязаны состыковаться):
- Каждый модуль экспортирует именованные экспорты, никаких default.
- Единицы: метры, секунды, радианы. dt всегда в секундах.
- Класс Settings (src/core/settings.js) даёт: settings.quality ('low'|'medium'|'high'),
  settings.sensitivity, settings.fov, settings.volume, settings.get(key), settings.set(key, value).
- Ассетов на диске нет: вся геометрия и текстуры генерируются кодом.
- Комментарии по-русски, JSDoc на публичных методах, магические числа — в константы.
- Никаких аллокаций в горячем цикле: переиспользовать векторы через модульные временные.

Формат ответа: ТОЛЬКО код запрошенного файла в одном блоке ```javascript
(или ```html / ```css по типу файла). Без вступлений, без объяснений после.
"""

# (путь относительно app/static/game/, описание задачи)
FILES: list[tuple[str, str]] = [
    (
        "src/core/settings.js",
        "Класс Settings: уровни качества low/medium/high с автоопределением по "
        "navigator.hardwareConcurrency, devicePixelRatio и наличию тача; персист в "
        "localStorage под ключом 'doday-arena-settings'; поля sensitivity (0.1..3), "
        "fov (60..110), volume (0..1); методы get/set/reset; событие onChange(callback). "
        "Экспортировать также QUALITY_PRESETS с параметрами: shadowMapSize, "
        "maxPixelRatio, postfx (bool), shadowCascades, fogDensity, drawDistance.",
    ),
    (
        "src/core/events.js",
        "Минимальная шина событий: класс EventBus с методами on(name, fn), "
        "off(name, fn), emit(name, payload), once(name, fn). Без зависимостей. "
        "Защита от исключений в подписчиках — один упавший обработчик не должен "
        "ломать остальные.",
    ),
    (
        "src/core/loop.js",
        "Класс Loop — игровой цикл с фиксированным шагом физики. Конструктор "
        "принимает {step: 1/60, maxSubSteps: 5}. Методы: start(), stop(), "
        "onFixed(fn) для физики (получает фиксированный dt), onRender(fn) для "
        "рендера (получает alpha-интерполяцию 0..1 и реальный dt). Аккумулятор "
        "времени, защита от spiral of death при долгих кадрах, автопауза по "
        "document visibilitychange, счётчик FPS со сглаживанием (свойство loop.fps).",
    ),
    (
        "src/render/renderer.js",
        "Функция createRenderer(canvas, settings) -> {renderer, resize, "
        "updateAdaptiveResolution(fps)}. WebGLRenderer с antialias по уровню "
        "качества, ACESFilmicToneMapping, outputColorSpace = SRGBColorSpace, "
        "shadowMap PCFSoft. Адаптивное разрешение: если fps ниже 55, снижать "
        "множитель разрешения шагами до 0.6; если стабильно выше 58 — поднимать "
        "обратно к пределу качества. Обработчик resize с учётом devicePixelRatio.",
    ),
    (
        "src/render/sky.js",
        "Функция createSky(scene, renderer, settings) -> {update(dt), envMap}. "
        "Процедурное закатное небо: большая сфера с BackSide и собственным "
        "ShaderMaterial (градиент горизонт-зенит, диск солнца с ореолом, лёгкая "
        "дымка у горизонта). Генерация environment map через PMREMGenerator из "
        "этого же неба и присвоение scene.environment. Экспоненциальный туман "
        "FogExp2 в тон горизонта, плотность из QUALITY_PRESETS.",
    ),
    (
        "src/render/lighting.js",
        "Функция createLighting(scene, settings) -> {sun, update(playerPosition)}. "
        "DirectionalLight как солнце низко над горизонтом в тон закату, тени с "
        "размером карты из QUALITY_PRESETS, ортографическая камера теней, которая "
        "следует за игроком (метод update подвигает её, чтобы тени не пропадали "
        "вдали). HemisphereLight для мягкой заливки. На качестве low тени выключены.",
    ),
    (
        "src/world/textures.js",
        "Процедурные PBR-текстуры через canvas, все с повторением (RepeatWrapping) "
        "и корректным colorSpace. Экспортировать функции: makeConcrete(), "
        "makeAsphalt(), makeBrick(), makeMetal(), makeWindowAtlas(). Каждая "
        "возвращает {map, normalMap, roughnessMap}. Нормали считать из карты высот "
        "по соседним пикселям. Размер текстур 512, кэшировать результат по имени.",
    ),
    # Город разбит на четыре модуля намеренно: одним файлом он не влезает в
    # окно модели — на шестом круге продолжений швы ломают синтаксис.
    (
        "src/world/rng.js",
        "Детерминированный ГПСЧ: экспорт mulberry32(seed) -> функция random() в "
        "[0,1), а также createRng(seed) -> {random(), range(min,max), int(min,max), "
        "pick(array), chance(p)}. Никаких зависимостей, только чистые функции.",
    ),
    (
        "src/world/streets.js",
        "Сетка улиц квартала 200x200 м. Экспорт buildStreets(settings, rng) -> "
        "{meshes, colliders, spawnPoints, plots}. Дороги с асфальтом, тротуары с "
        "бордюром высотой 0.14 м, разметка. Центры дорог по координатам "
        "[-80,-40,0,40,80]. plots — список свободных участков {x, z, w, d} под "
        "здания. spawnPoints — точки на проезжей части и тротуарах. "
        "colliders — только бордюры, массив {position:[x,y,z], size:[w,h,d]}. "
        "Текстуры брать из src/world/textures.js.",
    ),
    (
        "src/world/buildings.js",
        "Здания на участках. Экспорт buildBuildings(plots, settings, rng) -> "
        "{meshes, colliders}. Высота 8..34 м; у трети первый этаж проходной "
        "(аркада на колоннах высотой 4 м) — это укрытия; окна эмиссивными "
        "инстансами (InstancedMesh) со случайным включением света; запечённое "
        "затенение в вершинных цветах — низ и углы темнее; LOD для дальних. "
        "Коллайдер на здание — один кубоид, у аркадных — только колонны.",
    ),
    (
        "src/world/city.js",
        "Сборка города: экспорт buildCity(scene, settings, seed) -> "
        "{group, colliders, spawnPoints}. Вызывает createRng, buildStreets, "
        "buildBuildings, добавляет уличный декор через InstancedMesh (фонари, "
        "машины-коробки, контейнеры, отбойники), складывает всё в THREE.Group и "
        "добавляет в сцену, объединяет коллайдеры и точки спавна. "
        "Файл-композитор: сам геометрию улиц и зданий не строит.",
    ),
    (
        "styles/hud.css",
        "Стили страницы и загрузочного экрана: тёмная тема, canvas на весь экран "
        "без скролла, системные шрифты, safe-area-inset для мобилок, экран "
        "загрузки с полосой прогресса и процентом, FPS-счётчик в углу, "
        "запрет выделения и тач-callout. Никаких внешних шрифтов и картинок.",
    ),
    (
        "index.html",
        "Точка входа: importmap с three, three/addons/ и rapier (версии из "
        "контракта), canvas#game, экран загрузки с полосой и процентом, "
        "подключение styles/hud.css и src/main.js как модуля, meta viewport с "
        "viewport-fit=cover, тёмный theme-color, русский lang. Без внешних "
        "скриптов кроме importmap-зависимостей.",
    ),
    (
        "src/main.js",
        "Bootstrap. В разметке уже есть: canvas#game, оверлей #loading-screen с "
        "полосой #loading-bar-fill, процентом #loading-percent и подписью "
        "#loading-status — используй ИМЕННО эти идентификаторы, новых не создавай "
        "и canvas не добавляй в DOM повторно. Порядок: Settings → createRenderer "
        "(canvas#game) → THREE.Scene → createSky → createLighting → буферы "
        "текстур → buildCity → initPhysics (await, вернёт world) → "
        "addGroundPlane(world) → buildStaticColliders(world, city.colliders) → "
        "временная орбитальная камера OrbitControls для облёта → Loop с "
        "onFixed/onRender → скрыть #loading-screen. Экспортировать объект Game. "
        "Если WebGL2 недоступен — понятное сообщение по-русски вместо игры. "
        "ВАЖНО: вызывай функции строго по сигнатурам из карты ниже.",
    ),
    # --- фаза 1B: физика, игрок, управление ---
    (
        "src/world/collision.js",
        "Инициализация Rapier (у compat-сборки обязателен await RAPIER.init()) и "
        "сборка мира. Экспорт initPhysics() -> world, buildStaticColliders(world, "
        "colliders), где colliders — массив {position, size} из buildCity: создаёт "
        "неподвижные кубоиды. Плюс addGroundPlane(world) и raycast(world, origin, "
        "dir, maxDist, filter) -> {point, normal, distance, collider} | null. "
        "Гравитация -9.81.",
    ),
    (
        "src/core/input-state.js",
        "ТОЛЬКО структура состояния ввода, без слушателей событий. Класс "
        "InputState: поля move {x, y} в диапазоне -1..1, look {x, y} — дельта за "
        "кадр, кнопки fire/aim/jump/crouch/sprint/reload/interact как объекты "
        "{pressed, justPressed}. Методы: setButton(name, down), setMove(x, y), "
        "addLook(dx, dy), endFrame() — сбрасывает justPressed и обнуляет look, "
        "isTouch — статическое определение тача по 'ontouchstart' и "
        "maxTouchPoints. Файл маленький, до 120 строк.",
    ),
    (
        "src/core/input.js",
        "Слушатели клавиатуры и мыши поверх InputState из "
        "src/core/input-state.js. Экспорт createInput(canvas, settings) -> "
        "{state, dispose}. WASD и стрелки в move; Space — jump, Shift — sprint, "
        "Ctrl/C — crouch, R — reload, E — interact; ЛКМ — fire, ПКМ — aim. "
        "Pointer lock по клику на canvas, корректный выход по Esc и повторный "
        "захват; движение мыши в addLook с умножением на settings.sensitivity. "
        "Тач не трогать — он в src/ui/touch.js. Файл до 150 строк.",
    ),
    (
        "src/ui/touch.js",
        "Тач-управление поверх canvas: два виртуальных стика (левый — движение, "
        "правый — обзор свайпом в любой точке правой половины экрана) и кнопки "
        "fire/aim/jump/reload. Рисуется в DOM, не в canvas. Multi-touch: каждый "
        "палец отслеживается по identifier. Экспорт createTouchControls(container, "
        "input) -> {show, hide, destroy}. Скрыт на устройствах без тача. "
        "Учитывать safe-area, не перекрывать центр экрана.",
    ),
    (
        "src/player/controller.js",
        "Kinematic character controller на Rapier (KinematicCharacterController): "
        "капсула радиусом 0.35 и высотой 1.8. Гравитация, прыжок с coyote-time "
        "0.12 с и буфером нажатия 0.1 с, спринт, приседание (высота 1.0), слайд с "
        "сохранением импульса и затуханием, воздушный контроль, автоподъём на "
        "ступеньки до 0.35 м, скольжение вдоль стен. Экспорт createPlayer(world, "
        "spawnPoint) -> {update(dt, input, cameraYaw), position, velocity, grounded, "
        "state}. Ускорение и торможение экспоненциальные, не мгновенные.",
    ),
    (
        "src/player/camera.js",
        "Камера от первого лица: экспорт createPlayerCamera(settings) -> "
        "{camera, update(dt, player, input), applyRecoil(pitch, yaw), setAim(bool)}. "
        "Yaw/pitch с ограничением тангажа ±89°, FOV из настроек, плавный переход "
        "FOV при ADS и спринте, покачивание при ходьбе с амплитудой от скорости, "
        "тряска от выстрелов и приземления, отдача с возвратом по экспоненте.",
    ),
    # --- фаза 1C: оружие, боты, интерфейс, звук ---
    (
        "src/weapons/registry.js",
        "ЧИСТЫЕ ДАННЫЕ, без логики: экспорт WEAPONS — объект с описаниями стволов. "
        "Пока один: rifle. Поля — name (по-русски), damage, headshotMultiplier, "
        "rpm, magazine, reserveAmmo, reloadTime, spreadHip, spreadAds, "
        "recoilPattern (массив [pitch, yaw] на каждый выстрел, циклический), "
        "recoilRecovery, adsFov, adsTime, rangeFalloff {start, end, minFactor}, "
        "muzzleVelocity, model (параметры примитивов для сборки модели в руках). "
        "Экспортировать также getWeapon(id).",
    ),
    (
        "src/weapons/ballistics.js",
        "Hitscan-стрельба: экспорт fireHitscan(world, origin, direction, weapon, "
        "spread, rng) -> {hit, point, normal, distance, damage, target}. Разброс — "
        "равномерно в конусе. Спад урона по rangeFalloff. Пробитие тонких "
        "препятствий: до 2 рикошет-проходов с потерей урона. Использует raycast из "
        "src/world/collision.js. Без побочных эффектов и без работы со сценой.",
    ),
    (
        "src/weapons/fx.js",
        "Визуальные эффекты стрельбы через пулы объектов: трассеры (тонкие "
        "вытянутые меши, живут 0.08 с), вспышка у ствола (эмиссивный спрайт + "
        "короткий PointLight на высоком качестве), декали от попаданий "
        "(ориентированные по нормали плоскости, кольцевой буфер на 64 штуки), "
        "гильзы (динамические тела Rapier, исчезают через 3 с), искры. Экспорт "
        "createWeaponFx(scene, world, settings) -> {tracer, muzzleFlash, impact, "
        "ejectShell, update(dt)}. Ни одной аллокации в горячем пути.",
    ),
    (
        "src/weapons/weapon.js",
        "Логика оружия в руках: экспорт createWeapon(id, deps) -> {update(dt, "
        "input, camera), fire(), reload(), setAds(bool), ammo, reserve, state}. "
        "Скорострельность по rpm, автоогонь, отдача по recoilPattern с возвратом, "
        "разброс от бедра и в прицеле, перезарядка с таймером и прерыванием, "
        "модель из примитивов в углу экрана с покачиванием и анимацией отдачи, "
        "hitmarker при попадании. Дёргает ballistics и fx, сам их не реализует.",
    ),
    (
        "src/ai/perception.js",
        "Восприятие бота, без логики поведения и без работы со сценой. Экспорт "
        "createPerception(world, deps) -> {canSee(fromPos, targetPos, forwardDir), "
        "hearShot(fromPos, shotPos), leadTarget(fromPos, targetPos, targetVel, "
        "projectileSpeed)}. canSee: конус обзора 110 градусов плюс проверка "
        "видимости рейкастом через raycast из src/world/collision.js. hearShot: "
        "слышимость выстрела в радиусе 40 м. leadTarget: точка упреждения по "
        "скорости цели. Файл до 150 строк, чистые вычисления.",
    ),
    (
        "src/ai/bot.js",
        "Бот-противник: конечный автомат patrol -> search -> combat -> retreat. "
        "Экспорт createBot(scene, world, spawnPoint, deps) -> {update(dt, player), "
        "takeDamage(amount, point), alive, position}. Зрение, слух и упреждение "
        "БЕРИ ГОТОВЫМИ из src/ai/perception.js, не реализуй заново. Стрельба "
        "очередями с разбросом, поиск укрытия при низком здоровье, движение с "
        "обходом препятствий рейкастами. Модель — капсула с головой и цветной "
        "подсветкой, при смерти падает динамическим телом с импульсом. "
        "Файл до 250 строк.",
    ),
    (
        "src/ai/spawner.js",
        "Управление популяцией ботов: экспорт createSpawner(scene, world, "
        "spawnPoints, deps) -> {update(dt, player), spawnWave(count), alive, "
        "killed, reset()}. Спавн только вне поля зрения игрока и не ближе 25 м, "
        "пул переиспользуемых ботов, ограничение одновременно живых по уровню "
        "качества (low 6, medium 10, high 16).",
    ),
    (
        "src/ui/hud.js",
        "HUD в DOM поверх canvas: здоровье полосой, патроны «в магазине / запас», "
        "динамический прицел (разводится по текущему разбросу, краснеет при "
        "наведении на врага), hitmarker, killfeed списком на 5 строк, счётчик "
        "фрагов, индикатор урона по направлению источника, экран смерти с "
        "кнопкой возрождения. Экспорт createHud(container) -> {setHealth, setAmmo, "
        "setSpread, hitmarker, killfeed, showDeath, hideDeath, update(dt)}. "
        "Обновлять только изменившиеся узлы, не перерисовывать всё каждый кадр.",
    ),
    (
        "src/audio/audio.js",
        "Звук на WebAudio без единого файла: выстрел (шум с быстрой огибающей + "
        "низкочастотный удар), попадание, рикошет, шаги (фильтрованный шум с "
        "вариацией), перезарядка (щелчки), эмбиент города (гул на низких "
        "частотах). Позиционный звук через PannerNode. Экспорт createAudio("
        "listener) -> {play(name, position, volume), setListener(pos, forward), "
        "setMasterVolume(v), resume()}. Автозапуск после первого клика "
        "(политика браузеров), пул источников.",
    ),
]
