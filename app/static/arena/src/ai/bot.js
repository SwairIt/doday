// Бот-противник: FSM patrol -> search -> combat -> retreat.
// Зрение/слух/упреждение берутся из src/ai/perception.js.

import * as THREE from 'three';
import { raycast } from '../world/collision.js';

// --- Константы, недостающие в исходной генерации ---
const BURST_MIN = 3;              // минимум выстрелов в очереди
const BURST_MAX = 6;              // максимум выстрелов в очереди
const FIRE_SPREAD = 0.045;        // разброс стрельбы бота, радианы
const RAGDOLL_IMPULSE = 5.5;      // импульс, придаваемый трупу при смерти
const RETREAT_HEALTH_FRAC = 0.35; // доля здоровья, ниже которой бот отступает
const SPEED_SLOW = 1.6;           // скорость патрулирования, м/с

/** @type {object|null} Ссылка на RAPIER после initPhysics. */
let RAPIER = null;

/** Физические константы бота. */
const CAPSULE_RADIUS = 0.35;
const CAPSULE_HALF_HEIGHT = 0.55;
const SPEED_PATROL = 2.2;
const SPEED_COMBAT = 4.5;
const SPEED_RETREAT = 5.2;
const TURN_SPEED = 10;

/** Параметры поведения. */
const SIGHT_CHECK_INTERVAL = 0.12;
const SEARCH_DURATION = 6;
const RETREAT_HEALTH = 30;
const REENGAGE_HEALTH = 70;
const MAX_HEALTH = 100;
const ATTACK_RANGE = 45;
const COVER_SEARCH_RADIUS = 14;
const COVER_SAMPLE_DIRS = 8;
const AVOID_RAY_DIST = 2.2;
const AVOID_RAY_COUNT = 5;
const AVOID_RAY_ARC = 1.2;
const PATROL_POINT_RADIUS = 1.2;
const TARGET_HEIGHT = 1.4;
const DEATH_IMPULSE = 6;
const DEATH_UP_IMPULSE = 2;

/** Параметры огня очередями. */
const BURST_SHOTS = 4;
const BURST_SHOT_INTERVAL = 0.1;
const BURST_PAUSE_MIN = 0.6;
const BURST_PAUSE_MAX = 1.1;
const FIRE_SPREAD_BASE = 0.035;
const MUZZLE_OFFSET = 0.4;

/** Цвета подсветки по состояниям FSM. */
const STATE_COLORS = {
	patrol: 0x33cc55,
	search: 0xffaa22,
	combat: 0xff3333,
	retreat: 0x3388ff,
};

// Временные векторы (без аллокаций в горячем цикле).
const _dir = new THREE.Vector3();
const _tmp = new THREE.Vector3();
const _tmp2 = new THREE.Vector3();
const _flat = new THREE.Vector3();
const _strafe = new THREE.Vector3();
const _up = new THREE.Vector3(0, 1, 0);

/**
 * Создаёт простую модель бота: капсула-корпус, сфера-голова, точечная подсветка.
 * @param {THREE.Scene} scene
 * @returns {{group: THREE.Group, body: THREE.Mesh, light: THREE.PointLight}}
 */
function buildBotModel() {
	const group = new THREE.Group();
	const material = new THREE.MeshStandardMaterial({
		color: 0x554a3f,
		roughness: 0.6,
		metalness: 0.3,
	});
	const body = new THREE.Mesh(
		new THREE.CapsuleGeometry(CAPSULE_RADIUS, CAPSULE_HALF_HEIGHT * 2, 4, 8),
		material
	);
	body.position.y = CAPSULE_HALF_HEIGHT + CAPSULE_RADIUS;
	body.castShadow = true;
	group.add(body);

	const head = new THREE.Mesh(
		new THREE.SphereGeometry(0.22, 10, 8),
		new THREE.MeshStandardMaterial({ color: 0x3a332c, roughness: 0.5 })
	);
	head.position.y = CAPSULE_HALF_HEIGHT * 2 + CAPSULE_RADIUS * 2;
	head.castShadow = true;
	group.add(head);

	const light = new THREE.PointLight(STATE_COLORS.patrol, 1.6, 6);
	light.position.y = 1.6;
	group.add(light);

	return { group, body, light };
}

