// Career Brain logo kit.
//
//   node build-logo.mjs   ->   ./logo/*.svg  +  ./logo/index.html
//
// The mark is the product's own idea taken literally: a relationship graph in the
// shape of a brain. The left hemisphere is the network you already have, drawn in the
// grey ramp; the right hemisphere is the path the system found, in Safety Orange.
//
// Drawn flat, per the brand book's don'ts — no glow, no gradient, no shadow, no 3D.
// Nodes are filled circles, edges are 1px strokes, and that is the whole vocabulary.
import { mkdirSync, writeFileSync } from 'node:fs'

const OUT = new URL('./logo/', import.meta.url)
mkdirSync(OUT, { recursive: true })

const T = {
  dark: { fg: '#F3F4F6', mut: '#9A9CA4', bd: '#34373D', edge: '#585D66', acc: '#FF6B00', bg: '#0A0B0D', card: '#111316' },
  light: { fg: '#1A1C1C', mut: '#8A8A8A', bd: '#D8D8D8', edge: '#B4B4B4', acc: '#FF6B00', bg: '#F9F9F9', card: '#FFFFFF' },
}

// ---------------------------------------------------------------- the mark
// Brain profile facing right, in a 120x96 box. `h: 1` marks the right hemisphere -
// the found path. `r` is the node radius; hubs are larger.
const NODES = [
  // --- hull, clockwise from the upper back. The silhouette is the whole job:
  // a broad dome, the frontal lobe dropping to a temporal hook at the front,
  // a notch under it, then the lower lobe and the occipital curve back up.
  { id: 'a', x: 18, y: 41, r: 2.6 }, { id: 'b', x: 22, y: 28, r: 2.6 },
  { id: 'c', x: 33, y: 17, r: 2.8 }, { id: 'd', x: 47, y: 10, r: 3.2 },
  { id: 'e', x: 63, y: 8, r: 2.8, h: 1 }, { id: 'f', x: 78, y: 11, r: 3.2, h: 1 },
  { id: 'g', x: 91, y: 20, r: 2.8, h: 1 }, { id: 'h', x: 100, y: 33, r: 3.4, h: 1 },
  { id: 'i', x: 101, y: 46, r: 2.8, h: 1 }, { id: 'j', x: 95, y: 58, r: 3.0, h: 1 },
  { id: 'k', x: 86, y: 68, r: 2.8, h: 1 }, { id: 'l', x: 75, y: 74, r: 3.2, h: 1 },
  { id: 'm', x: 65, y: 65, r: 2.6, h: 1 },
  { id: 'n', x: 55, y: 76, r: 3.0 }, { id: 'o', x: 43, y: 74, r: 2.6 },
  { id: 'p', x: 32, y: 66, r: 2.6 }, { id: 'q', x: 22, y: 54, r: 2.6 },
  // --- inner web
  { id: 'r', x: 33, y: 34, r: 2.2 }, { id: 's', x: 47, y: 25, r: 2.4 },
  { id: 't', x: 63, y: 22, r: 2.6, h: 1 }, { id: 'u', x: 79, y: 28, r: 3.0, h: 1 },
  { id: 'v', x: 91, y: 41, r: 2.4, h: 1 },
  { id: 'w', x: 30, y: 48, r: 2.2 }, { id: 'x', x: 44, y: 41, r: 2.6 },
  { id: 'y', x: 59, y: 38, r: 3.4, h: 1 }, { id: 'z', x: 76, y: 44, r: 2.8, h: 1 },
  { id: 'A', x: 40, y: 59, r: 2.2 }, { id: 'B', x: 54, y: 55, r: 2.6 },
  { id: 'C', x: 70, y: 54, r: 2.6, h: 1 }, { id: 'D', x: 86, y: 53, r: 2.2, h: 1 },
]

