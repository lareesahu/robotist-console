/* Motion Library viewer — skeleton playback from joint-space data.
   No capture files, no meshes: the panel draws links between bone origins. */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';

const $ = (sel) => document.querySelector(sel);

const state = {
  clips: [], rows: [], selected: null, group: 'all', modelSet: null, modelName: '',
  clip: null, bones: [], links: [], joints: [], pose: null,
  t: 0, playing: true, mode: 'links', duration: 1, rootBone: null,
};

/* ── skeleton ─────────────────────────────────────────────── */
const matBody = new THREE.MeshStandardMaterial({ color: 0xA9C6D6, roughness: 0.8, metalness: 0.03 });
const matBodyDim = new THREE.MeshStandardMaterial({ color: 0x8FAFC4, roughness: 0.84, metalness: 0.03 });
const matLink = new THREE.MeshStandardMaterial({ color: 0x4aa8c8, roughness: 0.45, metalness: 0.35 });
const matLinkDim = new THREE.MeshStandardMaterial({ color: 0x2e6f8a, roughness: 0.6, metalness: 0.25 });
const matJoint = new THREE.MeshStandardMaterial({ color: 0xa8dcef, roughness: 0.3, metalness: 0.2, emissive: 0x0d2b36 });

/* The figure is assembled from body volumes — head, neck, torso, arms, legs —
   rather than drawn as links between joints. Each volume spans one bone pair and
   tapers from its parent end to its child end, so the silhouette reads as a body
   at thumbnail size while the joint data stays exactly what it was. */
const BODY = [
  // parent bone,  child bone,   radius at parent, radius at child, depth squash
  ['chest',      'head',       0.056, 0.044, 0.90],   // neck
  ['chest',      'upperarm_l', 0.098, 0.070, 0.82],   // clavicle
  ['chest',      'upperarm_r', 0.098, 0.070, 0.82],
  ['upperarm_l', 'forearm_l',  0.048, 0.038, 0.95],
  ['upperarm_r', 'forearm_r',  0.048, 0.038, 0.95],
  ['forearm_l',  'hand_l',     0.038, 0.028, 0.95],
  ['forearm_r',  'hand_r',     0.038, 0.028, 0.95],
  ['thigh_l',    'shin_l',     0.086, 0.056, 0.95],
  ['thigh_r',    'shin_r',     0.086, 0.056, 0.95],
  ['shin_l',     'foot_l',     0.054, 0.040, 0.95],
  ['shin_r',     'foot_r',     0.054, 0.040, 0.95],
];
const BALLS = [['upperarm_l', 0.083], ['upperarm_r', 0.083], ['thigh_l', 0.090], ['thigh_r', 0.090],
               ['forearm_l', 0.040], ['forearm_r', 0.040], ['shin_l', 0.056], ['shin_r', 0.056],
               ['hand_l', 0.030], ['hand_r', 0.030]];
const TORSO_PROFILE = [[0.000, 0.00], [0.148, 0.03], [0.136, 0.18], [0.124, 0.36], [0.138, 0.56], [0.160, 0.74], [0.176, 0.88], [0.150, 0.96], [0.000, 1.00]];

