// Feynman runtime -- the only JavaScript shipped to the reader.
//
// Two responsibilities:
//   1. <feynman-viz>: a step-driven visualisation. It reads a JSON spec and
//      renders one of several shapes -- a box grid, a radial sweep, or a
//      travelling wave -- each a pure function of an integer step, driven by
//      play / prev / next / scrub controls. IntersectionObserver pauses
//      playback while the figure is offscreen.
//   2. the light/dark theme toggle in the header.
//
// The single architectural idea: every visualisation is a pure function of an
// integer step. A "type" selects a renderer; the driving machinery is shared.
//
// No dependencies, no build step; this file is served verbatim.

const SVG_NS = "http://www.w3.org/2000/svg";

function svgEl(name, attrs) {
  const el = document.createElementNS(SVG_NS, name);
  for (const k in attrs) el.setAttribute(k, attrs[k]);
  return el;
}

// --- grid renderer ---------------------------------------------------------
// patterns: (row, col, step, spec) -> boolean "is this cell active?". Each is a
// pure function of the step; new box behaviours are new entries here.
const PATTERNS = {
  // Cells whose centre falls inside the quarter circle of radius = grid size.
  // The fraction of revealed cells inside the circle approaches pi/4.
  circle: (r, c, step, spec) => {
    const n = spec.rows || 8;
    if (c >= step) return false; // reveal column by column
    const x = (c + 0.5) / n;
    const y = (n - r - 0.5) / n; // flip y: circle sits bottom-left
    return x * x + y * y <= 1;
  },
  // Lower-triangular mask revealed one row per step.
  causal: (r, c, step) => c <= r && r < step,
  // A grid filling left to right, one column per step.
  fill: (r, c, step) => c < step,
  // Diagonal wavefront sweeping across the grid.
  diagonal: (r, c, step) => r + c < step,
};

class GridRenderer {
  constructor(spec) {
    this.spec = spec;
    this.rows = (spec.rows | 0) || 8;
    this.cols = (spec.cols | 0) || 8;
    this.steps = (spec.steps | 0) || this.rows;
    this.pattern = PATTERNS[spec.pattern] || PATTERNS.causal;
  }

  build() {
    const gap = 2;
    const size = 30;
    const w = this.cols * (size + gap) - gap;
    const h = this.rows * (size + gap) - gap;
    const svg = svgEl("svg", { class: "fv-grid", viewBox: `0 0 ${w} ${h}`, role: "img" });
    this.cells = [];
    for (let r = 0; r < this.rows; r++) {
      for (let c = 0; c < this.cols; c++) {
        const rect = svgEl("rect", {
          class: "fv-cell",
          x: c * (size + gap), y: r * (size + gap),
          width: size, height: size, rx: 4,
        });
        rect.dataset.r = r;
        rect.dataset.c = c;
        svg.appendChild(rect);
        this.cells.push(rect);
      }
    }
    return svg;
  }

  paint(step) {
    const active = "var(--accent)";
    const idle = "var(--line)";
    const isCircle = this.spec.pattern === "circle";
    this.on = 0;
    this.revealed = 0;
    for (const rect of this.cells) {
      const r = +rect.dataset.r;
      const c = +rect.dataset.c;
      const isOn = this.pattern(r, c, step, this.spec);
      if (isCircle ? c < step : true) this.revealed++;
      rect.setAttribute("fill", isOn ? active : idle);
      rect.setAttribute("opacity", isOn ? "1" : "0.35");
      if (isOn) this.on++;
    }
  }

  readout(step) {
    if (this.spec.pattern === "circle" && this.revealed > 0) {
      const estimate = (4 * this.on) / this.revealed;
      return `step ${step}/${this.steps} · π ≈ ${estimate.toFixed(3)}`;
    }
    return `step ${step}/${this.steps} · ${this.on} on`;
  }
}

// --- radial renderer -------------------------------------------------------
// A polar field of dots arranged in rings and spokes, swept like radar. The
// sweep line rotates by one spoke per step; every point it has passed lights
// up. One full turn lights the whole field.
class RadialRenderer {
  constructor(spec) {
    this.spec = spec;
    this.rings = (spec.rings | 0) || 5;
    this.spokes = (spec.spokes | 0) || 16;
    this.steps = (spec.steps | 0) || this.spokes;
    this.cx = 120;
    this.cy = 120;
    this.maxR = 104;
  }

