(function () {
  'use strict';
  var stage = document.getElementById('stage');
  var track = document.getElementById('track');
  var starsEl = document.getElementById('stars');
  var orbSun = document.getElementById('orbSun');
  var orbMoon = document.getElementById('orbMoon');
  var floorEls = Array.prototype.slice.call(document.querySelectorAll('#floors li'));
  var copies = Array.prototype.slice.call(document.querySelectorAll('.copy'));
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var root = document.documentElement;

  var renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  } catch (e) {
    var m = document.createElement('div');
    m.className = 'nogl';
    m.textContent = 'Browser kamu belum mendukung WebGL, jadi cerita 3D tidak bisa tampil.';
    stage.insertBefore(m, stage.firstChild);
    return;
  }
  var small = Math.min(window.innerWidth, window.innerHeight) < 600;
  var DPR = Math.min(window.devicePixelRatio || 1, small ? 1.75 : 2);
  renderer.setPixelRatio(DPR);
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  stage.insertBefore(renderer.domElement, document.querySelector('.scrim'));

  var scene = new THREE.Scene();
  scene.fog = new THREE.Fog(0xffffff, 90, 112);
  var camera = new THREE.OrthographicCamera(-10, 10, 10, -10, 0.1, 400);
  var hemi = new THREE.HemisphereLight(0xffffff, 0xcfd6dc, 0.6);
  scene.add(hemi);
  var sun = new THREE.DirectionalLight(0xffffff, 0.8);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.bias = -0.0006;
  sun.shadow.normalBias = 0.03;
  scene.add(sun);
  var moon = new THREE.DirectionalLight(0x8fb4ff, 0);
  moon.position.set(-10, 25, 30);
  scene.add(moon);

  /* ---------- small helpers ---------- */
  function clamp01(x) { return Math.max(0, Math.min(1, x)); }
  function smooth(a, b, x) { var t = clamp01((x - a) / (b - a)); return t * t * (3 - 2 * t); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function outCubic(t) { t = clamp01(t); return 1 - Math.pow(1 - t, 3); }
  function backOut(t) { var c = 1.70158, u = t - 1; return 1 + (c + 1) * u * u * u + c * u * u; }
  /* springy pop: 0 -> overshoot ~1.2 -> settles on 1 */
  function elastic(t) {
    if (t <= 0) return 0;
    if (t >= 1) return 1;
    return 1 - Math.exp(-4.2 * t) * Math.cos(8 * t);
  }
  function pop(a, b, x) { return elastic((x - a) / (b - a)); }
  /* squash and stretch: taller means thinner, so the volume feels constant */
  function setPop(g, e, s) {
    if (e <= 0.002) { g.scale.setScalar(0.001); return; }
    var sxz = 1 - 0.42 * (e - 1);
    sxz = Math.max(0.2, Math.min(1.6, sxz));
    g.scale.set(sxz * s, e * s, sxz * s);
  }
  var V3 = function (x, y, z) { return new THREE.Vector3(x, y, z); };

  function roundedBox(w, h, d, r, s) {
    s = s || 4;
    var g = new THREE.BoxGeometry(w, h, d, s, s, s);
    var p = g.attributes.position;
    var v = new THREE.Vector3(), c = new THREE.Vector3(), dir = new THREE.Vector3();
    var hx = w / 2 - r, hy = h / 2 - r, hz = d / 2 - r;
    for (var i = 0; i < p.count; i++) {
      v.fromBufferAttribute(p, i);
      c.set(Math.max(-hx, Math.min(hx, v.x)), Math.max(-hy, Math.min(hy, v.y)), Math.max(-hz, Math.min(hz, v.z)));
      dir.copy(v).sub(c);
      if (dir.lengthSq() > 0) dir.normalize();
      v.copy(c).addScaledVector(dir, r);
      p.setXYZ(i, v.x, v.y, v.z);
    }
    g.computeVertexNormals();
    return g;
  }
  var gcache = {};
  function bx(w, h, d) { var k = w + '|' + h + '|' + d; return gcache[k] || (gcache[k] = new THREE.BoxGeometry(w, h, d)); }
  function mat(color, rough) { return new THREE.MeshStandardMaterial({ color: color, roughness: rough == null ? 0.7 : rough, metalness: 0 }); }
  function mesh(geo, m, x, y, z, shadows) {
    var o = new THREE.Mesh(geo, m);
    o.position.set(x || 0, y || 0, z || 0);
    if (shadows !== false) { o.castShadow = true; o.receiveShadow = true; }
    return o;
  }
  function ball(r, color, x, y, z, rough) { return mesh(new THREE.SphereGeometry(r, 18, 12), mat(color, rough == null ? 0.6 : rough), x, y, z); }

  /* surfaces that turn from grey to pastel as the building turns green, top first */
  var tints = [];
  function tinted(geo, grey, green, x, y, z, rough) {
    var m = mat(grey, rough);
    var o = mesh(geo, m, x, y, z);
    tints.push({ m: m, a: new THREE.Color(grey), b: new THREE.Color(green), y: y });
    return o;
  }

  var world = new THREE.Group();
  scene.add(world);

  var seedN = 11;
  function rnd() { seedN = (seedN * 16807) % 2147483647; return seedN / 2147483647; }

  /* ---------- windows: blue glass by day, a few warm squares at night ---------- */
  var winDay = new THREE.Color(0x8fb3cc), winNight = new THREE.Color(0x1f2c4a);
  function newWin() { return new THREE.MeshStandardMaterial({ color: 0x8fb3cc, roughness: 0.22, metalness: 0.1, emissive: 0x4a7aa0, emissiveIntensity: 0.16 }); }
  var winMats = [{ m: newWin(), th: 9 }, { m: newWin(), th: 0.25 }, { m: newWin(), th: 0.5 }, { m: newWin(), th: 0.75 }];
  function pickWin() { var r = rnd(); return (r < 0.5 ? winMats[0] : r < 0.68 ? winMats[1] : r < 0.86 ? winMats[2] : winMats[3]).m; }
  var frameMat = mat(0xf6f1e6, 0.6);
  var curtCols = [0xf4a7b9, 0xffe0a8, 0xb7e4c7, 0xfdedc9, 0xcdb4ee];
  var curtMats = {};
  function curtMat(c) { return curtMats[c] || (curtMats[c] = mat(c, 0.9)); }
  function addWin(parent, x, y, z, w, h, rotY) {
    var g = new THREE.Group();
    g.position.set(x, y, z);
    g.rotation.y = rotY || 0;
    g.add(mesh(bx(w + 0.16, h + 0.16, 0.05), frameMat, 0, 0, 0, false));
    g.add(mesh(bx(w, h, 0.06), pickWin(), 0, 0, 0.012, false));
    if (rnd() < 0.3) {
      var cc = curtCols[Math.floor(rnd() * curtCols.length)], sd = rnd() < 0.5 ? -1 : 1;
      g.add(mesh(bx(w * 0.5, h * 0.96, 0.03), curtMat(cc), sd * w * 0.25, 0, 0.05, false));
    }
    parent.add(g);
  }
  function facade(parent, w, h, d) {
    var rows = Math.max(1, Math.floor((h - 1.0) / 2.5));
    var cols = Math.max(1, Math.floor(w / 2.3)), colsS = Math.max(1, Math.floor(d / 2.3));
    for (var r = 0; r < rows; r++) {
      var y = 1.6 + r * 2.5;
      for (var c = 0; c < cols; c++) addWin(parent, (c - (cols - 1) / 2) * (w / cols), y, d / 2 + 0.03, 1.0, 1.1, 0);
      for (var s = 0; s < colsS; s++) addWin(parent, w / 2 + 0.03, y, (s - (colsS - 1) / 2) * (d / colsS), 1.0, 1.1, Math.PI / 2);
    }
  }
  function tower(x, z, w, h, d, grey, green) {
    var g = new THREE.Group();
    g.position.set(x, 0, z);
    g.add(tinted(roundedBox(w, h, d, 0.25, 4), grey, green, 0, h / 2, 0, 0.85));
    /* roof deck: sand-coloured slab with a low parapet all round, so a roof always reads as a roof */
    var pw = w + 0.3, pd = d + 0.3;
    g.add(tinted(roundedBox(pw, 0.22, pd, 0.08, 3), 0x9aa0a7, 0xd9cbb0, 0, h + 0.11, 0, 0.8));
    [-1, 1].forEach(function (s) {
      g.add(tinted(roundedBox(pw, 0.46, 0.18, 0.05, 2), 0xaeb3b9, 0xfdedc9, 0, h + 0.45, s * (pd / 2 - 0.09), 0.8));
      g.add(tinted(roundedBox(0.18, 0.46, pd - 0.36, 0.05, 2), 0xaeb3b9, 0xfdedc9, s * (pw / 2 - 0.09), h + 0.45, 0, 0.8));
    });
    facade(g, w, h, d);
    world.add(g);
    return g;
  }

  /* ---------- sparkle bursts (drawn later by one Points object, fully driven by scroll progress) ---------- */
  var emitters = [];
  function addBurst(x, y, z, t0, dur, n, rad, size, hue) {
    var d = [];
    for (var i = 0; i < n; i++) {
      var a = rnd() * Math.PI * 2, u = rnd() * 2 - 1, r = Math.sqrt(1 - u * u);
      d.push([Math.cos(a) * r, Math.abs(u) * 0.8 + 0.25, Math.sin(a) * r, 0.55 + rnd() * 0.6, rnd()]);
    }
    emitters.push({ x: x, y: y, z: z, t0: t0, dur: dur, n: n, rad: rad, size: size, d: d, hue: hue || 0 });
  }

  /* ---------- plants, pots, beds ---------- */
  var greens = [0x2fbf5c, 0x45cf72, 0x23a84e, 0x62d98a, 0x2fbf5c, 0x39c466];
  var potColors = [0xffb35c, 0xf4a7b9, 0x95d5b2, 0xfdedc9, 0x8fd0f2];
  var swayers = [];
  var flowerCols = [0xf4a7b9, 0xffd34d, 0xffffff, 0xc9a7ee, 0xff8a6b];
  function dot(r, c, x, y, z) { return ball(r, c, x, y, z, 0.55); }
  /* Plants have their own random stream, so adding variety here never moves anything else in the scene.
     Every plant rolls its own green family, height, leaf count, lean, spin and size: no two are the same. */
  var pSeed = 90210;
  function pr() { pSeed = (pSeed * 16807) % 2147483647; return pSeed / 2147483647; }
  function pri(a, b) { return a + pr() * (b - a); }
  function pick(a) { return a[Math.floor(pr() * a.length)]; }
  var gmCache = {};
  function gm(hex, rough) { var k = hex + '/' + (rough == null ? 0.6 : rough); return gmCache[k] || (gmCache[k] = mat(hex, rough == null ? 0.6 : rough)); }
  var families = [0x2fbf5c, 0x259a4a, 0x6fc23f, 0x2aa88a, 0x5fae5a, 0x8fcf7a, 0x1f8a4a, 0x4cb86a];
  function tone(hex, step) { var c = new THREE.Color(hex); c.offsetHSL(0, 0, (step - 2) * 0.035); return c.getHex(); }
  var uS = new THREE.SphereGeometry(0.5, 12, 8);
  function blob(m, sx, sy, sz, x, y, z) { var b = mesh(uS, m, x, y, z); b.scale.set(sx, sy, sz); return b; }
  function cyl(rt, rb, h, m, x, y, z) { return mesh(new THREE.CylinderGeometry(rt, rb, h, 7), m, x, y, z); }
  var fruitCols = [0xff6b4a, 0xe8452f, 0xffb52e, 0xffd34d];
  var succCols = [0x7fbfa5, 0x8fcfb0, 0x9cc9a0, 0xa9c9d8, 0xc3a6d6];
  var cactusCols = [0x4fae6b, 0x5fb87a, 0x3f9a63];

  function makePlant(n, fruit, type) {
    var g = new THREE.Group(), r = new THREE.Group(), leaves = [], tom = [], i;
    g.add(r);
    type = type || 'rosette';
    var fam = pick(families);
    function lc() { return gm(tone(fam, Math.floor(pr() * 5)), 0.55); }
    var stem = gm(tone(fam, -1), 0.6);
    function sway(m, base) { leaves.push({ m: m, base: base, ph: pr() * 6.28 }); }

    if (type === 'grass') {
      var nb = 7 + Math.floor(pr() * 6);
      for (i = 0; i < nb; i++) {
        var bp = new THREE.Group(), ang = pr() * 6.28, rad = pri(0.02, 0.2), ht = pri(0.55, 1.25), tilt = pri(0.05, 0.5);
        bp.position.set(Math.cos(ang) * rad, 0, Math.sin(ang) * rad);
        bp.rotation.set(0, ang, tilt);
        var bl = mesh(new THREE.ConeGeometry(pri(0.04, 0.075), ht, 5), lc(), 0, ht / 2, 0);
        bl.scale.z = 0.4;
        bp.add(bl);
        r.add(bp);
        sway(bp, tilt);
      }
    } else if (type === 'bush') {
      r.add(cyl(0.05, 0.07, 0.3, stem, 0, 0.15, 0));
      var cl = [[0, pri(0.55, 0.7), 0, pri(0.34, 0.44)]], nc = 2 + Math.floor(pr() * 3);
      for (i = 0; i < nc; i++) { var ca = pr() * 6.28; cl.push([Math.cos(ca) * pri(0.22, 0.34), pri(0.38, 0.55), Math.sin(ca) * pri(0.22, 0.34), pri(0.2, 0.3)]); }
      if (pr() < 0.6) cl.push([pri(-0.05, 0.05), pri(0.88, 1.0), pri(-0.05, 0.05), pri(0.17, 0.24)]);
      cl.forEach(function (s) { r.add(blob(lc(), s[3] * 2, s[3] * 2 * pri(0.85, 1.05), s[3] * 2, s[0], s[1], s[2])); });
      if (pr() < 0.65) {
        var fcol = pick(flowerCols), fcol2 = pick(flowerCols), nf = 4 + Math.floor(pr() * 6);
        for (i = 0; i < nf; i++) {
          var s0 = cl[Math.floor(pr() * cl.length)], a2 = pr() * 6.28, el = pri(0.2, 1.0), cr = Math.sqrt(1 - el * el);
          r.add(dot(pri(0.04, 0.065), pr() < 0.8 ? fcol : fcol2, s0[0] + Math.cos(a2) * cr * s0[3], s0[1] + el * s0[3], s0[2] + Math.sin(a2) * cr * s0[3]));
        }
      }
    } else if (type === 'cactus') {
      var cc = gm(pick(cactusCols), 0.6), kind = pick(['column', 'column', 'barrel', 'paddle']);
      if (kind === 'column') {
        var ch = pri(0.7, 1.0), cw = pri(0.15, 0.2);
        r.add(cyl(cw, cw + 0.02, ch, cc, 0, ch / 2, 0));
        r.add(blob(cc, cw * 2, cw * 2, cw * 2, 0, ch, 0));
        [-1, 1].forEach(function (sd) {
          if (pr() < 0.35) return;
          var ay = pri(0.3, 0.55) * ch, up = pri(0.18, 0.38), aw = pri(0.07, 0.09);
          var arm = cyl(aw, aw, 0.24, cc, sd * (cw + 0.1), ay, 0);
          arm.rotation.z = Math.PI / 2;
          r.add(arm);
          r.add(cyl(aw, aw, up, cc, sd * (cw + 0.21), ay + up / 2, 0));
          r.add(blob(cc, aw * 2, aw * 2, aw * 2, sd * (cw + 0.21), ay + up, 0));
        });
        if (pr() < 0.6) r.add(dot(0.075, pick(flowerCols), pri(-0.05, 0.05), ch + cw * 0.9, 0));
      } else if (kind === 'barrel') {
        var bw = pri(0.38, 0.5);
        r.add(blob(cc, bw * 2, bw * 1.7, bw * 2, 0, bw * 0.8, 0));
        for (i = 0; i < 6; i++) { var ra = i / 6 * 6.28; r.add(blob(gm(0x9ad5ae, 0.6), 0.04, bw * 1.5, 0.04, Math.cos(ra) * bw * 0.94, bw * 0.8, Math.sin(ra) * bw * 0.94)); }
        r.add(dot(0.09, pick(flowerCols), 0, bw * 1.58, 0));
      } else {
        r.add(blob(cc, 0.5, 0.62, 0.14, 0, 0.3, 0));
        var p2 = blob(cc, 0.36, 0.44, 0.12, pri(-0.18, -0.1), 0.68, 0); p2.rotation.z = 0.35; r.add(p2);
        var p3 = blob(cc, 0.32, 0.4, 0.12, pri(0.1, 0.18), 0.74, 0); p3.rotation.z = -0.4; r.add(p3);
        r.add(dot(0.06, 0xff8fa8, -0.14, 0.9, 0.04));
        r.add(dot(0.06, 0xff8fa8, 0.16, 0.95, 0.04));
      }
    } else if (type === 'flower') {
      var ns = 3 + Math.floor(pr() * 4), head = pick(['daisy', 'daisy', 'tulip', 'pom']), main = pick(flowerCols), acc = pick(flowerCols);
      for (i = 0; i < ns; i++) {
        var sp = new THREE.Group(), sa = pr() * 6.28, sh = pri(0.55, 1.15), st = pri(0.06, 0.34);
        sp.position.set(Math.cos(sa) * 0.08, 0, Math.sin(sa) * 0.08);
        sp.rotation.set(0, sa, st);
        sp.add(cyl(0.03, 0.04, sh, stem, 0, sh / 2, 0));
        var fc = pr() < 0.75 ? main : acc, fm = gm(fc, 0.5);
        if (head === 'daisy') {
          var np2 = 7 + Math.floor(pr() * 3);
          for (var q = 0; q < np2; q++) {
            var qa = q / np2 * 6.28, pt = blob(fm, 0.15, 0.04, 0.075, Math.cos(qa) * 0.11, sh + 0.02, Math.sin(qa) * 0.11);
            pt.rotation.y = -qa;
            sp.add(pt);
          }
          sp.add(dot(0.06, fc === 0xffd34d ? 0xe88a1a : 0xffb52e, 0, sh + 0.04, 0));
        } else if (head === 'tulip') {
          sp.add(blob(fm, 0.2, 0.3, 0.2, 0, sh + 0.08, 0));
        } else {
          sp.add(blob(fm, 0.27, 0.27, 0.27, 0, sh + 0.06, 0));
        }
        r.add(sp);
        sway(sp, st);
      }
      var nl = 4 + Math.floor(pr() * 3);
      for (i = 0; i < nl; i++) {
        var lp = new THREE.Group();
        lp.rotation.y = pr() * 6.28;
        var lm = blob(lc(), pri(0.4, 0.6), 0.07, pri(0.12, 0.2), 0.24, pri(0.08, 0.16), 0);
        lm.rotation.z = pri(0.2, 0.5);
        lp.add(lm);
        r.add(lp);
      }
    } else if (type === 'trail') {
      var nk = 3 + Math.floor(pr() * 2);
      for (i = 0; i < nk; i++) { var ba = pr() * 6.28, br = pri(0.12, 0.19); r.add(blob(lc(), br * 2, br * 1.7, br * 2, Math.cos(ba) * 0.15, 0.12, Math.sin(ba) * 0.15)); }
      var nsd = 4 + Math.floor(pr() * 3), flowering = pr() < 0.35, tcol = pick(flowerCols);
      for (i = 0; i < nsd; i++) {
        var ta = pr() * 6.28, len = 3 + Math.floor(pr() * 4), bend = pri(0.01, 0.05);
        for (var t = 0; t < len; t++) {
          var lr = pri(0.06, 0.1) - t * 0.008;
          r.add(blob(lc(), lr * 2.2, lr * 1.5, lr * 2, Math.cos(ta) * (0.26 + t * bend), -0.04 - t * pri(0.14, 0.19), Math.sin(ta) * (0.26 + t * bend)));
        }
        if (flowering && i % 2 === 0) r.add(dot(0.05, tcol, Math.cos(ta) * (0.26 + len * bend), -0.1 - len * 0.16, Math.sin(ta) * (0.26 + len * bend)));
      }
    } else if (type === 'fern') {
      var nf2 = 5 + Math.floor(pr() * 3);
      for (i = 0; i < nf2; i++) {
        var fg = new THREE.Group(), fa = i / nf2 * 6.28 + pri(-0.3, 0.3), ft = pri(0.45, 1.05), fl = pri(0.7, 1.05), cm = lc();
        fg.rotation.set(0, fa, ft);
        for (var s2 = 0; s2 < 4; s2++) {
          var tt = s2 / 3, fy = 0.08 + tt * fl, fx = -tt * tt * 0.28, lw = 0.38 * (1 - tt * 0.6);
          [-1, 1].forEach(function (sd) {
            var lf = blob(cm, lw, 0.07, 0.16 * (1 - tt * 0.4), fx, fy, sd * lw * 0.42);
            lf.rotation.y = sd * -0.55;
            fg.add(lf);
          });
        }
        fg.add(blob(cm, 0.12, 0.05, 0.07, -0.3, 0.08 + fl + 0.02, 0));
        r.add(fg);
        sway(fg, ft);
      }
    } else if (type === 'succulent') {
      var sc = gm(pick(succCols), 0.5), sc2 = gm(tone(0x8fcfb0, Math.floor(pr() * 5)), 0.5);
      var no = 6 + Math.floor(pr() * 3);
      for (i = 0; i < no; i++) {
        var sg = new THREE.Group(), sa2 = i / no * 6.28 + pri(-0.2, 0.2);
        sg.rotation.y = sa2;
        var sl = blob(sc, pri(0.36, 0.46), 0.11, 0.2, 0.2, 0.12, 0);
        sl.rotation.z = pri(0.35, 0.6);
        sg.add(sl);
        r.add(sg);
      }
      for (i = 0; i < 5; i++) {
        var sg2 = new THREE.Group();
        sg2.rotation.y = i / 5 * 6.28 + 0.6;
        var sl2 = blob(sc2, 0.28, 0.1, 0.16, 0.12, 0.24, 0);
        sl2.rotation.z = pri(0.8, 1.1);
        sg2.add(sl2);
        r.add(sg2);
      }
      r.add(blob(sc2, 0.16, 0.16, 0.16, 0, 0.26, 0));
      if (pr() < 0.35) {
        var fsh = pri(0.45, 0.7);
        r.add(cyl(0.015, 0.02, fsh, stem, 0.04, 0.3 + fsh / 2, 0));
        var fcc = pick([0xff8fa8, 0xffb52e, 0xff8a6b]);
        for (i = 0; i < 3; i++) r.add(dot(0.04, fcc, 0.04 + (i - 1) * 0.05, 0.3 + fsh - i * 0.04, 0));
      }
    } else if (type === 'leafy') {
      var nst = 5 + Math.floor(pr() * 4), lcol = lc();
      for (i = 0; i < nst; i++) {
        var lg = new THREE.Group(), la = i / nst * 6.28 + pri(-0.35, 0.35), lt = pri(0.12, 0.62), lh = pri(0.45, 1.0);
        lg.rotation.set(0, la, lt);
        lg.add(cyl(0.02, 0.03, lh, stem, 0, lh / 2, 0));
        var ld = pri(0.34, 0.5), disc = blob(i % 2 ? lcol : lc(), ld, 0.06, ld * pri(0.85, 1), 0, lh + 0.02, 0);
        disc.rotation.set(pri(-0.2, 0.2), 0, pri(-0.25, 0.25));
        lg.add(disc);
        if (pr() < 0.5) { var ld2 = ld * 0.7, d2 = blob(lc(), ld2, 0.05, ld2 * 0.9, 0.1, lh * 0.55, 0); d2.rotation.z = -0.5; lg.add(d2); }
        r.add(lg);
        sway(lg, lt);
      }
    } else {
      /* rosette: a leafy herb on one stem, tiers of leaves, sometimes fruit */
      var h = pri(0.75, 1.15);
      r.add(cyl(0.06, 0.09, h, stem, 0, h / 2, 0));
      var cnt = Math.max(4, (n || 6) + Math.floor(pri(-1.5, 3))), tiers = cnt > 6 ? 3 : 2;
      for (i = 0; i < cnt; i++) {
        var tier = i % tiers, pv = new THREE.Group();
        pv.position.y = h * pri(0.4, 0.5) + tier * pri(0.28, 0.4);
        pv.rotation.y = i * 2.4 + pri(-0.3, 0.3);
        var ll = pri(0.8, 1.1) - tier * 0.14, lw2 = pri(0.4, 0.62) - tier * 0.07;
        var leaf = blob(lc(), ll, pri(0.12, 0.24), lw2, ll / 2, 0, 0);
        leaf.rotation.z = pri(0.25, 0.7) + tier * 0.15;
        pv.add(leaf);
        r.add(pv);
        sway(leaf, leaf.rotation.z);
      }
      if (fruit) {
        var fcl = pick(fruitCols), nfr = 2 + Math.floor(pr() * 2);
        for (i = 0; i < nfr; i++) {
          var fa2 = pr() * 6.28, fr = pri(0.28, 0.4), b = ball(pri(0.13, 0.19), fcl, Math.cos(fa2) * fr, h * pri(0.5, 0.8), Math.sin(fa2) * fr, 0.35);
          b.scale.setScalar(0.001);
          r.add(b);
          tom.push(b);
        }
      }
    }
    /* each plant stands a little crooked and faces its own way */
    r.rotation.set(pri(-0.06, 0.06), pr() * 6.28, pri(-0.06, 0.06));
    g.scale.setScalar(0.001);
    var pl = { g: g, tom: tom, leaves: leaves, ph: pr() * 6.28, grown: 0, size: 1, jit: pri(0.88, 1.14) };
    swayers.push(pl);
    return pl;
  }
  function growPlant(pl, k) {
    var e = k <= 0 ? 0 : backOut(clamp01(k));
    pl.grown = clamp01(k);
    pl.g.scale.setScalar(Math.max(0.001, pl.size * (pl.jit || 1) * e));
  }

  function makePot(color) {
    var g = new THREE.Group();
    g.add(mesh(new THREE.CylinderGeometry(0.42, 0.3, 0.55, 16), mat(color, 0.55), 0, 0.275, 0));
    var rim = mesh(new THREE.TorusGeometry(0.42, 0.05, 8, 16), mat(color, 0.55), 0, 0.55, 0);
    rim.rotation.x = Math.PI / 2;
    g.add(rim);
    g.add(mesh(new THREE.CylinderGeometry(0.4, 0.4, 0.05, 16), mat(0x6b4226, 0.9), 0, 0.54, 0));
    return g;
  }
  var mascot = { eyes: [], mouth: null };
  function makeBed(w, d, n, face, fruit, h, pn, ptype) {
    h = h || 0.7;
    var g = new THREE.Group();
    g.add(mesh(roundedBox(w, h, d, Math.min(0.16, h * 0.4), 4), mat(0xc98a4b, 0.7), 0, h / 2, 0));
    g.add(mesh(roundedBox(w - 0.4, 0.1, d - 0.4, 0.04, 3), mat(0x6b4226, 0.9), 0, h + 0.02, 0));
    var plants = [];
    for (var i = 0; i < n; i++) {
      var p = makePlant(pn || 6, fruit, ptype);
      p.size = pn ? 0.62 : [1, 1.18, 0.92][i % 3];
      p.g.position.set(n === 1 ? 0 : (i - (n - 1) / 2) * ((w - 0.9) / (n - 1)), h + 0.04, 0);
      g.add(p.g);
      plants.push(p);
    }
    if (face) {
      var zf = d / 2 + 0.01;
      [-1, 1].forEach(function (s) {
        var e = ball(0.09, 0x17301f, s * 0.5, 0.38, zf, 0.3);
        e.scale.set(1, 1.25, 0.5);
        g.add(e);
        mascot.eyes.push(e);
        g.add(mesh(new THREE.CircleGeometry(0.12, 16), new THREE.MeshBasicMaterial({ color: 0xff8fa8, transparent: true, opacity: 0.85 }), s * 0.9, 0.24, zf, false));
      });
      var sm = mesh(new THREE.TorusGeometry(0.09, 0.025, 8, 16, Math.PI), mat(0x17301f, 0.4), 0, 0.33, zf, false);
      sm.rotation.z = Math.PI;
      g.add(sm);
      mascot.mouth = sm;
    }
    return { g: g, plants: plants };
  }

  /* a pot hung on the railing by three cords, with a trailing vine */
  function makeHang(color) {
    var g = new THREE.Group();
    var bowl = mesh(new THREE.SphereGeometry(0.3, 14, 10, 0, Math.PI * 2, Math.PI / 2, Math.PI / 2), mat(color, 0.55), 0, 0, 0);
    bowl.material.side = THREE.DoubleSide;
    g.add(bowl);
    var rim = mesh(new THREE.TorusGeometry(0.3, 0.03, 6, 16), mat(color, 0.55), 0, 0, 0);
    rim.rotation.x = Math.PI / 2;
    g.add(rim);
    g.add(mesh(new THREE.CylinderGeometry(0.28, 0.28, 0.03, 14), mat(0x6b4226, 0.9), 0, -0.01, 0));
    var apex = V3(0, 0.72, -0.34), up = V3(0, 1, 0);
    [0, 2.09, 4.19].forEach(function (a) {
      var s = V3(Math.cos(a) * 0.3, 0, Math.sin(a) * 0.3), dir = apex.clone().sub(s), len = dir.length();
      var c = mesh(new THREE.CylinderGeometry(0.012, 0.012, len, 4), railMat, 0, 0, 0, false);
      c.position.copy(s).addScaledVector(dir, 0.5);
      c.quaternion.setFromUnitVectors(up, dir.normalize());
      g.add(c);
    });
    var pl = makePlant(0, false, 'trail');
    pl.size = 1;
    pl.g.position.y = 0.02;
    g.add(pl.g);
    return { g: g, pl: pl };
  }

  /* ---------- Petak, the EcoPatch mascot: a planter box with a face, sprouts for hair and a stitched patch on its tummy ---------- */
  var petaks = [];
  var pm = {
    body: mat(0xff9d2e, 0.6), foot: mat(0xe8841a, 0.65), rim: mat(0xffb85c, 0.55), soil: mat(0x5b3a24, 0.95),
    ink: mat(0x17301f, 0.3), cream: mat(0xfdedc9, 0.7), creamD: mat(0xe6cf95, 0.7), leaf: mat(0x2fbf5c, 0.5)
  };
  function decal(c, op) {
    return new THREE.MeshStandardMaterial({ color: c, roughness: 0.6, metalness: 0, transparent: op != null, opacity: op == null ? 1 : op, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
  }
  var pmCheek = decal(0xff8fa8, 0.9), pmTongue = decal(0xff8fa8), pmInk = decal(0x17301f), pmWhite = new THREE.MeshBasicMaterial({ color: 0xffffff });
  var zMat = (function () {
    var c = document.createElement('canvas');
    c.width = c.height = 64;
    var x = c.getContext('2d');
    x.font = '800 54px "Baloo 2", "Trebuchet MS", sans-serif';
    x.fillStyle = '#29b6d8';
    x.textAlign = 'center';
    x.textBaseline = 'middle';
    x.fillText('z', 32, 36);
    return new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(c), transparent: true, depthWrite: false, depthTest: false, fog: false });
  })();
  var MOODS = {
    happy: { eye: 'open', k: 1, mouth: 'smile' },
    wow: { eye: 'open', k: 1.25, mouth: 'o' },
    cheer: { eye: 'happy', k: 1, mouth: 'grin' },
    proud: { eye: 'open', k: 1.2, mouth: 'grin' },
    sleep: { eye: 'sleep', k: 1, mouth: 'tiny' }
  };
  function halfDisc(r, m) { return new THREE.Mesh(new THREE.CircleGeometry(r, 18, Math.PI, Math.PI), m); }
  function makePetak(o) {
    var w = o.w, h = o.h, d = o.d, fh = o.fh == null ? 0.14 : o.fh, er = o.er || w * 0.047;
    var rimH = h * 0.2, rr = Math.min(w, d) * 0.16;
    var g = new THREE.Group();
    var body = new THREE.Group();
    g.add(body);
    var pt = { g: g, body: body, main: !!o.main, plants: [], eyes: [], mouths: {}, arms: null, zs: null, mood: '', ph: rnd() * 6.28, er: er, gx: 0, gy: 0, sleep: 0, aL: 0.45, aR: 0.45, eyeK: 1, eyeY: fh + h * 0.6, d: d, h: h };

    /* feet, box, rim, soil */
    [-1, 1].forEach(function (s) { body.add(mesh(roundedBox(w * 0.22, fh + 0.08, d * 0.36, 0.05, 3), pm.foot, s * w * 0.24, (fh + 0.08) / 2, 0)); });
    body.add(mesh(roundedBox(w, h, d, rr, 4), pm.body, 0, fh + h / 2, 0));
    body.add(mesh(roundedBox(w + 0.18, rimH, d + 0.18, Math.min(rr + 0.05, rimH * 0.45), 4), pm.rim, 0, fh + h + rimH / 2 - 0.05, 0));
    var topY = fh + h + rimH - 0.05;
    body.add(mesh(roundedBox(w - 0.14, 0.1, d - 0.14, 0.04, 3), pm.soil, 0, topY - 0.02, 0));

    /* face */
    var zf = d / 2 + 0.006, ex = w * 0.185;
    [-1, 1].forEach(function (s) {
      var slot = new THREE.Group();
      slot.position.set(s * ex, pt.eyeY, zf + er * 0.2);
      var open = new THREE.Group();
      var ob = mesh(new THREE.SphereGeometry(er, 16, 12), pm.ink, 0, 0, 0, false);
      ob.scale.set(1, 1.3, 0.5);
      var hl = new THREE.Mesh(new THREE.SphereGeometry(er * 0.4, 8, 6), pmWhite);
      hl.position.set(er * 0.38, er * 0.55, er * 0.42);
      var hl2 = new THREE.Mesh(new THREE.SphereGeometry(er * 0.2, 6, 5), pmWhite);
      hl2.position.set(-er * 0.34, -er * 0.4, er * 0.4);
      open.add(ob, hl, hl2);
      var happy = new THREE.Mesh(new THREE.TorusGeometry(er * 1.1, er * 0.3, 6, 14, Math.PI), pmInk);
      happy.position.y = -er * 0.55;
      var sl = new THREE.Mesh(new THREE.TorusGeometry(er * 1.1, er * 0.3, 6, 14, Math.PI), pmInk);
      sl.rotation.z = Math.PI;
      sl.position.y = er * 0.45;
      slot.add(open, happy, sl);
      body.add(slot);
      pt.eyes.push({ slot: slot, open: open, happy: happy, sleep: sl, bx: slot.position.x, by: slot.position.y });
      var c = new THREE.Mesh(new THREE.CircleGeometry(w * 0.055, 16), pmCheek);
      c.scale.set(1.35, 0.85, 1);
      c.position.set(s * w * 0.285, fh + h * 0.46, zf);
      body.add(c);
    });
    var mY = fh + h * 0.49, mr = w * 0.07;
    function mouthGroup(name) {
      var m = new THREE.Group();
      m.position.set(0, mY, zf);
      body.add(m);
      pt.mouths[name] = m;
      return m;
    }
    var mSmile = mouthGroup('smile');
    var hd = halfDisc(mr, pmInk); hd.scale.y = 1.1; mSmile.add(hd);
    var tg = new THREE.Mesh(new THREE.CircleGeometry(mr * 0.5, 12), pmTongue); tg.scale.set(1.1, 0.6, 1); tg.position.set(0, -mr * 0.78, 0.004); mSmile.add(tg);
    var mGrin = mouthGroup('grin');
    var hg = halfDisc(mr * 1.6, pmInk); hg.scale.set(1, 0.95, 1); mGrin.add(hg);
    var tg2 = new THREE.Mesh(new THREE.CircleGeometry(mr * 0.8, 14), pmTongue); tg2.scale.set(1.2, 0.6, 1); tg2.position.set(0, -mr * 1.2, 0.004); mGrin.add(tg2);
    var mO = mouthGroup('o');
    var oc = new THREE.Mesh(new THREE.CircleGeometry(mr * 0.62, 16), pmInk); oc.scale.set(1, 1.3, 1); oc.position.y = -mr * 0.6; mO.add(oc);
    var mTiny = mouthGroup('tiny');
    var tt = new THREE.Mesh(new THREE.TorusGeometry(mr * 0.6, mr * 0.15, 6, 12, Math.PI), pmInk); tt.rotation.z = Math.PI; tt.position.y = -mr * 0.1; mTiny.add(tt);

    /* the stitched patch, lower right */
    var pw = w * 0.19, ph = h * 0.26;
    var patch = new THREE.Group();
    patch.position.set(w * 0.255, fh + h * 0.22, d / 2 - 0.01);
    patch.rotation.z = -0.14;
    patch.add(mesh(roundedBox(pw, ph, 0.08, 0.03, 2), pm.cream, 0, 0, 0, false));
    patch.add(mesh(roundedBox(pw * 0.78, ph * 0.74, 0.085, 0.025, 2), pm.creamD, 0, 0, 0, false));
    patch.add(mesh(roundedBox(pw * 0.7, ph * 0.66, 0.09, 0.02, 2), pm.cream, 0, 0, 0, false));
    var lf = mesh(new THREE.SphereGeometry(pw * 0.2, 10, 8), pm.leaf, 0, 0, 0.045, false);
    lf.scale.set(1.2, 0.62, 0.3);
    lf.rotation.z = 0.6;
    patch.add(lf);
    body.add(patch);

    /* sprouts */
    (o.plants || []).forEach(function (pp) {
      var pl = makePlant(pp.n || 5, !!pp.fruit, pp.type);
      pl.size = pp.size || 1;
      var hold = new THREE.Group();
      hold.position.set(pp.x || 0, topY + 0.03, pp.z || 0);
      hold.rotation.z = pp.tilt || 0;
      hold.add(pl.g);
      body.add(hold);
      pt.plants.push(pl);
    });

    /* stubby arms (the main Petak only) */
    if (o.arms) {
      pt.arms = [-1, 1].map(function (s) {
        var piv = new THREE.Group();
        piv.position.set(s * (w / 2 - 0.04), fh + h * 0.58, -0.05);
        var L = h * 0.4, r = h * 0.08;
        piv.add(mesh(new THREE.CylinderGeometry(r, r, L, 10), pm.body, 0, -L / 2, 0));
        piv.add(mesh(new THREE.SphereGeometry(r * 1.35, 12, 10), pm.body, 0, -L, 0));
        piv.rotation.z = s * 0.45;
        body.add(piv);
        return { piv: piv, s: s };
      });
    }
    /* sleepy z's drift up from the main Petak at night */
    if (o.zzz) {
      pt.zs = [0, 1, 2].map(function () {
        var sp = new THREE.Sprite(zMat.clone());
        sp.renderOrder = 20;
        sp.visible = false;
        g.add(sp);
        return sp;
      });
      pt.zTop = topY + 0.5;
      pt.zX = w * 0.34 + 0.9;
    }

    pt.setMood = function (m) {
      var c = MOODS[m] || MOODS.happy;
      pt.mood = m;
      pt.eyeK = c.k;
      pt.eyes.forEach(function (e) { e.open.visible = c.eye === 'open'; e.happy.visible = c.eye === 'happy'; e.sleep.visible = c.eye === 'sleep'; });
      Object.keys(pt.mouths).forEach(function (k) { pt.mouths[k].visible = k === c.mouth; });
    };
    pt.setMood('happy');
    return pt;
  }

  /* every pot and bed in the story is a "spot": it pops in with a squash and a burst of sparkles, then grows */
  var spots = [];
  function addSpot(parent, x, y, z, o) {
    o = o || {};
    var g = new THREE.Group();
    g.position.set(x, y, z);
    if (o.ry) g.rotation.y = o.ry;
    var plants = [];
    var pt = null;
    if (o.kind === 'petak') {
      pt = makePetak(o);
      g.add(pt.g);
      plants = pt.plants;
    } else if (o.kind === 'bed') {
      var b = makeBed(o.w || 3.4, o.d || 2.1, o.n || 3, !!o.face, !!o.fruit);
      g.add(b.g);
      plants = b.plants;
    } else if (o.kind === 'hang') {
      var hg = makeHang(o.color);
      g.add(hg.g);
      plants = [hg.pl];
    } else if (o.kind === 'rail') {
      var rb = makeBed(1.5, 0.5, 3, false, false, 0.38, 4, o.ptype);
      g.add(rb.g);
      plants = rb.plants;
    } else {
      g.add(makePot(o.color || potColors[Math.floor(rnd() * potColors.length)]));
      var pl = makePlant(5, !!o.fruit, o.type);
      pl.size = 1;
      pl.g.position.y = 0.55;
      g.add(pl.g);
      plants = [pl];
    }
    g.scale.setScalar(0.001);
    parent.add(g);
    var s = {
      g: g, plants: plants, s: o.s || 1,
      popA: o.popA == null ? 0.14 : o.popA, popB: o.popB == null ? 0.2 : o.popB,
      growA: o.growA == null ? 0.22 : o.growA, growB: o.growB == null ? 0.55 : o.growB,
      fruitA: o.fruitA == null ? 9 : o.fruitA, fruitB: o.fruitB == null ? 10 : o.fruitB,
      harvA: o.harvA == null ? 9 : o.harvA, harvB: o.harvB == null ? 10 : o.harvB
    };
    spots.push(s);
    if (pt) {
      pt.spot = s;
      pt.fx = x;
      pt.fy = y + pt.eyeY * (o.s || 1);
      pt.fz = z + (o.d / 2) * (o.s || 1);
      petaks.push(pt);
    }
    if (o.burst !== false) addBurst(x, y + 0.7 * (o.s || 1), z, s.popA, 0.05, 11, 0.9 * (o.s || 1) + 0.3, 0.16, o.hue);
    return s;
  }

  var baskets = [];
  function addBasket(parent, x, y, z, s, a, b) {
    var g = new THREE.Group();
    g.position.set(x, y, z);
    g.add(mesh(new THREE.CylinderGeometry(0.62, 0.48, 0.55, 16), mat(0xd9a15f, 0.8), 0, 0.28, 0));
    var toms = [];
    [[-0.2, 0, 0.1], [0.2, 0.05, 0.1], [0, 0.02, -0.22], [-0.12, 0.18, -0.05], [0.14, 0.2, -0.06], [0, 0.25, 0.14]].forEach(function (t) {
      var bb = ball(0.18, 0xff6b4a, t[0], 0.58 + t[1], t[2], 0.35);
      bb.scale.setScalar(0.001);
      g.add(bb);
      toms.push(bb);
    });
    g.scale.setScalar(0.001);
    parent.add(g);
    baskets.push({ g: g, toms: toms, s: s || 1, a: a, b: b });
    return g;
  }

  var railMat = mat(0xf6f1e6, 0.6);
  function postRow(parent, x0, x1, n, y, z, h, m) {
    for (var i = 0; i < n; i++) {
      var x = lerp(x0, x1, n === 1 ? 0 : i / (n - 1));
      parent.add(mesh(new THREE.CylinderGeometry(0.035, 0.035, h, 8), m || railMat, x, y + h / 2, z));
    }
  }

  /* street trees arrive at the end */
  var popTrees = [];
  function makeTree(x, z, delay) {
    var g = new THREE.Group();
    g.position.set(x, 0, z);
    g.add(mesh(new THREE.CylinderGeometry(0.18, 0.24, 1.6, 10), mat(0x8b5a2b, 0.8), 0, 0.8, 0));
    g.add(ball(1.0, 0x2fbf5c, 0, 2.2, 0, 0.6));
    g.add(ball(0.75, 0x45cf72, 0.5, 2.9, 0.2, 0.6));
    g.add(ball(0.6, 0x23a84e, -0.5, 1.8, 0.3, 0.6));
    g.scale.setScalar(0.001);
    world.add(g);
    popTrees.push({ g: g, delay: delay || 0 });
    return g;
  }

  var shadowSize = 30;
  var sunTarget = new THREE.Vector3(0, 9, 0);
  var keys = [];
  var legs = [];
  var rainZone = { x: 0, z: 0, w: 3, d: 2, top: 10, bot: 2, cloudY: 11, cloudZ: 0 };
  var followRange = [0.575, 0.86];
  var floorMarks = [];

  /* ===== scene begins ===== */
  /* ===== SCENE: one apartment block. A seed lands on the roof, grows, and moves down balcony by balcony ===== */
  var BW = 9.6, BD = 6.0, H0 = 3.2, RH = 3.0, NF = 5, TH = H0 + NF * RH;
  var FR = TH + 0.125;
  var COLX = 2.45;
  function slabY(k) { return H0 + (k - 1) * RH; }

  /* the schedule, in scroll progress */
  var T = { dropA: 0.11, dropB: 0.158, emergeA: 0.575, emergeB: 0.62, hop0: 0.62, hopStep: 0.046, hopFly: 0.034 };

  function part(w, h, d, x, y, z, grey, green) {
    var o = tinted(roundedBox(w, h, d, 0.06, 3), grey, green, x, y, z, 0.85);
    world.add(o);
    return o;
  }

  /* ground, sidewalk, road */
  world.add(tinted(roundedBox(96, 0.5, 96, 0.25, 4), 0xb4bab6, 0x7cc78f, 0, -0.25, 0, 0.9));
  part(80, 0.12, 2.6, 0, 0.06, 3.5, 0xb6bcc2, 0xd6ead6);
  world.add(mesh(bx(80, 0.06, 4.6), mat(0x555b63, 0.9), 0, 0.03, 7.3, false));
  for (var dx = -36; dx <= 36; dx += 3.4) world.add(mesh(bx(1.6, 0.02, 0.16), mat(0xf2f2ee, 0.9), dx, 0.075, 7.3, false));

  /* the building */
  world.add(tinted(roundedBox(BW, TH, BD, 0.3, 4), 0xc9cdd2, 0xfdedc9, 0, TH / 2, -BD / 2, 0.85));
  var bandCols = [0xffe0a8, 0xb7e4c7, 0xf7c9d4, 0xbfe2f5, 0xffe0a8];
  for (var bk = 1; bk <= NF; bk++) part(BW + 0.34, 0.2, BD + 0.34, 0, slabY(bk) - 0.02, -BD / 2, 0xb4b9bf, bandCols[bk - 1]);
  part(BW + 0.4, 0.25, BD + 0.4, 0, TH, -BD / 2, 0xa2a7ae, 0xf1e6cf);
  part(BW + 0.4, 0.5, 0.2, 0, TH + 0.37, 0.1, 0xaeb3b9, 0xfdedc9);
  part(0.2, 0.5, BD + 0.4, BW / 2 + 0.1, TH + 0.37, -BD / 2, 0xaeb3b9, 0xfdedc9);

  /* lobby with shop windows and an awning */
  for (var lw = -2; lw <= 2; lw++) addWin(world, lw * 1.9, 1.7, 0.03, 1.5, 1.9, 0);
  part(BW, 0.25, 1.2, 0, H0 - 0.45, 0.6, 0xe0c9a8, 0xff9d2e);
  addWin(world, BW / 2 + 0.03, 1.7, -2.2, 1.6, 1.9, Math.PI / 2);

  /* roof furniture: stair hut, water barrel */
  part(2.4, 2.3, 2.2, -3.1, FR + 1.15, -4.7, 0xc9cdd2, 0xd7ccf0);
  world.add(mesh(bx(0.9, 1.6, 0.06), mat(0x8b5a2b, 0.8), -3.1, FR + 0.8, -3.58));
  world.add(mesh(new THREE.CylinderGeometry(0.5, 0.5, 1.0, 16), mat(0x6cb4e4, 0.4), 3.5, FR + 0.5, -4.3));
  world.add(mesh(new THREE.CylinderGeometry(0.54, 0.54, 0.1, 16), mat(0x4f97cc, 0.4), 3.5, FR + 1.05, -4.3));

  /* floors: balconies on the front, windows, side windows */
  var hops = [];
  for (var hi = 0; hi < NF; hi++) {
    var a = T.hop0 + hi * T.hopStep;
    hops.push({ a: a, b: a + T.hopFly, k: NF - hi, col: hi % 2 === 0 ? -1 : 1 });
  }
  var potCols = [0xffb35c, 0xf4a7b9, 0x95d5b2, 0xfdedc9, 0x8fd0f2];
  /* every balcony is a little different: rail colour, slab tint, where the Petak sits, how many sprouts, pots, and some lived-in props.
     A fixed formula (not the random stream) keeps it identical on every load. */
  function vr(k, c, i) { var q = Math.sin(k * 12.9898 + (c + 2) * 78.233 + i * 37.719) * 43758.5453; return q - Math.floor(q); }
  var potTypes = ['rosette', 'grass', 'bush', 'cactus', 'flower', 'fern', 'leafy', 'succulent', 'flower'];
  var hairTypes = ['rosette', 'leafy', 'flower', 'rosette', 'leafy', 'flower'];
  function ht(k, c, i) { return hairTypes[Math.floor(vr(k, c, 26 + i) * hairTypes.length)]; }
  var railCols = [0xf6f1e6, 0xdbe8df, 0xf4dccb, 0xd3dce8];
  var slabCols = [0xfff0d0, 0xe3f3e0, 0xfde0e6, 0xdcecf8, 0xfff0d0];
  var chairCols = [0xf4a7b9, 0x8fd0f2, 0x95d5b2, 0xffb35c];
  var clothCols = [0xffffff, 0xf4a7b9, 0x8fd0f2, 0xffe0a8, 0x95d5b2];
  function propChair(x, fl, z, col, rm) {
    var m = mat(col, 0.6);
    world.add(mesh(roundedBox(0.42, 0.07, 0.42, 0.03, 2), m, x, fl + 0.38, z));
    world.add(mesh(roundedBox(0.42, 0.42, 0.06, 0.025, 2), m, x, fl + 0.62, z - 0.18));
    [[-1, -1], [1, -1], [-1, 1], [1, 1]].forEach(function (l) { world.add(mesh(bx(0.05, 0.36, 0.05), rm, x + l[0] * 0.17, fl + 0.18, z + l[1] * 0.17)); });
    world.add(mesh(new THREE.CylinderGeometry(0.3, 0.3, 0.05, 14), mat(0xfdedc9, 0.6), x + 0.78, fl + 0.5, z + 0.08));
    world.add(mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.48, 8), rm, x + 0.78, fl + 0.25, z + 0.08));
    world.add(mesh(new THREE.CylinderGeometry(0.06, 0.05, 0.1, 10), mat(0xff9d2e, 0.5), x + 0.84, fl + 0.58, z + 0.08));
  }
  function propLaundry(x, fl, z, k, c, rm) {
    [-1, 1].forEach(function (s) { world.add(mesh(new THREE.CylinderGeometry(0.03, 0.03, 1.4, 6), rm, x + s * 1.55, fl + 0.7, z)); });
    world.add(mesh(bx(3.1, 0.025, 0.025), rm, x, fl + 1.38, z));
    [[-1.0, 0.34, 0.46], [-0.4, 0.3, 0.4], [0.2, 0.4, 0.5], [0.9, 0.3, 0.38]].forEach(function (q, i) {
      var cl = mesh(bx(q[1], q[2], 0.02), mat(clothCols[Math.floor(vr(k, c, 20 + i) * 5)], 0.9), x + q[0], fl + 1.38 - q[2] / 2, z, false);
      cl.rotation.z = (vr(k, c, 30 + i) - 0.5) * 0.12;
      world.add(cl);
    });
  }
  function propCrates(x, fl, z) {
    var m = mat(0xc98a4b, 0.8);
    world.add(mesh(roundedBox(0.55, 0.4, 0.5, 0.04, 2), m, x, fl + 0.2, z));
    world.add(mesh(roundedBox(0.4, 0.3, 0.4, 0.04, 2), m, x + 0.02, fl + 0.55, z));
    world.add(mesh(roundedBox(0.5, 0.34, 0.46, 0.04, 2), mat(0xe0b27a, 0.8), x + 0.6, fl + 0.17, z + 0.05));
  }
  function propAC(x, y) {
    world.add(mesh(roundedBox(0.5, 0.32, 0.28, 0.06, 2), mat(0xf1f1ee, 0.5), x, y + 2.45, 0.17));
    world.add(mesh(bx(0.38, 0.03, 0.02), mat(0xc9cdd2, 0.5), x, y + 2.42, 0.32, false));
  }
  for (var k = 1; k <= NF; k++) {
    var y = slabY(k), fl = y + 0.11;
    addWin(world, BW / 2 + 0.03, y + 1.6, -1.5, 1.0, 1.1, Math.PI / 2);
    addWin(world, BW / 2 + 0.03, y + 1.6, -4.5, 1.0, 1.1, Math.PI / 2);
    addWin(world, 0, y + 1.6, 0.03, 0.6, 1.2, 0);
    var hop = hops[NF - k];
    [-1, 1].forEach(function (c) {
      var x = c * COLX;
      var rm = mat(railCols[Math.floor(vr(k, c, 1) * 4)], 0.6);
      part(3.8, 0.22, 1.7, x, y, 0.85, 0xb0b5bb, slabCols[Math.floor(vr(k, c, 2) * 5)]);
      world.add(mesh(bx(3.8, 0.09, 0.09), rm, x, y + 1.15, 1.7));
      [-1, 1].forEach(function (s) { world.add(mesh(bx(0.09, 0.09, 1.7), rm, x + s * 1.9, y + 1.15, 0.85)); });
      postRow(world, x - 1.7, x + 1.7, 8, y, 1.7, 1.15, rm);
      addWin(world, x - 0.55, y + 1.45, 0.03, 1.7, 2.3, 0);
      addWin(world, x + 1.25, y + 1.7, 0.03, 0.9, 1.0, 0);
      var landing = c === hop.col;
      var t0 = hop.b + (landing ? 0 : 0.026);
      var fruit = vr(k, c, 9) > 0.45 && !landing;

      /* where things sit on this balcony */
      var pOff = [-1.05, -0.35, 0.6][Math.floor(vr(k, c, 3) * 3)];
      var otherX = pOff < 0 ? 1.0 : -1.0;
      var pw = 1.0 + vr(k, c, 4) * 0.35;
      var pn = 1 + Math.floor(vr(k, c, 5) * 3);
      var plants = pn === 1 ? [{ x: 0, n: 5, size: 0.82, fruit: fruit, type: ht(k, c, 0) }]
        : pn === 2 ? [{ x: -0.2, n: 4, size: 0.7, tilt: 0.2, type: ht(k, c, 1) }, { x: 0.2, n: 5, size: 0.8, tilt: -0.2, fruit: fruit, type: ht(k, c, 0) }]
        : [{ x: 0, n: 5, size: 0.78, fruit: fruit, type: ht(k, c, 0) }, { x: -0.36, n: 4, size: 0.5, tilt: 0.3, type: ht(k, c, 1) }, { x: 0.36, n: 4, size: 0.5, tilt: -0.3, type: ht(k, c, 2) }];
      addSpot(world, x + pOff, fl, 1.05 + vr(k, c, 6) * 0.2, { kind: 'petak', w: pw, h: 0.72 + vr(k, c, 10) * 0.2, d: 0.95, fh: 0.1, er: 0.07, ry: (vr(k, c, 11) - 0.5) * 0.5, plants: plants,
        s: 0.95, popA: t0, popB: t0 + 0.045, growA: t0 + 0.012, growB: t0 + 0.085, fruitA: t0 + 0.09, fruitB: t0 + 0.12 });
      var np = vr(k, c, 12) < 0.3 ? 1 : 2;
      addSpot(world, x + otherX * (0.85 + vr(k, c, 13) * 0.15), fl, 0.95 + vr(k, c, 14) * 0.3, { s: 0.72 + vr(k, c, 15) * 0.2, popA: t0 + 0.01, popB: t0 + 0.055, growA: t0 + 0.02, growB: t0 + 0.095, color: potCols[Math.floor(vr(k, c, 16) * 5)], type: potTypes[Math.floor(vr(k, c, 21) * potTypes.length)] });
      if (np === 2) addSpot(world, x + (pOff < 0 ? 1.55 : -1.55), fl, 0.6 + vr(k, c, 17) * 0.4, { s: 0.55, popA: t0 + 0.03, popB: t0 + 0.07, growA: t0 + 0.04, growB: t0 + 0.1, color: potCols[Math.floor(vr(k, c, 18) * 5)], type: potTypes[Math.floor(vr(k, c, 23) * potTypes.length)], burst: false });
      var rr = vr(k, c, 7);
      if (rr < 0.5) addSpot(world, x + (pOff < 0 ? 1.25 : -1.0), y + 1.2, 1.78, { kind: 'rail', ptype: ['flower', 'trail', 'grass', 'succulent', 'leafy'][Math.floor(vr(k, c, 24) * 5)], popA: t0 + 0.018, popB: t0 + 0.062, growA: t0 + 0.028, growB: t0 + 0.1, hue: 1 });
      else if (rr < 0.9) addSpot(world, x + (pOff < 0 ? 1.4 : -1.4), y + 0.5, 2.05, { kind: 'hang', color: potCols[Math.floor(vr(k, c, 25) * 5)], s: 0.9, popA: t0 + 0.02, popB: t0 + 0.065, growA: t0 + 0.03, growB: t0 + 0.1, hue: 1 });

      /* lived-in details that are there from the start */
      var pv = vr(k, c, 8);
      if (pv < 0.2) { /* an empty-looking balcony */ }
      else if (pv < 0.45) propChair(x + otherX * 0.9 - 0.4, fl, 0.45, chairCols[Math.floor(vr(k, c, 19) * 4)], rm);
      else if (pv < 0.65) propLaundry(x, fl, 0.25, k, c, rm);
      else if (pv < 0.85) propCrates(x + otherX * 1.0, fl, 0.45);
      else propAC(x + 0.55, y);
    });
  }

  /* roof garden, the first spot to wake up */
  var bedX = -1.4, bedZ = -1.6;
  /* the main Petak wakes up where the seed lands; its sprouts are the first plants to grow */
  addSpot(world, bedX, FR, bedZ, { kind: 'petak', main: true, arms: true, zzz: true, w: 2.5, h: 1.5, d: 1.9, fh: 0.18, er: 0.115,
    plants: [{ x: 0, n: 6, size: 1.15, fruit: true }, { x: -0.74, n: 4, size: 0.7, tilt: 0.3, type: 'leafy' }, { x: 0.74, n: 4, size: 0.7, tilt: -0.3, type: 'flower' }],
    popA: 0.153, popB: 0.215, growA: 0.17, growB: 0.42, fruitA: 0.4, fruitB: 0.5, harvA: 0.53, harvB: 0.58, burst: false });
  addBurst(bedX, FR + 0.9, bedZ, 0.153, 0.06, 22, 1.9, 0.2, 0);
  addSpot(world, 1.2, FR, -0.9, { s: 0.95, popA: 0.18, popB: 0.235, growA: 0.23, growB: 0.46, fruit: true, fruitA: 0.41, fruitB: 0.51, harvA: 0.54, harvB: 0.59, color: 0xffb35c });
  addSpot(world, 2.3, FR, -2.5, { s: 0.85, popA: 0.195, popB: 0.25, growA: 0.24, growB: 0.47, color: 0xf4a7b9, type: 'cactus' });
  addSpot(world, 0.4, FR, -3.3, { s: 0.8, popA: 0.21, popB: 0.265, growA: 0.25, growB: 0.48, color: 0x95d5b2, type: 'bush' });
  addBasket(world, 3.3, FR, -0.9, 1, 0.52, 0.58);

  /* neighbours and the skyline */
  tower(-10.7, -2, 5.2, 14, 5.5, 0xb6bcc3, 0xffe0a8);
  tower(10.4, -2.6, 5.0, 9.5, 5.5, 0xbcc1c7, 0xb7e4c7);
  tower(-3, -13, 6, 13, 5, 0xc4cacf, 0xfdedc9);
  tower(6, -14.5, 5.5, 11, 5, 0xcdd2d6, 0xb7e4c7);
  tower(15, -11, 5, 14, 5, 0xc1c7cc, 0xffd4a0);
  tower(-17, -9, 5, 12, 5, 0xcbd0d5, 0xf7c9d4);
  tower(-23, -2, 4.5, 10, 5, 0xc9cfd4, 0xbfe2f5);
  tower(22, -3, 4.5, 10, 5, 0xc4cacf, 0xffe0a8);
  /* the low neighbour's roof gets the same furniture as ours (stair hut, door, water tank, vents), so it clearly reads as a rooftop */
  var rn = world.children[world.children.length - 1];
  (function () {
    var hy = 9.72;
    var hut = tinted(roundedBox(1.7, 1.7, 1.5, 0.08, 3), 0xc9cdd2, 0xd7ccf0, 10.4 + 1.4, hy + 0.85, -2.6 - 1.6, 0.85);
    world.add(hut);
    world.add(mesh(bx(0.7, 1.2, 0.06), mat(0x8b5a2b, 0.8), 10.4 + 1.4, hy + 0.6, -2.6 - 0.84));
    world.add(mesh(new THREE.CylinderGeometry(0.45, 0.45, 0.9, 16), mat(0x6cb4e4, 0.4), 10.4 - 1.5, hy + 0.45, -2.6 - 1.7));
    world.add(mesh(new THREE.CylinderGeometry(0.49, 0.49, 0.1, 16), mat(0x4f97cc, 0.4), 10.4 - 1.5, hy + 0.95, -2.6 - 1.7));
    [[-0.4, -1.9], [0.1, -1.95]].forEach(function (v) {
      world.add(mesh(new THREE.CylinderGeometry(0.07, 0.07, 0.7, 8), mat(0x8e949b, 0.5), 10.4 + v[0], hy + 0.35, -2.6 + v[1]));
    });
  })();
  /* the low neighbour catches a bed of its own once the seeds have come down */
  addSpot(world, 10.0, 9.72, -1.3, { kind: 'petak', w: 1.5, h: 0.95, d: 1.2, fh: 0.1, er: 0.08,
    plants: [{ x: -0.34, n: 4, size: 0.72, tilt: 0.22, fruit: true }, { x: 0.34, n: 4, size: 0.8, tilt: -0.22, type: 'leafy' }],
    popA: 0.87, popB: 0.93, growA: 0.88, growB: 0.97, fruitA: 0.95, fruitB: 0.99 });

  /* street level: a few pots on the pavement and trees, arriving last */
  addSpot(world, -1.6, 0.12, 2.9, { type: 'flower', s: 0.9, popA: 0.88, popB: 0.935, growA: 0.89, growB: 0.97 });
  addSpot(world, 1.6, 0.12, 2.9, { type: 'grass', s: 0.9, popA: 0.895, popB: 0.94, growA: 0.9, growB: 0.97 });
  addSpot(world, -4.4, 0.12, 2.9, { type: 'bush', s: 0.8, popA: 0.905, popB: 0.95, growA: 0.91, growB: 0.98 });
  addSpot(world, 4.5, 0.12, 2.9, { type: 'cactus', s: 0.8, popA: 0.91, popB: 0.955, growA: 0.92, growB: 0.98 });
  [-8, -6.2, 6.4, 8.4].forEach(function (x, i) { makeTree(x, 3.6, 0.86 + i * 0.014); });

  /* cars */
  var cars = [];
  function makeCar(color, z, dir, speed, off) {
    var g = new THREE.Group();
    g.add(mesh(roundedBox(1.9, 0.55, 0.95, 0.18, 3), mat(color, 0.5), 0, 0.5, 0));
    g.add(mesh(roundedBox(1.0, 0.45, 0.85, 0.16, 3), mat(0xdfe9f2, 0.3), -0.1, 0.95, 0));
    [[-0.6, 0.42], [0.6, 0.42], [-0.6, -0.42], [0.6, -0.42]].forEach(function (w) {
      var wh = mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.16, 12), mat(0x23272d, 0.9), w[0], 0.22, w[1]);
      wh.rotation.x = Math.PI / 2;
      g.add(wh);
    });
    var hl = new THREE.MeshBasicMaterial({ color: 0xfff2b0 });
    g.add(mesh(bx(0.06, 0.14, 0.2), hl, 0.96, 0.52, 0.28, false));
    g.add(mesh(bx(0.06, 0.14, 0.2), hl, 0.96, 0.52, -0.28, false));
    g.position.set(0, 0, z);
    g.rotation.y = dir < 0 ? Math.PI : 0;
    world.add(g);
    cars.push({ g: g, dir: dir, speed: speed, off: off });
  }
  makeCar(0xff9d2e, 6.4, 1, 1.5, 6);
  makeCar(0x8fd0f2, 8.2, -1, 1.9, 40);
  makeCar(0xf4a7b9, 6.4, 1, 1.5, 38);

  /* drifting clouds in the background */
  var skyClouds = [];
  [[-24, 29, -20, 1.2], [-4, 33, -26, 1.5], [18, 27, -22, 1.0], [34, 31, -18, 1.3]].forEach(function (c, i) {
    var g = new THREE.Group();
    [[-1.0, 0, 0.7], [0, 0.35, 1.0], [1.1, 0, 0.75], [0.1, -0.3, 0.8]].forEach(function (b) {
      var bl = ball(b[2], 0xffffff, b[0], b[1], 0, 0.95);
      bl.castShadow = false; bl.receiveShadow = false;
      g.add(bl);
    });
    g.scale.setScalar(c[3]);
    g.position.set(c[0], c[1], c[2]);
    world.add(g);
    skyClouds.push({ g: g, x0: c[0], speed: 0.25 + i * 0.07 });
  });

  rainZone = { x: -0.4, z: -2.2, w: 7.2, d: 4.4, top: FR + 4.4, bot: FR + 0.5, cloudY: FR + 5.0, cloudZ: -2.2 };

  /* the seed packet's journey: it drops onto the roof, comes back out of the basket, then hops down floor by floor */
  var P0 = V3(bedX + 0.1, FR + 2.3, bedZ + 0.2);
  legs.push({ a: T.dropA, b: T.dropB, from: V3(bedX + 3.2, FR + 7.0, bedZ + 2.4), to: P0, arc: 0.4, kind: 'drop' });
  var Pb = V3(3.3, FR + 0.9, -0.9);
  var hopStart = V3(0.2, FR + 2.8, 0.4);
  legs.push({ a: T.emergeA, b: T.emergeB, from: Pb, to: hopStart, arc: 1.6, kind: 'emerge' });
  var prev = hopStart;
  hops.forEach(function (h, i) {
    var to = V3(h.col * COLX, slabY(h.k) + 1.75, 1.15);
    legs.push({ a: h.a, b: h.b, from: i === 0 ? prev : V3(prev.x, prev.y - 0.3, prev.z), to: to, arc: 2.1, kind: 'hop', idx: i });
    prev = to;
  });
  hops.forEach(function (h, i) { floorMarks.push({ seen: h.b, now0: h.a, now1: i + 1 < hops.length ? hops[i + 1].a : 0.9 }); });

  keys = [
    { p: 0.00, zoom: 0.58, t: [0, 9.3, -1],       az: 34, el: 25 },
    { p: 0.07, zoom: 0.58, t: [0, 9.3, -1],       az: 36, el: 25 },
    { p: 0.15, zoom: 1.3,  t: [-0.3, 18.7, -1.2], az: 38, el: 27 },
    { p: 0.23, zoom: 1.75, t: [0, 19.3, -1.4],    az: 40, el: 28 },
    { p: 0.34, zoom: 1.8,  t: [0.3, 19.4, -1.4],  az: 44, el: 28 },
    { p: 0.50, zoom: 1.85, t: [0.4, 19.4, -1.4],  az: 50, el: 27 },
    { p: 0.575, zoom: 1.5, t: [0.4, 19.0, -1.0],  az: 46, el: 28 },
    { p: 0.62, zoom: 1.15, t: [-2, 16.5, 0.5],    az: 42, el: 28 },
    { p: 0.84, zoom: 1.15, t: [-2, 6.5, 0.5],     az: 40, el: 27 },
    { p: 0.90, zoom: 0.9,  t: [0, 9, 0],          az: 38, el: 27 },
    { p: 1.00, zoom: 0.62, t: [0, 8.8, -0.5],     az: 40, el: 26 }
  ];

  /* ===== scene ends ===== */

  var sc = sun.shadow.camera;
  sc.left = -shadowSize; sc.right = shadowSize; sc.top = shadowSize; sc.bottom = -shadowSize; sc.near = 1; sc.far = 170;
  sc.updateProjectionMatrix();
  sun.target.position.copy(sunTarget);
  scene.add(sun.target);

  /* rain cloud and drops */
  var cloud = new THREE.Group();
  [[-1.5, -0.05, 0.75], [0, 0.3, 1.05], [1.6, -0.04, 0.8], [0.3, -0.34, 0.85], [-0.6, -0.3, 0.6]].forEach(function (c) { cloud.add(ball(c[2], 0xffffff, c[0], c[1], 0, 0.9)); });
  cloud.scale.setScalar(0.001);
  world.add(cloud);
  var RAIN = 70;
  var rain = new THREE.InstancedMesh(new THREE.SphereGeometry(0.06, 8, 6), mat(0x6cc8ff, 0.3), RAIN);
  rain.frustumCulled = false;
  var rainSeed = [];
  for (var ri = 0; ri < RAIN; ri++) rainSeed.push({ x: rnd() - 0.5, z: rnd() - 0.5, ph: rnd(), sp: 0.8 + rnd() * 0.5 });
  world.add(rain);
  var dummy = new THREE.Object3D();

  /* the seed packet */
  var gcv = document.createElement('canvas');
  gcv.width = gcv.height = 64;
  var gctx = gcv.getContext('2d');
  var grad = gctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, 'rgba(255,214,110,0.9)');
  grad.addColorStop(0.45, 'rgba(255,200,90,0.35)');
  grad.addColorStop(1, 'rgba(255,200,90,0)');
  gctx.fillStyle = grad;
  gctx.fillRect(0, 0, 64, 64);
  var packet = new THREE.Group();
  packet.add(mesh(roundedBox(0.5, 0.7, 0.1, 0.04, 3), mat(0xff9d2e, 0.5), 0, 0, 0));
  packet.add(mesh(bx(0.34, 0.26, 0.02), mat(0xffffff, 0.6), 0, -0.08, 0.06, false));
  packet.add(ball(0.07, 0x2fbf5c, -0.05, 0.14, 0.07, 0.5));
  packet.add(ball(0.06, 0x45cf72, 0.06, 0.18, 0.07, 0.5));
  var pGlow = new THREE.Sprite(new THREE.SpriteMaterial({ map: new THREE.CanvasTexture(gcv), transparent: true, depthWrite: false, opacity: 0.55 }));
  pGlow.scale.set(2.6, 2.6, 1);
  packet.add(pGlow);
  packet.visible = false;
  world.add(packet);

  var tmpA = new THREE.Vector3();
  function legPos(L, s, out, arcScale) {
    s = clamp01(s);
    var e = L.kind === 'drop' ? s * s : L.kind === 'emerge' ? outCubic(s) : s * s * (3 - 2 * s);
    out.set(lerp(L.from.x, L.to.x, e), lerp(L.from.y, L.to.y, e), lerp(L.from.z, L.to.z, e));
    var as = arcScale == null ? 1 : arcScale;
    out.y += Math.sin(Math.PI * s) * L.arc * as;
    out.x += Math.sin(s * Math.PI * 2) * (L.kind === 'hop' ? 0.28 : 0.35) * (L.kind === 'drop' ? 1 - s : 1) * as;
    return out;
  }
  /* where the packet is (or last was); the camera follows this point */
  var follow = new THREE.Vector3();
  function followPoint(p) {
    var idx = 1;
    for (var i = 1; i < legs.length; i++) if (p >= legs[i].a) idx = i;
    var L = legs[idx];
    if (p >= L.b) follow.copy(L.to); else legPos(L, (p - L.a) / (L.b - L.a), follow, 0.2);
    return follow;
  }

  /* ---------- sparkles: one Points object, positions computed from scroll progress, so it works in both directions ---------- */
  var MAXP = 900;
  var pPos = new Float32Array(MAXP * 3), pCol = new Float32Array(MAXP * 3), pSize = new Float32Array(MAXP), pAlpha = new Float32Array(MAXP);
  var pGeo = new THREE.BufferGeometry();
  [['position', pPos, 3], ['aColor', pCol, 3], ['aSize', pSize, 1], ['aAlpha', pAlpha, 1]].forEach(function (a) {
    var at = new THREE.BufferAttribute(a[1], a[2]);
    at.setUsage(THREE.DynamicDrawUsage);
    pGeo.setAttribute(a[0], at);
  });
  var pMat = new THREE.ShaderMaterial({
    uniforms: { uPx: { value: 30 } },
    transparent: true, depthTest: false, depthWrite: false,
    vertexShader: 'attribute vec3 aColor; attribute float aSize; attribute float aAlpha; varying vec3 vC; varying float vA; uniform float uPx;' +
      'void main(){ vC=aColor; vA=aAlpha; gl_PointSize=aSize*uPx; gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }',
    fragmentShader: 'varying vec3 vC; varying float vA;' +
      'void main(){ vec2 c=gl_PointCoord-0.5; float d=length(c);' +
      'float core=smoothstep(0.2,0.0,d);' +
      'float star=max(smoothstep(0.07,0.0,abs(c.x))*smoothstep(0.5,0.05,abs(c.y)), smoothstep(0.07,0.0,abs(c.y))*smoothstep(0.5,0.05,abs(c.x)));' +
      'float halo=smoothstep(0.5,0.1,d)*0.35;' +
      'float a=clamp(core+star+halo,0.0,1.0)*vA; if(a<0.01) discard;' +
      'gl_FragColor=vec4(mix(vC,vec3(1.0),core*0.85),a); }'
  });
  var points = new THREE.Points(pGeo, pMat);
  points.frustumCulled = false;
  points.renderOrder = 20;
  scene.add(points);
  var pn = 0;
  function put(x, y, z, size, alpha, r, g, b) {
    if (pn >= MAXP || alpha < 0.01 || size < 0.005) return;
    var i = pn++;
    pPos[i * 3] = x; pPos[i * 3 + 1] = y; pPos[i * 3 + 2] = z;
    pCol[i * 3] = r; pCol[i * 3 + 1] = g; pCol[i * 3 + 2] = b;
    pSize[i] = size; pAlpha[i] = alpha;
  }
  function drawSparkles(p, time) {
    pn = 0;
    for (var i = 0; i < emitters.length; i++) {
      var e = emitters[i], u = (p - e.t0) / e.dur;
      if (u < 0 || u > 1) continue;
      var r = e.rad * outCubic(u), fade = Math.pow(1 - u, 1.3);
      for (var j = 0; j < e.n; j++) {
        var d = e.d[j], rr = r * d[3];
        var gold = d[4] > 0.5;
        var c = gold ? [1, 0.78, 0.25] : (e.hue ? [0.3, 0.85, 0.45] : [1, 0.55, 0.3]);
        put(e.x + d[0] * rr, e.y + d[1] * rr - 0.9 * u * u * e.rad * 0.5, e.z + d[2] * rr, e.size * (0.6 + 0.8 * d[3]) * (1 - u * 0.5), fade, c[0], c[1], c[2]);
      }
    }
    /* trail behind the seed packet */
    if (packet.visible && trail.n) {
      for (var t = 0; t < trail.n; t++) {
        var f = 1 - t / trail.n;
        put(trail.x[t], trail.y[t], trail.z[t], 0.26 * f + 0.06, 0.8 * f, 1, 0.8, 0.3);
      }
    }
    pGeo.attributes.position.needsUpdate = true;
    pGeo.attributes.aColor.needsUpdate = true;
    pGeo.attributes.aSize.needsUpdate = true;
    pGeo.attributes.aAlpha.needsUpdate = true;
    pGeo.setDrawRange(0, pn);
  }
  var trail = { n: 0, x: [], y: [], z: [] };

  /* ---------- camera: keyframes give the target, critically damped springs give the weight ---------- */
  var ct = { zoom: 0.58, tx: 0, ty: 9.3, tz: -1, az: 34, el: 25 };
  var cs = { zoom: 0.58, tx: 0, ty: 9.3, tz: -1, az: 34, el: 25 };
  var cv = { zoom: 0, tx: 0, ty: 0, tz: 0, az: 0, el: 0 };
  var camSmooth = { zoom: 0.4, tx: 0.3, ty: 0.34, tz: 0.3, az: 0.55, el: 0.55 };
  function sampleKeys(p) {
    var i = 0;
    while (i < keys.length - 2 && p > keys[i + 1].p) i++;
    var a = keys[i], b = keys[i + 1];
    var u = smooth(0, 1, clamp01((p - a.p) / (b.p - a.p)));
    ct.zoom = lerp(a.zoom, b.zoom, u);
    ct.az = lerp(a.az, b.az, u);
    ct.el = lerp(a.el, b.el, u);
    ct.tx = lerp(a.t[0], b.t[0], u); ct.ty = lerp(a.t[1], b.t[1], u); ct.tz = lerp(a.t[2], b.t[2], u);
    var pu = 0;
    for (var li = 0; li < legs.length; li++) {
      var uu = (p - legs[li].b) / 0.022;
      if (uu > 0 && uu < 1) pu += 0.035 * Math.sin(Math.PI * uu) * (1 - uu);
    }
    ct.zoom *= 1 + pu;
    var w = smooth(followRange[0], followRange[0] + 0.04, p) * (1 - smooth(followRange[1] - 0.03, followRange[1] + 0.02, p));
    if (w > 0.001) {
      var f = followPoint(p);
      ct.ty = lerp(ct.ty, f.y - 0.5, w * 0.92);
      ct.tx = lerp(ct.tx, f.x * 0.4 - 2.0, w * 0.85);
    }
  }
  function sdamp(cur, tgt, vel, st, dt) {
    var om = 2 / Math.max(0.0001, st), x = om * dt;
    var ex = 1 / (1 + x + 0.48 * x * x + 0.235 * x * x * x);
    var ch = cur - tgt, tmp = (vel + om * ch) * dt;
    return { v: (vel - om * tmp) * ex, x: tgt + (ch + tmp) * ex };
  }
  function stepCamera(dt, snap) {
    ['zoom', 'tx', 'ty', 'tz', 'az', 'el'].forEach(function (k) {
      if (snap) { cs[k] = ct[k]; cv[k] = 0; return; }
      var r = sdamp(cs[k], ct[k], cv[k], camSmooth[k], dt);
      cs[k] = r.x; cv[k] = r.v;
    });
  }

  var viewW = 29.4, viewH = 16.5, aspect = 1.78;
  function resize() {
    var w = stage.clientWidth, h = stage.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    aspect = w / h;
    if (aspect >= 1) { viewH = Math.max(16.5, 28 / aspect); viewW = viewH * aspect; }
    else { viewW = 28 * lerp(0.42, 1, smooth(0.5, 1.0, aspect)); viewH = viewW / aspect; }
    pMat.uniforms.uPx.value = h * DPR / viewH;
  }
  if (window.ResizeObserver) new ResizeObserver(resize).observe(stage);
  window.addEventListener('resize', resize);
  resize();

  var ptr = { x: 0, y: 0, sx: 0, sy: 0, vx: 0, vy: 0 };
  window.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch') return;
    ptr.x = e.clientX / window.innerWidth * 2 - 1;
    ptr.y = e.clientY / window.innerHeight * 2 - 1;
  }, { passive: true });

  var lean = 0;
  function applyCamera(time) {
    var breathe = reduced ? 0 : Math.sin(time * 0.35) * 0.6;
    var az = (cs.az + ptr.sx * 2.4 + lean * 5 + breathe) * Math.PI / 180;
    var el = (cs.el - ptr.sy * 1.1 + Math.abs(lean) * 1.2) * Math.PI / 180;
    var d = 90;
    camera.position.set(cs.tx + Math.sin(az) * Math.cos(el) * d, cs.ty + Math.sin(el) * d, cs.tz + Math.cos(az) * Math.cos(el) * d);
    var hw = viewW / 2, hh = viewH / 2;
    var sx = aspect > 1.15 ? viewW * 0.15 : 0;
    var sy = aspect < 0.9 ? viewH * 0.17 : 0;
    camera.left = -hw - sx; camera.right = hw - sx; camera.top = hh - sy; camera.bottom = -hh - sy;
    var zk = lerp(0.6, 1, smooth(0.5, 1.0, aspect));
    camera.zoom = cs.zoom > 1 ? 1 + (cs.zoom - 1) * zk : cs.zoom;
    camera.updateProjectionMatrix();
    camera.lookAt(cs.tx, cs.ty, cs.tz);
  }

  /* ---------- time of day: three sun cycles in the time-lapse; it starts and ends at dawn ---------- */
  var hourKeys = [[0, 9.2], [0.09, 9.9], [0.28, 16], [0.37, 31], [0.55, 40], [0.60, 42.5], [0.62, 43.4], [0.84, 53], [0.88, 54.9], [0.92, 56.6], [1, 58.5]];
  function hourAt(p) {
    for (var i = 0; i < hourKeys.length - 1; i++) {
      var a = hourKeys[i], b = hourKeys[i + 1];
      if (p <= b[0]) return lerp(a[1], b[1], clamp01((p - a[0]) / (b[0] - a[0])));
    }
    return 80.2;
  }
  /* how dark it is at scroll position p (same curve the sky uses) */
  function nightOf(p) {
    var hr = ((hourAt(p) % 24) + 24) % 24, e = Math.sin(Math.PI * (hr - 6) / 12);
    return 1 - smooth(-0.25, 0.12, e);
  }

  /* ---------- Petak: what the mascots feel and do at each moment of the story ---------- */
  function mainMood(p, night) {
    if (p < 0.19) return 'wow';
    if (night > 0.6 && p < 0.5) return 'sleep';
    if (p >= 0.335 && p < 0.385) return 'wow';
    if (p >= 0.385 && p < 0.475) return 'cheer';
    if (p >= 0.5 && p < 0.585) return 'proud';
    if (night > 0.6) return 'sleep';
    if (p > 0.88) return 'cheer';
    return 'happy';
  }
  function miniMood(s, p, night) {
    var t = p - s.popA;
    if (t < 0.016) return 'wow';
    if (p > 0.885) return 'cheer';
    if (night > 0.6 && t > 0.06) return 'sleep';
    return 'happy';
  }
  function wave(time) { return reduced ? 0 : Math.sin(time * 9) * 0.3; }
  function updatePetak(pk, p, time, dt) {
    var s = pk.spot;
    if (pop(s.popA, s.popB, p) <= 0.002) return;
    var night = nightOf(p);
    var mood = pk.main ? mainMood(p, night) : miniMood(s, p, night);
    if (mood !== pk.mood) pk.setMood(mood);
    var k = Math.min(1, dt * 8);

    /* blink */
    var bl = 0;
    if (!reduced && pk.eyeK >= 1 && (mood === 'happy' || mood === 'wow' || mood === 'proud')) {
      var bph = (time + pk.ph) % 3.7;
      bl = bph < 0.16 ? Math.sin(bph / 0.16 * Math.PI) : 0;
    }
    /* eyes follow the seed packet when it is near */
    var tx = 0, ty = 0;
    if (packet.visible && mood !== 'sleep') {
      var dx = packet.position.x - pk.fx, dy = packet.position.y - pk.fy, dz = packet.position.z - pk.fz;
      if (dx * dx + dy * dy + dz * dz < 160) { tx = Math.max(-1, Math.min(1, dx / 3)); ty = Math.max(-1, Math.min(1, dy / 3)); }
    }
    pk.gx += (tx * pk.er * 0.45 - pk.gx) * k;
    pk.gy += (ty * pk.er * 0.35 - pk.gy) * k;
    pk.eyes.forEach(function (e) {
      e.open.scale.set(pk.eyeK, pk.eyeK * (1 - 0.9 * bl), 1);
      e.open.position.set(pk.gx, pk.gy, 0);
    });
    /* breathing */
    pk.body.scale.y = reduced ? 1 : 1 + 0.018 * Math.sin(time * 2.3 + pk.ph);

    if (pk.arms) {
      var tl = 0.45, tr = 0.45;
      if (p >= 0.2 && p < 0.27) tr = 2.3 + wave(time);
      else if (p >= 0.385 && p < 0.475) { tl = 2.5; tr = 2.5; }
      else if (p >= 0.5 && p < 0.585) { tl = 2.5; tr = 2.3 + wave(time); }
      else if (p >= 0.62 && p < 0.7) tr = 2.3 + wave(time);
      pk.aL += (tl - pk.aL) * k;
      pk.aR += (tr - pk.aR) * k;
      pk.arms[0].piv.rotation.z = -pk.aL;
      pk.arms[1].piv.rotation.z = pk.aR;
    }
    if (pk.zs) {
      pk.sleep += ((mood === 'sleep' ? 1 : 0) - pk.sleep) * Math.min(1, dt * 3);
      pk.zs.forEach(function (sp, i) {
        var ph = (time * 0.45 + i / 3) % 1;
        sp.visible = pk.sleep > 0.03;
        sp.position.set(pk.zX + ph * 0.7, pk.zTop + ph * 1.1, 0.5);
        var sc = (0.55 + ph * 0.45);
        sp.scale.set(sc, sc, 1);
        sp.material.opacity = pk.sleep * Math.sin(Math.PI * ph) * 0.95;
      });
    }
  }
  /* the page is cream and light on purpose, whatever the device theme is */
  function isDark() { return false; }
  var cA = new THREE.Color(), cB = new THREE.Color(), cT = new THREE.Color(), cI = new THREE.Color();
  var inkDark = new THREE.Color(0x0f2216), inkLight = new THREE.Color(0xf1f7f2), mutedDark = new THREE.Color(0x2c4233), mutedLight = new THREE.Color(0xb9cdc0);
  var lastInk = '', lastScrim = '';
  function arc(t) { return clamp01((t + 0.08) / 0.1) * (1 - clamp01((t - 0.92) / 0.1)); }
  function light(hour, g) {
    var hr = ((hour % 24) + 24) % 24, t = (hr - 6) / 12;
    var e = Math.sin(Math.PI * t);
    var dayAmt = smooth(-0.25, 0.2, e);
    var night = 1 - smooth(-0.25, 0.12, e);
    var th = (45 + (clamp01(t) - 0.5) * 170) * Math.PI / 180, el = Math.max(e, 0.06) * 62 * Math.PI / 180;
    sun.position.set(sunTarget.x + Math.sin(th) * Math.cos(el) * 45, sunTarget.y + Math.sin(el) * 45, sunTarget.z + Math.cos(th) * Math.cos(el) * 45);
    sun.intensity = 0.6 * dayAmt + 0.04;
    sun.color.set(0xffb26b).lerp(cT.set(0xfff4e0), smooth(0.05, 0.5, e));
    moon.intensity = 0.95 * night;
    var dark = isDark();
    hemi.intensity = (0.42 + 0.16 * dayAmt) * (dark ? 0.9 : 1);
    hemi.color.set(0x7088c8).lerp(cT.set(0xffffff), dayAmt);
    hemi.groundColor.set(0x1c2540).lerp(cT.set(0xcfd6dc), dayAmt).lerp(cT.set(0xcfe8d4), g * dayAmt);

    var warm = (1 - smooth(0.08, 0.55, e)) * (1 - night);
    cA.set(0x8ecaf1).lerp(cT.set(0xf2b9a1), warm).lerp(cT.set(0x0b1630), night);
    cB.set(0xdcf0fb).lerp(cT.set(0xffe6c8), warm).lerp(cT.set(0x233559), night);
    var gt = g * 0.3 * (1 - night);
    cA.lerp(cT.set(0xcdeed6), gt);
    cB.lerp(cT.set(0xe3f7e5), gt);
    if (dark) { cA.lerp(cT.set(0x0c1218), 0.25); cB.lerp(cT.set(0x0c1218), 0.25); }
    stage.style.setProperty('--sky-a', '#' + cA.getHexString());
    stage.style.setProperty('--sky-b', '#' + cB.getHexString());
    scene.fog.color.copy(cB);
    starsEl.style.opacity = (night * night * 0.9).toFixed(3);

    /* text colour follows the sky so it always reads */
    var lum = 0.5 * (0.299 * cA.r + 0.587 * cA.g + 0.114 * cA.b + 0.299 * cB.r + 0.587 * cB.g + 0.114 * cB.b);
    var kd = smooth(0.5, 0.6, lum);
    var ink = '#' + cI.copy(inkLight).lerp(inkDark, kd).getHexString();
    if (ink !== lastInk) {
      lastInk = ink;
      stage.style.setProperty('--ink', ink);
      root.style.setProperty('--stage-ink', ink);
      root.style.setProperty('--stage-ink-inverse', kd > 0.5 ? '#f1f7f2' : '#0f2216');
      stage.style.setProperty('--accent', kd > 0.5 ? '#178a3c' : '#6fe39a');
      stage.style.setProperty('--ink-muted', '#' + cI.copy(mutedLight).lerp(mutedDark, kd).getHexString());
      root.style.setProperty('--stage-ink-muted', '#' + cI.copy(mutedLight).lerp(mutedDark, kd).getHexString());
    }
    cI.copy(cB).lerp(cT.set(kd > 0.5 ? 0xffffff : 0x0a1426), 0.3);
    var sr = Math.round(cI.r * 255) + ',' + Math.round(cI.g * 255) + ',' + Math.round(cI.b * 255);
    if (sr !== lastScrim) { lastScrim = sr; stage.style.setProperty('--scrim-rgb', sr); }

    /* sun and moon discs */
    var ts = t, tm = (((hr - 18) % 24) + 24) % 24 / 12;
    orbSun.style.left = lerp(8, 92, clamp01(ts)) + '%';
    orbSun.style.top = (74 - Math.sin(Math.PI * clamp01(ts)) * 50) + '%';
    orbSun.style.opacity = (arc(ts) * (1 - 0.35 * warm)).toFixed(3);
    orbMoon.style.left = lerp(10, 90, clamp01(tm)) + '%';
    orbMoon.style.top = (70 - Math.sin(Math.PI * clamp01(tm)) * 46) + '%';
    orbMoon.style.opacity = (arc(tm) * 0.95).toFixed(3);

    /* the Petaks keep a faint warm glow at night so they stay readable and friendly */
    [pm.body, pm.rim, pm.foot].forEach(function (m) { m.emissive.set(0xff8a2a); m.emissiveIntensity = 0.3 * night; });
    winMats.forEach(function (w) {
      var lit = w.th > 1 ? 0 : smooth(w.th, w.th + 0.25, night);
      w.m.color.copy(winDay).lerp(winNight, smooth(0, 0.7, night));
      w.m.emissive.set(0x4a7aa0).lerp(cT.set(0xffbf70), lit);
      w.m.emissiveIntensity = 0.16 * (1 - night) * (1 - lit) + 0.8 * lit;
    });
    return hr;
  }

  function band(p, a, b, fade) {
    fade = fade || 0.03;
    if (p < a - fade || p > b + fade) return 0;
    if (p < a) return (p - (a - fade)) / fade;
    if (p > b) return 1 - (p - b) / fade;
    return 1;
  }
  var lastFloor = [], lastSO = '';

  /* ---------- everything the scroll position controls ---------- */
  function update(p, time, dt) {
    var g = smooth(0.8, 0.98, p);
    for (var i = 0; i < tints.length; i++) {
      var ny = clamp01(tints[i].y / 26);
      tints[i].m.color.copy(tints[i].a).lerp(tints[i].b, smooth(0.84 + (1 - ny) * 0.06, 0.92 + (1 - ny) * 0.06, p));
    }

    spots.forEach(function (s) {
      setPop(s.g, pop(s.popA, s.popB, p), s.s);
      var gm = smooth(s.growA, s.growB, p);
      var fr = smooth(s.fruitA, s.fruitB, p) * (1 - smooth(s.harvA, s.harvB, p));
      s.plants.forEach(function (pl, i) {
        growPlant(pl, clamp01((gm - i * 0.1) / 0.8));
        var fs = fr > 0.001 ? Math.max(0.001, backOut(fr)) : 0.001;
        pl.tom.forEach(function (t) { t.scale.setScalar(fs); });
      });
    });
    baskets.forEach(function (b) {
      setPop(b.g, pop(b.a, b.a + 0.045, p), b.s);
      b.toms.forEach(function (t, i) { t.scale.setScalar(Math.max(0.001, pop(0.55 + i * 0.01, 0.585 + i * 0.01, p))); });
    });
    popTrees.forEach(function (t) { setPop(t.g, pop(0.86 + t.delay, 0.93 + t.delay, p), 1); });

    /* idle life: plants sway; every Petak blinks, breathes and follows the seed with its eyes */
    petaks.forEach(function (pk) { updatePetak(pk, p, time, dt); });
    if (!reduced) {
      swayers.forEach(function (pl) {
        if (pl.grown < 0.05) return;
        pl.g.rotation.z = Math.sin(time * 1.4 + pl.ph) * 0.035 * pl.grown;
        pl.g.rotation.x = Math.cos(time * 1.1 + pl.ph) * 0.03 * pl.grown;
        for (var l = 0; l < pl.leaves.length; l++) pl.leaves[l].m.rotation.z = pl.leaves[l].base + Math.sin(time * 2.2 + pl.leaves[l].ph) * 0.07 * pl.grown;
      });
      skyClouds.forEach(function (c) { c.g.position.x = ((c.x0 + time * c.speed + 45) % 90) - 45; });
      cars.forEach(function (c) { c.g.position.x = ((((time * c.speed * c.dir + c.off) % 64) + 64) % 64) - 32; });
    }

    /* weather */
    var presence = smooth(0.335, 0.36, p) * (1 - smooth(0.45, 0.475, p));
    cloud.scale.setScalar(Math.max(0.001, presence));
    cloud.position.set(rainZone.x + Math.sin(time * 0.5) * 0.35, rainZone.cloudY + Math.sin(time * 0.9) * 0.12, rainZone.cloudZ);
    for (var r = 0; r < RAIN; r++) {
      var q = rainSeed[r], f = (time * 1.6 * q.sp + q.ph) % 1;
      dummy.position.set(rainZone.x + q.x * rainZone.w, lerp(rainZone.top, rainZone.bot, f), rainZone.z + q.z * rainZone.d);
      dummy.scale.set(1, 2.4, 1);
      dummy.scale.multiplyScalar(presence > 0.05 ? presence : 0.001);
      dummy.updateMatrix();
      rain.setMatrixAt(r, dummy.matrix);
    }
    rain.instanceMatrix.needsUpdate = true;

    /* the seed packet and its sparkle trail */
    var vis = false;
    trail.n = 0;
    for (var li = 0; li < legs.length; li++) {
      var L = legs[li];
      if (p < L.a || p > L.b) continue;
      var s = (p - L.a) / (L.b - L.a);
      legPos(L, s, packet.position);
      var sIn = (L.kind === 'drop' || L.idx === 0) ? 1 : smooth(0, 0.16, s);
      var sOut = L.kind === 'emerge' ? 1 : 1 - smooth(0.86, 1, s);
      var bob = reduced ? 0 : Math.sin(time * 5) * 0.05;
      packet.position.y += bob;
      packet.scale.setScalar(Math.max(0.001, 2.2 * sIn * sOut * (1 + 0.08 * Math.sin(s * 20))));
      packet.rotation.set(0.2 * Math.sin(s * 9), 0.65 + 0.55 * Math.sin(s * 6), 0.4 * Math.sin(s * 7 + 1));
      vis = true;
      for (var tj = 1; tj <= 9; tj++) {
        var sj = s - tj * 0.05;
        if (sj < 0) break;
        legPos(L, sj, tmpA);
        trail.x[trail.n] = tmpA.x; trail.y[trail.n] = tmpA.y; trail.z[trail.n] = tmpA.z;
        trail.n++;
      }
      break;
    }
    packet.visible = vis;
    if (!vis) trail.n = 0;
    drawSparkles(p, time);

    var hr = light(hourAt(p), g);
    var fk = clamp01((p - 0.925) / 0.075);
    stage.style.setProperty('--fade-o', (fk * fk * (3 - 2 * fk)).toFixed(3));

    var maxO = 0;
    copies.forEach(function (el) {
      var o = band(p, parseFloat(el.getAttribute('data-a')), parseFloat(el.getAttribute('data-b')));
      var oo = o < 0.01 ? 0 : o;
      el.style.opacity = oo;
      if (oo > maxO) maxO = oo;
      el.style.transform = 'translateY(' + ((1 - oo) * 18).toFixed(1) + 'px)';
      el.style.visibility = oo === 0 ? 'hidden' : 'visible';
      var live = oo > 0.5;
      if (live !== el._live) { el._live = live; el.classList.toggle('live', live); el.setAttribute('aria-hidden', live ? 'false' : 'true'); }
    });

    var so = maxO.toFixed(2);
    if (so !== lastSO) { lastSO = so; stage.style.setProperty('--scrim-o', so); }

    /* floor gauge: roof, then 5 to 1 */
    var st = [];
    var gAll = p > 0.9;
    st.push((p > 0.145 ? 'seen' : '') + (p < T.hop0 && p > 0.1 ? ' now' : ''));
    for (var fi = 0; fi < 5; fi++) {
      var fm = floorMarks[fi];
      st.push((p > fm.seen ? 'seen' : '') + (p >= fm.now0 && p < fm.now1 && !gAll ? ' now' : ''));
    }
    floorEls.forEach(function (el, i) {
      if (lastFloor[i] !== st[i]) { lastFloor[i] = st[i]; el.className = st[i]; }
    });
  }

  /* ---------- scroll -> progress ---------- */
  var target = 0, pSm = 0, pVel = 0, onScreen = true, snapNow = true, lastNow = 0, simTime = 0;
  function readScroll() {
    var rect = track.getBoundingClientRect();
    var total = rect.height - window.innerHeight;
    target = total <= 0 ? 0 : clamp01(-rect.top / total);
  }
  var navEl = document.getElementById('nav'), navScrolled = false;
  function navState() {
    var over = track.getBoundingClientRect().bottom > 56;
    var sc = !over && window.scrollY > 8;
    if (sc !== navScrolled) { navScrolled = sc; navEl.classList.toggle('scrolled', sc); }
  }
  window.addEventListener('scroll', navState, { passive: true });
  window.addEventListener('resize', navState);
  navState();
  window.addEventListener('scroll', readScroll, { passive: true });
  window.addEventListener('resize', readScroll);
  readScroll();
  if ('IntersectionObserver' in window) {
    new IntersectionObserver(function (en) { onScreen = en[0].isIntersecting; }, { threshold: 0 }).observe(track);
  }

  var fixedTime = null;
  function frame(now) {
    requestAnimationFrame(frame);
    if (document.hidden || !onScreen) { lastNow = now; return; }
    var dt = Math.min(0.05, Math.max(0.001, (now - lastNow) / 1000));
    lastNow = now;
    simTime += dt;
    var time = fixedTime == null ? simTime : fixedTime;

    if (snapNow || reduced) {
      pSm = target; pVel = 0; lean = 0;
    } else {
      var r = sdamp(pSm, target, pVel, 0.16, dt);
      pSm = r.x; pVel = r.v;
      lean = lean + (clamp01(Math.abs(pVel) * 0.6) * (pVel < 0 ? -1 : 1) - lean) * Math.min(1, dt * 6);
    }
    if (Math.abs(target - pSm) < 0.00002 && Math.abs(pVel) < 0.0005) { pSm = target; pVel = 0; }
    pSm = clamp01(pSm);

    var pr = sdamp(ptr.sx, ptr.x, ptr.vx, 0.35, dt); ptr.sx = pr.x; ptr.vx = pr.v;
    var py = sdamp(ptr.sy, ptr.y, ptr.vy, 0.35, dt); ptr.sy = py.x; ptr.vy = py.v;
    if (reduced) { ptr.sx = ptr.sy = 0; }

    sampleKeys(pSm);
    stepCamera(dt, snapNow || reduced);
    applyCamera(time);
    update(pSm, time, dt);
    renderer.render(scene, camera);
    snapNow = false;
  }
  requestAnimationFrame(frame);
  window.__story = { set: function (p, t) { target = p; snapNow = true; fixedTime = t == null ? 1.2 : t; }, sample: function (p) { sampleKeys(p); return JSON.parse(JSON.stringify(ct)); }, info: function () { return JSON.parse(JSON.stringify(renderer.info.render)); } };
})();

