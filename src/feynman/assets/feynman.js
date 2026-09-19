// Feynman runtime -- the only JavaScript shipped to the reader.
//
// Two responsibilities:
//   1. <feynman-viz>: a step-driven visualisation. It reads a JSON spec and
//      renders one of several shapes -- a box grid, a radial sweep, a
//      travelling wave, a Fourier synthesiser, or a Galton board -- driven by
//      play / prev / next / scrub controls. IntersectionObserver pauses
//      playback while offscreen. A figure marked data-viz-scroll instead binds
//      its step to the reader's scroll position: nested [data-viz-step]
//      waypoints seek the drawing as they pass, so prose drives the animation.
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

// --- fourier renderer ------------------------------------------------------
// A Fourier-series synthesiser: the step is the number of harmonic terms
// summed. The partial sum converges toward a target waveform (square by
// default), exposing the Gibbs overshoot at its jumps. A faint dashed
// reference of the ideal target sits behind the bold accent partial sum.
//
// Each target gives the coefficient of its k-th harmonic; coefficients are
// normalised so the ideal waveform peaks at ±1 and `amp` scales that to pixels
// (as in WaveRenderer). Term N adds the N-th *nonzero* harmonic. New target
// waveforms are new entries here -- the analogue of the grid's PATTERNS.
const FOURIER_TARGETS = {
  // Odd harmonics, all positive: (4/π)/k. Discontinuous -> Gibbs (peak ~1.18).
  square: (k) => (k % 2 === 1 ? 4 / Math.PI / k : 0),
  // Every harmonic, alternating sign: (2/π)(-1)^(k+1)/k. Discontinuous.
  sawtooth: (k) => ((k % 2 === 1 ? 1 : -1) * 2) / (Math.PI * k),
  // Odd harmonics, sign flips each term, 1/k² decay. Continuous -> no Gibbs.
  triangle: (k) =>
    k % 2 === 1
      ? ((((k - 1) / 2) % 2 === 0 ? 1 : -1) * 8) / (Math.PI * Math.PI * k * k)
      : 0,
};

class FourierRenderer {
  constructor(spec) {
    this.spec = spec;
    this.terms = (spec.terms | 0) || 8;
    this.steps = (spec.steps | 0) || this.terms;
    this.amp = (spec.amp | 0) || 54;
    this.freq = (spec.freq | 0) || 1;
    this.target = FOURIER_TARGETS[spec.target] ? spec.target : "square";
    this.coef = FOURIER_TARGETS[this.target];
    this.W = 320;
    this.H = 160;
    this.mid = 80;

    // Precompute the first `steps` nonzero harmonics as {k, c} pairs, so a step
    // is simply "how many of these to sum".
    this.harmonics = [];
    for (let k = 1; this.harmonics.length < this.steps; k++) {
      const c = this.coef(k);
      if (c !== 0) this.harmonics.push({ k, c });
    }
    // Sample density tracks the highest harmonic so the Gibbs spike doesn't
    // alias; capped so a large `terms` can't blow up the path.
    const top = this.harmonics.length ? this.harmonics[this.harmonics.length - 1].k : 1;
    this.samples = Math.min(512, Math.max(128, 8 * top));
  }

  // Ideal target value at phase p, normalised to ±1 (the dashed reference).
  ideal(p) {
    const t = (((p / (2 * Math.PI)) % 1) + 1) % 1; // fractional period 0..1
    switch (this.target) {
      case "sawtooth":
        return t < 0.5 ? 2 * t : 2 * t - 2;
      case "triangle":
        if (t < 0.25) return 4 * t;
        if (t < 0.75) return 2 - 4 * t;
        return 4 * t - 4;
      default: // square
        return Math.sin(p) >= 0 ? 1 : -1;
    }
  }

  // Partial sum of the first `step` harmonics at phase p (normalised to ±1).
  partial(p, step) {
    let y = 0;
    const n = Math.min(step, this.harmonics.length);
    for (let i = 0; i < n; i++) {
      y += this.harmonics[i].c * Math.sin(this.harmonics[i].k * p);
    }
    return y;
  }