  angle(step) {
    // Start the sweep at the top (−90°) and rotate clockwise.
    return (step / this.steps) * 2 * Math.PI - Math.PI / 2;
  }

  build() {
    const svg = svgEl("svg", { class: "fv-radial", viewBox: "0 0 240 240", role: "img" });
    for (let i = 1; i <= this.rings; i++) {
      svg.appendChild(svgEl("circle", {
        class: "fv-ring", cx: this.cx, cy: this.cy, r: (i / this.rings) * this.maxR,
      }));
    }
    this.dots = [];
    for (let j = 0; j < this.spokes; j++) {
      const ang = (j / this.spokes) * 2 * Math.PI - Math.PI / 2;
      for (let i = 1; i <= this.rings; i++) {
        const r = (i / this.rings) * this.maxR;
        const dot = svgEl("circle", {
          class: "fv-dot",
          cx: (this.cx + r * Math.cos(ang)).toFixed(1),
          cy: (this.cy + r * Math.sin(ang)).toFixed(1),
          r: 4.5,
        });
        dot.dataset.j = j;
        svg.appendChild(dot);
        this.dots.push(dot);
      }
    }
    this.sweep = svgEl("line", {
      class: "fv-sweep", x1: this.cx, y1: this.cy, x2: this.cx, y2: this.cy - this.maxR,
    });
    svg.appendChild(this.sweep);
    return svg;
  }

  paint(step) {
    const active = "var(--accent)";
    const idle = "var(--line)";
    this.on = 0;
    for (const dot of this.dots) {
      const isOn = +dot.dataset.j < step;
      dot.setAttribute("fill", isOn ? active : idle);
      dot.setAttribute("opacity", isOn ? "1" : "0.3");
      if (isOn) this.on++;
    }
    const ang = this.angle(step);
    this.sweep.setAttribute("x2", (this.cx + this.maxR * Math.cos(ang)).toFixed(1));
    this.sweep.setAttribute("y2", (this.cy + this.maxR * Math.sin(ang)).toFixed(1));
  }

  readout(step) {
    return `step ${step}/${this.steps} · ${this.on} points lit`;
  }
}

// --- wave renderer ---------------------------------------------------------
// A travelling sine wave: y = sin(2π f x/W − φ), with the phase φ advancing one
// increment per step so the whole waveform slides to the right.
class WaveRenderer {
  constructor(spec) {
    this.spec = spec;
    this.steps = (spec.steps | 0) || 24;
    this.amp = (spec.amp | 0) || 54;
    this.freq = (spec.freq | 0) || 2;
    this.samples = 64;
    this.W = 320;
    this.H = 160;
    this.mid = 80;
  }

  yAt(x, step) {
    const phase = (step / this.steps) * 2 * Math.PI;
    return this.mid - this.amp * Math.sin((2 * Math.PI * this.freq * x) / this.W - phase);
  }

  build() {
    const svg = svgEl("svg", { class: "fv-wave", viewBox: `0 0 ${this.W} ${this.H}`, role: "img" });
    svg.appendChild(svgEl("line", {
      class: "fv-axis", x1: 0, y1: this.mid, x2: this.W, y2: this.mid,
    }));
    this.path = svgEl("path", { class: "fv-wave-path", fill: "none" });
    svg.appendChild(this.path);
    this.dot = svgEl("circle", {
      class: "fv-wave-dot", r: 5, cx: this.W / 2, cy: this.mid,
    });
    svg.appendChild(this.dot);
    return svg;
  }

  paint(step) {
    let d = "";
    for (let i = 0; i <= this.samples; i++) {
      const x = (i / this.samples) * this.W;
      const y = this.yAt(x, step);
      d += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1);
    }
    this.path.setAttribute("d", d);
    this.cy = this.yAt(this.W / 2, step);
    this.dot.setAttribute("cy", this.cy.toFixed(1));
  }

  readout(step) {
    const value = (this.mid - this.cy) / this.amp;
    return `step ${step}/${this.steps} · sin φ = ${value.toFixed(2)}`;
  }
}