function buildSkeleton(clip) {
  const bones = clip.nodes.map((b) => {
    const node = new THREE.Object3D();
    node.name = b.n;
    node.position.fromArray(b.o);
    node.quaternion.fromArray(b.r);
    node.scale.fromArray(b.s);
    return node;
  });
  clip.nodes.forEach((b, i) => {
    if (b.p >= 0) bones[b.p].add(bones[i]);
  });
  const rootBone = bones[clip.nodes.findIndex((b) => b.p < 0)] || bones[0];

  const byName = {};
  bones.forEach((b, i) => { byName[clip.nodes[i].n] = b; });

  // the clip's units are not metres: measure the rest pose once and size the body to it
  rootBone.updateMatrixWorld(true);
  const restBox = new THREE.Box3();
  const restVec = new THREE.Vector3();
  bones.forEach((b) => { b.getWorldPosition(restVec); restBox.expandByPoint(restVec); });
  const restHeight = restBox.max.y - restBox.min.y;
  const rigScale = restHeight > 0.2 ? restHeight / 1.72 : 1;

  const jointGeo = new THREE.SphereGeometry(1, 12, 9);
  const ballGeo = new THREE.SphereGeometry(1, 18, 14);
  const boxGeo = new THREE.BoxGeometry(1, 1, 1);
  const links = [], joints = [];

  const add = (entry) => { state.group3d.add(entry.mesh); links.push(entry); };

  // torso: one lathed silhouette from pelvis to chest, so there is a waist
  if (byName.hips && byName.chest) {
    const lathe = new THREE.LatheGeometry(TORSO_PROFILE.map(([r, y]) => new THREE.Vector2(r, y)), 24);
    add({ kind: 'torso', mesh: new THREE.Mesh(lathe, matBody), a: byName.hips, b: (byName.neck || byName.chest) });
  }

  for (const [pn, cn, rp, rc, squash] of BODY) {
    if (!byName[pn] || !byName[cn]) continue;
    const geo = new THREE.CylinderGeometry(rc, rp, 1, 16, 1, false);  // +Y end = child
    add({ kind: 'limb', mesh: new THREE.Mesh(geo, matBody), a: byName[pn], b: byName[cn], squash });
  }

  if (byName.upperarm_l && byName.upperarm_r) {
    const barGeo = new THREE.CylinderGeometry(0.074, 0.074, 1, 18, 1, false);
    add({ kind: 'bar', mesh: new THREE.Mesh(barGeo, matBody), a: byName.upperarm_l, b: byName.upperarm_r });
  }
  for (const [bn, r] of BALLS) {
    if (!byName[bn]) continue;
    add({ kind: 'ball', mesh: new THREE.Mesh(ballGeo, matBody), at: byName[bn], r });
  }

  if (byName.chest) {
    add({ kind: 'ball', mesh: new THREE.Mesh(ballGeo, matBody), at: byName.chest, r: 0.083 });
  }
  if (byName.head) {
    add({ kind: 'head', mesh: new THREE.Mesh(ballGeo, matBody), at: byName.head });
  }
  if (byName.hips) {
    add({ kind: 'pelvis', mesh: new THREE.Mesh(ballGeo, matBody), at: byName.hips });
  }
  for (const s of ['l', 'r']) {
    if (byName['hand_' + s]) add({ kind: 'hand', mesh: new THREE.Mesh(ballGeo, matBody), at: byName['hand_' + s] });
    if (byName['foot_' + s] && byName['toe_' + s]) add({ kind: 'foot', mesh: new THREE.Mesh(ballGeo, matBody), a: byName['foot_' + s], b: byName['toe_' + s] });
  }

  // joint pins: the same 23 joints, kept for the "joints" reading of the data
  clip.nodes.forEach((b, i) => {
    if (b.v === false) return;
    const jm = new THREE.Mesh(jointGeo, matJoint);
    state.group3d.add(jm);
    joints.push({ bone: bones[i], mesh: jm });
  });

  return { bones, rootBone, links, joints, rigScale };
}

const _a = new THREE.Vector3(), _b = new THREE.Vector3(), _d = new THREE.Vector3();
const _up = new THREE.Vector3(0, 1, 0);
const _qa = new THREE.Quaternion(), _qb = new THREE.Quaternion();

function decode(b64, count) {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const view = new Int16Array(bytes.buffer, 0, count);
  return view;
}

function samplePose(clip, t) {
  const f = Math.min(clip.frames - 1, Math.max(0, t * clip.fps));
  const i0 = Math.floor(f), i1 = Math.min(clip.frames - 1, i0 + 1), a = f - i0;
  const n = clip.nodes.length, q = state.pose.quats, p = state.pose.pos;
  const qs = 32767, ps = clip.pos_scale;
  for (let b = 0; b < n; b++) {
    const o0 = (i0 * n + b) * 4, o1 = (i1 * n + b) * 4;
    _qa.set(q[o0] / qs, q[o0 + 1] / qs, q[o0 + 2] / qs, q[o0 + 3] / qs).normalize();
    _qb.set(q[o1] / qs, q[o1 + 1] / qs, q[o1 + 2] / qs, q[o1 + 3] / qs).normalize();
    if (_qa.dot(_qb) < 0) _qb.set(-_qb.x, -_qb.y, -_qb.z, -_qb.w);
    state.bones[b].quaternion.copy(_qa.slerp(_qb, a));

    const p0 = (i0 * n + b) * 3, p1 = (i1 * n + b) * 3;
    state.bones[b].position.set(
      (p[p0] / ps) * (1 - a) + (p[p1] / ps) * a,
      (p[p0 + 1] / ps) * (1 - a) + (p[p1 + 1] / ps) * a,
      (p[p0 + 2] / ps) * (1 - a) + (p[p1 + 2] / ps) * a,
    );
  }
}