  path(fn) {
    let d = "";
    for (let i = 0; i <= this.samples; i++) {
      const x = (i / this.samples) * this.W;
      const p = (2 * Math.PI * this.freq * x) / this.W;
      const y = this.mid - this.amp * fn(p);
      d += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1);
    }
    return d;
  }

  build() {
    const svg = svgEl("svg", { class: "fv-fourier", viewBox: `0 0 ${this.W} ${this.H}`, role: "img" });
    svg.appendChild(svgEl("line", {
      class: "fv-axis", x1: 0, y1: this.mid, x2: this.W, y2: this.mid,
    }));
    // Static dashed reference: the ideal target waveform the sum converges to.
    svg.appendChild(svgEl("path", {
      class: "fv-fourier-target", fill: "none", d: this.path((p) => this.ideal(p)),
    }));
    this.sum = svgEl("path", { class: "fv-fourier-sum", fill: "none" });
    svg.appendChild(this.sum);
    return svg;
  }

  paint(step) {
    let d = "";
    let peak = 0;
    for (let i = 0; i <= this.samples; i++) {
      const x = (i / this.samples) * this.W;
      const p = (2 * Math.PI * this.freq * x) / this.W;
      const v = this.partial(p, step);
      if (Math.abs(v) > peak) peak = Math.abs(v);
      const y = this.mid - this.amp * v;
      d += (i === 0 ? "M" : "L") + x.toFixed(1) + " " + y.toFixed(1);
    }
    this.sum.setAttribute("d", d);
    // max|partial| == max amplitude / amp -> ~1.18 for a square wave (Gibbs).
    this.peak = peak;
  }

  readout(step) {
    const n = Math.min(step, this.harmonics.length);
    if (n === 0) return `step 0/${this.steps} · 0 harmonics · flat`;
    const term = n === 1 ? "harmonic" : "harmonics";
    return `step ${step}/${this.steps} · ${n} ${term} · peak ${(this.peak || 0).toFixed(2)}`;
  }
}

// --- galton board renderer -------------------------------------------------
// A quincunx: balls drop through `rows` of pegs, each bounce going left or
// right, and land in one of `rows + 1` bins -- with enough balls the pile
// converges on the binomial (bell) curve. The step is the number of balls
// dropped, so play fills the board ball by ball.
//
// The board is genuinely random: each ball's per-row left/right decisions are
// drawn once from Math.random() in the constructor, so every page load gives a
// fresh board. But a ball's path is fixed for the life of the element -- the
// engine repaints on every scrub, and re-drawing paths each frame would make the
// pile reshuffle chaotically as you drag. So scrubbing just grows or shrinks a
// stable pile, and every ball is the same accent colour.
//
// The just-dropped ball (the newest one for the current step) is animated: it
// descends through the lattice along its own zig-zag, visibly deflecting left or
// right at each peg row, then drops into its slot. Earlier balls are drawn
// already settled. Because the drop freezes at the landing slot, a static frame
// (after the motion finishes) shows the same pile a pure paint() would.

class GaltonRenderer {
  constructor(spec) {
    this.spec = spec;
    this.rows = Math.max(1, (spec.rows | 0) || 12);
    this.balls = (spec.balls | 0) || 120;
    this.steps = (spec.steps | 0) || this.balls;
    this.bins = this.rows + 1;
    this.W = 360;
    this.H = 260;
    this.pegR = 3;
    this.ballR = 5;
    this.rowGap = 15; // vertical spacing between peg rows
    this.top = 20; // pegs occupy the upper band; bins stack below
    this.binTop = this.top + this.rows * this.rowGap + 10;
    // Seconds for a marble to fall the whole lattice. Tie it to the frame
    // interval (1/fps) so during autoplay a marble finishes its drop just before
    // the next one is released -- otherwise a fast fps repaints and wipes the
    // falling marble before it has visibly moved. Leave a little margin so the
    // ball settles before the next paint, and clamp for very slow/fast rates.
    const fps = (spec.fps | 0) || 2;
    this.dropDur = Math.min(0.9, Math.max(0.2, 0.85 / fps));

    // Draw each ball's path once, up front, from a random seed. `walk[i]` is the
    // sequence of +/-1 deflections (one per peg row); `landing[i]` is how many
    // went right, i.e. the bin index. Fixing them here (not per paint) keeps the
    // pile stable while scrubbing.
    this.walks = [];
    this.landing = [];
    for (let i = 0; i < this.steps; i++) {
      const walk = [];
      let right = 0;
      for (let k = 0; k < this.rows; k++) {
        const dir = Math.random() < 0.5 ? -1 : 1;
        walk.push(dir);
        if (dir > 0) right++;
      }
      this.walks.push(walk);
      this.landing.push(right);
    }
  }