// The client-side half of the viz registry. Its Python counterpart,
// `VIZ_TYPES` in directives.py, is the build-time source of truth for which
// `type=` values are valid and which params each takes; a `type=` with no entry
// there is reported as a build warning. Adding a shape is one `VizType` entry
// there plus one renderer here. An unknown type still falls back to the grid.
const RENDERERS = { grid: GridRenderer, radial: RadialRenderer, wave: WaveRenderer };

class FeynmanViz extends HTMLElement {
  connectedCallback() {
    this.spec = this.readSpec();
    const Renderer = RENDERERS[this.spec.type] || RENDERERS.grid;
    this.renderer = new Renderer(this.spec);
    this.playing = false;
    this.timer = null;
    this.build();
    // Open on a partially-advanced frame so a reader who never presses play
    // still sees a meaningful picture.
    const initial = this.spec.start != null ? this.spec.start : Math.round(this.steps * 0.6);
    this.seek(initial);
    this.observe();
  }

  disconnectedCallback() {
    this.stop();
    if (this.io) this.io.disconnect();
  }

  readSpec() {
    const el = this.querySelector(".feynman-viz-spec");
    const fallback = { type: "grid" };
    if (!el) return fallback;
    try {
      return Object.assign(fallback, JSON.parse(el.textContent));
    } catch (_e) {
      return fallback;
    }
  }

  build() {
    this.steps = this.renderer.steps;
    if (this.step == null) this.step = 0;
    // Wipe any prerendered content (the spec script) and rebuild.
    this.textContent = "";
    this.appendChild(this.renderer.build());
    this.buildControls();
    this.paint();
  }

  buildControls() {
    const bar = document.createElement("div");
    bar.className = "fv-controls";

    this.playBtn = button("play", () => this.toggle());
    const prev = button("‹", () => this.seek(this.step - 1));
    const next = button("›", () => this.seek(this.step + 1));

    this.range = document.createElement("input");
    this.range.type = "range";
    this.range.min = "0";
    this.range.max = String(this.steps);
    this.range.value = "0";
    this.range.setAttribute("aria-label", "Step");
    this.range.addEventListener("input", () => this.seek(this.range.valueAsNumber));

    this.readout = document.createElement("span");
    this.readout.className = "fv-step";

    bar.append(this.playBtn, prev, next, this.range, this.readout);
    this.appendChild(bar);
  }

  paint() {
    this.renderer.paint(this.step);
    if (this.range) this.range.value = String(this.step);
    if (this.readout) this.readout.textContent = this.renderer.readout(this.step);
  }

  seek(step) {
    this.step = Math.max(0, Math.min(this.steps, step | 0));
    this.paint();
  }

  toggle() {
    this.playing ? this.stop() : this.play();
  }

  play() {
    this.playing = true;
    this.playBtn.textContent = "pause";
    const fps = this.spec.fps || 2;
    this.timer = setInterval(() => {
      const next = this.step >= this.steps ? 0 : this.step + 1;
      this.seek(next);
    }, 1000 / fps);
  }

  stop() {
    this.playing = false;
    if (this.playBtn) this.playBtn.textContent = "play";
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
  }

  observe() {
    // Pause when scrolled offscreen so no cycles are spent on unseen figures.
    if (!("IntersectionObserver" in window)) return;
    this.io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting && this.playing) this.stop();
        }
      },
      { threshold: 0.1 }
    );
    this.io.observe(this);
  }
}

function button(label, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.textContent = label;
  b.addEventListener("click", onClick);
  return b;
}

customElements.define("feynman-viz", FeynmanViz);

