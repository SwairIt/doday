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
        "Точка сборки ВСЕЙ игры. В разметке уже есть: canvas#game, оверлей #loading-screen с полосой #loading-bar-fill, процентом #loading-percent и подписью #loading-status — используй ИМЕННО эти идентификаторы, новых не создавай, canvas в DOM не добавляй.\n\nОБЯЗАТЕЛЬНЫЕ ДЕТАЛИ, без них игра не запускается (проверено на реальном запуске):\n- createRenderer отдаёт обёртку {renderer, resize, updateAdaptiveResolution}: разбери её и сразу вызови resize(), иначе холст остаётся 300x150;\n- проверку WebGL2 делай на ОДНОРАЗОВОМ document.createElement('canvas'), не на игровом: занятый контекст ломает WebGLRenderer;\n- initPhysics асинхронна, дождись world до коллайдеров;\n- buildCity отдаёт {group, colliders, spawnPoints}.\n\nПОРЯДОК: Settings -> createRenderer + resize() -> THREE.Scene -> createSky -> createLighting -> buildCity -> await initPhysics -> addGroundPlane -> buildStaticColliders -> createInput -> createTrackpadInput -> createTouchControls -> createPlayer(world, city.spawnPoints[0]) -> createPlayerCamera -> createAudio -> createHud(document.body) -> createWeaponFx -> createWeapon -> createSpawner -> Loop.\n\nАДАПТЕР ВВОДА обязателен: InputState хранит move/look/buttons, контроллер читает input.moveX/moveZ/jump/crouch/sprint, камера — input.mouseDX/mouseDY. Держи ОДИН переиспользуемый объект и заполняй его каждый кадр, не создавай новый.\n\nАзимут камеры для контроллера бери из camera.getWorldDirection: Math.atan2(-dir.x, -dir.z) — камера своё состояние наружу не отдаёт.\n\ncreateWeapon(id, deps) ждёт deps {camera, fx, settings, getTargets, getMoveSpeed}: getTargets возвращает живых ботов от спавнера, getMoveSpeed — длину горизонтальной скорости игрока для разброса.\n\nЦИКЛ: в onFixed — синхронизация ввода, player.update, weapon.update, spawner.update, шаг физики. В onRender — playerCamera.update, lighting.update(player.position), обновление HUD (setHealth, setAmmo, setSpread), рендер, затем input.state.endFrame().\n\nСтрельба по кнопке fire, перезарядка по reload, смена оружия цифрами 1-6 и колесом мыши. Попадание в бота: bot.takeDamage, hud.hitmarker, звук через audio.play. Смерть бота — hud.addKill. Первая волна запускается после загрузки: spawner.spawnWave(5).\n\nЭкспортируй объект Game со всеми подсистемами. Если WebGL2 недоступен — понятное сообщение по-русски вместо игры.",
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
        "src/core/input-trackpad.js",
        "Управление под трекпад Mac, поверх InputState из "
        "src/core/input-state.js. Экспорт createTrackpadInput(canvas, settings, "
        "state) -> {enabled, dispose, setEnabled(on)}. Задача: играть без мыши. "
        "1) Автоопределение Mac и трекпада: navigator.platform/userAgentData "
        "содержит Mac, либо приходят wheel-события с deltaMode 0 и дробными "
        "значениями (тачпад), либо pointerType 'touch' на трекпаде. "
        "2) Обзор: pointer lock плюс сглаживание — накапливать movementX/Y и "
        "отдавать в state.addLook через экспоненциальный фильтр, чтобы рывки "
        "пальца не дёргали прицел; отдельный множитель чувствительности "
        "settings.trackpadSensitivity (по умолчанию 1.8, трекпад даёт меньшую "
        "дельту, чем мышь). Никакого ускорения курсора — только линейно. "
        "3) Двухпальцевый свайп БЕЗ pointer lock тоже должен вращать камеру: "
        "wheel с ctrlKey=false и небольшими дельтами — это скролл двумя "
        "пальцами, переводим в обзор. Это главный режим, если игрок не хочет "
        "захват курсора. "
        "4) Прицеливание переключателем, а не удержанием: правая кнопка на "
        "трекпаде неудобна, поэтому клавиша F и Shift-клик переключают ADS "
        "(state.setButton('aim', ...)), а удержание тоже продолжает работать. "
        "5) Стрельба: левый клик, пробел и клавиша J — чтобы можно было "
        "стрелять, не отрывая пальцы от трекпада. "
        "6) Обзор с клавиатуры как запасной вариант: стрелки вращают камеру с "
        "постоянной скоростью — на случай, если трекпад совсем не подходит. "
        "Все обработчики снимаются в dispose. Файл до 200 строк.",
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
        "src/weapons/viewmodel.js",
        "Детальная модель оружия в руках, в стиле AK — заменяет примитивный ствол.\nТолько геометрия и материалы, без логики стрельбы.\n\nЭкспорт buildRifleViewModel(options) -> {group, parts, muzzlePoint, ejectPoint}.\noptions: {quality}. parts должен содержать: receiver, barrel, magazine, stock, handguard,\ngrip, dustCover, rearSight, frontSight, muzzleDevice, charging, hands.\n\nСтроение (локальные координаты, ствол смотрит в -Z, начало координат — у рукояти):\n- ресивер: Box 0.062 x 0.075 x 0.34, тёмный воронёный металл;\n- крышка ствольной коробки сверху: Box чуть уже, с фаской через масштаб;\n- цевьё: ДЕРЕВО тёплого рыжего оттенка, два Box сверху и снизу ствола;\n- ствол: Cylinder радиусом 0.011 длиной 0.30, впереди дульный компенсатор\n  чуть большего радиуса со скосом;\n- газовая трубка над стволом: тонкий Cylinder;\n- магазин: изогнутый — три Box с нарастающим наклоном (0, 8, 16 градусов),\n  тёмно-рыжий бакелит;\n- приклад: деревянный Box с сужением к затыльнику;\n- пистолетная рукоять: Box с наклоном 15 градусов;\n- прицельные: мушка в кольце (Cylinder + тонкий Box) и целик — планка с прорезью;\n- рукоятка затвора: маленький Box справа;\n- РУКИ: две кисти из скруглённых Box в перчатках тёмно-серого цвета —\n  правая на рукояти, левая на цевье. Это важно: без рук оружие висит в воздухе.\n\nmuzzlePoint и ejectPoint — THREE.Object3D-пустышки в нужных местах, чтобы эффекты\nцеплялись к ним, а не к магическим координатам.\n\nМатериалы: не больше четырёх на всю модель (металл, дерево, бакелит, перчатки),\nMeshStandardMaterial. Все меши на слой 1 (вью-модель освещается отдельно).\nНа quality==='low' пропусти прицельные, газовую трубку и рукоятку затвора.\n\nФайл до 220 строк, комментарии по-русски.",
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
        "src/ai/soldier-model.js",
        "Процедурная модель бойца в экипировке — вместо капсулы у ботов. Только геометрия\nи анимация, никакой логики ИИ и никакой физики.\n\nЭкспорт createSoldierModel(options) -> {group, update(dt, pose), setTeamColor(hex), playMuzzleFlash(), setDead(on), dispose()}.\noptions: {rng, quality}. pose: {speed, aiming, firing, grounded, yaw}.\n\nСтроение (всё из примитивов, суммарно не больше 30 мешей, рост 1.8 м, начало координат — В НОГАХ):\n- голова: слегка сплюснутый Box, поверх каска — половина сферы с козырьком (Box), тёмные очки-полоска;\n- торс: Box, поверх бронежилет — второй Box чуть шире и толще, другого оттенка, с плечевыми накладками;\n- разгрузка: 3-4 маленьких Box-подсумка спереди на жилете и подсумок-рация на плече;\n- рюкзак: Box за спиной со скруглением через масштаб;\n- руки: по два сегмента (плечо, предплечье) на THREE.Group-суставах, чтобы можно было вращать;\n- ноги: по два сегмента (бедро, голень) на суставах + ботинки (Box);\n- автомат в руках: ресивер, ствол, магазин, приклад, рукоять — простые Box/Cylinder,\n  ствол смотрит вперёд по -Z, крепится к правой руке;\n- дульная вспышка: маленький эмиссивный меш у среза, по умолчанию невидим.\n\nАнимация в update(dt, pose) — БЕЗ скелета и без внешних библиотек, простым вращением суставов:\n- ходьба: ноги и руки качаются противофазно, амплитуда и частота от pose.speed\n  (0 — стоит, 5 м/с — бег); фазу копим сами по dt;\n- лёгкое покачивание корпуса вверх-вниз в такт шагам;\n- прицеливание (pose.aiming): руки поднимаются, автомат идёт к линии глаз, шаг короче;\n- выстрел (pose.firing): короткая отдача — автомат и руки отскакивают назад и возвращаются\n  по экспоненте; вспышка видна 50 мс;\n- setDead(true): модель заваливается набок за 0.6 с и остаётся лежать.\n\nЦвета: хаки и тёмно-серый, бронежилет темнее формы, каска ещё темнее; setTeamColor красит\nполосу на каске и плечах, чтобы врага было видно в сумерках — цвет эмиссивный, слабый.\n\nМатериалы: MeshStandardMaterial, ОДИН общий материал на группу деталей одного цвета\n(не создавай материал на каждый меш). На quality==='low' пропусти подсумки, рацию и очки.\n\nНикаких аллокаций в update: временные векторы и кватернионы — модульные константы.",
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
        "src/modes/waves.js",
        "Режим раундов (волн) — отдельный модуль, поверх готовых спавнера и HUD.\n\nЭкспорт createWaveMode(deps) -> {update(dt), start(), reset(), round, enemiesLeft, phase}.\ndeps: {spawner, hud, audio, player, settings, container}. Ничего из этого не создавай сам.\n\nПравила:\n- Фазы: 'prepare' (пауза перед раундом, 5 секунд) -> 'fighting' -> 'cleared' -> снова 'prepare'.\n- Раунд N выпускает 3 + N*2 ботов, но не больше лимита живых у спавнера.\n- Спавн через spawner.spawnWave(count, playerPos, fov, forward) — ИМЕННО с четырьмя\n  аргументами, иначе метод вернёт 0 и никто не появится.\n- Раунд считается зачищенным, когда spawner.alive === 0 и все выпущенные заспавнены.\n- Сложность растёт: каждый раунд множитель здоровья ботов +12%, интервал подспавна короче.\n  Передавай это через deps.spawner если у него есть setDifficulty, иначе просто копи число\n  и отдавай наружу как поле difficulty.\n\nИнтерфейс раунда (свой DOM поверх canvas, стили инлайном, ничего внешнего):\n- крупная надпись по центру «РАУНД N» на 1.5 секунды в начале фазы prepare, плавно гаснет;\n- обратный отсчёт до начала боя под надписью;\n- в верхнем центре постоянная строка «Раунд N · осталось K» во время боя;\n- при зачистке — «РАУНД N ЗАЧИЩЕН» на 1.5 секунды;\n- по-русски, шрифт системный, цвета в тон тёмной теме (белый текст, полупрозрачная подложка,\n  скругление 10px), не перекрывать прицел в центре — надписи смещать по вертикали.\n\nЗвук: audio.play('wave-start') в начале боя и audio.play('wave-clear') при зачистке —\nесли такого имени нет, звук просто не проиграется, это допустимо.\n\nНикаких таймеров setInterval: всё считается по dt в update. Файл до 220 строк.",
    ),
    (
        "src/ui/nameplates.js",
        "Ники над ботами, в стиле сетевых шутеров. Только отображение, без логики ИИ.\n\nЭкспорт createNameplates(scene, camera, options) -> {add(bot, name), remove(bot), update(dt), dispose()}.\noptions: {maxDistance: 60, container}.\n\nКак рисовать: НЕ DOM, а THREE.Sprite с текстурой из canvas — так метка корректно\nперекрывается стенами по глубине и не тормозит на десятках ботов.\n- Текст белый, полужирный, с тёмной обводкой 3 px, подложка полупрозрачная чёрная\n  со скруглением, отступы 8/4 px. Canvas 256x64, texture.colorSpace = SRGBColorSpace.\n- Спрайт висит на 0.35 м выше макушки бота (рост 1.8 м), sizeAttenuation = true,\n  базовый масштаб 0.6x0.15 м, дальше 20 м плавно уменьшается до 0.6 от базового.\n- Под ником — тонкая полоска здоровья шириной с ник: зелёная, краснеет к нулю.\n  Полоску рисуй в тот же canvas и перерисовывай ТОЛЬКО когда здоровье изменилось\n  больше чем на 5% (кэшируй последнее значение).\n- Дальше options.maxDistance метка скрывается (visible = false), ближе — видна.\n- Мёртвые боты: метку сразу убрать.\n\nИмена: экспортируй также RU_CALLSIGNS — массив из 24 коротких позывных кириллицей\n(Волк, Ястреб, Гром, Крот, Сапёр и т.п.), и pickCallsign(rng) без повторов подряд.\n\nНикаких аллокаций в update: временные векторы — модульные константы. Файл до 200 строк.",
    ),
    (
        "src/ui/minimap.js",
        "Радар в левом верхнем углу, в стиле сетевых шутеров. Рисуется в отдельный canvas 2D,\nникакого WebGL и никаких DOM-элементов на каждый объект.\n\nЭкспорт createMinimap(options) -> {element, update(dt, view), dispose()}.\noptions: {size: 180, worldSize: 200, container}.\nview: {playerPos, playerYaw, bots: [{position, alive}], buildings: [{x, z, w, d}]}.\n\nОтрисовка каждый кадр (canvas 2D, размер options.size):\n- круглая маска: всё за пределами круга обрезается (ctx.clip по дуге);\n- фон тёмный полупрозрачный, тонкая светлая окантовка круга;\n- здания — светло-серые прямоугольники, повёрнутые вместе с картой;\n- КАРТА ВРАЩАЕТСЯ вместе с игроком: игрок всегда смотрит вверх. Поворот через\n  ctx.rotate(playerYaw), центр — позиция игрока;\n- игрок — белый треугольник в центре, вершиной вверх;\n- боты — красные точки радиусом 3, только живые; кто дальше радиуса радара —\n  прижимается к краю круга и рисуется мельче (радиус 2), чтобы было понятно направление;\n- масштаб: радиус радара покрывает 60 м мира.\n\nПозиция: absolute, left 16, top 16, z-index над canvas, pointer-events none,\nскругление 50%, лёгкая тень.\n\nПерерисовку зданий кэшируй: они статичны, поэтому строй их путь один раз в\nPath2D и переиспользуй, применяя только трансформацию. Файл до 200 строк.",
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