  binX(bin) {
    const slot = this.W / this.bins;
    return slot * (bin + 0.5);
  }

  build() {
    const svg = svgEl("svg", { class: "fv-galton", viewBox: `0 0 ${this.W} ${this.H}`, role: "img" });
    // Peg triangle: row r has r + 1 pegs, centred.
    for (let r = 0; r < this.rows; r++) {
      const y = this.top + r * this.rowGap;
      const count = r + 1;
      const slot = this.W / (count + 1);
      for (let c = 0; c < count; c++) {
        svg.appendChild(svgEl("circle", {
          class: "fv-peg", cx: (slot * (c + 1)).toFixed(1), cy: y, r: this.pegR,
        }));
      }
    }
    // Bin floor + a dashed target curve for the binomial the pile approaches.
    svg.appendChild(svgEl("line", {
      class: "fv-galton-floor", x1: 0, y1: this.H - 2, x2: this.W, y2: this.H - 2,
    }));
    this.target = svgEl("path", { class: "fv-galton-target", fill: "none" });
    svg.appendChild(this.target);
    // A layer that holds the settled balls, repainted per step.
    this.pile = svgEl("g", { class: "fv-galton-pile" });
    svg.appendChild(this.pile);
    return svg;
  }

  paint(step) {
    // Bin heights for the first `step` balls (their landings are fixed).
    const heights = new Array(this.bins).fill(0);
    for (let i = 0; i < step; i++) heights[this.landing[i]]++;
    this.peak = Math.max(1, ...heights);

    const total = step || 1;
    const coef = binomial(this.rows);
    const denom = Math.pow(2, this.rows);
    const floorY = this.H - 2;
    const span = floorY - this.binTop; // balls stack down from here to the floor

    // Dashed target: the ideal binomial scaled to the current ball count and
    // the tallest bin, so the curve tracks the growing pile.
    let d = "";
    for (let b = 0; b < this.bins; b++) {
      const expected = (coef[b] / denom) * total; // expected balls in bin b
      const y = floorY - (expected / this.peak) * span;
      d += (b === 0 ? "M" : "L") + this.binX(b).toFixed(1) + " " + y.toFixed(1);
    }
    this.target.setAttribute("d", d);

    // Redraw the settled pile: each bin stacks its balls up from the floor. A
    // running counter gives each ball its height without an inner scan. The
    // newest ball (index step-1) is animated separately, so hold its slot open.
    this.pile.textContent = "";
    const rowH = Math.min(2 * this.ballR, span / this.peak);
    const stacked = new Array(this.bins).fill(0);
    const newest = step - 1;
    const slotOf = []; // final (cx, cy) for the newest ball, if any
    for (let i = 0; i < step; i++) {
      const bin = this.landing[i];
      const cy = floorY - this.ballR - stacked[bin] * rowH;
      stacked[bin]++;
      if (i === newest) {
        slotOf[0] = this.binX(bin);
        slotOf[1] = cy;
        continue; // drawn by the animated marble below, not the static pile
      }
      this.pile.appendChild(svgEl("circle", {
        class: "fv-ball",
        cx: this.binX(bin).toFixed(1), cy: cy.toFixed(1), r: this.ballR,
      }));
    }
    if (newest >= 0) this.dropNewest(newest, slotOf[0], slotOf[1]);
    this._mode = heights.indexOf(this.peak);
  }