const EDGES = [
  // hull
  'ab', 'bc', 'cd', 'de', 'ef', 'fg', 'gh', 'hi', 'ij', 'jk', 'kl', 'lm', 'mn', 'no', 'op', 'pq', 'qa',
  // upper web
  'br', 'cr', 'rs', 'ds', 'st', 'et', 'tu', 'fu', 'gu', 'uv', 'hv', 'vi', 'vz',
  // mid web
  'rw', 'aw', 'wx', 'sx', 'xy', 'ty', 'yz', 'uz', 'zD', 'Dj', 'Di', 'zC', 'yC',
  // lower web
  'wA', 'qA', 'Ap', 'AB', 'xB', 'Bn', 'Bo', 'BC', 'Cm', 'Ck', 'CD', 'Cl',
]

const byId = Object.fromEntries(NODES.map((n) => [n.id, n]))
const isHot = (n) => n.h === 1

/** The mark. `scale` maps the 120x96 space onto the caller's box. */
function mark(t, { edgeWidth = 1.4 } = {}) {
  const edges = EDGES.map((e) => {
    const a = byId[e[0]]
    const b = byId[e[1]]
    const hot = isHot(a) && isHot(b)
    return `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${hot ? t.acc : t.edge}" stroke-width="${edgeWidth}"/>`
  }).join('')
  const dots = NODES.map(
    (n) => `<circle cx="${n.x}" cy="${n.y}" r="${n.r}" fill="${isHot(n) ? t.acc : t.mut}"/>`,
  ).join('')
  return `<g>${edges}${dots}</g>`
}

/** Reduced mark for 16-32px: the closed silhouette plus one orange triangle in the
 *  frontal lobe. The inner web does not survive at this size and the crossing lines
 *  read as a division rather than a brain, so they are dropped rather than shrunk. */
const SMALL_NODES = ['a', 'b', 'd', 'f', 'h', 'j', 'l', 'm', 'n', 'p', 'u']
const SMALL_EDGES = ['ab', 'bd', 'df', 'fh', 'hj', 'jl', 'lm', 'mn', 'np', 'pa', 'uf', 'uh']

function markSmall(t) {
  const edges = SMALL_EDGES.map((e) => {
    const a = byId[e[0]]
    const b = byId[e[1]]
    const hot = isHot(a) && isHot(b)
    return `<line x1="${a.x}" y1="${a.y}" x2="${b.x}" y2="${b.y}" stroke="${hot ? t.acc : t.edge}" stroke-width="3.2"/>`
  }).join('')
  const dots = SMALL_NODES.map((id) => {
    const n = byId[id]
    return `<circle cx="${n.x}" cy="${n.y}" r="${isHot(n) ? 5.6 : 4.8}" fill="${isHot(n) ? t.acc : t.mut}"/>`
  }).join('')
  return `<g>${edges}${dots}</g>`
}

const FONTS = `<style>text{font-family:Inter,-apple-system,'Segoe UI',sans-serif}</style>`
const svg = (w, h, body, title) =>
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="${title}">
  <title>${title}</title>${FONTS}
