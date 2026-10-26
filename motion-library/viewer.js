/* Motion Library viewer — skeleton playback from joint-space data.
   No capture files, no meshes: the panel draws links between bone origins. */

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';

const $ = (sel) => document.querySelector(sel);

const state = {
  clips: [], rows: [], selected: null, group: 'all',
  clip: null, bones: [], links: [], joints: [], pose: null,
  t: 0, playing: true, mode: 'links', duration: 1, rootBone: null,
};

/* ── skeleton ─────────────────────────────────────────────── */
const matLink = new THREE.MeshStandardMaterial({ color: 0x4aa8c8, roughness: 0.45, metalness: 0.35 });
const matLinkDim = new THREE.MeshStandardMaterial({ color: 0x2e6f8a, roughness: 0.6, metalness: 0.25 });
const matJoint = new THREE.MeshStandardMaterial({ color: 0xa8dcef, roughness: 0.3, metalness: 0.2, emissive: 0x0d2b36 });

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

  const linkGeo = new THREE.BoxGeometry(1, 1, 1);
  const jointGeo = new THREE.SphereGeometry(1, 14, 10);
  const links = [], joints = [];

  clip.nodes.forEach((b, i) => {
    if (b.p >= 0) {
      const mesh = new THREE.Mesh(linkGeo, b.n.endsWith('_r') ? matLinkDim : matLink);
      state.group3d.add(mesh);
      links.push({ bone: bones[i], parent: bones[b.p], mesh });
    }
    const jm = new THREE.Mesh(jointGeo, matJoint);
    state.group3d.add(jm);
    joints.push({ bone: bones[i], mesh: jm });
  });

  return { bones, rootBone, links, joints };
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
  for (const { bone, parent, mesh } of state.links) {
    parent.getWorldPosition(_a);
    bone.getWorldPosition(_b);
    _d.subVectors(_b, _a);
    const len = Math.max(_d.length(), 0.02);
    mesh.position.addVectors(_a, _b).multiplyScalar(0.5);
    mesh.quaternion.setFromUnitVectors(_up, _d.normalize());
    const thick = Math.min(0.055, Math.max(0.020, len * 0.20));
    mesh.scale.set(thick, len, thick * 0.82);
  }
  for (const { bone, mesh } of state.joints) {
    bone.getWorldPosition(_a);
    mesh.position.copy(_a);
    mesh.scale.setScalar(0.025);
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

  const resize = () => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  };
  new ResizeObserver(resize).observe(canvas);
  resize();
}

function groundRig() {
  // Feet on the grid, and the clip's whole footprint measured once so the camera
  // can hold a travelling figure in frame instead of chasing frame zero.
  const p = new THREE.Vector3();
  const box = new THREE.Box3();
  const step = Math.max(1, Math.floor(state.clip.frames / 16));
  state.group3d.position.y = 0;
  for (let f = 0; f < state.clip.frames; f += step) {
    samplePose(state.clip, f / state.clip.fps);
    state.group3d.updateMatrixWorld(true);
    for (const { bone } of state.joints) {
      bone.getWorldPosition(p);
      box.expandByPoint(p);
    }
  }
  if (Number.isFinite(box.min.y)) state.group3d.position.y = -box.min.y;
  box.min.y += state.group3d.position.y;
  box.max.y += state.group3d.position.y;
  state.bounds = box;
  state.group3d.updateMatrixWorld(true);
}

function frameCamera() {
  const box = state.bounds ? state.bounds.clone() : new THREE.Box3();
  if (box.isEmpty()) {
    const p = new THREE.Vector3();
    for (const { bone } of state.joints) {
      bone.getWorldPosition(p);
      box.expandByPoint(p);
    }
  }
  const h = Math.max(1.2, box.max.y - Math.max(0, box.min.y));
  const spread = Math.max(box.max.x - box.min.x, box.max.z - box.min.z);
  const cy = (box.max.y + Math.max(0, box.min.y)) * 0.5;
  const cx = (box.max.x + box.min.x) * 0.5;
  const cz = (box.max.z + box.min.z) * 0.5;
  // Three-quarter view: straight-on foreshortens any pose that moves along Z
  // (push-ups, crawls) into an unreadable knot.
  const dist = Math.max(2.1, h * 1.92, spread * 1.9);
  const az = 0.56;  // ~32 degrees
  state.camera.position.set(cx + Math.sin(az) * dist, cy + h * 0.10, cz + Math.cos(az) * dist);
  state.controls.target.set(cx, cy, cz);
  state.controls.update();
}

/* ── transport ────────────────────────────────────────────── */
function setTime(t) {
  state.t = Math.max(0, Math.min(state.duration, t));
  if (!state.clip) return;
  samplePose(state.clip, state.t);
  state.group3d.updateMatrixWorld(true);
  updateRig();
  const scrub = $('#scrub');
  if (scrub && document.activeElement !== scrub) scrub.value = String(state.duration ? state.t / state.duration : 0);
  $('#time').textContent = `${state.t.toFixed(2)} / ${state.duration.toFixed(2)} s`;
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
  state.controls.update();
  state.renderer.render(state.scene, state.camera);
  requestAnimationFrame(tick);
}

