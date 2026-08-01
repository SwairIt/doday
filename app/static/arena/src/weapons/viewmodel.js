// src/weapons/viewmodel.js — вью-модель винтовки в стиле АК.
// Только геометрия и материалы; логика стрельбы живёт в других модулях.
// Ось ствола смотрит в -Z, начало координат — у пистолетной рукояти.

import * as THREE from 'three';

// Слой вью-модели: освещается отдельным проходом рендера.
const VIEW_LAYER = 1;

// Размеры основных узлов (метры).
const RECEIVER = { w: 0.062, h: 0.075, l: 0.34 };
const BARREL = { r: 0.011, l: 0.30 };
const GAS_TUBE = { r: 0.006, l: 0.17 };
const MUZZLE = { r: 0.016, l: 0.05 };
const FRONT_Z = -(RECEIVER.l * 0.5 + BARREL.l); // торец ствола по Z

/**
 * Создаёт прямоугольный меш заданного материала и переводит на слой вью-модели.
 * @param {number} w Ширина.
 * @param {number} h Высота.
 * @param {number} l Длина.
 * @param {THREE.Material} material Материал.
 * @returns {THREE.Mesh}
 */
function box(w, h, l, material) {
	const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, l), material);
	mesh.layers.set(VIEW_LAYER);
	return mesh;
}

/**
 * Создаёт цилиндрический меш (ось вдоль Z) и переводит на слой вью-модели.
 * @param {number} radius Радиус.
 * @param {number} length Длина вдоль Z.
 * @param {THREE.Material} material Материал.
 * @returns {THREE.Mesh}
 */
function tube(radius, length, material) {
	const mesh = new THREE.Mesh(new THREE.CylinderGeometry(radius, radius, length, 12), material);
	mesh.rotation.x = Math.PI / 2; // ось цилиндра вдоль ствола (Z)
	mesh.layers.set(VIEW_LAYER);
	return mesh;
}

/**
 * Скруглённый «брусок» для кистей рук — Box с лёгким масштабированием.
 * @param {number} w Ширина.
 * @param {number} h Высота.
 * @param {number} l Длина.
 * @param {THREE.Material} material Материал.
 * @returns {THREE.Mesh}
 */
function glove(w, h, l, material) {
	const mesh = box(w, h, l, material);
	mesh.scale.y = 0.92;
	return mesh;
}

/**
 * Строит вью-модель винтовки в стиле АК с руками.
 * Ствол смотрит в -Z, начало координат — у пистолетной рукояти.
 * @param {{quality: string}} options Качество: на 'low' пропускаются мелкие детали.
 * @returns {{group: THREE.Group, parts: object, muzzlePoint: THREE.Object3D, ejectPoint: THREE.Object3D}}
 */