(function () {
  'use strict';
  var sheet = document.getElementById('sheet');
  if (!sheet) return;
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var hasIO = 'IntersectionObserver' in window;
  var $ = function (s, r) { return (r || sheet).querySelector(s); };
  var $$ = function (s, r) { return Array.prototype.slice.call((r || sheet).querySelectorAll(s)); };
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };

  /* Where "Cari" leads. Left empty here (this page is a standalone preview); in Django set it to the Plant Library URL.
     The parameter names follow the Plant model fields (sunlight_needs, difficulty_level, indoor_outdoor) as a proposal;
     both these names and the chip values (data-v in the markup) must match what the Plant Library view reads. */
  var ECO = {
    plantLibrary: document.body.getAttribute('data-plant-library-url') || '',
    params: { q: 'q', cahaya: 'sunlight', kesulitan: 'difficulty', lokasi: 'indoor_outdoor' },
    /* chip value -> the value Plant.Sunlight stores (difficulty and indoor/outdoor already match) */
    values: { full_sun: 'full', low_light: 'shade' }
  };

  sheet.classList.add('sheet-js');

  /* run fn once, the first time el is mostly on screen */
  function once(el, th, fn) {
    if (!el) return;
    if (!hasIO) { fn(); return; }
    var o = new IntersectionObserver(function (es) { if (es[0].isIntersecting) { o.disconnect(); fn(); } }, { threshold: th });
    o.observe(el);
  }

  /* stagger the Petaks so they never move in unison */
  $$('.pet').forEach(function (p, i) { p.style.setProperty('--pd', ((i * 0.83) % 3.6).toFixed(2) + 's'); });

  /* ---------- reveal on scroll ---------- */
  var rv = $$('.rv');
  if (hasIO && !reduced) {
    var io = new IntersectionObserver(function (es) {
      es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { threshold: 0.12, rootMargin: '0px 0px -6% 0px' });
    rv.forEach(function (el) { io.observe(el); });
  } else {
    rv.forEach(function (el) { el.classList.add('in'); });
  }

  /* ---------- headings: each word slides up out of a mask ---------- */
  function wrapW(content, i) {
    var w = document.createElement('span'); w.className = 'w';
    var x = document.createElement('span'); x.className = 'wi'; x.style.setProperty('--i', i);
    if (typeof content === 'string') x.textContent = content; else x.appendChild(content);
    w.appendChild(x);
    return w;
  }
  if (!reduced) {
    $$('.head h2, .faq-intro h2, .bal-copy h2').forEach(function (h) {
      var n = 0, kids = Array.prototype.slice.call(h.childNodes);
      h.textContent = '';
      kids.forEach(function (k) {
        if (k.nodeType === 3) {
          k.textContent.split(/(\s+)/).forEach(function (t) {
            if (!t) return;
            if (/^\s+$/.test(t)) h.appendChild(document.createTextNode(' '));
            else h.appendChild(wrapW(t, n++));
          });
        } else { h.appendChild(wrapW(k, n++)); }
      });
      once(h, 0.35, function () { h.classList.add('hin'); });
    });
  }

  /* ---------- tiny potted plants, shared by the finder and the plot grid ---------- */
  var POT = ['#ff9d2e', '#f4a7b9', '#95d5b2', '#fdedc9', '#8fd0f2', '#e8841a'];
  var LEAF = ['#2fbf5c', '#1f9142', '#5ccf82', '#45cf72'];
  function potSvg(kind, i) {
    var pot = POT[(i * 3 + kind) % POT.length], lf = LEAF[(i + kind) % LEAF.length], lf2 = LEAF[(i + kind + 2) % LEAF.length];
    var plant;
    if (kind === 0) plant = '<path d="M20 28V14" stroke="#1f9142" stroke-width="2.4" stroke-linecap="round" fill="none"/><path d="M20 17C13 17 9 12 9 6c6 0 11 4 11 11Z" fill="' + lf + '"/><path d="M20 14c0-7 5-11 11-11 0 6-4 11-11 11Z" fill="' + lf2 + '"/>';
    else if (kind === 1) plant = '<circle cx="14" cy="20" r="8" fill="' + lf + '"/><circle cx="26" cy="20" r="8" fill="' + lf2 + '"/><circle cx="20" cy="13" r="9" fill="' + lf + '"/>';
    else if (kind === 2) plant = '<path d="M20 28V12" stroke="#1f9142" stroke-width="2.4" stroke-linecap="round" fill="none"/><path d="M20 22c-5 0-8-3-8-7 5 0 8 3 8 7Z" fill="' + lf + '"/><g fill="' + ['#f4a7b9', '#ffd34d', '#c9a7ee', '#ff8a6b'][i % 4] + '"><circle cx="20" cy="6" r="4"/><circle cx="15" cy="10" r="4"/><circle cx="25" cy="10" r="4"/></g><circle cx="20" cy="9" r="3" fill="#ffb52e"/>';
    else plant = '<rect x="15" y="8" width="10" height="21" rx="5" fill="#4fae6b"/><rect x="8" y="15" width="6" height="9" rx="3" fill="#4fae6b"/><rect x="26" y="12" width="6" height="9" rx="3" fill="#4fae6b"/><rect x="9" y="21" width="9" height="4" rx="2" fill="#4fae6b"/><rect x="22" y="18" width="9" height="4" rx="2" fill="#4fae6b"/><circle cx="20" cy="8" r="2.6" fill="#ff8fa8"/>';
    return '<svg viewBox="0 0 40 44" aria-hidden="true">' + plant + '<path d="M10 30h20l-3 12H13z" fill="' + pot + '"/><rect x="8" y="27" width="24" height="5" rx="2.5" fill="' + pot + '"/><rect x="8" y="27" width="24" height="2" rx="1" fill="#fff" opacity=".25"/></svg>';
  }

  /* ---------- finder ---------- */
  var finder = $('#finder'), q = $('#q');
  var fpet = $('.finder-pet', finder);
  function cheer() { if (reduced || !fpet) return; fpet.classList.remove('cheer'); void fpet.offsetWidth; fpet.classList.add('cheer'); }
  var chips = $$('.chip', finder), field = $('#cmpsel', finder), groups = $$('.fg', finder);
  var XSVG = '<span class="x" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18"/></svg></span>';
  chips.forEach(function (c, i) { c._i = i; c._home = c.parentNode; });
  function isSel(c) { return c.getAttribute('aria-pressed') === 'true'; }
  function backHome(c) {
    var ref = null, sibs = Array.prototype.slice.call(c._home.children);
    for (var j = 0; j < sibs.length; j++) { if (sibs[j]._i > c._i) { ref = sibs[j]; break; } }
    c._home.insertBefore(c, ref);
  }
  function setSel(c, on) {
    c.setAttribute('aria-pressed', on ? 'true' : 'false');
    var x = c.querySelector('.x');
    if (on) {
      c.setAttribute('aria-label', 'Hapus filter ' + c.textContent.trim());
      field.appendChild(c);
      if (!x) c.insertAdjacentHTML('beforeend', XSVG);
    } else {
      if (x) x.remove();
      c.removeAttribute('aria-label');
      backHome(c);
    }
  }
  /* shared-element move: every chip glides from where it was to where it lands (first / last / invert / play) */
  function flip(mutate, lead) {
    var first = chips.map(function (e) { return e.getBoundingClientRect(); });
    mutate();
    if (reduced) return;
    chips.forEach(function (e, i) {
      var a = first[i], r = e.getBoundingClientRect(), dx = a.left - r.left, dy = a.top - r.top;
      if (!dx && !dy) return;
      if (e === lead) e.style.zIndex = 20;
      var an = e.animate([{ transform: 'translate(' + dx + 'px,' + dy + 'px)' }, { transform: 'none' }], { duration: e === lead ? 520 : 420, easing: 'cubic-bezier(.3,1.15,.5,1)' });
      an.onfinish = an.oncancel = function () { e.style.zIndex = ''; };
    });
  }
  function toggle(c) {
    var on = !isSel(c);
    flip(function () {
      if (on) chips.forEach(function (o) { if (o !== c && o.dataset.k === c.dataset.k && isSel(o)) setSel(o, false); });
      setSel(c, on);
      groups.forEach(function (g) { g.classList.toggle('done', !!g.querySelector('.fchips') && !g.querySelector('.fchips').children.length); });
    }, c);
    c.focus({ preventScroll: true });
    cheer();
  }
  chips.forEach(function (c) { c.addEventListener('click', function () { toggle(c); }); });
  q.addEventListener('keydown', function (e) {
    if (e.key !== 'Backspace' || q.value) return;
    var prev = field.lastElementChild;
    if (prev) toggle(prev);
  });
  /* the search box suggests plants by typing them out, and stops the moment someone focuses it or types */
  if (!reduced) {
    var WORDS = ['tanaman yang menghasilkan dan mudah dirawat oleh anak kos', 'kemangi untuk balkon kecil', 'tanaman yang tahan lupa disiram', 'cabai rawit'], wi = 0, ci = 0, del = false, finderVisible = false;
    if (hasIO) new IntersectionObserver(function (es) { finderVisible = es[0].isIntersecting; }, { threshold: 0.2 }).observe(finder);
    (function tick() {
      var d = 100;
      if (!finderVisible || document.activeElement === q || q.value) { q.placeholder = 'Cari tanaman…'; ci = 0; del = false; setTimeout(tick, 700); return; }
      var w = WORDS[wi];
      if (!del) { ci++; if (ci >= w.length) { del = true; d = 2200; } else d = 58; }
      else { ci--; d = 18; if (ci <= 0) { del = false; ci = 0; wi = (wi + 1) % WORDS.length; d = 400; } }
      q.placeholder = ci ? 'Coba “' + w.slice(0, ci) + '”' : 'Cari tanaman…';
      setTimeout(tick, d);
    })();
  }
  /* ---------- search: a small working preview ----------
     This is sample data so the page can be tried on its own. In Django, set ECO.plantLibrary and the form
     redirects to the real Plant Library with the same query + filters instead (and none of this runs). */
  var PLANTS = [
    { n: 'Cabai rawit', c: 'Sayur dan buah', s: 'full_sun', d: 'medium', l: ['outdoor'], y: 1 },
    { n: 'Tomat ceri', c: 'Sayur dan buah', s: 'full_sun', d: 'medium', l: ['outdoor'], y: 1 },
    { n: 'Kemangi', c: 'Herbal', s: 'full_sun', d: 'easy', l: ['outdoor', 'indoor'], y: 1 },
    { n: 'Selada', c: 'Sayur', s: 'low_light', d: 'easy', l: ['indoor', 'outdoor'], y: 1 },
    { n: 'Kangkung', c: 'Sayur', s: 'full_sun', d: 'easy', l: ['outdoor', 'indoor'], y: 1 },
    { n: 'Bayam', c: 'Sayur', s: 'full_sun', d: 'easy', l: ['outdoor'], y: 1 },
    { n: 'Daun bawang', c: 'Bumbu', s: 'full_sun', d: 'easy', l: ['indoor', 'outdoor'], y: 1 },
    { n: 'Mint', c: 'Herbal', s: 'low_light', d: 'easy', l: ['indoor', 'outdoor'], y: 1 },
    { n: 'Terong', c: 'Sayur dan buah', s: 'full_sun', d: 'medium', l: ['outdoor'], y: 1 },
    { n: 'Lidah buaya', c: 'Tanaman obat', s: 'full_sun', d: 'easy', l: ['indoor', 'outdoor'], y: 0 },
    { n: 'Sirih gading', c: 'Tanaman hias', s: 'low_light', d: 'easy', l: ['indoor'], y: 0 }
  ];
  var LBL = { full_sun: 'Cahaya penuh', low_light: 'Teduh', easy: 'Mudah', medium: 'Sedang', indoor: 'Indoor', outdoor: 'Outdoor' };
  var STOP = /^(tanaman|yang|dan|oleh|untuk|di|dari|ke|dengan|anak|buat|cari|carikan|saya|aku|ingin|mau|apa|dirawat|merawat|rawat|perawatan|ruang|ruangan|kamar|nya|atau|tapi|bisa|yg)$/;
  /* read a sentence the way a person means it: "mudah dirawat", "anak kos", "menghasilkan" */
  function readQuery(text) {
    var s = ' ' + text.toLowerCase().replace(/[^a-z0-9\s]/g, ' ') + ' ', hit = { want: {}, notes: [], rest: [] };
    function take(re, fn, note) { if (re.test(s)) { s = s.replace(re, ' '); fn(); if (note) hit.notes.push(note); } }
    take(/\s(menghasilkan|dipanen|panen|produktif|bisa dimakan|dimakan|konsumsi)\s/g, function () { hit.want.y = 1; }, 'bisa dipanen');
    take(/\s(mudah|gampang|pemula|tahan lupa|ga ribet|nggak ribet)\s/g, function () { hit.want.d = 'easy'; }, 'mudah dirawat');
    take(/\s(kos|kost|kamar|dalam ruangan|dalam rumah|indoor|apartemen)\s/g, function () { hit.want.l = 'indoor'; }, 'indoor');
    take(/\s(balkon|teras|halaman|outdoor|luar ruangan|rooftop|atap)\s/g, function () { hit.want.l = 'outdoor'; }, 'outdoor');
    take(/\s(teduh|minim cahaya|kurang cahaya|gelap|redup)\s/g, function () { hit.want.s = 'low_light'; }, 'teduh');
    take(/\s(cahaya penuh|terik|panas|matahari)\s/g, function () { hit.want.s = 'full_sun'; }, 'cahaya penuh');
    hit.rest = s.split(/\s+/).filter(function (w) { return w && !STOP.test(w); });
    return hit;
  }
  function findPlants() {
    var hit = readQuery(q.value || ''), want = hit.want;
    chips.forEach(function (c) {
      if (!isSel(c)) return;
      if (c.dataset.k === 'cahaya') want.s = c.dataset.v;
      if (c.dataset.k === 'kesulitan') want.d = c.dataset.v;
      if (c.dataset.k === 'lokasi') want.l = c.dataset.v;
    });
    var list = PLANTS.filter(function (p) {
      if (want.s && p.s !== want.s) return false;
      if (want.d && p.d !== want.d) return false;
      if (want.l && p.l.indexOf(want.l) < 0) return false;
      if (want.y && !p.y) return false;
      var hay = (p.n + ' ' + p.c).toLowerCase();
      return hit.rest.every(function (w) { return hay.indexOf(w) >= 0; });
    });
    return { list: list, notes: hit.notes };
  }
  var fres = $('#fres');
  function metaOf(p) { return [LBL[p.s], LBL[p.d], p.l.map(function (x) { return LBL[x]; }).join(' / ')].join(' · '); }
  function esc(t) { return String(t).replace(/[&<>"]/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[m]; }); }
  function anyInput() { return q.value.trim() || chips.some(isSel); }
  function renderResults(force) {
    if (!fres) return;
    if (!anyInput()) { fres.hidden = !force; fres.innerHTML = force ? '<p class="fres-hint">Ketik nama tanaman atau pilih filter dulu, lalu tekan panah.</p>' : ''; return; }
    var r = findPlants(), shown = r.list.slice(0, 4), h = '';
    h += '<div class="fres-head"><b>' + (r.list.length ? r.list.length + ' tanaman cocok' : 'Belum ada yang cocok') + '</b>';
    if (r.notes.length) h += '<span class="fres-read">Dibaca sebagai: ' + r.notes.map(esc).join(', ') + '</span>';
    h += '<span class="fres-eg">Contoh hasil. Di EcoPatch diambil dari Plant Library.</span></div>';
    if (shown.length) {
      h += '<ul class="fres-list">' + shown.map(function (p, i) {
        return '<li style="--k:' + i + '"><span class="fp" aria-hidden="true">' + potSvg(i % 4, i + 3) + '</span><span class="fn"><b>' + esc(p.n) + '</b><small>' + esc(metaOf(p)) + '</small></span>' + (p.y ? '<em>Bisa dipanen</em>' : '') + '</li>';
      }).join('') + '</ul>';
      h += '<a class="fres-more" href="' + (ECO.plantLibrary || '#plant-library') + '">' + (r.list.length > shown.length ? 'Lihat ' + r.list.length + ' tanaman' : 'Lihat di') + ' Plant Library <svg class="ico" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h14M13 6l6 6-6 6"/></svg></a>';
    } else {
      h += '<p class="fres-hint">Coba kurangi filter atau ganti kata kuncinya.</p><button type="button" class="fres-clear">Hapus semua filter</button>';
    }
    fres.hidden = false; fres.innerHTML = h;
    var clr = $('.fres-clear', fres);
    if (clr) clr.addEventListener('click', function () { chips.filter(isSel).forEach(function (c) { setSel(c, false); }); groups.forEach(function (g) { g.classList.remove('done'); }); q.value = ''; renderResults(false); q.focus(); });
  }
  var liveT = null;
  function live() { if (ECO.plantLibrary) return; clearTimeout(liveT); liveT = setTimeout(function () { renderResults(false); }, 180); }
  q.addEventListener('input', live);
  chips.forEach(function (c) { c.addEventListener('click', live); });
  finder.addEventListener('submit', function (e) {
    e.preventDefault();
    if (ECO.plantLibrary) {
      var p = [];
      if (q.value.trim()) p.push(ECO.params.q + '=' + encodeURIComponent(q.value.trim()));
      chips.forEach(function (c) { if (isSel(c)) p.push(ECO.params[c.dataset.k] + '=' + encodeURIComponent(ECO.values[c.dataset.v] || c.dataset.v)); });
      window.location.href = ECO.plantLibrary + (p.length ? '?' + p.join('&') : '');
      return;
    }
    renderResults(true);
  });

  /* ---------- fitur: four name cards on a clothesline ---------- */
  var hang = $('#hang'), cards = $$('.hc', hang), N = cards.length;
  var timers = cards.map(function () { return []; });
  function later(i, fn, ms) { timers[i].push(setTimeout(fn, ms)); }
  function stopTimers(i) { timers[i].forEach(clearTimeout); timers[i] = []; }
  function hop(i) {
    var c = cards[i];
    if (!c || reduced) return;
    c.classList.remove('jig'); void c.offsetWidth; c.classList.add('jig');
    setTimeout(function () { c.classList.remove('jig'); }, 650);
  }

  /* My EcoPatch: a plot that plants itself, then is yours to click */
  var grid = $('#plotgrid'), cap = $('#plotcap'), CELLS = 12, start = { 0: 1, 2: 1, 5: 1, 6: 1 }, AUTO = [1, 3, 7, 8, 10], cells = [];
  function countCap() {
    var n = $$('.cell[aria-pressed="true"]', grid).length;
    cap.textContent = n + ' dari ' + CELLS + ' petak terisi' + (n === CELLS ? '. Kebunmu penuh!' : '. Contoh denah balkon. Coba klik petaknya.');
  }
  for (var c = 0; c < CELLS; c++) {
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'cell'; b.setAttribute('aria-pressed', start[c] ? 'true' : 'false'); b.setAttribute('aria-label', 'Petak ' + (c + 1));
    b.innerHTML = potSvg((c * 7 + 1) % 4, c);
    b.addEventListener('click', function () {
      var on = this.getAttribute('aria-pressed') !== 'true';
      this.setAttribute('aria-pressed', on ? 'true' : 'false');
      countCap();
      if (on) hop(0);
    });
    grid.appendChild(b); cells.push(b);
  }
  if (reduced) AUTO.forEach(function (i) { cells[i].setAttribute('aria-pressed', 'true'); });
  countCap();
  function playPlot() {
    cells.forEach(function (el, i) { el.setAttribute('aria-pressed', start[i] ? 'true' : 'false'); });
    countCap();
    AUTO.forEach(function (ci, k) {
      later(0, function () { cells[ci].setAttribute('aria-pressed', 'true'); countCap(); if (k === AUTO.length - 1) hop(0); }, 350 + k * 260);
    });
  }

  /* Smart Care: the weather turns rainy, the advice appears, a task gets done (everything stays clickable) */
  var tasks = $$('#tasks input'), tcap = $('#taskcap');
  var wx = $('.wx'), wxT = $('.wx-t'), wxS = $('.wx-s'), adv = $('#wxadv');
  function taskCap() {
    var n = tasks.filter(function (t) { return t.checked; }).length;
    tcap.textContent = n === tasks.length ? 'Semua beres. Tanamanmu senang!' : n + ' dari ' + tasks.length + ' tugas selesai hari ini.';
  }
  function setWx(rain) {
    wx.dataset.state = rain ? 'rain' : 'sun';
    wxT.textContent = rain ? '27°C' : '31°C';
    wxS.textContent = rain ? 'Hujan · peluang 70% · Jakarta' : 'Cerah berawan · Jakarta';
    adv.classList.toggle('show', rain);
  }
  tasks.forEach(function (t) { t.addEventListener('change', function () { taskCap(); if (t.checked) hop(1); }); });
  function playCare() {
    setWx(false); tasks[0].checked = true; tasks[1].checked = false; tasks[2].checked = false; taskCap();
    later(1, function () { setWx(true); }, 900);
    later(1, function () { tasks[1].checked = true; taskCap(); hop(1); }, 2400);
  }
  taskCap();

  /* Garden Journal: a plant's notebook. A note is typed, saved, and the condition and count change with it */
  var jbBadge = $('.jb-badge'), jbN = $('#jbn'), jbNote = $('#jbnote');
  var NOTES = [{ t: 'Bunga pertama mulai mekar', c: 'flowering', l: 'Flowering', n: 2 }, { t: 'Buah sudah siap dipanen', c: 'harvest', l: 'Ready to Harvest', n: 3 }];
  function setJb(c, l, n, pop) {
    jbBadge.dataset.c = c; jbBadge.textContent = l; jbN.textContent = n;
    if (pop && !reduced) { jbBadge.classList.remove('pop'); void jbBadge.offsetWidth; jbBadge.classList.add('pop'); }
  }
  function typeNote(at, text) {
    later(2, function () { jbNote.classList.add('typing'); }, at);
    for (var k = 1; k <= text.length; k++) (function (k) { later(2, function () { jbNote.textContent = text.slice(0, k); }, at + k * 48); })(k);
    return at + text.length * 48;
  }
  function playTl() {
    setJb('healthy', 'Healthy', 1); jbNote.textContent = ''; jbNote.classList.remove('typing');
    var at = 450;
    NOTES.forEach(function (nt, i) {
      var end = typeNote(at, nt.t);
      later(2, function () { jbNote.classList.remove('typing'); setJb(nt.c, nt.l, nt.n, true); hop(2); }, end + 350);
      later(2, function () { jbNote.textContent = ''; }, end + 900);
      at = end + 1100;
    });
  }
  if (reduced) setJb('harvest', 'Ready to Harvest', 3, false);

  /* Seed Exchange: two seeds cross between the balconies, and the listing moves through its statuses */
  var sx = $('#sx'), sxst = $$('#sxst i');
  function setSt(n) { sxst.forEach(function (el, i) { el.classList.toggle('on', i === n); }); }
  function playSx() {
    setSt(0);
    if (reduced) return;
    $$('animateMotion', sx).forEach(function (a) { if (a.beginElement) a.beginElement(); });
    later(3, function () { setSt(1); }, 2300);
    later(3, function () { setSt(2); hop(3); }, 4300);
  }
  var PLAY = [playPlot, playCare, playTl, playSx];

  /* turning a card over: the back plays its own demo */
  function turnCard(i, on) {
    var c = cards[i], front = $('.front', c), back = $('.back', c), turn = $('.turn', c);
    if (on === undefined) on = !c.classList.contains('flipped');
    c.classList.toggle('flipped', on);
    front.inert = on; back.inert = !on;
    turn.setAttribute('aria-expanded', on ? 'true' : 'false');
    stopTimers(i);
    if (on && !reduced) later(i, PLAY[i], 420);
    if (on) later(i, function () { var u = $('.unturn', c); if (u && document.activeElement === turn) u.focus({ preventScroll: true }); }, 300);
    else later(i, function () { turn.focus({ preventScroll: true }); }, 0);
  }
  cards.forEach(function (c, i) {
    $('.front', c).addEventListener('click', function () { turnCard(i, true); });
    $('.unturn', c).addEventListener('click', function () { turnCard(i, false); });
    /* the card follows the pointer a little, and the light follows it too */
    if (reduced) return;
    c.addEventListener('pointermove', function (e) {
      if (e.pointerType === 'touch') return;
      var r = c.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
      var t = $('.hc-tilt', c);
      t.style.setProperty('--ry', ((x - 0.5) * 10).toFixed(2) + 'deg');
      t.style.setProperty('--rx', ((0.5 - y) * 8).toFixed(2) + 'deg');
      c.style.setProperty('--mx', (x * 100).toFixed(1) + '%'); c.style.setProperty('--my', (y * 100).toFixed(1) + '%'); c.style.setProperty('--mx-n', x.toFixed(3));
    });
    c.addEventListener('pointerleave', function () { var t = $('.hc-tilt', c); t.style.setProperty('--rx', '0deg'); t.style.setProperty('--ry', '0deg'); });
  });
  /* they drop onto the line when they come into view; the first one turns over by itself, once, to show there is a demo */
  once(hang, 0.3, function () {
    hang.classList.add('in');
    if (reduced) return;
    later(0, function () { if (!cards[0].classList.contains('flipped')) turnCard(0, true); }, 3000);
  });

  /* ---------- FAQ as a chat with Petak: tap a question, the answer opens right under it ---------- */
  var chat = $('#chat'), sugg = $('#sugg'), avTpl = $('#avtpl'), rest = $('#rest');
  function syncRest() { rest.classList.toggle('open', !qa.some(function (it) { return it.ans.classList.contains('open'); })); }
  var qa = $$('.q', sugg).map(function (btn, n) {
    var wrap = document.createElement('div'); wrap.className = 'qa';
    var ans = document.createElement('div'); ans.className = 'ans'; ans.id = 'ans' + n;
    ans.innerHTML = '<div class="ans-in"><div class="msg"><span class="av" aria-hidden="true">' + (avTpl ? avTpl.innerHTML : '') + '</span><p></p></div></div>';
    btn.parentNode.insertBefore(wrap, btn); wrap.appendChild(btn); wrap.appendChild(ans);
    btn.setAttribute('aria-expanded', 'false'); btn.setAttribute('aria-controls', ans.id);
    return { btn: btn, ans: ans, p: $('p', ans), text: btn.dataset.a, shown: false, t: [] };
  });
  function esc2(t) { return t.replace(/[&<>]/g, function (m) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;' }[m]; }); }
  function full(it) { it.p.innerHTML = '<span class="sr">' + esc2(it.text) + '</span><span aria-hidden="true">' + esc2(it.text) + '</span>'; it.shown = true; }
  function openQ(it) {
    it.btn.setAttribute('aria-expanded', 'true'); it.ans.classList.add('open'); syncRest();
    if (it.shown) return;
    if (reduced) { full(it); return; }
    it.p.innerHTML = '<span class="dots" aria-hidden="true"><i></i><i></i><i></i></span>';
    var words = it.text.split(' ');
    it.t.push(setTimeout(function () {
      var k = 0; it.p.innerHTML = '<span aria-hidden="true"></span>'; var out = it.p.firstChild;
      (function step() { k++; out.textContent = words.slice(0, k).join(' '); if (k < words.length) it.t.push(setTimeout(step, 42)); else full(it); })();
    }, 800));
  }
  function closeQ(it) {
    it.t.forEach(clearTimeout); it.t = [];
    it.btn.setAttribute('aria-expanded', 'false'); it.ans.classList.remove('open'); syncRest();
  }
  qa.forEach(function (it) {
    it.btn.addEventListener('click', function () {
      if (it.btn.getAttribute('aria-expanded') === 'true') { closeQ(it); return; }
      /* one answer at a time: opening a question closes the others */
      qa.forEach(function (other) { if (other !== it) closeQ(other); });
      openQ(it);
    });
  });
  /* the first question opens by itself, so the page shows what this is */
  once(chat, 0.5, function () { setTimeout(function () { if (!qa.some(function (it) { return it.ans.classList.contains('open'); })) openQ(qa[0]); }, reduced ? 0 : 500); });

  /* closing bed: the petak grow one after another when it scrolls into view */
  var bal = $('#bal');
  once(bal, 0.3, function () { bal.classList.add('in'); });
  if (!reduced) bal.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch') return;
    var r = bal.getBoundingClientRect(); bal.style.setProperty('--px', (((e.clientX - r.left) / r.width) * 2 - 1).toFixed(3));
  }, { passive: true });

  /* Petak looks at the pointer */
  var pets = $$('.pet'), px = -1, py = -1, gazeQueued = false;
  function gaze() {
    gazeQueued = false;
    pets.forEach(function (p) {
      var r = p.getBoundingClientRect();
      if (r.bottom < 0 || r.top > window.innerHeight || !r.width) return;
      var dx = px - (r.left + r.width * 0.5), dy = py - (r.top + r.height * 0.6), d = Math.sqrt(dx * dx + dy * dy) || 1, k = Math.min(1, d / 260);
      p.style.setProperty('--gx', (dx / d * 6 * k).toFixed(1) + 'px');
      p.style.setProperty('--gy', (dy / d * 4 * k).toFixed(1) + 'px');
    });
  }
  if (!reduced) window.addEventListener('pointermove', function (e) {
    if (e.pointerType === 'touch') return;
    px = e.clientX; py = e.clientY;
    if (!gazeQueued) { gazeQueued = true; requestAnimationFrame(gaze); }
  }, { passive: true });

  /* the vine on the left edge grows with the page */
  var stem = $('.vstem'), leaves = $$('.vl'), vineIn = $('.vine-in');
  function updVine() {
    if (!stem || !stem.getBoundingClientRect().height) return;
    var r = sheet.getBoundingClientRect(), p = clamp((window.innerHeight - r.top) / r.height, 0, 1);
    stem.style.strokeDashoffset = (1 - p).toFixed(4);
    /* once the sheet runs out, the vine bows out instead of hanging in the air */
    var gone = clamp((window.innerHeight - r.bottom) / (window.innerHeight * 0.22), 0, 1);
    vineIn.style.opacity = (1 - gone).toFixed(3);
    vineIn.style.transform = 'translateY(' + (gone * 40).toFixed(1) + 'px)';
    leaves.forEach(function (l) { l.classList.toggle('on', p >= +l.dataset.t); });
  }

  var queued = false;
  function onScroll() { if (queued) return; queued = true; requestAnimationFrame(function () { queued = false; updVine(); }); }
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('resize', onScroll);
  updVine();
})();