function updateRig() {
  if (!state.clip) return;
  // The clips are authored in their own units; measure the rig once so the body
  // volumes are sized to the figure instead of to metres.
  const S = state.rigScale || 1;
  for (const part of state.links) {
    const { mesh } = part;
    if (part.kind === 'head') {
      part.at.getWorldPosition(_a);
      mesh.scale.set(0.089 * S, 0.104 * S, 0.096 * S);
      mesh.position.copy(_a).addScaledVector(_up, 0.052 * S);
      continue;
    }
    if (part.kind === 'pelvis') {
      part.at.getWorldPosition(_a);
      mesh.position.copy(_a).addScaledVector(_up, 0.02 * S);
      mesh.scale.set(0.152 * S, 0.108 * S, 0.112 * S);
      continue;
    }
    if (part.kind === 'ball') {
      part.at.getWorldPosition(_a);
      mesh.position.copy(_a);
      mesh.scale.setScalar(part.r * S);
      continue;
    }
    if (part.kind === 'hand') {
      part.at.getWorldPosition(_a);
      mesh.position.copy(_a).addScaledVector(_up, -0.018 * S);
      mesh.scale.set(0.042 * S, 0.062 * S, 0.030 * S);
      continue;
    }
    if (part.kind === 'bar') {
      part.a.getWorldPosition(_a);
      part.b.getWorldPosition(_b);
      _d.subVectors(_b, _a);
      mesh.position.addVectors(_a, _b).multiplyScalar(0.5);
      mesh.quaternion.setFromUnitVectors(_up, _d.clone().normalize());
      mesh.scale.set(S, _d.length(), 0.8 * S);
      continue;
    }
    if (part.kind === 'torso') {
      part.a.getWorldPosition(_a);
      part.b.getWorldPosition(_b);
      _d.subVectors(_b, _a);
      mesh.position.copy(_a);
      mesh.quaternion.setFromUnitVectors(_up, _d.clone().normalize());
      mesh.scale.set(S, Math.max(_d.length(), 0.3), 0.64 * S);
      continue;
    }
    part.a.getWorldPosition(_a);
    part.b.getWorldPosition(_b);
    _d.subVectors(_b, _a);
    const len = Math.max(_d.length(), 0.02);
    if (part.kind === 'foot') {
      // a soft wedge: heel thicker than toe, sole flat-ish
      mesh.position.copy(_a).addScaledVector(_d.clone().normalize(), len * 0.42);
      mesh.quaternion.setFromUnitVectors(_up, _d.clone().normalize());
      mesh.scale.set(0.062 * S, len * 1.05, 0.042 * S);
      continue;
    }
    mesh.position.addVectors(_a, _b).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(_up, _d.clone().normalize());
    if (part.squash) mesh.scale.set(S, len, part.squash * S);
    else { const t = Math.min(0.055, Math.max(0.020, len * 0.20)); mesh.scale.set(t, len, t * 0.82); }
  }
  for (const { bone, mesh } of state.joints) {
    bone.getWorldPosition(_a);
    mesh.position.copy(_a);
    mesh.scale.setScalar(0.021 * S);
  }
}

