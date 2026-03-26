/* ── FX.js — Animaciones y efectos especiales ──────────────────────────────
   Tecnologías: Canvas 2D API, Web Audio API, CSS @keyframes, WAAPI
   Sin dependencias externas. Funciona 100% offline.
   Expone: window.FX
   Inicialización: FX.init() desde DOMContentLoaded (app.js)
   ─────────────────────────────────────────────────────────────────────── */

window.FX = (() => {
  'use strict';

  /* ── Estado interno ───────────────────────────────────────────────── */
  let _audioCtx = null;
  let _canvas = null;
  let _ctx2d = null;
  let _tiltListeners = new WeakMap(); // card → { move, leave }
  let _soundEnabled = false;          // estado local — se sincroniza en init() y con toggleSound()

  const _lightningState = {
    active: false,
    sx: 0, sy: 0,    // source center
    cx: 0, cy: 0,    // current cursor
    rafId: null,
  };

  /* ── Audio context (lazy) ─────────────────────────────────────────── */
  async function _ensureAudioCtx() {
    if (!_audioCtx) {
      try {
        _audioCtx = new (window.AudioContext || window['webkitAudioContext'])();
      } catch (e) {
        _audioCtx = null;
        return null;
      }
    }
    // Algunos navegadores crean el contexto en estado "suspended"; reanudar aquí
    if (_audioCtx.state === 'suspended') {
      try { await _audioCtx.resume(); } catch (e) {}
    }
    return _audioCtx;
  }

  /* ── Preference helper ────────────────────────────────────────────── */
  function soundEnabled() {
    return _soundEnabled;
  }

  // Actualiza el estado local y reproduce preview; el guardado lo hace settings.js
  async function toggleSound(enabled) {
    _soundEnabled = enabled;
    if (enabled) {
      const ctx = await _ensureAudioCtx();
      if (ctx) sound._playBell(ctx);
    }
  }

  /* ════════════════════════════════════════════════════════════════════
     TILT — Rotación 3D de tarjetas al mouseover
     ════════════════════════════════════════════════════════════════════ */
  const tilt = {
    attach(card) {
      if (_tiltListeners.has(card)) return; // ya adjuntado

      const onMove = (e) => tilt._onMove(e, card);
      const onLeave = () => tilt._onLeave(card);

      card.addEventListener('mousemove', onMove, { passive: true });
      card.addEventListener('mouseleave', onLeave, { passive: true });
      _tiltListeners.set(card, { onMove, onLeave });
    },

    detach(card) {
      const listeners = _tiltListeners.get(card);
      if (!listeners) return;
      card.removeEventListener('mousemove', listeners.onMove);
      card.removeEventListener('mouseleave', listeners.onLeave);
      _tiltListeners.delete(card);
      card.style.transform = '';
    },

    attachAll() {
      document.querySelectorAll('.card').forEach(card => tilt.attach(card));
    },

    _onMove(e, card) {
      if (_lightningState.active) return; // no tilt durante drag
      const rect = card.getBoundingClientRect();
      const x = ((e.clientX - rect.left) / rect.width - 0.5) * 2;   // -1 → 1
      const y = ((e.clientY - rect.top) / rect.height - 0.5) * 2;   // -1 → 1
      const rotY =  x * 14;   // ±14°
      const rotX = -y * 14;   // ±14°
      card.style.transform =
        `perspective(550px) rotateY(${rotY}deg) rotateX(${rotX}deg) translateY(-3px)`;
    },

    _onLeave(card) {
      // CSS transition en .card ya incluye "transition: transform .15s"
      card.style.transform = '';
    },
  };

  /* ════════════════════════════════════════════════════════════════════
     LIGHTNING — Rayo eléctrico fractal durante drag
     ════════════════════════════════════════════════════════════════════ */
  const lightning = {
    start(sourceEl) {
      if (!_ctx2d) return;
      const rect = sourceEl.getBoundingClientRect();
      _lightningState.sx = rect.left + rect.width / 2;
      _lightningState.sy = rect.top + rect.height / 2;
      _lightningState.cx = _lightningState.sx;
      _lightningState.cy = _lightningState.sy;
      _lightningState.active = true;
      lightning._loop();
    },

    update(x, y) {
      _lightningState.cx = x;
      _lightningState.cy = y;
    },

    stop(success) {
      _lightningState.active = false;
      if (_lightningState.rafId) {
        cancelAnimationFrame(_lightningState.rafId);
        _lightningState.rafId = null;
      }
      if (_ctx2d && _canvas) {
        _ctx2d.clearRect(0, 0, _canvas.width, _canvas.height);
      }
      if (success) sound.drop(true);
    },

    _loop() {
      if (!_lightningState.active) return;
      lightning._bolt(
        _lightningState.sx, _lightningState.sy,
        _lightningState.cx, _lightningState.cy
      );
      _lightningState.rafId = requestAnimationFrame(() => lightning._loop());
    },

    /* Midpoint displacement recursivo — el Math.random() por frame produce flicker */
    _draw(x1, y1, x2, y2, color, lineWidth, depth) {
      if (depth === 0) {
        _ctx2d.beginPath();
        _ctx2d.moveTo(x1, y1);
        _ctx2d.lineTo(x2, y2);
        _ctx2d.strokeStyle = color;
        _ctx2d.lineWidth = lineWidth;
        _ctx2d.stroke();
        return;
      }
      let mx = (x1 + x2) / 2;
      let my = (y1 + y2) / 2;
      const dx = x2 - x1;
      const dy = y2 - y1;
      const len = Math.sqrt(dx * dx + dy * dy);
      if (len < 1) return;
      const disp = (Math.random() - 0.5) * len * 0.45;
      const perpX = -dy / len;
      const perpY =  dx / len;
      mx += perpX * disp;
      my += perpY * disp;

      lightning._draw(x1, y1, mx, my, color, lineWidth, depth - 1);
      lightning._draw(mx, my, x2, y2, color, lineWidth, depth - 1);

      // Rama lateral con 30% de probabilidad a partir de profundidad 3
      if (depth >= 3 && Math.random() < 0.30) {
        const branchFactor = len * 0.35 * (Math.random() * 0.4 + 0.3);
        const bx = mx + perpX * branchFactor;
        const by = my + perpY * branchFactor;
        lightning._draw(mx, my, bx, by, color, lineWidth * 0.5, depth - 2);
      }
    },

    _bolt(x1, y1, x2, y2) {
      if (!_ctx2d || !_canvas) return;
      _ctx2d.clearRect(0, 0, _canvas.width, _canvas.height);
      // Capa glow (debajo, más ancha y translúcida)
      _ctx2d.globalAlpha = 0.25;
      lightning._draw(x1, y1, x2, y2, '#88aaff', 5.0, 4);
      // Capa nítida (encima)
      _ctx2d.globalAlpha = 0.90;
      lightning._draw(x1, y1, x2, y2, '#c8e6ff', 2.0, 6);
      _ctx2d.globalAlpha = 1.0;
    },
  };

  /* ════════════════════════════════════════════════════════════════════
     SOUND — Síntesis Web Audio API
     ════════════════════════════════════════════════════════════════════ */
  const sound = {
    async drag() {
      if (!soundEnabled()) return;
      const ctx = await _ensureAudioCtx();
      if (ctx) sound._playBuzz(ctx);
    },

    async drop(success) {
      if (!soundEnabled()) return;
      const ctx = await _ensureAudioCtx();
      if (!ctx) return;
      if (success) sound._playThud(ctx);
    },

    async confirm() {
      if (!soundEnabled()) return;
      const ctx = await _ensureAudioCtx();
      if (ctx) sound._playConfirm(ctx);
    },

    async cancel() {
      if (!soundEnabled()) return;
      const ctx = await _ensureAudioCtx();
      if (ctx) sound._playCancel(ctx);
    },

    async page() {
      if (!soundEnabled()) return;
      const ctx = await _ensureAudioCtx();
      if (ctx) sound._playPage(ctx);
    },

    /* Buzz eléctrico — sawtooth + LFO que modula el gain */
    _playBuzz(ctx) {
      try {
        const now = ctx.currentTime;
        const dur = 0.35;

        const osc = ctx.createOscillator();
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(80, now);
        osc.frequency.linearRampToValueAtTime(120, now + 0.1);
        osc.frequency.linearRampToValueAtTime(60, now + dur);

        const lfo = ctx.createOscillator();
        lfo.type = 'square';
        lfo.frequency.setValueAtTime(60, now);

        const lfoGain = ctx.createGain();
        lfoGain.gain.setValueAtTime(0.35, now);

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0, now);
        gain.gain.linearRampToValueAtTime(0.35, now + 0.02);
        gain.gain.linearRampToValueAtTime(0.18, now + 0.1);
        gain.gain.setValueAtTime(0.18, now + dur - 0.05);
        gain.gain.linearRampToValueAtTime(0, now + dur);

        lfo.connect(lfoGain);
        lfoGain.connect(gain.gain);
        osc.connect(gain);
        gain.connect(ctx.destination);

        osc.start(now);
        osc.stop(now + dur);
        lfo.start(now);
        lfo.stop(now + dur);
      } catch (e) {}
    },

    /* Crash/thud — white noise + lowpass + sine sub-bass */
    _playThud(ctx) {
      try {
        const now = ctx.currentTime;
        const dur = 0.4;

        // White noise buffer
        const bufSize = Math.ceil(ctx.sampleRate * 0.5);
        const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) data[i] = Math.random() * 2 - 1;

        const noise = ctx.createBufferSource();
        noise.buffer = buf;

        const filter = ctx.createBiquadFilter();
        filter.type = 'lowpass';
        filter.frequency.setValueAtTime(400, now);
        filter.frequency.exponentialRampToValueAtTime(80, now + dur);
        filter.Q.value = 0.5;

        const noiseGain = ctx.createGain();
        noiseGain.gain.setValueAtTime(0.55, now);
        noiseGain.gain.exponentialRampToValueAtTime(0.001, now + dur);

        // Sub-bass punch
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(100, now);
        osc.frequency.exponentialRampToValueAtTime(30, now + 0.15);

        const oscGain = ctx.createGain();
        oscGain.gain.setValueAtTime(0.7, now);
        oscGain.gain.exponentialRampToValueAtTime(0.001, now + 0.2);

        noise.connect(filter);
        filter.connect(noiseGain);
        noiseGain.connect(ctx.destination);
        osc.connect(oscGain);
        oscGain.connect(ctx.destination);

        noise.start(now);
        osc.start(now);
        osc.stop(now + 0.2);
      } catch (e) {}
    },

    /* Acept — dos notas ascendentes al confirmar diálogo */
    _playConfirm(ctx) {
      try {
        const now = ctx.currentTime;
        [660, 880].forEach((freq, i) => {
          const osc = ctx.createOscillator();
          osc.type = 'sine';
          osc.frequency.value = freq;
          const gain = ctx.createGain();
          const t0 = now + i * 0.07;
          gain.gain.setValueAtTime(0, t0);
          gain.gain.linearRampToValueAtTime(0.20, t0 + 0.01);
          gain.gain.exponentialRampToValueAtTime(0.001, t0 + 0.28);
          osc.connect(gain);
          gain.connect(ctx.destination);
          osc.start(t0);
          osc.stop(t0 + 0.28);
        });
      } catch (e) {}
    },

    /* Cancel — nota descendente al cerrar/cancelar diálogo */
    _playCancel(ctx) {
      try {
        const now = ctx.currentTime;
        const osc = ctx.createOscillator();
        osc.type = 'sine';
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.linearRampToValueAtTime(280, now + 0.18);
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.14, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.18);
        osc.connect(gain);
        gain.connect(ctx.destination);
        osc.start(now);
        osc.stop(now + 0.18);
      } catch (e) {}
    },

    /* Page — susurro suave al cambiar de vista */
    _playPage(ctx) {
      try {
        const now = ctx.currentTime;
        const dur = 0.12;
        const bufSize = Math.ceil(ctx.sampleRate * dur);
        const buf = ctx.createBuffer(1, bufSize, ctx.sampleRate);
        const data = buf.getChannelData(0);
        for (let i = 0; i < bufSize; i++) data[i] = Math.random() * 2 - 1;
        const noise = ctx.createBufferSource();
        noise.buffer = buf;
        const filter = ctx.createBiquadFilter();
        filter.type = 'highpass';
        filter.frequency.setValueAtTime(3000, now);
        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.06, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + dur);
        noise.connect(filter);
        filter.connect(gain);
        gain.connect(ctx.destination);
        noise.start(now);
      } catch (e) {}
    },

    /* Campana — preview al activar sonidos */
    _playBell(ctx) {
      try {
        const now = ctx.currentTime;

        const osc1 = ctx.createOscillator();
        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(880, now);

        const osc2 = ctx.createOscillator();
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(1108, now);  // quinta justa

        const gain = ctx.createGain();
        gain.gain.setValueAtTime(0.28, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.8);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(ctx.destination);

        osc1.start(now); osc1.stop(now + 0.8);
        osc2.start(now); osc2.stop(now + 0.8);
      } catch (e) {}
    },
  };

  /* ════════════════════════════════════════════════════════════════════
     RIPPLE — Efecto onda en botones al hacer click
     ════════════════════════════════════════════════════════════════════ */
  const ripple = {
    init() {
      document.addEventListener('click', (e) => {
        const btn = e.target.closest('button, [data-ripple]');
        if (!btn) return;
        if (btn.dataset.noRipple !== undefined) return;
        ripple._spawn(e.clientX, e.clientY, btn);
      }, { passive: true });
    },

    _spawn(x, y, btn) {
      const rect = btn.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height) * 2;
      const span = document.createElement('span');
      span.className = 'btn-ripple';
      span.style.cssText = [
        `width:${size}px`,
        `height:${size}px`,
        `left:${x - rect.left - size / 2}px`,
        `top:${y - rect.top - size / 2}px`,
      ].join(';');

      // Asegurar overflow:hidden y position:relative en el host
      const cs = getComputedStyle(btn);
      if (cs.position === 'static') btn.style.position = 'relative';
      if (cs.overflow === 'visible') btn.style.overflow = 'hidden';

      btn.appendChild(span);
      span.addEventListener('animationend', () => span.remove(), { once: true });
    },
  };

  /* ════════════════════════════════════════════════════════════════════
     TRANSITION — Transición fade-slide entre vistas
     ════════════════════════════════════════════════════════════════════ */
  const transition = {
    out(el) {
      return new Promise(resolve => {
        el.classList.add('fx-view-leaving');
        el.addEventListener('animationend', () => {
          el.classList.remove('fx-view-leaving');
          resolve();
        }, { once: true });
        // Safety fallback si animationend no dispara (display:none, etc.)
        setTimeout(resolve, 200);
      });
    },

    in(el) {
      el.classList.add('fx-view-entering');
      el.addEventListener('animationend', () => {
        el.classList.remove('fx-view-entering');
      }, { once: true });
    },
  };

  /* ════════════════════════════════════════════════════════════════════
     STAGGER — Entrada en cascada de filas de tabla
     ════════════════════════════════════════════════════════════════════ */
  const stagger = {
    rows(container) {
      if (!container) return;
      // Incluir tanto <tr> como filas de listas y cards de reportes
      const rows = container.querySelectorAll('tr:not(.fx-staggered), .report-row:not(.fx-staggered)');
      rows.forEach((row, i) => {
        row.classList.add('fx-row-stagger', 'fx-staggered');
        row.style.animationDelay = `${Math.min(i * 30, 420)}ms`;
      });
    },
  };

  /* ════════════════════════════════════════════════════════════════════
     INIT — Punto de entrada
     ════════════════════════════════════════════════════════════════════ */
  function init() {
    // Sincronizar estado de sonido con la preferencia ya cargada en State
    // NOTA: State/View/Modal son const en app.js → NO están en window; usar bare name + typeof
    _soundEnabled = !!(typeof State !== 'undefined' && State.userPreferences && State.userPreferences.fx_sounds_enabled);

    // Canvas lightning overlay
    _canvas = document.getElementById('fx-lightning-canvas');
    if (_canvas) {
      _ctx2d = _canvas.getContext('2d');
      _resizeCanvas();
      window.addEventListener('resize', _debounce(_resizeCanvas, 200), { passive: true });
    }

    // Ripple global
    ripple.init();

    // Tilt inicial (Board ya renderizó en View.show('board'))
    tilt.attachAll();

    // Envolver View.show para transiciones (debe hacerse UNA sola vez)
    if (typeof View !== 'undefined' && !View.__fxWrapped) {
      const _orig = View.show.bind(View);
      View.show = async function(name) {
        const main = document.getElementById('main');
        if (main && main.children.length > 0) {
          await transition.out(main);
        }
        sound.page();
        const result = await _orig(name);
        if (main) {
          transition.in(main);
          stagger.rows(main);
          // Re-adjuntar tilt si volvemos al board
          if (name === 'board') tilt.attachAll();
        }
        return result;
      };
      View.__fxWrapped = true;
    }

    // Envolver Modal para sonidos en confirm/cancel (una sola vez)
    if (typeof Modal !== 'undefined' && !Modal.__fxWrapped) {
      const _origModalSubmit = Modal._submit.bind(Modal);
      const _origModalClose  = Modal.close.bind(Modal);
      let _modalSubmitting   = false;

      Modal._submit = async function() {
        _modalSubmitting = true;
        await _origModalSubmit.call(this);
        _modalSubmitting = false;
      };

      Modal.close = function() {
        const wasOpen = this._isOpen();
        _origModalClose.call(this);
        if (wasOpen) {
          if (_modalSubmitting) sound.confirm();
          else sound.cancel();
        }
      };

      Modal.__fxWrapped = true;
    }
  }

  /* ── Helpers privados ─────────────────────────────────────────────── */
  function _resizeCanvas() {
    if (!_canvas) return;
    _canvas.width = window.innerWidth;
    _canvas.height = window.innerHeight;
  }

  function _debounce(fn, ms) {
    let t;
    return function(...args) {
      clearTimeout(t);
      t = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  /* ── API pública ──────────────────────────────────────────────────── */
  return { init, soundEnabled, toggleSound, tilt, lightning, sound, ripple, transition, stagger };
})();