// --- theme toggle ----------------------------------------------------------
// The inline head script already applied any stored theme before first paint;
// here we only sync the button's a11y state and handle clicks. The sun/moon
// icons themselves are swapped by CSS on [data-theme].
(function initTheme() {
  const root = document.documentElement;
  const KEY = "feynman-theme";
  if (!localStorage.getItem(KEY) && window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches) {
    root.dataset.theme = "dark";
  }

  const sync = () => {
    const btn = document.querySelector(".feynman-theme-toggle");
    if (!btn) return;
    const dark = root.dataset.theme === "dark";
    btn.setAttribute("aria-label", `Switch to ${dark ? "light" : "dark"} theme`);
    btn.setAttribute("aria-pressed", String(dark));
  };

  document.addEventListener("click", (e) => {
    const toggle = e.target.closest(".feynman-theme-toggle");
    if (!toggle) return;
    root.dataset.theme = root.dataset.theme === "dark" ? "light" : "dark";
    try { localStorage.setItem(KEY, root.dataset.theme); } catch (_e) {}
    sync();
  });

  if (document.readyState !== "loading") sync();
  else document.addEventListener("DOMContentLoaded", sync);
})();

// --- copy buttons ----------------------------------------------------------
// Code cards copy their highlighted source; equation buttons copy raw LaTeX
// from data-latex. A small toast confirms (or explains the manual fallback).
(function initCopy() {
  const toast = document.querySelector(".toast");
  let timer;
  const announce = (msg) => {
    if (!toast) return;
    clearTimeout(timer);
    toast.textContent = msg;
    timer = setTimeout(() => { toast.textContent = ""; }, 2500);
  };

  const copyText = async (text) => {
    try {
      if (navigator.clipboard && window.isSecureContext) {
        await navigator.clipboard.writeText(text);
      } else {
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.setAttribute("readonly", "");
        ta.style.cssText = "position:fixed;left:-9999px;top:0";
        document.body.append(ta);
        ta.select();
        let ok;
        try { ok = document.execCommand("copy"); } finally { ta.remove(); }
        if (!ok) throw new Error("clipboard unavailable");
      }
      return true;
    } catch (_e) {
      return false;
    }
  };

  document.addEventListener("click", async (e) => {
    const codeBtn = e.target.closest(".copy-button");
    if (codeBtn) {
      const pre = codeBtn.closest("figure")?.querySelector(".highlight pre");
      const ok = pre && (await copyText(pre.textContent));
      announce(ok ? "Code copied to clipboard." : "Press Ctrl+C / ⌘C to copy.");
      return;
    }
    const eqBtn = e.target.closest(".equation-copy");
    if (eqBtn) {
      const ok = await copyText(eqBtn.dataset.latex || "");
      announce(ok ? "LaTeX copied to clipboard." : "Press Ctrl+C / ⌘C to copy.");
    }
  });
})();

// --- table of contents + reading progress ---------------------------------
// The page ships with an empty <ol> in the sidebar; we fill it from the h2s so
// the document stays the single source of truth for its own structure.
(function initContents() {
  const list = document.querySelector(".contents ol");
  const aside = document.querySelector(".contents");
  const headings = Array.from(document.querySelectorAll(".feynman-prose h2[id]"));
  const links = [];

  if (list && headings.length) {
    headings.forEach((h, i) => {
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = `#${h.id}`;
      const num = document.createElement("span");
      num.textContent = String(i + 1).padStart(2, "0");
      a.append(num, document.createTextNode(h.textContent));
      li.append(a);
      list.append(li);
      links.push(a);
    });
    if (aside) aside.setAttribute("aria-hidden", "false");
  }

  const progress = document.querySelector(".reading-progress");
  const root = document.documentElement;
  let queued = false;

  const update = () => {
    queued = false;
    const available = root.scrollHeight - root.clientHeight;
    const ratio = available > 0 ? Math.min(1, Math.max(0, window.scrollY / available)) : 0;
    if (progress) progress.style.transform = `scaleX(${ratio})`;
    if (!headings.length) return;
    let active = headings[0];
    for (const h of headings) if (h.getBoundingClientRect().top <= 140) active = h;
    if (ratio > 0.995) active = headings[headings.length - 1];
    for (const a of links) {
      if (a.hash === `#${active.id}`) a.setAttribute("aria-current", "location");
      else a.removeAttribute("aria-current");
    }
  };
  const queue = () => { if (!queued) { queued = true; requestAnimationFrame(update); } };
  window.addEventListener("scroll", queue, { passive: true });
  window.addEventListener("resize", queue, { passive: true });
  update();
})();