/* ── scene ────────────────────────────────────────────────── */
function initScene() {
  const canvas = $('#stage-canvas');
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.06;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(34, 16 / 11, 0.1, 100);
  camera.position.set(0, 1.15, 4.2);

  const controls = new OrbitControls(camera, canvas);
  controls.target.set(0, 0.95, 0);
  controls.enableDamping = true;
  controls.dampingFactor = 0.07;
  controls.minDistance = 1.6;
  controls.maxDistance = 9;
  controls.maxPolarAngle = Math.PI * 0.52;
  controls.enablePan = false;

  scene.add(new THREE.HemisphereLight(0xa8dcef, 0x081018, 1.5));
  const key = new THREE.DirectionalLight(0xffffff, 2.1);
  key.position.set(2.4, 4.2, 3.2);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x4aa8c8, 1.4);
  rim.position.set(-3, 1.6, -2.6);
  scene.add(rim);

  const grid = new THREE.GridHelper(10, 20, 0x1b3448, 0x101d2b);
  grid.position.y = 0;
  grid.material.transparent = true;
  grid.material.opacity = 0.55;
  scene.add(grid);

  const group3d = new THREE.Group();
  scene.add(group3d);

  state.renderer = renderer; state.scene = scene; state.camera = camera;
  state.controls = controls; state.group3d = group3d;
  controls.addEventListener('change', () => { state.dirty = true; });

  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    state.dirty = true;
  };
  new ResizeObserver(resize).observe(canvas);
  resize();
}

function groundRig() {
  // Two different measurements. The box is everywhere the figure travels; the body is
  // how big the figure itself gets. Framing on the box leaves a crawling body a splinter
  // in the middle of its own runway, so the camera sizes on the body.
  const p = new THREE.Vector3();
  const box = new THREE.Box3();
  const one = new THREE.Box3();
  const step = Math.max(1, Math.floor(state.clip.frames / 16));
  let w = 0, h = 0, d = 0;
  state.group3d.position.y = 0;
  for (let f = 0; f < state.clip.frames; f += step) {
    samplePose(state.clip, f / state.clip.fps);
    state.group3d.updateMatrixWorld(true);
    one.makeEmpty();
    for (const { bone } of state.joints) {
      bone.getWorldPosition(p);
      box.expandByPoint(p);
      one.expandByPoint(p);
    }
    w = Math.max(w, one.max.x - one.min.x);
    h = Math.max(h, one.max.y - one.min.y);
    d = Math.max(d, one.max.z - one.min.z);
  }
  if (Number.isFinite(box.min.y)) state.group3d.position.y = -box.min.y;
  box.min.y += state.group3d.position.y;
  box.max.y += state.group3d.position.y;
  state.bounds = box;
  state.body = { w: Math.max(w, 0.8), h: Math.max(h, 0.6), d: Math.max(d, 0.8) };
  state.group3d.updateMatrixWorld(true);
}

function frameCamera() {
  const body = state.body || { w: 1, h: 1.7, d: 0.8 };
  // The figure is pinned to the origin, so the target is the body's middle, not the
  // runway's. Width uses the horizontal axis of the body, whichever it is.
  const bw = Math.max(body.w, body.d * 1.15);
  const bh = body.h;
  // Aim at the body where it actually stands at the first frame: a clip can start
  // anywhere in the room, so a hard-coded origin leaves the figure off to one side.
  const poseBox = new THREE.Box3();
  const p = new THREE.Vector3();
  for (const { bone } of state.joints) {
    bone.getWorldPosition(p);
    poseBox.expandByPoint(p);
  }
  const cy = poseBox.isEmpty() ? bh * 0.52 : (poseBox.max.y + Math.max(0, poseBox.min.y)) * 0.5;
  const cx = poseBox.isEmpty() ? 0 : (poseBox.max.x + poseBox.min.x) * 0.5;
  const cz = poseBox.isEmpty() ? 0 : (poseBox.max.z + poseBox.min.z) * 0.5;
  // Three-quarter view: straight-on foreshortens any pose that moves along Z
  // (push-ups, crawls) into an unreadable knot.
  // Fit both axes from the real field of view, so a phone in portrait frames the body
  // as tightly as a laptop does instead of shrinking it into the middle of the canvas.
  const fov = THREE.MathUtils.degToRad(state.camera.fov || 38);
  const aspect = state.camera.aspect || 1.82;
  const fitY = (bh * 1.34) / (2 * Math.tan(fov / 2));
  const fitX = (bw * 1.40) / (2 * Math.tan(fov / 2) * aspect);
  const dist = Math.max(1.7, fitY, fitX);
  const az = 0.56;  // ~32 degrees
  state.camera.position.set(cx + Math.sin(az) * dist, cy + bh * 0.14, cz + Math.cos(az) * dist);
  state.controls.target.set(cx, cy, cz);
  state.controls.update();
  // The follow offset restarts from the pose the camera was framed on, so a new clip
  // opens exactly where frameCamera put it.
  _hasHip = false;
  state.dirty = true;
}

