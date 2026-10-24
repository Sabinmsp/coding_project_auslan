import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.180.0/build/three.module.js";

// --------------------------------------------------
// TUNING
// --------------------------------------------------
const TARGET_SHOULDER_WIDTH = 1.6;  // scene units; original skeleton was +/-0.8
const HIP_Y = 1.2;                  // where the hip sits in the scene
const Z_DAMP = 0.35;                // only used for image-space data (see prepare())
const RIGID_BONES = true;           // enforce constant limb lengths
const MOTION_FILE = "./motion.json";

// MediaPipe Pose landmark indices
const L = {
  nose: 0,
  leftShoulder: 11, rightShoulder: 12,
  leftElbow: 13,    rightElbow: 14,
  leftWrist: 15,    rightWrist: 16,
  leftHip: 23,      rightHip: 24
};

// --------------------------------------------------
// SCENE
// --------------------------------------------------
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x111111);

const camera = new THREE.PerspectiveCamera(
  45, window.innerWidth / window.innerHeight, 0.1, 100
);
camera.position.set(0, 3.0, 8);
camera.lookAt(0, 3.0, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

const light = new THREE.DirectionalLight(0xffffff, 3);
light.position.set(3, 5, 5);
scene.add(light);
scene.add(new THREE.AmbientLight(0xffffff, 1));

// --------------------------------------------------
// JOINTS + BONES
// --------------------------------------------------
const jointMaterial = new THREE.MeshStandardMaterial({ color: 0x00ffcc });
const boneMaterial = new THREE.MeshStandardMaterial({ color: 0xffffff });

function createJoint(x, y, z) {
  const joint = new THREE.Mesh(
    new THREE.SphereGeometry(0.12, 16, 16),
    jointMaterial
  );
  joint.position.set(x, y, z);
  scene.add(joint);
  return joint;
}

function createBone() {
  const bone = new THREE.Mesh(
    new THREE.CylinderGeometry(0.06, 0.06, 1, 12),
    boneMaterial
  );
  scene.add(bone);
  return bone;
}

const head          = createJoint(0, 3.6, 0);
const leftShoulder  = createJoint(-0.8, 2.8, 0);
const rightShoulder = createJoint(0.8, 2.8, 0);
const leftElbow     = createJoint(-1.4, 2.0, 0);
const rightElbow    = createJoint(1.4, 2.0, 0);
const leftWrist     = createJoint(-1.6, 1.2, 0);
const rightWrist    = createJoint(1.6, 1.2, 0);
const chest         = createJoint(0, 2.8, 0);
const hip           = createJoint(0, 1.2, 0);

// name -> mesh, so a prepared frame can be applied by key
const RIG = {
  head, chest, hip,
  leftShoulder, rightShoulder,
  leftElbow, rightElbow,
  leftWrist, rightWrist
};

const leftUpperArm      = createBone();
const leftLowerArm      = createBone();
const rightUpperArm     = createBone();
const rightLowerArm     = createBone();
const spine             = createBone();
const leftShoulderBone  = createBone();
const rightShoulderBone = createBone();
const neck              = createBone();

const UP = new THREE.Vector3(0, 1, 0);
const _mid = new THREE.Vector3();
const _dir = new THREE.Vector3();

function updateBone(bone, start, end) {
  const a = start.position;
  const b = end.position;

  _mid.addVectors(a, b).multiplyScalar(0.5);
  bone.position.copy(_mid);

  bone.scale.set(1, a.distanceTo(b), 1);

  _dir.subVectors(b, a).normalize();
  bone.quaternion.setFromUnitVectors(UP, _dir);
}

function updateAllBones() {
  updateBone(leftUpperArm, leftShoulder, leftElbow);
  updateBone(leftLowerArm, leftElbow, leftWrist);
  updateBone(rightUpperArm, rightShoulder, rightElbow);
  updateBone(rightLowerArm, rightElbow, rightWrist);
  updateBone(spine, chest, hip);
  updateBone(leftShoulderBone, chest, leftShoulder);
  updateBone(rightShoulderBone, chest, rightShoulder);
  updateBone(neck, chest, head);
}

// --------------------------------------------------
// HUD
// --------------------------------------------------
const hud = document.createElement("div");
hud.style.cssText =
  "position:fixed;top:12px;left:12px;color:#00ffcc;font:13px/1.5 ui-monospace,monospace;" +
  "white-space:pre;pointer-events:none;text-shadow:0 0 4px #000";
document.body.appendChild(hud);

// --------------------------------------------------
// MOTION DATA
// --------------------------------------------------
// Both MediaPipe landmark sets put +y DOWN and -z TOWARD the camera, so both
// need y and z flipped for Three.js. They differ in scale:
//   pose        -- image space, x/y normalised 0..1, z a rough relative guess
//   pose_world  -- metres, origin already at the hip midpoint, z comparable to x/y
// pose_world is preferred when present; z damping is only needed for the other.
let motion = null;
let playing = true;
let useMotion = false;
let playhead = 0;

const ARM_CHAINS = [
  { shoulder: "leftShoulder",  elbow: "leftElbow",  wrist: "leftWrist"  },
  { shoulder: "rightShoulder", elbow: "rightElbow", wrist: "rightWrist" }
];

function median(values) {
  const s = [...values].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
}

function midpoint(lms, a, b) {
  return {
    x: (lms[a].x + lms[b].x) / 2,
    y: (lms[a].y + lms[b].y) / 2,
    z: (lms[a].z + lms[b].z) / 2
  };
}

function prepare(data) {
  const world = data.frames.some(f => f.pose_world);
  const source = f => (world ? f.pose_world : f.pose);
  const zDamp = world ? 1 : Z_DAMP;

  const posed = data.frames.filter(f => source(f));

  // Scale from median shoulder width, so the figure always fills the frame
  // the same way regardless of signer distance or units.
  const scale = TARGET_SHOULDER_WIDTH / median(
    posed.map(f => {
      const p = source(f);
      return Math.hypot(
        p[L.leftShoulder].x - p[L.rightShoulder].x,
        p[L.leftShoulder].y - p[L.rightShoulder].y
      );
    })
  );

  // Pass 1 -- transform every frame into scene space.
  const frames = data.frames.map(f => {
    const p = source(f);
    if (!p) return null;

    const origin = midpoint(p, L.leftHip, L.rightHip);
    const put = lm => new THREE.Vector3(
       (lm.x - origin.x) * scale,
      -(lm.y - origin.y) * scale + HIP_Y,
      -(lm.z - origin.z) * scale * zDamp
    );

    return {
      head:          put(p[L.nose]),
      leftShoulder:  put(p[L.leftShoulder]),
      rightShoulder: put(p[L.rightShoulder]),
      leftElbow:     put(p[L.leftElbow]),
      rightElbow:    put(p[L.rightElbow]),
      leftWrist:     put(p[L.leftWrist]),
      rightWrist:    put(p[L.rightWrist]),
      chest:         put(midpoint(p, L.leftShoulder, L.rightShoulder)),
      hip:           put(origin),
      hasLeftHand:  !!f.left_hand,
      hasRightHand: !!f.right_hand
    };
  });

  // Pass 2 -- MediaPipe estimates each joint independently, so limb lengths
  // wobble frame to frame (depth is the noisy axis). Keep the direction it
  // reports, but pin the length to the clip median so bones stay rigid.
  if (RIGID_BONES) {
    const valid = frames.filter(Boolean);

    for (const chain of ARM_CHAINS) {
      const upper = median(valid.map(f => f[chain.shoulder].distanceTo(f[chain.elbow])));
      const fore  = median(valid.map(f => f[chain.elbow].distanceTo(f[chain.wrist])));

      for (const f of valid) {
        f[chain.elbow].copy(
          f[chain.elbow].clone().sub(f[chain.shoulder]).normalize()
            .multiplyScalar(upper).add(f[chain.shoulder])
        );
        f[chain.wrist].copy(
          f[chain.wrist].clone().sub(f[chain.elbow]).normalize()
            .multiplyScalar(fore).add(f[chain.elbow])
        );
      }
    }
  }

  return { fps: data.fps, frames, world, scale, count: frames.length };
}

function applyFrame(frame) {
  if (!frame) return;
  for (const name in RIG) RIG[name].position.copy(frame[name]);
}

// --------------------------------------------------
// FALLBACK: the Step 2 synthetic movement
// --------------------------------------------------
function applyDemo(time) {
  rightWrist.position.x = 1.5 + Math.sin(time * 3) * 0.5;
  rightWrist.position.y = 2.5 + Math.sin(time * 4) * 0.3;
  rightWrist.position.z = Math.sin(time * 2) * 0.5;
  rightElbow.position.y = 2.3 + Math.sin(time * 2) * 0.2;
  leftWrist.position.y  = 1.8 + Math.sin(time * 2) * 0.2;
}

// --------------------------------------------------
// ANIMATION
// --------------------------------------------------
const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);

  const delta = clock.getDelta();
  const time = clock.getElapsedTime();

  if (useMotion && motion) {
    if (playing) playhead += delta;

    const total = motion.count / motion.fps;
    const index = Math.floor((playhead % total) * motion.fps);
    const frame = motion.frames[index];

    applyFrame(frame);

    hud.textContent =
      `motion.json  ${motion.world ? "pose_world (metres)" : "pose (image space)"}` +
      `${RIGID_BONES ? "  rigid bones" : ""}\n` +
      `frame ${index + 1}/${motion.count} @ ${motion.fps}fps\n` +
      `hands  L:${frame && frame.hasLeftHand ? "yes" : "--"}  ` +
      `R:${frame && frame.hasRightHand ? "yes" : "--"}\n` +
      `${playing ? "playing" : "paused"}   [space] pause   [d] demo`;
  } else {
    applyDemo(time);
    hud.textContent =
      `synthetic demo (Step 2)\n` +
      (motion ? "[d] switch to motion.json" : "motion.json not loaded");
  }

  updateAllBones();
  renderer.render(scene, camera);
}

animate();

// --------------------------------------------------
// LOAD
// --------------------------------------------------
fetch(MOTION_FILE)
  .then(r => {
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  })
  .then(data => {
    motion = prepare(data);
    useMotion = true;
    console.log(
      `motion.json: ${motion.count} frames @ ${motion.fps}fps, ` +
      `${motion.world ? "pose_world" : "pose"}, scale ${motion.scale.toFixed(2)}`
    );
  })
  .catch(err => {
    console.warn("Could not load motion.json, staying on synthetic demo:", err);
  });

// --------------------------------------------------
// CONTROLS
// --------------------------------------------------
window.addEventListener("keydown", e => {
  if (e.code === "Space") {
    e.preventDefault();
    playing = !playing;
  }
  if (e.key === "d" || e.key === "D") {
    useMotion = !useMotion && motion !== null;
  }
});

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