export function buildRifleViewModel(options = {}) {
	const { quality = 'high' } = options;
	const low = quality === 'low';

	// Четыре материала на всю модель.
	const metal = new THREE.MeshStandardMaterial({
		color: 0x1d1f22, roughness: 0.45, metalness: 0.85, // воронёный металл
	});
	const wood = new THREE.MeshStandardMaterial({
		color: 0x8a4f24, roughness: 0.75, metalness: 0.0, // тёплое рыжее дерево
	});
	const bakelite = new THREE.MeshStandardMaterial({
		color: 0x5c2e14, roughness: 0.55, metalness: 0.1, // тёмно-рыжий бакелит
	});
	const gloveMat = new THREE.MeshStandardMaterial({
		color: 0x3a3d42, roughness: 0.9, metalness: 0.0, // тёмно-серые перчатки
	});

	const group = new THREE.Group();
	const parts = {};

	// --- Ресивер ---
	const receiver = box(RECEIVER.w, RECEIVER.h, RECEIVER.l, metal);
	receiver.position.set(0, 0.02, 0.05);
	parts.receiver = receiver;
	group.add(receiver);

	// --- Крышка ствольной коробки (фаска через масштаб) ---
	const dustCover = box(RECEIVER.w * 0.86, 0.014, RECEIVER.l * 0.96, metal);
	dustCover.position.set(0, 0.02 + RECEIVER.h * 0.5, 0.05);
	dustCover.scale.set(1, 1, 0.94);
	parts.dustCover = dustCover;
	group.add(dustCover);

	// --- Ствол ---
	const barrel = tube(BARREL.r, BARREL.l, metal);
	barrel.position.set(0, 0.03, -(RECEIVER.l * 0.5 + BARREL.l * 0.5));
	parts.barrel = barrel;
	group.add(barrel);

	// --- Дульный компенсатор со скосом ---
	const muzzleDevice = new THREE.Mesh(new THREE.CylinderGeometry(MUZZLE.r * 0.8, MUZZLE.r, MUZZLE.l, 12), metal);
	muzzleDevice.rotation.x = Math.PI / 2;
	muzzleDevice.position.set(0, 0.03, FRONT_Z - MUZZLE.l * 0.5 + 0.008);
	muzzleDevice.layers.set(VIEW_LAYER);
	parts.muzzleDevice = muzzleDevice;
	group.add(muzzleDevice);

	// --- Цевьё: дерево, секции сверху и снизу ствола ---
	const handguard = new THREE.Group();
	const hgTop = box(0.05, 0.022, 0.16, wood);
	hgTop.position.set(0, 0.055, -(RECEIVER.l * 0.5 + 0.09));
	const hgBottom = box(0.054, 0.026, 0.16, wood);
	hgBottom.position.set(0, 0.005, -(RECEIVER.l * 0.5 + 0.09));
	handguard.add(hgTop, hgBottom);
	parts.handguard = handguard;
	group.add(handguard);

	// --- Пистолетная рукоять, наклон 15° ---
	const grip = box(0.036, 0.115, 0.052, bakelite);
	grip.position.set(0, -0.062, 0.055);
	grip.rotation.x = THREE.MathUtils.degToRad(15);
	parts.grip = grip;
	group.add(grip);

	// --- Магазин: изогнутый, три секции с нарастающим наклоном (0/8/16°) ---
	const magazine = new THREE.Group();
	const magAngles = [0, 8, 16];
	let magZ = 0.005, magY = -0.04;
	for (let i = 0; i < 3; i++) {
		const ang = THREE.MathUtils.degToRad(magAngles[i]);
		const seg = box(0.042, 0.075, 0.075, bakelite);
		seg.rotation.x = ang;
		// каждая следующая секция уходит ниже и вперёд по дуге
		magY -= 0.055 * Math.cos(ang);
		magZ -= 0.03 + 0.012 * i;
		seg.position.set(0, magY + 0.075 * Math.cos(ang) * 0.5, magZ + 0.075 * Math.sin(ang) * 0.5);
		magazine.add(seg);
	}
	parts.magazine = magazine;
	group.add(magazine);

	// --- Приклад: деревянный, с сужением к затыльнику ---
	const stock = new THREE.Group();
	const stockMain = box(0.05, 0.062, 0.19, wood);
	stockMain.position.set(0, 0.03, RECEIVER.l * 0.5 + 0.095);
	const stockButt = box(0.038, 0.078, 0.06, wood);
	stockButt.position.set(0, 0.022, RECEIVER.l * 0.5 + 0.19 + 0.03);
	stockButt.rotation.x = THREE.MathUtils.degToRad(-6);
	stock.add(stockMain, stockButt);
	parts.stock = stock;
	group.add(stock);

	if (!low) {
		// --- Газовая трубка над стволом ---
		const gasTube = tube(GAS_TUBE.r, GAS_TUBE.l, metal);
		gasTube.position.set(0, 0.058, -(RECEIVER.l * 0.5 + GAS_TUBE.l * 0.5 + 0.01));
		parts.gasTube = gasTube;
		group.add(gasTube);

		// --- Мушка в кольце ---
		const frontSight = new THREE.Group();
		const fsRing = new THREE.Mesh(new THREE.TorusGeometry(0.012, 0.0022, 8, 16), metal);
		fsRing.layers.set(VIEW_LAYER);
		const fsPost = box(0.003, 0.018, 0.003, metal);
		fsPost.position.y = -0.002;
		const fsBase = box(0.014, 0.03, 0.012, metal);
		fsBase.position.y = -0.022;
		frontSight.add(fsRing, fsPost, fsBase);
		frontSight.position.set(0, 0.075, FRONT_Z + 0.06);
		parts.frontSight = frontSight;
		group.add(frontSight);

		// --- Целик: планка с прорезью ---
		const rearSight = new THREE.Group();
		const rsBar = box(0.05, 0.004, 0.09, metal);
		rsBar.rotation.x = THREE.MathUtils.degToRad(-4);
		const rsLeft = box(0.006, 0.014, 0.006, metal);
		rsLeft.position.set(-0.011, 0.008, 0.04);
		const rsRight = rsLeft.clone();
		rsRight.position.x = 0.011;
		rearSight.add(rsBar, rsLeft, rsRight);
		rearSight.position.set(0, 0.075, 0.02);
		parts.rearSight = rearSight;
		group.add(rearSight);

		// --- Рукоятка затвора справа ---
		const charging = box(0.024, 0.012, 0.016, metal);
		charging.position.set(RECEIVER.w * 0.5 + 0.012, 0.028, 0.10);
		parts.charging = charging;
		group.add(charging);
	} else {
		parts.gasTube = null;
		parts.frontSight = null;
		parts.rearSight = null;
		parts.charging = null;
	}

	// --- Руки: две кисти в перчатках ---
	const hands = new THREE.Group();
	// Правая кисть — на пистолетной рукояти
	const rightHand = new THREE.Group();
	const rhPalm = glove(0.052, 0.055, 0.07, gloveMat);
	const rhFingers = glove(0.05, 0.03, 0.062, gloveMat);
	rhFingers.position.set(0, -0.038, -0.004);
	rhFingers.rotation.x = THREE.MathUtils.degToRad(20);
	const rhWrist = glove(0.05, 0.048, 0.08, gloveMat);
	rhWrist.position.set(0, -0.05, 0.06);
	rhWrist.rotation.x = THREE.MathUtils.degToRad(35);
	rightHand.add(rhPalm, rhFingers, rhWrist);
	rightHand.position.set(0, -0.045, 0.05);
	rightHand.rotation.x = THREE.MathUtils.degToRad(15);
	hands.add(rightHand);
	// Левая кисть — под цевьём, пальцы огибают дерево
	const leftHand = new THREE.Group();
	const lhPalm = glove(0.055, 0.04, 0.075, gloveMat);
	const lhFingers = glove(0.056, 0.035, 0.05, gloveMat);
	lhFingers.position.set(0, 0.03, 0.0);
	const lhWrist = glove(0.05, 0.045, 0.09, gloveMat);
	lhWrist.position.set(0, -0.02, 0.085);
	lhWrist.rotation.x = THREE.MathUtils.degToRad(-25);
	leftHand.add(lhPalm, lhFingers, lhWrist);
	leftHand.position.set(0, -0.035, -(RECEIVER.l * 0.5 + 0.09));
	hands.add(leftHand);
	parts.hands = hands;
	group.add(hands);

	// --- Точки крепления эффектов ---
	const muzzlePoint = new THREE.Object3D();
	muzzlePoint.name = 'muzzlePoint';
	muzzlePoint.position.set(0, 0.03, FRONT_Z - MUZZLE.l);
	group.add(muzzlePoint);

	const ejectPoint = new THREE.Object3D();
	ejectPoint.name = 'ejectPoint';
	ejectPoint.position.set(RECEIVER.w * 0.5 + 0.01, 0.04, 0.08);
	group.add(ejectPoint);

	// Тень вью-модели не отбрасывает — рендерится отдельным проходом.
	group.traverse((obj) => {
		if (obj.isMesh) {
			obj.castShadow = false;
			obj.receiveShadow = false;
		}
	});

	return { group, parts, muzzlePoint, ejectPoint };
}