/* Keep the travelling figure in the middle of the frame. The camera follows the hips
   along the ground instead of the rig being teleported: moving the group fought the
   pose data and ran away, and shifting the camera leaves every joint where the clip
   put it. */
const _hipWorld = new THREE.Vector3();
const _lastHip = new THREE.Vector3();
let _hasHip = false;
function followHip() {
  if (!state.anchor) return;
  state.anchor.getWorldPosition(_hipWorld);
  if (!Number.isFinite(_hipWorld.x)) return;
  // Move the camera by the step the figure took, never to an absolute position: the
  // reader's own orbit drag has to survive the next frame.
  if (_hasHip) {
    const dx = _hipWorld.x - _lastHip.x;
    const dz = _hipWorld.z - _lastHip.z;
    if (Math.abs(dx) > 1e-6 || Math.abs(dz) > 1e-6) {
      state.camera.position.x += dx;
      state.camera.position.z += dz;
      state.controls.target.x += dx;
      state.controls.target.z += dz;
    }
  }
  _lastHip.copy(_hipWorld);
  _hasHip = true;
}

/* ── transport ────────────────────────────────────────────── */
function setTime(t) {
  state.t = Math.max(0, Math.min(state.duration, t));
  if (!state.clip) return;
  samplePose(state.clip, state.t);
  state.group3d.updateMatrixWorld(true);
  followHip();
  updateRig();
  const scrub = $('#scrub');
  if (scrub && document.activeElement !== scrub) scrub.value = String(state.duration ? state.t / state.duration : 0);
  $('#time').textContent = `${state.t.toFixed(2)} / ${state.duration.toFixed(2)} s`;
  state.dirty = true;
}

let last = performance.now();
function tick(now) {
  const dt = Math.min(0.05, (now - last) / 1000);
  last = now;
  if (state.playing && state.clip) {
    let t = state.t + dt;
    if (t > state.duration) t -= state.duration;
    setTime(t);
  }
  // Redraw while playing, or once after any change. A static skeleton redrawn at
  // 60 Hz keeps the GPU busy for no reason and drains a laptop battery.
  if (state.playing || state.dirty) {
    state.dirty = false;
    state.controls.update();
    state.renderer.render(state.scene, state.camera);
  }
  requestAnimationFrame(tick);
}

/* ── library ──────────────────────────────────────────────── */
const GROUPS = ['all', 'locomotion', 'sport', 'combat', 'fitness', 'form', 'daily', 'gesture'];

function renderRows() {
  const host = $('#rows');
  host.innerHTML = '';
  const list = state.clips.filter((c) => (state.group === 'all' || c.group === state.group)
    && (!state.modelSet || state.modelSet.has(c.id)));
  for (const clip of list) {
    const row = document.createElement('button');
    row.className = 'row';
    row.type = 'button';
    row.setAttribute('aria-current', String(clip.id === state.selected));
    row.dataset.id = clip.id;
    row.innerHTML = `<img src="thumbs/${clip.id}.webp" alt="" width="62" height="40" loading="lazy" decoding="async">
      <span><span class="name"></span><span class="sub">${clip.joints} joints · ${Math.round(clip.fps)} fps</span></span>
      <span class="len">${clip.seconds.toFixed(1)} s</span>`;
    row.querySelector('.name').textContent = clip.name;
    row.addEventListener('click', () => select(clip.id));
    host.append(row);
  }
  $('#count').textContent = `${list.length} of ${state.clips.length}`;
}

let selectToken = 0;