  // Animate the newest marble falling from the spout, bouncing left/right at
  // each peg row, into its slot. Uses SMIL <animateMotion> when available so the
  // motion is declarative and self-cleaning; if unsupported, the marble is just
  // placed in its slot. Rapid scrubbing simply restarts the drop for the new
  // newest ball -- earlier balls are already static in the pile.
  dropNewest(i, cx, cy) {
    const ball = svgEl("circle", { class: "fv-ball fv-ball-live", r: this.ballR });
    if (typeof SVGAnimateMotionElement === "undefined") {
      ball.setAttribute("cx", cx.toFixed(1));
      ball.setAttribute("cy", cy.toFixed(1));
      this.pile.appendChild(ball);
      return;
    }
    // Park the base circle at the destination; the motion animation offsets it
    // along the path and freezes at the end (fill=freeze), leaving it in place.
    ball.setAttribute("cx", cx.toFixed(1));
    ball.setAttribute("cy", cy.toFixed(1));
    const motion = svgEl("animateMotion", {
      dur: this.dropDur + "s",
      fill: "freeze",
      calcMode: "linear",
      path: this.translatePath(i, cx, cy),
      begin: "indefinite",
    });
    ball.appendChild(motion);
    this.pile.appendChild(ball);
    // animateMotion adds the path offset to the element's own position, so the
    // path must be expressed as displacement from the parked destination.
    if (typeof motion.beginElement === "function") motion.beginElement();
  }

  // dropPath in coordinates relative to the parked destination (cx, cy), since
  // animateMotion translates the element by the path rather than moving it to
  // absolute points.
  translatePath(i, cx, cy) {
    const half = this.W / this.bins / 2;
    let p = 0;
    let d = "M " + (this.W / 2 - cx).toFixed(1) + " " + (0 - cy).toFixed(1);
    const walk = this.walks[i];
    for (let r = 0; r < this.rows; r++) {
      p += walk[r];
      const x = this.W / 2 + p * half - cx;
      const y = this.top + r * this.rowGap - cy;
      d += " L " + x.toFixed(1) + " " + y.toFixed(1);
    }
    d += " L 0 0";
    return d;
  }

  readout(step) {
    return `${step}/${this.steps} balls · tallest bin ${this.peak} (bin ${this._mode < 0 ? 0 : this._mode})`;
  }
}

// Binomial coefficients C(n, 0..n) for the target curve.
function binomial(n) {
  const row = [1];
  for (let k = 1; k <= n; k++) row.push((row[k - 1] * (n - k + 1)) / k);
  return row;
}

// The client-side half of the viz registry. Its Python counterpart,
// `VIZ_TYPES` in directives.py, is the build-time source of truth for which
// `type=` values are valid and which params each takes; a `type=` with no entry
// there is reported as a build warning. Adding a shape is one `VizType` entry
// there plus one renderer here. An unknown type still falls back to the grid.
const RENDERERS = {
  grid: GridRenderer,
  radial: RadialRenderer,
  wave: WaveRenderer,
  fourier: FourierRenderer,
  galton: GaltonRenderer,
};

class FeynmanViz extends HTMLElement {
  connectedCallback() {
    this.spec = this.readSpec();
    const Renderer = RENDERERS[this.spec.type] || RENDERERS.grid;
    this.renderer = new Renderer(this.spec);
    this.playing = false;
    this.timer = null;
    this.build();
    // The wrapping <figure> carries the #viz- id (when the directive gave one);
    // a step can then be deep-linked as `#<id>@<step>` so a reader can share the
    // figure at an exact frame. Only ided, non-scroll figures participate.
    const fig = this.closest("figure[id]");
    this.vizId = fig ? fig.id : null;
    // A figure marked data-viz-scroll drives its step from the reading position
    // rather than an opening frame; wire that up and let the first waypoint set
    // the initial step. Otherwise open on a deep-linked step if the URL names
    // this figure, else a partially-advanced frame so a reader who never presses
    // play still sees a meaningful picture.
    this.scrollFigure = this.closest("[data-viz-scroll]");
    if (this.scrollFigure) {
      this.observeScroll();
    } else {
      const linked = this.stepFromHash();
      const initial =
        linked != null
          ? linked
          : this.spec.start != null
          ? this.spec.start
          : Math.round(this.steps * 0.6);
      this.seek(initial);
      // A matching deep link should bring its figure into view; the native
      // anchor jump can't, since `#id@step` is not an element id. Defer one
      // frame so later-upgrading content below doesn't shift the target away.
      if (linked != null && fig) {
        requestAnimationFrame(() => fig.scrollIntoView({ block: "center" }));
      }
    }
    this.observe();
    // Reflect *user* seeks into the URL from here on. The initial seek above must
    // not write, or on a page with several vizzes a later one's default frame
    // would clobber an incoming deep link aimed at an earlier figure.
    this._ready = true;
    // Keep the drawing in sync if the hash changes while the page is open (a
    // pasted link, a same-page anchor, a back/forward step).
    this._onHashChange = () => {
      const s = this.stepFromHash();
      if (s != null && s !== this.step) this.seek(s);
    };
    window.addEventListener("hashchange", this._onHashChange);
  }