${body}
</svg>
`

const WORD = 'Career Brain'
const TAG = 'Your network, working for your career.'

// ---------------------------------------------------------------- lockups
function markOnly(theme) {
  const t = T[theme]
  return svg(120, 96, mark(t), 'Career Brain mark')
}

function horizontal(theme, { tagline = true } = {}) {
  const t = T[theme]
  const body = `<g transform="translate(0,14)">${mark(t)}</g>
  <text x="134" y="${tagline ? 50 : 62}" font-size="42" font-weight="600" letter-spacing="-1.5" fill="${t.fg}">${WORD}</text>
  ${tagline ? `<rect x="134" y="62" width="72" height="4" fill="${t.acc}"/>
  <text x="134" y="88" font-size="15" font-weight="400" letter-spacing="0.2" fill="${t.mut}">${TAG}</text>` : ''}`
  return svg(600, 124, body, 'Career Brain horizontal lockup')
}

function stacked(theme) {
  const t = T[theme]
  const body = `<g transform="translate(150,0)">${mark(t)}</g>
  <text x="210" y="150" text-anchor="middle" font-size="44" font-weight="600" letter-spacing="-1.6" fill="${t.fg}">${WORD}</text>
  <rect x="174" y="164" width="72" height="4" fill="${t.acc}"/>
  <text x="210" y="192" text-anchor="middle" font-size="15" font-weight="400" letter-spacing="0.2" fill="${t.mut}">${TAG}</text>`
  return svg(420, 210, body, 'Career Brain stacked lockup')
}

/** Wordmark alone. The one place the split colour is allowed - there is no mark to
 *  carry the accent, so BRAIN takes it. Never use this next to the mark. */
function wordmark(theme) {
  const t = T[theme]
  const body = `<text x="0" y="52" font-size="56" font-weight="600" letter-spacing="-2" fill="${t.fg}">Career <tspan fill="${t.acc}">Brain</tspan></text>
  <rect x="0" y="66" width="96" height="5" fill="${t.acc}"/>
  <text x="0" y="94" font-size="16" font-weight="400" letter-spacing="0.2" fill="${t.mut}">${TAG}</text>`
  return svg(400, 112, body, 'Career Brain wordmark')
}

function appIcon(theme) {
  const t = T[theme]
  const body = `<rect width="180" height="180" rx="40" fill="${theme === 'dark' ? t.bg : t.card}"/>
  <g transform="translate(6.7,31.2) scale(1.4)">${mark(t, { edgeWidth: 1.5 })}</g>`
  return svg(180, 180, body, 'Career Brain app icon')
}

function monogram(theme) {
  const t = T[theme]
  const body = `<rect width="180" height="180" rx="40" fill="${theme === 'dark' ? t.bg : t.card}"/>
  <text x="90" y="122" text-anchor="middle" font-size="86" font-weight="600" letter-spacing="-3" fill="${t.fg}">C<tspan fill="${t.acc}">B</tspan></text>`
  return svg(180, 180, body, 'Career Brain monogram')
}

function favicon(theme) {
  const t = T[theme]
  return svg(120, 96, markSmall(t), 'Career Brain favicon')
}

const files = {}
for (const theme of ['dark', 'light']) {
  files[`career-brain-mark-${theme}.svg`] = markOnly(theme)
  files[`career-brain-horizontal-${theme}.svg`] = horizontal(theme)
  files[`career-brain-horizontal-compact-${theme}.svg`] = horizontal(theme, { tagline: false })
  files[`career-brain-stacked-${theme}.svg`] = stacked(theme)
  files[`career-brain-wordmark-${theme}.svg`] = wordmark(theme)
  files[`career-brain-appicon-${theme}.svg`] = appIcon(theme)
  files[`career-brain-monogram-${theme}.svg`] = monogram(theme)
  files[`career-brain-favicon-${theme}.svg`] = favicon(theme)
}
for (const [name, body] of Object.entries(files)) writeFileSync(new URL(name, OUT), body)

// ---------------------------------------------------------------- sheet
const panel = (theme) => {
  const t = T[theme]
  const box = (label, file, w, note) => `<div style="border:1px solid ${t.bd};background:${t.card};padding:28px;display:flex;flex-direction:column;gap:18px;min-width:0">
    <div style="font:700 11px/1 Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:${t.mut}">${label}</div>
    <div style="display:flex;align-items:center;justify-content:center;flex:1;min-height:120px"><img src="${file}" style="max-width:${w};height:auto"></div>
    ${note ? `<div style="font:400 12px/1.5 Inter,sans-serif;color:${t.mut}">${note}</div>` : ''}
  </div>`
  return `<section style="background:${t.bg};padding:40px">
    <div style="font:700 11px/1 Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:${t.mut};margin-bottom:24px">${theme} theme</div>
    <div style="display:grid;grid-template-columns:2fr 1fr;gap:20px;margin-bottom:20px">
      ${box('Primary — horizontal', `career-brain-horizontal-${theme}.svg`, '100%', 'Default lockup. Use everywhere there is horizontal room.')}
      ${box('Stacked', `career-brain-stacked-${theme}.svg`, '260px', 'Square placements: covers, slides, avatars.')}
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px">
      ${box('Mark alone', `career-brain-mark-${theme}.svg`, '150px', 'When the name is already on screen.')}
      ${box('Wordmark', `career-brain-wordmark-${theme}.svg`, '100%', 'No mark present — BRAIN carries the accent instead.')}
      ${box('App icon', `career-brain-appicon-${theme}.svg`, '110px', '180px rounded square.')}
      ${box('Monogram', `career-brain-monogram-${theme}.svg`, '110px', 'Favicon fallback, avatars, 32px and below.')}
    </div>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:20px;margin-top:20px">
      ${box('Compact horizontal', `career-brain-horizontal-compact-${theme}.svg`, '100%', 'Top bars — no tagline, no rule.')}
      ${box('Small mark', `career-brain-favicon-${theme}.svg`, '90px', 'Reduced web. Use at 32px and below.')}
      <div style="border:1px solid ${t.bd};background:${t.card};padding:28px;display:flex;flex-direction:column;gap:14px">
        <div style="font:700 11px/1 Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:${t.mut}">Small sizes</div>
        <div style="display:flex;align-items:flex-end;gap:20px">
          <img src="career-brain-favicon-${theme}.svg" width="16"><img src="career-brain-favicon-${theme}.svg" width="24">
          <img src="career-brain-favicon-${theme}.svg" width="32"><img src="career-brain-mark-${theme}.svg" width="48">
        </div>
        <div style="font:400 12px/1.5 Inter,sans-serif;color:${t.mut}">16 · 24 · 32 px use the reduced mark. 48px and up use the full one.</div>
      </div>
      <div style="border:1px solid ${t.bd};background:${t.card};padding:28px;display:flex;flex-direction:column;gap:14px">
        <div style="font:700 11px/1 Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:${t.mut}">Clear space</div>
        <div style="position:relative;padding:24px;border:1px dashed ${t.acc}">
          <img src="career-brain-mark-${theme}.svg" width="96" style="display:block">
        </div>
        <div style="font:400 12px/1.5 Inter,sans-serif;color:${t.mut}">Minimum clear space on every side equals the cap height of the wordmark.</div>
      </div>
    </div>
  </section>`
}

writeFileSync(
  new URL('index.html', OUT),
  `<!doctype html><html><head><meta charset="utf-8"><title>Career Brain — logo</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>html,body{margin:0;background:#0A0B0D}</style></head><body>
<div style="background:#0A0B0D;padding:40px 40px 0">
  <div style="font:700 11px/1 Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#9A9CA4;margin-bottom:12px">Career Brain · logo</div>
  <div style="font:600 40px/1.15 Inter,sans-serif;letter-spacing:-1.4px;color:#F3F4F6;margin-bottom:10px">The graph is the brain</div>
  <div style="font:400 15px/1.6 Inter,sans-serif;color:#9A9CA4;max-width:72ch">The mark is the product taken literally: a relationship graph in the shape of a brain. The back of the head is the network you already have, in the grey ramp. The frontal lobe is the path the system found, in Safety Orange. Flat throughout — no glow, no gradient, no shadow, per the brand book.</div>
  <div style="display:flex;align-items:flex-end;gap:56px;padding:44px 0 4px">
    <img src="career-brain-mark-dark.svg" width="380">
    <img src="career-brain-favicon-dark.svg" width="150">
  </div>
</div>
${panel('dark')}${panel('light')}
<section style="background:#0A0B0D;padding:40px;border-top:1px solid #34373D">
  <div style="font:700 11px/1 Inter,sans-serif;letter-spacing:.12em;text-transform:uppercase;color:#9A9CA4;margin-bottom:20px">Don'ts</div>
  <ul style="font:400 14px/1.8 Inter,sans-serif;color:#9A9CA4;max-width:80ch;margin:0;padding-left:20px">
    <li>Never use the split-colour wordmark next to the mark — that is two oranges in one region.</li>
    <li>Never add glow, gradient, bevel or drop shadow to the mark. It is flat by design.</li>
    <li>Never recolour the hemispheres. Grey is the network you have, orange is the path found; swapping them inverts the meaning.</li>
    <li>Never stretch, rotate or outline the mark, and never place it on a busy image.</li>
    <li>Below 48px use the reduced mark; below 24px use the monogram instead.</li>
  </ul>
</section>
</body></html>`,
)

console.log(`wrote ${Object.keys(files).length} svg + index.html`)