async function select(id) {
  const meta = state.clips.find((c) => c.id === id) || state.clips[0];
  if (!meta) return;
  // Two selects can overlap (a fast second click lands while the first fetch is
  // still open). Only the newest one may draw, and it clears the stage first, so
  // a lost race can never leave the previous skeleton standing.
  const token = ++selectToken;
  state.selected = meta.id;
  // aria-selected is only valid inside a listbox; these are plain buttons, so the
  // current row is announced with aria-current.
  document.querySelectorAll('.row').forEach((r) => {
    if (r.dataset.id === meta.id) r.setAttribute('aria-current', 'true');
    else r.removeAttribute('aria-current');
  });
  const row = document.querySelector(`.row[data-id="${meta.id}"]`);
  const list = row && row.parentElement;
  if (row && list && list.scrollHeight > list.clientHeight) {
    const top = row.offsetTop - list.offsetTop;
    if (top < list.scrollTop || top + row.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = top - list.clientHeight / 2 + row.offsetHeight / 2;
    }
  }

  let clip;
  try {
    const res = await fetch(`data/${meta.id}.json`);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    clip = await res.json();
  } catch (err) {
    // A dropped fetch must say so; leaving the old clip under a highlighted row
    // claims a clip is loaded when it is not.
    if (token === selectToken) {
      // Empty the stage with it: a failed load showing the previous clip under the new
      // title claims a clip arrived when none did.
      for (const mesh of [...(state.links || []), ...(state.joints || [])]) {
        if (mesh && mesh.mesh) { mesh.mesh.geometry.dispose(); state.group3d.remove(mesh.mesh); }
      }
      state.group3d.clear();
      state.links = []; state.joints = []; state.dirty = true;
      $('#stage-name').textContent = meta.name;
      $('#stage-meta').textContent = `Could not load this clip (${err.message}). Try again.`;
    }
    return;
  }
  if (token !== selectToken) return;  // a newer clip superseded this one

  const stale = [...(state.links || []).map((l) => l && l.mesh), ...(state.joints || []).map((j) => j && j.mesh)];
  for (const mesh of stale) {
    if (!mesh) continue;
    mesh.geometry.dispose();
    state.group3d.remove(mesh);
  }
  state.group3d.clear();
  const rig = buildSkeleton(clip);
  state.bones = rig.bones;
  state.rootBone = rig.rootBone;
  state.links = rig.links;
  state.joints = rig.joints;
  state.rigScale = rig.rigScale;
  state.anchor = rig.bones.find((b) => /hips|pelvis/i.test(b.name)) || rig.bones[0];
  state.group3d.position.set(0, 0, 0);
  _hasHip = false;
  // The rig is rebuilt with links visible; if the reader chose joint-only mode, the
  // new clip has to honour it instead of quietly switching the button's promise.
  for (const { mesh } of state.links) mesh.visible = state.mode === 'links';
  state.clip = clip;
  state.duration = clip.seconds;

  const nodes = clip.nodes.length;
  state.pose = {
    quats: decode(clip.quats, clip.frames * nodes * 4),
    pos: decode(clip.pos, clip.frames * nodes * 3),
  };
  state.group3d.position.set(0, 0, 0);

  groundRig();
  const status = $('#stage-status');
  if (status) status.remove();
  $('#stage-name').textContent = clip.name;
  $('#stage-meta').textContent = `${clip.seconds.toFixed(1)} s · ${clip.joints} joints · ${Math.round(clip.fps)} fps`;
  // The payload link follows the selection: an engineer should be able to read the exact
  // data the viewer is playing without asking anyone for it.
  const href = `data/${meta.id}.json`;
  $('#payload').setAttribute('href', href);
  $('#payload').setAttribute('download', `${meta.id}.json`);
  $('#payload-link').setAttribute('href', href);
  $('#payload-link').setAttribute('download', `${meta.id}.json`);
  $('#viewer-spec').textContent =
    `joint-space JSON · +Y up · metres · ${Math.round(clip.fps)} fps fixed step · ${clip.joints} joints`;
  // The first frame, decoded, printed where the reader already is. Anyone judging the
  // data can see the bone order and the numbers before they download anything.
  const q = decode(clip.quats, clip.frames * clip.nodes.length * 4);
  const lines = clip.nodes.slice(0, 8).map((nd, i) => {
    // Stored as int16 at scale 32767, so print what they mean, not the storage.
    const o = Array.from(q.slice(i * 4, i * 4 + 4), (n) => (n / 32767).toFixed(3)).join(', ');
    return `${String(i).padStart(2, '0')} ${nd.n.padEnd(14)} quat ${o}`;
  });
  $('#schema-pre').textContent =
    `${clip.id} · frame 0 of ${clip.frames} · ${clip.fps} fps · ${clip.nodes.length} nodes, ${clip.joints} joints\n`
    + lines.join('\n') + `\n… ${clip.nodes.length - 8} more nodes`;
  setTime(0);
  frameCamera();
  history.replaceState(null, '', `?clip=${meta.id}`);
  document.title = `${clip.name} — Motion Library — Robotist`;
}