  disconnectedCallback() {
    this.stop();
    if (this.io) this.io.disconnect();
    if (this.stepIo) this.stepIo.disconnect();
    if (this._detachScroll) this._detachScroll();
    if (this._onHashChange) window.removeEventListener("hashchange", this._onHashChange);
    clearTimeout(this._hashTimer);
  }

  // Parse `#<vizId>@<step>` from the URL, returning the step for *this* figure
  // or null (no hash, a different figure, or a scroll-driven one, which owns its
  // step through scroll position rather than a shareable frame).
  stepFromHash() {
    if (!this.vizId || this.scrollFigure) return null;
    const m = /^#([^@]+)@(\d+)$/.exec(location.hash || "");
    if (!m || decodeURIComponent(m[1]) !== this.vizId) return null;
    return parseInt(m[2], 10);
  }

  // Reflect the current step into the URL as `#<vizId>@<step>`, so it can be
  // bookmarked or shared. `replaceState` (not `location.hash =`) avoids both a
  // history entry per scrub tick and the browser's native jump-to-anchor scroll;
  // a short debounce collapses a drag or an autoplay burst into one write. The
  // last figure the reader touches owns the hash.
  syncHash() {
    if (!this._ready || !this.vizId || this.scrollFigure) return;
    clearTimeout(this._hashTimer);
    this._hashTimer = setTimeout(() => {
      const hash = `#${this.vizId}@${this.step}`;
      if (hash === location.hash) return;
      try {
        history.replaceState(null, "", location.pathname + location.search + hash);
      } catch (_e) {
        /* file:// or a sandboxed frame: skip silently; the viz still works. */
      }
    }, 200);
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
    this.syncHash();
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

  // Scroll-driven mode: drive the drawing's step from the reading position,
  // interpolating *between* the [data-viz-step] waypoints so it advances one step
  // at a time as the reader scrolls rather than snapping between the waypoints'
  // target steps. The active waypoint (the last one whose top has crossed a
  // reading line partway down the viewport) sets the accent; the step is then
  // eased from its target toward the next waypoint's by how far the reading line
  // has travelled between them. The drawing and its caption pin together in a
  // sticky block (CSS) while the waypoints in .fv-scroll-steps scroll past. This
  // is pure progressive enhancement: with no JS the waypoints are ordinary
  // paragraphs and the scrubber still works.
  observeScroll() {
    const steps = Array.from(
      this.scrollFigure.querySelectorAll("[data-viz-step]")
    );
    if (!steps.length) return;
    // Autoplay is meaningless when scroll owns the step; hide the play button so
    // the two input models don't fight. Prev/next/scrub stay usable.
    if (this.playBtn) this.playBtn.hidden = true;

    // Seek to the first waypoint up front so the opening frame matches the prose
    // the reader starts on, rather than the generic 60%-advanced default.
    const stepOf = (el) => Math.max(0, Math.min(this.steps, parseInt(el.dataset.vizStep, 10) || 0));
    this.seek(stepOf(steps[0]));

    // A rAF-throttled scan picks the active waypoint. IntersectionObserver alone
    // can't tell us "the last one above the line" without tracking every entry,
    // so a cheap bounding-box scan on scroll is simpler and exact. We gate the
    // scans behind an IntersectionObserver so they only run while the figure (or
    // its waypoints) are near the viewport.
    let queued = false;
    const update = () => {
      queued = false;
      // Reading line: 55% down the viewport, matching where a sticky figure sits.
      const line = window.innerHeight * 0.55;
      // Find the active waypoint (last one whose top is above the line) and its
      // index, so we can interpolate toward the next one.
      let activeIdx = 0;
      for (let i = 0; i < steps.length; i++) {
        if (steps[i].getBoundingClientRect().top <= line) activeIdx = i;
      }
      const active = steps[activeIdx];
      if (active !== this.activeStep) {
        if (this.activeStep) this.activeStep.removeAttribute("aria-current");
        active.setAttribute("aria-current", "true");
        this.activeStep = active;
      }

      // Interpolate the step from how far the reading line has travelled from
      // the active waypoint toward the next, so the drawing steps through the
      // intermediate frames instead of jumping straight to each target.
      const from = stepOf(active);
      const next = steps[activeIdx + 1];
      let target = from;
      if (next) {
        const aTop = active.getBoundingClientRect().top;
        const nTop = next.getBoundingClientRect().top;
        const span = nTop - aTop;
        // Fraction of the gap the reading line has crossed (0 at the active
        // waypoint, 1 at the next); guard a zero/negative span.
        const frac = span > 0 ? Math.max(0, Math.min(1, (line - aTop) / span)) : 0;
        target = Math.round(from + frac * (stepOf(next) - from));
      }
      if (target !== this.step) this.seek(target);
    };
    const queue = () => {
      if (!queued) {
        queued = true;
        requestAnimationFrame(update);
      }
    };

    this.scrollActive = false;
    const onScroll = () => { if (this.scrollActive) queue(); };
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll, { passive: true });
    this._detachScroll = () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };

    // Only listen while the figure region is on (or near) screen.
    if ("IntersectionObserver" in window) {
      this.stepIo = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) this.scrollActive = entry.isIntersecting;
          if (this.scrollActive) queue();
        },
        { rootMargin: "20% 0px" }
      );
      this.stepIo.observe(this.scrollFigure);
    } else {
      this.scrollActive = true;
      queue();
    }
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

// --- sortable tables -------------------------------------------------------
// Progressive enhancement for tables authored with `.sortable`: click (or
// Enter/Space on) a header to sort the tbody rows by that column, toggling
// ascending/descending. The static table is fully readable without this; we
// only reorder existing rows, so nothing is hidden when JS is off.
(function initSortableTables() {
  // A column is numeric when every non-empty cell parses as a number (commas
  // and surrounding whitespace tolerated), so "1,000" and "30" sort by value
  // while text columns fall back to a locale compare.
  const parseNum = (text) => {
    const cleaned = text.trim().replace(/,/g, "");
    if (cleaned === "" || !/^[-+]?\d*\.?\d+(?:e[-+]?\d+)?$/i.test(cleaned)) return null;
    return parseFloat(cleaned);
  };

  const columnIsNumeric = (rows, col) => {
    let sawValue = false;
    for (const row of rows) {
      const text = (row.cells[col]?.textContent || "").trim();
      if (text === "") continue;
      if (parseNum(text) === null) return false;
      sawValue = true;
    }
    return sawValue;
  };

  const sortBy = (table, th, col) => {
    const tbody = table.tBodies[0];
    if (!tbody) return;
    const rows = Array.from(tbody.rows);
    const numeric = columnIsNumeric(rows, col);
    // Third click could reset, but toggling asc/desc is the common expectation;
    // `aria-sort` on the header is the single source of truth for direction.
    const asc = th.getAttribute("aria-sort") !== "ascending";

    rows.sort((ra, rb) => {
      const a = (ra.cells[col]?.textContent || "").trim();
      const b = (rb.cells[col]?.textContent || "").trim();
      let cmp;
      if (numeric) {
        const na = parseNum(a), nb = parseNum(b);
        // Empty cells sort last regardless of direction.
        if (na === null) return nb === null ? 0 : 1;
        if (nb === null) return -1;
        cmp = na - nb;
      } else {
        cmp = a.localeCompare(b, undefined, { numeric: true });
      }
      return asc ? cmp : -cmp;
    });

    for (const row of rows) tbody.appendChild(row);

    // Reflect state: clear siblings, mark this header.
    const headers = th.parentElement ? Array.from(th.parentElement.cells) : [];
    for (const h of headers) h.removeAttribute("aria-sort");
    th.setAttribute("aria-sort", asc ? "ascending" : "descending");
  };

  const enhance = (table) => {
    const headRow = table.tHead && table.tHead.rows[0];
    if (!headRow) return;
    Array.from(headRow.cells).forEach((th, col) => {
      th.classList.add("feynman-th-sortable");
      th.setAttribute("role", "button");
      th.tabIndex = 0;
      const activate = () => sortBy(table, th, col);
      th.addEventListener("click", activate);
      th.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activate();
        }
      });
    });
  };

  const init = () => {
    document.querySelectorAll("table.feynman-table-sortable").forEach(enhance);
  };
  if (document.readyState !== "loading") init();
  else document.addEventListener("DOMContentLoaded", init);
})();