/* ── library ──────────────────────────────────────────────── */
const GROUPS = ['all', 'locomotion', 'sport', 'combat', 'fitness', 'form', 'daily', 'gesture'];

function renderRows() {
  const host = $('#rows');
  host.innerHTML = '';
  const list = state.clips.filter((c) => state.group === 'all' || c.group === state.group);
  for (const clip of list) {
    const row = document.createElement('button');
    row.className = 'row';
    row.type = 'button';
    row.setAttribute('role', 'option');
    row.setAttribute('aria-selected', String(clip.id === state.selected));
    row.dataset.id = clip.id;
    row.innerHTML = `<img src="thumbs/${clip.id}.webp" alt="" width="62" height="40" loading="lazy" decoding="async">
      <span><span class="name"></span><span class="sub">${clip.nodes} bones · ${Math.round(clip.fps)} fps</span></span>
      <span class="len">${clip.seconds.toFixed(1)}s</span>`;
    row.querySelector('.name').textContent = clip.name;
    row.addEventListener('click', () => select(clip.id));
    host.append(row);
  }
  $('#count').textContent = `${list.length} of ${state.clips.length}`;
}

async function select(id) {
  const meta = state.clips.find((c) => c.id === id) || state.clips[0];
  if (!meta) return;
  state.selected = meta.id;
  document.querySelectorAll('.row').forEach((r) => r.setAttribute('aria-selected', String(r.dataset.id === meta.id)));
  const row = document.querySelector(`.row[data-id="${meta.id}"]`);
  const list = row && row.parentElement;
  if (row && list && list.scrollHeight > list.clientHeight) {
    const top = row.offsetTop - list.offsetTop;
    if (top < list.scrollTop || top + row.offsetHeight > list.scrollTop + list.clientHeight) {
      list.scrollTop = top - list.clientHeight / 2 + row.offsetHeight / 2;
    }
  }

  const clip = await (await fetch(`data/${meta.id}.json`)).json();
  for (const { mesh } of [...state.links.map((l) => l.mesh), ...state.joints.map((j) => j.mesh)]) {
    state.group3d.remove(mesh);
  }
  const rig = buildSkeleton(clip);
  state.bones = rig.bones;
  state.rootBone = rig.rootBone;
  state.links = rig.links;
  state.joints = rig.joints;
  state.clip = clip;
  state.duration = clip.seconds;

  const nodes = clip.nodes.length;
  state.pose = {
    quats: decode(clip.quats, clip.frames * nodes * 4),
    pos: decode(clip.pos, clip.frames * nodes * 3),
  };
  state.group3d.position.set(0, 0, 0);

  groundRig();
  $('#stage-name').textContent = clip.name;
  $('#stage-meta').textContent = `${clip.seconds.toFixed(2)} s · ${clip.nodes.length} joints · ${Math.round(clip.fps)} fps`;
  setTime(0);
  frameCamera();
  history.replaceState(null, '', `?clip=${meta.id}`);
  document.title = `${clip.name} — Motion Library — Robotist`;
}

async function boot() {
  initScene();
  const index = await (await fetch('data/index.json')).json();
  state.clips = index.clips;

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
  await select(state.clips.some((c) => c.id === wanted) ? wanted : state.clips[0].id);

  $('#play').addEventListener('click', () => {
    state.playing = !state.playing;
    $('#play').setAttribute('aria-pressed', String(state.playing));
    $('#play').innerHTML = state.playing
      ? '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><rect x="2" y="1.5" width="3" height="9" rx="1" fill="currentColor"/><rect x="7" y="1.5" width="3" height="9" rx="1" fill="currentColor"/></svg>'
      : '<svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 1.8v8.4L10.2 6z" fill="currentColor"/></svg>';
  });
  $('#scrub').addEventListener('input', (e) => {
    state.playing = false;
    $('#play').setAttribute('aria-pressed', 'false');
    setTime(Number(e.target.value) * state.duration);
  });
  $('#mode').addEventListener('click', (e) => {
    state.mode = state.mode === 'links' ? 'joints' : 'links';
    const linksOnly = state.mode === 'links';
    for (const { mesh } of state.links) mesh.visible = linksOnly;
    e.currentTarget.setAttribute('aria-pressed', String(!linksOnly));
    e.currentTarget.textContent = linksOnly ? 'links' : 'joints';
  });
  $('#nav-toggle').addEventListener('click', () => $('.nav').classList.toggle('open'));
  addEventListener('scroll', () => $('.nav').classList.toggle('scrolled', scrollY > 40), { passive: true });

  // debug handle for the thumbnail pass and for her to poke at
  window.__lib = { state, setTime, select, frameCamera };
  requestAnimationFrame(tick);
}

boot();