/**
 * Создаёт бота-противника с конечным автоматом поведения.
 * @param {THREE.Scene} scene Сцена рендера.
 * @param {object} world Физический мир Rapier.
 * @param {THREE.Vector3} spawnPoint Точка спауна.
 * @param {object} deps Зависимости: { perception, weapon, fx, rng, events, playerPosition }.
 * @returns {{update(dt:number, player:object):void, takeDamage(amount:number, point:THREE.Vector3):void, alive:boolean, position:THREE.Vector3}}
 */
export function createBot(scene, world, spawnPoint, deps) {
	const { perception, weapon, fx, rng, events } = deps;

	// --- Физика: кинематическая капсула до смерти.
	const bodyDesc = world.constructor && RAPIER
		? RAPIER.RigidBodyDesc.kinematicPositionBased().setTranslation(spawnPoint.x, spawnPoint.y, spawnPoint.z)
		: null;
	const body = bodyDesc
		? world.createRigidBody(bodyDesc)
		: null;
	if (body) {
		const colDesc = RAPIER.ColliderDesc.capsule(CAPSULE_HALF_HEIGHT, CAPSULE_RADIUS)
			.setTranslation(0, CAPSULE_HALF_HEIGHT + CAPSULE_RADIUS, 0);
		world.createCollider(colDesc, body);
	}

	// --- Модель.
	const { group, light } = buildBotModel();
	group.position.copy(spawnPoint);
	scene.add(group);

	const position = group.position;
	let health = MAX_HEALTH;
	let state = 'patrol';
	let stateTime = 0;
	let heading = rng() * Math.PI * 2;
	let patrolTarget = null;
	let lastKnownPlayerPos = null;
	let coverPoint = null;
	let sightTimer = rng() * SIGHT_CHECK_INTERVAL;
	let playerVisible = false;

	// Очередь: отсчёты выстрелов и пауз.
	let burstShotsLeft = 0;
	let burstTimer = BURST_PAUSE_MIN + rng() * (BURST_PAUSE_MAX - BURST_PAUSE_MIN);

	/** @param {string} next */
	function setState(next) {
		if (state === next) return;
		state = next;
		stateTime = 0;
		light.color.setHex(STATE_COLORS[next]);
		burstShotsLeft = 0; // сброс очереди при смене состояния
	}

	/** Поворот всей модели в сторону целевого угла с ограничением скорости. */
	function turnTowards(targetHeading, dt) {
		let d = targetHeading - heading;
		while (d > Math.PI) d -= Math.PI * 2;
		while (d < -Math.PI) d += Math.PI * 2;
		const maxTurn = TURN_SPEED * dt;
		heading += Math.abs(d) < maxTurn ? d : Math.sign(d) * maxTurn;
		group.rotation.y = heading;
	}

	/**
	 * Движение в направлении target с обходом препятствий рейкастами-веером.
	 * @param {THREE.Vector3} target
	 * @param {number} speed
	 * @param {number} dt
	 */
	function moveTowards(target, speed, dt) {
		_flat.copy(target).sub(position);
		_flat.y = 0;
		if (_flat.lengthSq() < 1e-6) return;
		_flat.normalize();

		// Веер рейкастов вокруг направления движения.
		let steer = 0;
		_tmp.copy(position);
		_tmp.y += 0.9;
		for (let i = 0; i < AVOID_RAY_COUNT; i++) {
			const t = AVOID_RAY_COUNT === 1 ? 0 : (i / (AVOID_RAY_COUNT - 1)) * 2 - 1;
			const angle = t * AVOID_RAY_ARC;
			_dir.copy(_flat).applyAxisAngle(_up, angle);
			const hit = raycast(world, _tmp, _dir, AVOID_RAY_DIST, null);
			if (hit && hit.distance < AVOID_RAY_DIST) {
				// Уводим в противоположную сторону пропорционально близости.
				steer -= Math.sign(angle || (i % 2 ? 1 : -1)) * (1 - hit.distance / AVOID_RAY_DIST);
			}
		}
		_flat.applyAxisAngle(_up, steer * 1.2);

		turnTowards(Math.atan2(-_flat.x, -_flat.z) + Math.PI, dt);
		_strafe.copy(_flat).multiplyScalar(speed * dt);
		position.add(_strafe);
		syncBody();
	}

	/** Синхронизация физического тела с позицией модели. */
	function syncBody() {
		if (body) {
			body.setNextKinematicTranslation({ x: position.x, y: position.y, z: position.z });
		}
	}

	/** Выбор случайной точки патрулирования неподалёку. */
	function pickPatrolTarget() {
		const angle = rng() * Math.PI * 2;
		const dist = 6 + rng() * 18;
		_tmp.set(position.x + Math.cos(angle) * dist, position.y, position.z + Math.sin(angle) * dist);
		const hit = raycast(world, position, _tmp.sub(position).normalize(), dist, null);
		const d = hit ? Math.max(1, hit.distance - 1) : dist;
		patrolTarget = patrolTarget || new THREE.Vector3();
		patrolTarget.set(position.x + Math.cos(angle) * d, position.y, position.z + Math.sin(angle) * d);
		patrolTarget.y = position.y;
	}

	/**
	 * Поиск точки укрытия: направления веером, точка должна блокировать обзор игрока.
	 * @param {THREE.Vector3} playerPos
	 */
	function findCover(playerPos) {
		coverPoint = coverPoint || new THREE.Vector3();
		let best = null;
		let bestScore = -Infinity;
		_tmp.copy(position);
		_tmp.y += 0.9;
		for (let i = 0; i < COVER_SAMPLE_DIRS; i++) {
			const angle = (i / COVER_SAMPLE_DIRS) * Math.PI * 2;
			_dir.set(Math.cos(angle), 0, Math.sin(angle));
			const hit = raycast(world, _tmp, _dir, COVER_SEARCH_RADIUS, null);
			if (!hit || hit.distance > COVER_SEARCH_RADIUS) continue;
			// Кандидат — точка за препятствием относительно игрока.
			const dist = Math.min(hit.distance + 2.0, COVER_SEARCH_RADIUS);
			_tmp2.copy(hit.point).addScaledVector(_dir, dist - hit.distance).sub(position);
			_tmp2.y = 0.9;
			// Оценка: ближе к боту — лучше, и точка должна скрывать игрока.
			const toCover = _tmp2.length();
			_tmp2.add(position);
			const blocked = !perception.canSee(_tmp2, playerPos);
			const score = (blocked ? 100 : 0) - toCover;
			if (score > bestScore) {
				bestScore = score;
				best = _tmp2;
			}
		}
		if (best) {
			coverPoint.copy(best);
			coverPoint.y = position.y;
			return true;
		}
		return false;
	}

	/**
	 * Стрельба очередями с разбросом по игроку.
	 * @param {THREE.Vector3} playerPos
	 * @param {number} dt
	 */
	function fireAt(playerPos, dt) {
		// Наведение: прицел в глаза бота.
		_tmp.copy(position);
		_tmp.y += CAPSULE_HALF_HEIGHT * 2 + CAPSULE_RADIUS; // уровень глаз
		turnTowards(Math.atan2(playerPos.x - position.x, playerPos.z - position.z), dt);

		burstTimer -= dt;
		if (burstShotsLeft > 0 && burstTimer <= 0) {
			_dir.copy(playerPos).sub(_tmp);
			_dir.y += 0.4; // прицел в корпус, не в ноги
			_dir.normalize();
			// Разброс по конусу.
			_dir.x += (rng() * 2 - 1) * FIRE_SPREAD;
			_dir.y += (rng() * 2 - 1) * FIRE_SPREAD;
			_dir.z += (rng() * 2 - 1) * FIRE_SPREAD;
			_dir.normalize();

			const hit = fireHitscan(world, _tmp, _dir, weapon, FIRE_SPREAD, rng);
			if (fx) fx.onShot(_tmp, _dir);
			if (hit && hit.player && hit.player.takeDamage) {
				hit.player.takeDamage(weapon.damage, hit.point);
			}
			if (events) events.emit('bot:shot', { point: _tmp });

			burstShotsLeft--;
			burstTimer = weapon ? weapon.fireInterval : 0.12;
		} else if (burstShotsLeft <= 0 && burstTimer <= 0) {
			// Начало новой очереди.
			burstShotsLeft = BURST_MIN + Math.floor(rng() * (BURST_MAX - BURST_MIN + 1));
			burstTimer = 0;
		}
	}

	/**
	 * Получение урона ботом. На любом небольшом остатке HP — уход в retreat.
	 * @param {number} amount Урон.
	 * @param {THREE.Vector3} [point] Точка попадания (для эффекта).
	 */
	function takeDamage(amount, point) {
		if (health <= 0) return;
		health -= amount;
		if (health <= 0) {
			die(point);
			return;
		}
		if (events) events.emit('bot:damaged', { amount, point, position });
		// Панический отход в укрытие при низком HP.
		if (health < MAX_HEALTH * RETREAT_HEALTH_FRAC && lastKnownPlayerPos) {
			if (findCover(lastKnownPlayerPos)) setState('retreat');
		}
	}

	/**
	 * Смерть: капсула становится динамическим телом и падает от импульса.
	 * @param {THREE.Vector3} [point] Точка последнего попадания.
	 */
	function die(point) {
		if (!body) return;
		body.setBodyType(RAPIER.RigidBodyType.Dynamic, true);
		// Импульс от точки попадания в сторону от неё.
		if (point) {
			_dir.copy(position).sub(point);
			_dir.y = Math.abs(_dir.y) + 0.35;
			if (_dir.lengthSq() < 1e-6) _dir.set(0, 1, 0);
			_dir.normalize();
			body.applyImpulse(
				{ x: _dir.x * RAGDOLL_IMPULSE, y: _dir.y * RAGDOLL_IMPULSE, z: _dir.z * RAGDOLL_IMPULSE },
				true
			);
			body.applyTorqueImpulse({ x: 2, y: 1, z: 2 }, true);
		}
		light.intensity = 0; // подсветка гаснет
		if (events) events.emit('bot:died', { position });
	}

	/** Приведение скорости к скорости состояния. */
	function speedFor(s) {
		return s === 'patrol' ? SPEED_PATROL : s === 'combat' ? SPEED_COMBAT : SPEED_SLOW;
	}

	/**
	 * Обновление автомата состояний и движения.
	 * @param {number} dt Дельта-время в секундах.
	 * @param {{position: THREE.Vector3}} player Игрок.
	 */
	function update(dt, player) {
		if (health <= 0) {
			// Труп: синхронизируем модель с динамическим телом.
			if (body) {
				const t = body.translation();
				group.position.set(t.x, t.y, t.z);
				const r = body.rotation();
				group.quaternion.set(r.x, r.y, r.z, r.w);
			}
			return;
		}

		stateTime += dt;
		sightTimer -= dt;
		const playerPos = player.position;

		// Периодическая проверка зрения/слуха.
		if (sightTimer <= 0) {
			sightTimer = SIGHT_CHECK_INTERVAL;
			playerVisible = perception.canSee(position, playerPos);
			if (playerVisible) {
				lastKnownPlayerPos = lastKnownPlayerPos || new THREE.Vector3();
				lastKnownPlayerPos.copy(playerPos);
			} else if (perception.canHear(position, playerPos)) {
				lastKnownPlayerPos = lastKnownPlayerPos || new THREE.Vector3();
				lastKnownPlayerPos.copy(playerPos);
			}
		}

		switch (state) {
			case 'patrol': {
				if (playerVisible && health > MAX_HEALTH * RETREAT_HEALTH_FRAC) { setState('combat'); break; }
				if (!playerVisible && lastKnownPlayerPos && stateTime > 1.0) { setState('search'); break; }
				if (!patrolTarget || position.distanceTo(patrolTarget) < 1.0) pickPatrolTarget();
				moveTowards(patrolTarget, speedFor(state), dt);
				break;
			}
			case 'search': {
				if (playerVisible) { setState('combat'); break; }
				if (lastKnownPlayerPos) {
					moveTowards(lastKnownPlayerPos, speedFor(state), dt);
					if (position.distanceTo(lastKnownPlayerPos) < 1.5) lastKnownPlayerPos = null;
				} else {
					setState('patrol');
				}
				break;
			}
			case 'combat': {
				if (health < MAX_HEALTH * RETREAT_HEALTH_FRAC) {
					if (findCover(playerPos)) setState('retreat');
					break;
				}
				if (playerVisible) {
					// Манёвр: лёгкий стрейф во время огня.
					_flat.copy(playerPos).sub(position);
					_flat.y = 0;
					_flat.normalize();
					_dir.set(-_flat.z, 0, _flat.x);
					_tmp.copy(position).addScaledVector(_dir, Math.sin(stateTime * 1.4) * 2);
					moveTowards(_tmp, SPEED_COMBAT * 0.6, dt);
					fireAt(playerPos, dt);
				} else {
					setState('search');
				}
				break;
			}
			case 'retreat': {
				if (!coverPoint) { if (!findCover(playerPos)) { setState('combat'); break; } }
				moveTowards(coverPoint, speedFor(state), dt);
				if (position.distanceTo(coverPoint) < 1.2) {
					// Прячемся за укрытием, но если здоровье восстановилось бы — в оригинале без регенерации.
					if (playerVisible) setState('combat');
				}
				break;
			}
		}
	}

	return {
		update,
		takeDamage,
		get alive() { return health > 0; },
		position,
	};
}