// --- cross-post search -----------------------------------------------------
// Only the collection listing page (built by `feynman build-all`) carries a
// [data-feynman-search] form; every other page skips this entirely. The page
// already lists all posts as links, so search is pure enhancement: we fetch
// search-index.json, build a MiniSearch index in the browser, and reorder /
// hide the existing post cards to match the query. With JS off, or if the fetch
// or the MiniSearch import fails, the full static list simply remains.
(function initSearch() {
  const form = document.querySelector("[data-feynman-search]");
  if (!form) return;
  const input = form.querySelector("input[type='search']");
  const status = form.querySelector(".search-status");
  const list = document.querySelector("[data-feynman-post-list]");
  const empty = document.querySelector("[data-feynman-search-empty]");
  if (!input || !list) return;

  // Map each post's url -> its <li>, and remember the authored (date) order so
  // clearing the query restores it exactly.
  const cards = Array.from(list.querySelectorAll("[data-post-url]"));
  const byUrl = new Map(cards.map((li) => [li.dataset.postUrl, li]));
  const originalOrder = cards.slice();

  const say = (msg) => { if (status) status.textContent = msg; };

  const showAll = () => {
    for (const li of originalOrder) { li.hidden = false; list.appendChild(li); }
    if (empty) empty.hidden = true;
    say("");
  };

  const showResults = (results) => {
    const matched = new Set();
    // Reorder the list to match relevance, then hide the non-matches.
    results.forEach((r) => {
      const li = byUrl.get(r.url);
      if (li) { li.hidden = false; list.appendChild(li); matched.add(li); }
    });
    for (const li of originalOrder) if (!matched.has(li)) li.hidden = true;
    if (empty) empty.hidden = results.length > 0;
    say(results.length
      ? `${results.length} result${results.length === 1 ? "" : "s"}.`
      : "No posts match your search.");
  };

  // Resolve the search-index.json next to this page (respects sub-path deploys).
  const indexUrl = new URL("search-index.json", document.baseURI).href;

  let engine = null;      // the built MiniSearch instance, once ready
  let pending = null;     // a query typed before the index finished loading

  const runQuery = (q) => {
    const query = q.trim();
    if (!query) { showAll(); return; }
    if (!engine) { pending = query; say("Searching…"); return; }
    // Prefix + fuzzy matching so partial words and small typos still hit.
    showResults(engine.search(query, { prefix: true, fuzzy: 0.2 }));
  };

  const load = async () => {
    try {
      const [{ default: MiniSearch }, res] = await Promise.all([
        import("./minisearch.min.js"),
        fetch(indexUrl),
      ]);
      if (!res.ok) throw new Error(`index ${res.status}`);
      const data = await res.json();
      engine = new MiniSearch({
        fields: data.fields,
        storeFields: data.storeFields,
        searchOptions: { prefix: true, fuzzy: 0.2 },
      });
      engine.addAll(data.docs || []);
      if (pending !== null) { const q = pending; pending = null; runQuery(q); }
    } catch (_e) {
      // Leave the full static list in place; disable the box so it can't mislead.
      input.disabled = true;
      say("Search is unavailable; browse the full list below.");
    }
  };

  let timer;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => runQuery(input.value), 120);
  });
  // Load the index eagerly so the first keystroke is responsive.
  if (document.readyState !== "loading") load();
  else document.addEventListener("DOMContentLoaded", load);
})();
