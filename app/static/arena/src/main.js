/**
 * Точка входа Doday Arena.
 * Bootstrap: настройки, рендерер, сцена, небо, свет, город,
 * временная орбитальная камера, главный цикл, FPS-счётчик.
 */
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { Settings } from './core/settings.js';
import { Loop } from './core/loop.js';
import { createRenderer } from './render/renderer.js';
import { createSky } from './render/sky.js';
import { createLights } from './render/lights.js';
import { createCity } from './world/city.js';
import { createFpsCounter } from './ui/fps.js';
import { hideLoadingScreen, showFatalError } from './ui/loading.js';

// --- Константы ---

const CAMERA_FOV_DEFAULT = 75;
const CAMERA_NEAR = 0.1;
const CAMERA_FAR = 2000;

// Параметры временной орбитальной камеры облёта
const ORBIT_START = new THREE.Vector3(60, 45, 60);
const ORBIT_TARGET = new THREE.Vector3(0, 10, 0);
const ORBIT_AUTO_ROTATE_SPEED = 0.6;

/**
 * Проверяет доступность WebGL2.
 * @returns {boolean}
 */
function isWebGL2Available() {
    try {
        const probe = document.createElement('canvas');
        return !!probe.getContext('webgl2');
    } catch (e) {
        return false;
    }
}

/**
 * Инициализирует игру и возвращает публичный объект Game.
 * @returns {object}
 */
function bootstrap() {
    if (!isWebGL2Available()) {
        showFatalError(
            'WebGL2 недоступен',
            'Ваш браузер или устройство не поддерживает WebGL2. ' +
            'Обновите браузер (подойдут свежие Chrome, Firefox, Edge, Safari) ' +
            'и убедитесь, что аппаратное ускорение включено.'
        );
        throw new Error('WebGL2 недоступен');
    }

    // --- Настройки ---
    const settings = new Settings();

    // --- Рендерер ---
    const renderer = createRenderer(settings);

    // --- Сцена ---
    const scene = new THREE.Scene();
    scene.add(createSky(settings));

    // --- Свет ---
    const lights = createLights(settings);
    for (const light of lights) {
        scene.add(light);
    }

    // --- Город ---
    const city = createCity(settings);
    scene.add(city.group);

    // --- Временная орбитальная камера (облёт арены) ---
    const camera = new THREE.PerspectiveCamera(
        settings.fov || CAMERA_FOV_DEFAULT,
        window.innerWidth / window.innerHeight,
        CAMERA_NEAR,
        CAMERA_FAR
    );
    camera.position.copy(ORBIT_START);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.copy(ORBIT_TARGET);
    controls.autoRotate = true;
    controls.autoRotateSpeed = ORBIT_AUTO_ROTATE_SPEED;
    controls.enableDamping = true;
    controls.update();

    // --- FPS-счётчик ---
    const fpsCounter = createFpsCounter();

    // --- Изменение размера окна ---
    window.addEventListener('resize', () => {
        camera.aspect = window.innerWidth / window.innerHeight;
        camera.updateProjectionMatrix();
        renderer.setSize(window.innerWidth, window.innerHeight);
    });

    // --- Главный цикл ---
    const loop = new Loop((dt) => {
        controls.update();
        city.update(dt);
        renderer.render(scene, camera);
        fpsCounter.update(dt);
    });

    const game = {
        settings,
        renderer,
        scene,
        camera,
        city,
        loop,
        /** Запускает главный цикл и прячет экран загрузки. */
        start() {
            loop.start();
            hideLoadingScreen();
        }
    };

    game.start();
    return game;
}

export const Game = bootstrap();