function syncPlay() {
  const btn = $('#play');
  btn.setAttribute('aria-pressed', String(state.playing));
  btn.setAttribute('aria-label', state.playing ? 'Pause' : 'Play');
  btn.innerHTML = state.playing
    ? '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="1.5" width="3" height="9" rx="1" fill="currentColor"/><rect x="7" y="1.5" width="3" height="9" rx="1" fill="currentColor"/></svg>'
    : '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 1.8v8.4L10.2 6z" fill="currentColor"/></svg>';
}

async function boot() {
  initScene();
  let index;
  try {
    const res = await fetch('data/index.json');
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    index = await res.json();
  } catch (err) {
    $('#stage-meta').textContent = `The clip index did not load (${err.message}). Reload the page.`;
    return;
  }
  state.clips = index.clips;
  // A product page can hand the viewer a model slug. Then the rail shows only the
  // clips mapped to that platform, and the header says whose list this is.
  const wantedModel = new URLSearchParams(location.search).get('model');
  if (wantedModel) {
    try {
      const map = await (await fetch('models.json')).json();
      const cls = map.models?.[wantedModel];
      const ids = map.modelClips?.[wantedModel] || map.clipSets?.[cls] || [];
      if (ids.length) {
        state.modelSet = new Set(ids);
        state.modelName = map.modelNames?.[wantedModel] || wantedModel.replace(/-/g, ' ');
        const note = document.createElement('div');
        note.className = 'model-filter';
        note.innerHTML = '<span></span> <a href="/motion-library/">Show all clips</a>';
        note.querySelector('span').textContent = `Showing the ${ids.length} clips mapped to ${state.modelName}`;
        $('#chips').before(note);
      }
    } catch (err) { /* a missing map just means no filter */ }
  }
  // Someone who asked the system for less motion should get a still frame and a
  // play button, not a loop they have to stop.
  if (matchMedia('(prefers-reduced-motion: reduce)').matches) { state.playing = false; syncPlay(); }

  const chipHost = $('#chips');
  for (const g of GROUPS) {
    const b = document.createElement('button');
    b.className = 'chip';
    b.type = 'button';
    b.textContent = g === 'all' ? 'All clips' : g[0].toUpperCase() + g.slice(1);
    b.dataset.group = g;
    b.setAttribute('aria-pressed', String(g === state.group));
    b.addEventListener('click', () => {
      state.group = g;
      chipHost.querySelectorAll('.chip').forEach((c) => c.setAttribute('aria-pressed', String(c.dataset.group === g)));
      renderRows();
    });
    chipHost.append(b);
  }

  renderRows();
  const wanted = new URLSearchParams(location.search).get('clip');
  const visible = state.clips.filter((c) => !state.modelSet || state.modelSet.has(c.id));
  await select((wanted && visible.some((c) => c.id === wanted)) ? wanted : visible[0].id);

  $('#play').addEventListener('click', () => {
    state.playing = !state.playing;
    state.dirty = true;
    syncPlay();
  });
  $('#scrub').addEventListener('input', (e) => {
    // Scrubbing pauses the clip, so the button has to show the play triangle at once —
    // otherwise it keeps showing pause bars over a clip that is standing still.
    state.playing = false;
    syncPlay();
    setTime(Number(e.target.value) * state.duration);
  });
  $('#mode').addEventListener('click', (e) => {
    state.mode = state.mode === 'links' ? 'joints' : 'links';
    const linksOnly = state.mode === 'links';
    for (const { mesh } of state.links) mesh.visible = linksOnly;
    e.currentTarget.setAttribute('aria-pressed', String(!linksOnly));
    e.currentTarget.textContent = linksOnly ? 'links' : 'joints';
    state.dirty = true;
  });
  $('#nav-toggle').addEventListener('click', () => {
    const open = $('.nav').classList.toggle('open');
    $('#nav-toggle').setAttribute('aria-expanded', String(open));
  });
  addEventListener('scroll', () => $('.nav').classList.toggle('scrolled', scrollY > 40), { passive: true });

  // debug handle for the thumbnail pass and for her to poke at
  window.__lib = { state, setTime, select, frameCamera };
  requestAnimationFrame(tick);
}

boot();
