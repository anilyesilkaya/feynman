// Feynman runtime -- the only JavaScript shipped to the reader.
//
// Two responsibilities:
//   1. <feynman-viz>: a step-driven visualisation. It reads a JSON spec and
//      renders an SVG grid whose cells are a pure function of an integer step,
//      driven by play / prev / next / scrub controls. IntersectionObserver
//      pauses playback while the figure is offscreen.
//   2. the light/dark theme toggle in the header.
//
// No dependencies, no build step; this file is served verbatim.

const SVG_NS = "http://www.w3.org/2000/svg";

// --- patterns: (row, col, step, spec) -> boolean "is this cell active?" ---
// Each pattern is a pure function of the integer step. New visual behaviours
// are new entries here; the driving machinery never changes.
const PATTERNS = {
  // Cells whose centre falls inside the quarter circle of radius = grid size.
  // Sweeping the step reveals more of the grid; the fraction of revealed cells
  // that are inside the circle approaches pi/4 -- a deterministic cousin of the
  // Monte Carlo estimate. This is the demo's headline visualisation.
  circle: (r, c, step, spec) => {
    const n = spec.rows;
    if (c >= step) return false; // reveal column by column
    const x = (c + 0.5) / n;
    // Flip y so row 0 (top of the SVG) maps to y near 1: this places the
    // quarter circle in the bottom-left corner, matching the matplotlib
    // scatter's origin-at-bottom-left orientation.
    const y = (n - r - 0.5) / n;
    return x * x + y * y <= 1;
  },
  // Lower-triangular mask revealed one row per step.
  causal: (r, c, step) => c <= r && r < step,
  // A grid filling left to right, one column per step.
  fill: (r, c, step) => c < step,
  // Diagonal wavefront sweeping across the grid.
  diagonal: (r, c, step) => r + c < step,
};

class FeynmanViz extends HTMLElement {
  connectedCallback() {
    const spec = this.readSpec();
    this.spec = spec;
    this.playing = false;
    this.timer = null;
    this.render(spec);
    // Open on a partially-revealed frame so a reader who never presses play
    // still sees a meaningful picture (and, for the circle, a live estimate).
    const initial = spec.start != null ? spec.start : Math.round(this.steps * 0.6);
    this.seek(initial);
    this.observe();
  }

  disconnectedCallback() {
    this.stop();
    if (this.io) this.io.disconnect();
  }

  readSpec() {
    const el = this.querySelector(".feynman-viz-spec");
    const fallback = { type: "grid", rows: 8, cols: 8, pattern: "causal", steps: 8 };
    if (!el) return fallback;
    try {
      return Object.assign(fallback, JSON.parse(el.textContent));
    } catch (_e) {
      return fallback;
    }
  }

  render(spec) {
    const rows = spec.rows | 0;
    const cols = spec.cols | 0;
    const steps = (spec.steps | 0) || rows;
    this.steps = steps;
    if (this.step == null) this.step = 0;

    const gap = 2;
    const size = 30;
    const w = cols * (size + gap) - gap;
    const h = rows * (size + gap) - gap;

    // Wipe any prerendered content (the spec script) and rebuild.
    this.textContent = "";

    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", "fv-grid");
    svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
    svg.setAttribute("role", "img");
    this.cells = [];
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        const rect = document.createElementNS(SVG_NS, "rect");
        rect.setAttribute("class", "fv-cell");
        rect.setAttribute("x", c * (size + gap));
        rect.setAttribute("y", r * (size + gap));
        rect.setAttribute("width", size);
        rect.setAttribute("height", size);
        rect.setAttribute("rx", 4);
        rect.dataset.r = r;
        rect.dataset.c = c;
        svg.appendChild(rect);
        this.cells.push(rect);
      }
    }
    this.appendChild(svg);
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
    const { pattern } = this.spec;
    const fn = PATTERNS[pattern] || PATTERNS.causal;
    const active = "var(--accent)";
    const idle = "var(--border)";
    let on = 0;
    let revealed = 0;
    for (const rect of this.cells) {
      const r = +rect.dataset.r;
      const c = +rect.dataset.c;
      const isOn = fn(r, c, this.step, this.spec);
      // For the circle pattern, "revealed" = columns exposed so far.
      if (pattern === "circle" ? c < this.step : true) revealed++;
      rect.setAttribute("fill", isOn ? active : idle);
      rect.setAttribute("opacity", isOn ? "1" : "0.35");
      if (isOn) on++;
    }
    if (this.range) this.range.value = String(this.step);
    if (this.readout) this.readout.textContent = this.readoutText(on, revealed);
  }

  readoutText(on, revealed) {
    if (this.spec.pattern === "circle" && revealed > 0) {
      const estimate = (4 * on) / revealed;
      return `step ${this.step}/${this.steps} · π ≈ ${estimate.toFixed(3)}`;
    }
    return `step ${this.step}/${this.steps} · ${on} on`;
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
