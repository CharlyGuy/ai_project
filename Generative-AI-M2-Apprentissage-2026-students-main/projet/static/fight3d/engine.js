/**
 * static/fight3d/engine.js — FightStrategist AI · Fight Simulator 3D
 * -------------------------------------------------------------------
 * Moteur Three.js r128 qui rejoue une timeline `simulate_fight_playbyplay`
 * en 3D animée, style jeu de combat console.
 *
 * API publique :
 *   window.FightEngine = { init(containerId), loadFight(json), play(), pause(), restart(), setSpeed(x) }
 * Données : window.FIGHT_DATA = { timeline: {...}, fighters: {a: {...}, b: {...}} }
 * (fallback : window.SAMPLE_FIGHT_DATA, pour ouvrir index.html seul.)
 *
 * Contraintes : r128 uniquement — PAS de CapsuleGeometry ni d'OrbitControls.
 * Corps = CylinderGeometry + SphereGeometry ; tête = billboard photo (data-URI).
 */
(function () {
  "use strict";

  // ---------- constantes ----------
  var BLUE = 0x4d7cff, RED = 0xff2d2d, SKIN = 0xc8956c;
  var ROUND_SIM_S = 60;                 // 60 s simulées = 5:00 affichées
  var CAGE_R = 4.6;

  // ---------- état global du moteur ----------
  var scene, camera, renderer, clock, container;
  var fighters = {};                    // {a: rig, b: rig}
  var data = null;                      // FIGHT_DATA
  var events = [], evIdx = 0;
  var simT = 0, curRound = 1, playing = false, speed = 1, timeScale = 1;
  var health = { a: 100, b: 100 }, stamina = { a: 100, b: 100 };
  var combo = { actor: null, count: 0 };
  var shake = 0, slowmoUntil = 0, finished = false, betweenRounds = 0;
  var particles = [], damageSprites = [];
  var groundPair = null;                // 'a'|'b' dominant au sol, ou null

  function $(id) { return document.getElementById(id); }

  // =====================================================================
  // SCÈNE : octogone, éclairage broadcast, caméra
  // =====================================================================
  function buildScene() {
    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0e0e10);
    scene.fog = new THREE.Fog(0x0e0e10, 14, 30);

    // --- sol octogonal + logo central procédural (canvas) ---
    var cv = document.createElement("canvas"); cv.width = cv.height = 512;
    var g = cv.getContext("2d");
    g.fillStyle = "#23232a"; g.fillRect(0, 0, 512, 512);
    g.strokeStyle = "#3a3a44"; g.lineWidth = 3;
    for (var i = 0; i < 8; i++) { g.beginPath(); g.moveTo(256, 256); g.lineTo(256 + 256 * Math.cos(i * Math.PI / 4), 256 + 256 * Math.sin(i * Math.PI / 4)); g.stroke(); }
    g.beginPath(); g.arc(256, 256, 120, 0, 6.3); g.strokeStyle = "#ff2d2d"; g.lineWidth = 8; g.stroke();
    g.font = "900 44px Arial"; g.fillStyle = "#ff9d2d"; g.textAlign = "center"; g.textBaseline = "middle";
    g.fillText("FIGHT", 256, 236); g.fillText("STRATEGIST", 256, 286);
    var mat = new THREE.MeshStandardMaterial({ map: new THREE.CanvasTexture(cv), roughness: 0.85 });
    var floor = new THREE.Mesh(new THREE.CylinderGeometry(CAGE_R, CAGE_R, 0.12, 8), mat);
    floor.position.y = -0.06; floor.receiveShadow = true; scene.add(floor);

    // --- 8 poteaux + grillage wireframe semi-transparent ---
    var postMat = new THREE.MeshStandardMaterial({ color: 0x111114, metalness: 0.6, roughness: 0.4 });
    var fenceMat = new THREE.MeshBasicMaterial({ color: 0x777788, wireframe: true, transparent: true, opacity: 0.28 });
    for (var p = 0; p < 8; p++) {
      var ang = p * Math.PI / 4 + Math.PI / 8;
      var post = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 1.9, 8), postMat);
      post.position.set(CAGE_R * Math.cos(ang), 0.95, CAGE_R * Math.sin(ang)); scene.add(post);
    }
    var fence = new THREE.Mesh(new THREE.CylinderGeometry(CAGE_R, CAGE_R, 1.8, 8, 6, true), fenceMat);
    fence.position.y = 0.9; scene.add(fence);
    var rail = new THREE.Mesh(new THREE.TorusGeometry(CAGE_R, 0.05, 8, 8), postMat);
    rail.rotation.x = Math.PI / 2; rail.position.y = 1.8; scene.add(rail);

    // --- éclairage broadcast ---
    scene.add(new THREE.AmbientLight(0x404050, 0.9));
    var spot = new THREE.SpotLight(0xffffff, 1.25, 40, Math.PI / 4, 0.4);
    spot.position.set(0, 11, 0); spot.castShadow = true; scene.add(spot);
    var lA = new THREE.PointLight(BLUE, 0.55, 18); lA.position.set(-6, 4, 3); scene.add(lA);
    var lB = new THREE.PointLight(RED, 0.55, 18); lB.position.set(6, 4, 3); scene.add(lB);

    camera = new THREE.PerspectiveCamera(46, container.clientWidth / container.clientHeight, 0.1, 60);
    camera.position.set(0, 3.4, 8.6); camera.lookAt(0, 1.1, 0);
  }

  // =====================================================================
  // PERSONNAGE : humanoïde articulé, tête-photo billboard, morpho data-driven
  // =====================================================================
  function weightScale(wc) {
    wc = (wc || "").toLowerCase();
    if (wc.indexOf("heavyweight") >= 0 && wc.indexOf("light") < 0) return 1.3;
    if (wc.indexOf("light heavyweight") >= 0) return 1.18;
    if (wc.indexOf("middleweight") >= 0) return 1.08;
    if (wc.indexOf("welterweight") >= 0) return 1.0;
    if (wc.indexOf("lightweight") >= 0) return 0.94;
    if (wc.indexOf("featherweight") >= 0) return 0.88;
    return 0.84; // bantamweight et moins
  }

  function makeNameBar(f) {
    var cv = document.createElement("canvas"); cv.width = 512; cv.height = 96;
    var g = cv.getContext("2d");
    g.fillStyle = "rgba(10,10,14,0.75)"; g.fillRect(0, 0, 512, 96);
    g.font = "900 34px Arial"; g.fillStyle = "#fff"; g.textAlign = "center";
    g.fillText((f.name || "?").toUpperCase(), 256, 38);
    g.font = "italic 24px Arial"; g.fillStyle = "#ff9d2d";
    var rec = f.wins != null ? f.wins + "-" + f.losses + "-" + (f.draws || 0) : "";
    g.fillText((f.nickname ? '"' + f.nickname + '" · ' : "") + rec, 256, 74);
    var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true }));
    sp.scale.set(1.7, 0.32, 1);
    return sp;
  }

  function buildFighter(f, corner, side) {
    var color = corner === "a" ? BLUE : RED;
    var h = (f.height_cm || 180) / 180;                       // hauteur ∝ height_cm
    var armLen = ((f.reach_cm || 180) / (f.height_cm || 180)) * 0.62; // bras ∝ reach
    var w = weightScale(f.weight_class);

    var mSkin = new THREE.MeshStandardMaterial({ color: SKIN, roughness: 0.7 });
    var mShort = new THREE.MeshStandardMaterial({ color: color, roughness: 0.6 });
    var mGlove = new THREE.MeshStandardMaterial({ color: color, roughness: 0.5 });

    var root = new THREE.Group();

    // torse
    var torso = new THREE.Group(); torso.position.y = 1.02 * h; root.add(torso);
    var chest = new THREE.Mesh(new THREE.CylinderGeometry(0.16 * w, 0.19 * w, 0.52 * h, 12), mSkin);
    chest.position.y = 0.13 * h; torso.add(chest);
    var shorts = new THREE.Mesh(new THREE.CylinderGeometry(0.19 * w, 0.16 * w, 0.24 * h, 12), mShort);
    shorts.position.y = -0.25 * h; torso.add(shorts);

    // tête : sphère + billboard photo circulaire (data-URI -> zéro CORS)
    var headG = new THREE.Group(); headG.position.y = 0.5 * h; torso.add(headG);
    headG.add(new THREE.Mesh(new THREE.SphereGeometry(0.13 * w + 0.02, 14, 12), mSkin));
    var photoOK = false;
    if (f.photo_datauri) {
      try {
        var tex = new THREE.TextureLoader().load(f.photo_datauri);
        var bb = new THREE.Mesh(new THREE.CircleGeometry(0.17, 24),
          new THREE.MeshBasicMaterial({ map: tex, side: THREE.DoubleSide }));
        var ring = new THREE.Mesh(new THREE.RingGeometry(0.17, 0.2, 24),
          new THREE.MeshBasicMaterial({ color: color, side: THREE.DoubleSide }));
        var bbG = new THREE.Group(); bbG.add(bb); bbG.add(ring);
        bbG.position.z = 0.05; headG.add(bbG);
        headG.userData.billboard = bbG;
        photoOK = true;
      } catch (e) { photoOK = false; }
    }
    if (!photoOK) headG.children[0].material = new THREE.MeshStandardMaterial({ color: SKIN, roughness: 0.6 });

    // bras : épaule -> coude -> gant (pivots imbriqués)
    function makeArm(sideX) {
      var sh = new THREE.Group(); sh.position.set(0.2 * w * sideX, 0.36 * h, 0); torso.add(sh);
      var up = new THREE.Mesh(new THREE.CylinderGeometry(0.05 * w, 0.045 * w, armLen * 0.5, 8), mSkin);
      up.position.y = -armLen * 0.25; sh.add(up);
      var el = new THREE.Group(); el.position.y = -armLen * 0.5; sh.add(el);
      var fo = new THREE.Mesh(new THREE.CylinderGeometry(0.042 * w, 0.04 * w, armLen * 0.45, 8), mSkin);
      fo.position.y = -armLen * 0.225; el.add(fo);
      var glove = new THREE.Mesh(new THREE.SphereGeometry(0.07 * w, 10, 8), mGlove);
      glove.position.y = -armLen * 0.5; el.add(glove);
      return { shoulder: sh, elbow: el, glove: glove };
    }
    // jambes : hanche -> genou -> pied
    function makeLeg(sideX) {
      var hip = new THREE.Group(); hip.position.set(0.1 * w * sideX, -0.37 * h, 0); torso.add(hip);
      var th = new THREE.Mesh(new THREE.CylinderGeometry(0.07 * w, 0.055 * w, 0.34 * h, 8), mSkin);
      th.position.y = -0.17 * h; hip.add(th);
      var kn = new THREE.Group(); kn.position.y = -0.34 * h; hip.add(kn);
      var sh2 = new THREE.Mesh(new THREE.CylinderGeometry(0.05 * w, 0.04 * w, 0.31 * h, 8), mSkin);
      sh2.position.y = -0.155 * h; kn.add(sh2);
      var foot = new THREE.Mesh(new THREE.BoxGeometry(0.09 * w, 0.05, 0.2), mSkin);
      foot.position.set(0, -0.31 * h, 0.05); kn.add(foot);
      return { hip: hip, knee: kn };
    }

    var southpaw = /southpaw/i.test(f.stance || "");
    var rig = {
      root: root, torso: torso, head: headG,
      armL: makeArm(-1), armR: makeArm(1),
      legL: makeLeg(-1), legR: makeLeg(1),
      corner: corner, southpaw: southpaw, h: h,
      homeX: side * 1.15, dir: -side,     // dir = vers l'adversaire
      anim: null, grounded: false, koDown: false,
    };
    var bar = makeNameBar(f); bar.position.y = 2.05 * h; root.add(bar);
    root.position.set(rig.homeX, 0, 0);
    root.rotation.y = side > 0 ? -Math.PI / 2 : Math.PI / 2;   // face à face
    scene.add(root);
    guardPose(rig, 1);
    return rig;
  }

  // ---------- poses & animations procédurales ----------
  function guardPose(r, t) {
    // garde : coudes pliés, gants hauts (miroir si southpaw)
    var lead = r.southpaw ? r.armR : r.armL, rear = r.southpaw ? r.armL : r.armR;
    lerpRot(lead.shoulder, { x: -1.15, y: 0, z: 0.25 }, t);
    lerpRot(lead.elbow, { x: -1.5, y: 0, z: 0 }, t);
    lerpRot(rear.shoulder, { x: -1.25, y: 0, z: -0.35 }, t);
    lerpRot(rear.elbow, { x: -1.75, y: 0, z: 0 }, t);
    lerpRot(r.torso, { x: 0.06, y: r.southpaw ? -0.3 : 0.3, z: 0 }, t);
    lerpRot(r.legL.hip, { x: -0.12, y: 0, z: 0 }, t); lerpRot(r.legL.knee, { x: 0.2, y: 0, z: 0 }, t);
    lerpRot(r.legR.hip, { x: 0.12, y: 0, z: 0 }, t); lerpRot(r.legR.knee, { x: 0.2, y: 0, z: 0 }, t);
  }
  function lerpRot(g, tgt, t) {
    g.rotation.x += (tgt.x - g.rotation.x) * t;
    g.rotation.y += ((tgt.y || 0) - g.rotation.y) * t;
    g.rotation.z += ((tgt.z || 0) - g.rotation.z) * t;
  }
  function easeOutQuad(x) { return 1 - (1 - x) * (1 - x); }

  // Une animation = {dur, fn(progress, rig)} ; progress 0->1 avec easing,
  // aller-retour (out-and-back) : p<0.5 extension, p>0.5 retour garde.
  function outBack(p) { return p < 0.5 ? easeOutQuad(p * 2) : easeOutQuad((1 - p) * 2); }

  var ANIMS = {
    jab: function (p, r) { var e = outBack(p), a = r.southpaw ? r.armR : r.armL;
      a.shoulder.rotation.x = -1.15 - 0.45 * e; a.elbow.rotation.x = -1.5 + 1.5 * e;
      r.torso.rotation.y += 0.25 * e * (r.southpaw ? 1 : -1); r.root.position.x = r.homeX + r.dir * 0.3 * e; },
    cross: function (p, r) { var e = outBack(p), a = r.southpaw ? r.armL : r.armR;
      a.shoulder.rotation.x = -1.25 - 0.5 * e; a.elbow.rotation.x = -1.75 + 1.75 * e;
      r.torso.rotation.y += 0.55 * e * (r.southpaw ? 1 : -1); r.root.position.x = r.homeX + r.dir * 0.42 * e; },
    hook: function (p, r) { var e = outBack(p), a = r.southpaw ? r.armR : r.armL;
      a.shoulder.rotation.x = -1.4 - 0.2 * e; a.shoulder.rotation.z = (r.southpaw ? -1 : 1) * (0.25 + 1.15 * e);
      a.elbow.rotation.x = -1.5 + 0.4 * e; r.torso.rotation.y += 0.7 * e * (r.southpaw ? 1 : -1);
      r.root.position.x = r.homeX + r.dir * 0.3 * e; },
    uppercut: function (p, r) { var e = outBack(p), a = r.southpaw ? r.armL : r.armR;
      a.shoulder.rotation.x = -1.0 - 0.9 * e; a.elbow.rotation.x = -2.1 + 0.9 * e;
      r.torso.rotation.x = 0.06 + 0.3 * e; r.root.position.y = 0.1 * e; },
    leg_kick: function (p, r) { var e = outBack(p), l = r.southpaw ? r.legL : r.legR;
      l.hip.rotation.x = 0.12 - 1.0 * e; l.hip.rotation.z = (r.southpaw ? 1 : -1) * 0.5 * e;
      l.knee.rotation.x = 0.2 + 0.7 * e; r.torso.rotation.y += 0.5 * e * (r.southpaw ? 1 : -1); },
    body_kick: function (p, r) { var e = outBack(p), l = r.southpaw ? r.legL : r.legR;
      l.hip.rotation.x = 0.12 - 1.5 * e; l.knee.rotation.x = 0.2 + 1.1 * e;
      r.torso.rotation.z = (r.southpaw ? -1 : 1) * 0.3 * e; },
    head_kick: function (p, r) { var e = outBack(p), l = r.southpaw ? r.legL : r.legR;
      l.hip.rotation.x = 0.12 - 2.3 * e; l.knee.rotation.x = 0.2 + 0.9 * e;
      r.torso.rotation.z = (r.southpaw ? -1 : 1) * 0.55 * e; r.torso.rotation.x = 0.06 - 0.25 * e; },
    takedown_attempt: function (p, r) { var e = outBack(p);
      r.torso.rotation.x = 0.06 + 1.15 * e;                    // plongée de niveau
      r.legL.knee.rotation.x = 0.2 + 1.3 * e; r.legR.knee.rotation.x = 0.2 + 1.3 * e;
      r.root.position.y = -0.32 * e; r.root.position.x = r.homeX + r.dir * 0.75 * e;
      r.armL.shoulder.rotation.x = -0.4 - 0.8 * e; r.armR.shoulder.rotation.x = -0.4 - 0.8 * e; },
    block: function (p, r) { var e = outBack(p);
      r.armL.shoulder.rotation.x = -1.5 - 0.3 * e; r.armR.shoulder.rotation.x = -1.5 - 0.3 * e;
      r.armL.elbow.rotation.x = -2.2; r.armR.elbow.rotation.x = -2.2; },
    dodge: function (p, r) { var e = outBack(p);
      r.torso.rotation.z = 0.5 * e * (Math.random() < 0.5 ? 1 : -1); r.root.position.y = -0.12 * e; },
    clinch: function (p, r) { var e = outBack(p);
      r.armL.shoulder.rotation.x = -1.6 - 0.2 * e; r.armR.shoulder.rotation.x = -1.6 - 0.2 * e;
      r.root.position.x = r.homeX + r.dir * 0.55 * e; },
    ground_strikes: function (p, r) { var e = Math.sin(p * Math.PI * 3);
      r.armR.shoulder.rotation.x = -1.0 - 0.8 * Math.abs(e); r.armR.elbow.rotation.x = -0.6; },
    submission_attempt: function (p, r) { var e = outBack(p);
      r.armL.shoulder.rotation.x = -2.0 * e; r.armR.shoulder.rotation.x = -2.0 * e;
      r.torso.rotation.x = 0.5 + 0.4 * e; },
    idle: function (p, r) { r.root.position.y = 0.03 * Math.sin(p * Math.PI * 2); },
  };

  function playAnim(rig, action, dur) {
    if (rig.koDown) return;
    rig.anim = { action: action, t: 0, dur: dur || 0.55 };
  }

  // états spéciaux plein-corps
  function setGrounded(domRig, subRig) {
    groundPair = domRig.corner;
    subRig.grounded = true; domRig.grounded = true;
    subRig.root.rotation.x = -Math.PI / 2; subRig.root.position.y = 0.18;  // dominé sur le dos
    domRig.root.position.set((subRig.homeX + domRig.homeX) / 2, 0.28, 0.25); // dominant au-dessus
    domRig.root.rotation.x = 0.9;
    subRig.root.position.x = (subRig.homeX + domRig.homeX) / 2;
  }
  function standUp() {
    groundPair = null;
    ["a", "b"].forEach(function (k) {
      var r = fighters[k]; if (r.koDown) return;
      r.grounded = false;
      r.root.rotation.x = 0; r.root.position.set(r.homeX, 0, 0);
    });
  }
  function knockdown(rig, permanent) {
    rig.koDown = !!permanent;
    rig.root.rotation.x = -Math.PI / 2; rig.root.position.y = 0.18;
    if (!permanent) setTimeout(function () {
      if (!rig.koDown && !rig.grounded) { rig.root.rotation.x = 0; rig.root.position.y = 0; }
    }, 900 / speed);
  }

  // =====================================================================
  // EFFETS jeu vidéo : sparks, damage numbers, shake, combo, slow-mo
  // =====================================================================
  function spawnSpark(pos, dmg) {
    var n = Math.min(40, 8 + Math.floor(dmg * 4));
    var geo = new THREE.BufferGeometry(), arr = new Float32Array(n * 3), vel = [];
    for (var i = 0; i < n; i++) {
      arr[i * 3] = pos.x; arr[i * 3 + 1] = pos.y; arr[i * 3 + 2] = pos.z;
      vel.push(new THREE.Vector3((Math.random() - 0.5) * 3, Math.random() * 2.5, (Math.random() - 0.5) * 3));
    }
    geo.setAttribute("position", new THREE.BufferAttribute(arr, 3));
    var mat = new THREE.PointsMaterial({ color: dmg > 8 ? 0xff2d2d : 0xffd24d, size: 0.05 + dmg * 0.008, transparent: true });
    var pts = new THREE.Points(geo, mat);
    pts.userData = { vel: vel, life: 0.6 };
    scene.add(pts); particles.push(pts);
  }
  function spawnDamage(pos, dmg) {
    var cv = document.createElement("canvas"); cv.width = 128; cv.height = 64;
    var g = cv.getContext("2d");
    g.font = "900 40px Arial"; g.textAlign = "center";
    g.fillStyle = dmg > 8 ? "#ff2d2d" : "#ffd24d";
    g.strokeStyle = "#000"; g.lineWidth = 5;
    g.strokeText("-" + dmg.toFixed(1), 64, 44); g.fillText("-" + dmg.toFixed(1), 64, 44);
    var sp = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(cv), transparent: true }));
    sp.position.copy(pos); sp.position.y += 0.3; sp.scale.set(0.7, 0.35, 1);
    sp.userData = { life: 1.0 };
    scene.add(sp); damageSprites.push(sp);
  }
  function updateEffects(dt) {
    for (var i = particles.length - 1; i >= 0; i--) {
      var p = particles[i]; p.userData.life -= dt;
      var pos = p.geometry.attributes.position;
      for (var j = 0; j < pos.count; j++) {
        var v = p.userData.vel[j];
        pos.setXYZ(j, pos.getX(j) + v.x * dt, pos.getY(j) + v.y * dt, pos.getZ(j) + v.z * dt);
        v.y -= 6 * dt;
      }
      pos.needsUpdate = true; p.material.opacity = Math.max(0, p.userData.life / 0.6);
      if (p.userData.life <= 0) { scene.remove(p); particles.splice(i, 1); }
    }
    for (var k = damageSprites.length - 1; k >= 0; k--) {
      var s = damageSprites[k]; s.userData.life -= dt;
      s.position.y += 0.8 * dt; s.material.opacity = Math.max(0, s.userData.life);
      if (s.userData.life <= 0) { scene.remove(s); damageSprites.splice(k, 1); }
    }
  }

  // =====================================================================
  // HUD
  // =====================================================================
  function setBar(id, v, isHealth) {
    var el = $(id); if (!el) return;
    el.style.width = Math.max(0, Math.min(100, v)) + "%";
    if (isHealth) el.style.background = v > 55 ? "linear-gradient(90deg,#2ecf7a,#9be15d)"
      : v > 25 ? "linear-gradient(90deg,#ff9d2d,#ffd24d)" : "linear-gradient(90deg,#ff2d2d,#ff6b6b)";
  }
  function updateHUD() {
    setBar("hpA", health.a, true); setBar("hpB", health.b, true);
    setBar("stA", stamina.a, false); setBar("stB", stamina.b, false);
    var remain = Math.max(0, ROUND_SIM_S - (simT - (curRound - 1) * ROUND_SIM_S)) * 5;
    $("timer").textContent = Math.floor(remain / 60) + ":" + ("0" + Math.floor(remain % 60)).slice(-2);
    $("roundLabel").textContent = "ROUND " + curRound;
    if (combo.count >= 2) { $("combo").textContent = "COMBO x" + combo.count; $("combo").style.opacity = 1; }
    else $("combo").style.opacity = 0;
  }
  function showComment(txt) { $("ticker").textContent = txt; }
  function showJudges() {
    var sc = data.timeline.result.scorecards || [];
    var done = sc.filter(function (c) { return c.round < curRound; });
    if (!done.length) { $("judges").textContent = ""; return; }
    $("judges").textContent = "JUGES : " + done.map(function (c) { return "R" + c.round + " " + c.a + "-" + c.b; }).join("  ·  ");
  }
  function overlay(html, ms) {
    var el = $("overlay"); el.innerHTML = html; el.style.opacity = 1;
    if (ms) setTimeout(function () { el.style.opacity = 0; }, ms);
  }
  function winnerScreen() {
    var res = data.timeline.result;
    var f = data.fighters[res.winner];
    var img = f && f.photo_datauri
      ? '<img src="' + f.photo_datauri + '" style="width:130px;height:130px;border-radius:50%;object-fit:cover;border:4px solid #ff9d2d">'
      : "🏆";
    overlay('<div style="text-align:center">' + img +
      '<div style="font-size:2.4rem;margin-top:10px">' + res.winner_name.toUpperCase() + "</div>" +
      '<div style="color:#ff9d2d;font-size:1.3rem">' + res.method + " · R" + res.round + " " + res.time + "</div>" +
      '<div style="font-size:1rem;color:#999;margin-top:8px">WINNER</div></div>');
  }

  // =====================================================================
  // PLAYBACK
  // =====================================================================
  function processEvent(e) {
    var atkRig = fighters[e.actor], dfn = e.actor === "a" ? "b" : "a", dfnRig = fighters[dfn];
    showComment(e.commentary || "");

    // gestion sol / debout
    var groundActs = { ground_control: 1, ground_strikes: 1, submission_attempt: 1 };
    if (groundActs[e.action]) { if (groundPair !== e.actor) setGrounded(atkRig, dfnRig); }
    else if (e.action === "takedown_attempt" && e.landed) { setGrounded(atkRig, dfnRig); }
    else if (groundPair && e.action !== "submission_win") { standUp(); }

    if (ANIMS[e.action]) playAnim(atkRig, e.action, e.action === "takedown_attempt" ? 0.8 : 0.55);
    else if (e.action === "knockdown") { knockdown(dfnRig, false); }
    else if (e.action === "ko") { knockdown(dfnRig, true); }
    else if (e.action === "submission_win") { /* fin — dominé reste au sol */ }

    if (e.landed && e.damage > 0) {
      health[dfn] = Math.max(0, health[dfn] - e.damage);
      var hit = dfnRig.root.position.clone(); hit.y = 1.3 * dfnRig.h;
      spawnSpark(hit, e.damage); spawnDamage(hit, e.damage);
      shake = Math.min(0.3, 0.02 + e.damage * 0.012);
      if (combo.actor === e.actor) combo.count++; else { combo.actor = e.actor; combo.count = 1; }
    } else if (!e.landed) { combo.count = 0; }

    stamina[e.actor] = Math.max(15, stamina[e.actor] - 1.6);

    // finish : slow-mo + zoom + overlay arcade
    if (e.action === "ko" || e.action === "submission_win") {
      timeScale = 0.25; slowmoUntil = performance.now() + 2000;
      health[dfn] = 0;
      overlay(e.action === "ko" ? "K.O. !" : "SOUMISSION !", 1800);
      finished = true;
      setTimeout(winnerScreen, 2300);
    }
    if (e.action === "decision") { finished = true; overlay("DÉCISION", 1500); setTimeout(winnerScreen, 1800); }
  }

  function tick() {
    requestAnimationFrame(tick);
    var dt = Math.min(0.05, clock.getDelta());
    if (playing && !betweenRounds) {
      if (slowmoUntil && performance.now() > slowmoUntil) { timeScale = 1; slowmoUntil = 0; }
      simT += dt * speed * timeScale * 2.2;   // 2.2x : rythme de visionnage agréable

      // changement de round ?
      var expectedRound = Math.min(Math.floor(simT / ROUND_SIM_S) + 1, 5);
      if (expectedRound > curRound && !finished) {
        curRound = expectedRound; betweenRounds = 1;
        overlay("ROUND " + curRound, 1400); showJudges();
        setTimeout(function () { betweenRounds = 0; }, 1500);
        standUp();
      }
      // événements dus
      while (evIdx < events.length) {
        var e = events[evIdx];
        var absT = (e.round - 1) * ROUND_SIM_S + e.t;
        if (absT <= simT) { processEvent(e); evIdx++; } else break;
      }
      if (evIdx >= events.length && !finished) { finished = true; setTimeout(winnerScreen, 800); }
    }

    // animations des rigs (fighters vide tant que loadFight n'a pas tourné)
    ["a", "b"].forEach(function (k) {
      var r = fighters[k];
      if (!r) return;
      if (r.anim) {
        r.anim.t += dt * speed * timeScale;
        var p = Math.min(1, r.anim.t / r.anim.dur);
        ANIMS[r.anim.action](p, r);
        if (p >= 1) { r.anim = null; if (!r.grounded && !r.koDown) { r.root.position.x = r.homeX; r.root.position.y = 0; guardPose(r, 1); } }
      } else if (!r.grounded && !r.koDown) {
        r.root.position.y = 0.02 * Math.sin(performance.now() * 0.004 + (k === "a" ? 0 : 2)); // idle bounce
        guardPose(r, 0.12);
      }
      // billboard tête face caméra
      if (r.head.userData.billboard) r.head.userData.billboard.lookAt(camera.position);
    });

    // caméra : travelling lent + shake + zoom slow-mo
    var t = performance.now() * 0.00012;
    var zoom = timeScale < 1 ? 6.6 : 8.6;
    camera.position.x += (Math.sin(t) * 1.6 - camera.position.x) * 0.02;
    camera.position.z += (zoom - camera.position.z) * 0.04;
    camera.position.y = 3.4 + (timeScale < 1 ? -0.7 : 0);
    if (shake > 0.002) {
      camera.position.x += (Math.random() - 0.5) * shake;
      camera.position.y += (Math.random() - 0.5) * shake;
      shake *= 0.88;
    }
    camera.lookAt(0, 1.05, 0);

    updateEffects(dt * speed);
    updateHUD();
    renderer.render(scene, camera);
  }

  // =====================================================================
  // API PUBLIQUE
  // =====================================================================
  window.FightEngine = {
    init: function (containerId) {
      container = $(containerId);
      var w = container.clientWidth || window.innerWidth || 900;
      var h = container.clientHeight || window.innerHeight || 700;
      renderer = new THREE.WebGLRenderer({ antialias: true });
      renderer.setSize(w, h);
      renderer.shadowMap.enabled = true;
      container.appendChild(renderer.domElement);
      clock = new THREE.Clock();
      buildScene();
      camera.aspect = w / h; camera.updateProjectionMatrix();
      window.addEventListener("resize", function () {
        var cw = container.clientWidth || window.innerWidth;
        var ch = container.clientHeight || window.innerHeight;
        camera.aspect = cw / ch;
        camera.updateProjectionMatrix();
        renderer.setSize(cw, ch);
      });
      tick();
    },
    loadFight: function (json) {
      data = json;
      events = (json.timeline.events || []).slice().sort(function (x, y) {
        return (x.round - y.round) || (x.t - y.t);
      });
      // reset complet
      ["a", "b"].forEach(function (k) { if (fighters[k]) scene.remove(fighters[k].root); });
      fighters.a = buildFighter(json.fighters.a, "a", -1);
      fighters.b = buildFighter(json.fighters.b, "b", 1);
      $("nameA").textContent = json.timeline.fighter_a.toUpperCase();
      $("nameB").textContent = json.timeline.fighter_b.toUpperCase();
      evIdx = 0; simT = 0; curRound = 1; finished = false; betweenRounds = 0;
      health = { a: 100, b: 100 }; stamina = { a: 100, b: 100 };
      combo = { actor: null, count: 0 }; timeScale = 1; slowmoUntil = 0; groundPair = null;
      $("overlay").style.opacity = 0; $("judges").textContent = "";
      showComment("🎬 Prêt — appuyez sur PLAY");
      updateHUD();
    },
    play: function () { playing = true; },
    pause: function () { playing = false; },
    restart: function () { if (data) { this.loadFight(data); this.play(); } },
    setSpeed: function (x) { speed = x; },
  };
})();
