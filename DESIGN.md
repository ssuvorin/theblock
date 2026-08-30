---
name: Career Brain — Mono Ether
tagline: Your network, working for your career.
canonical_theme: dark
supersedes:
  - CRM Brain / Mono Ether (light-only Stitch export)
  - mockups/BRANDBOOK.md (design-session export, kept for provenance)
colors-dark:
  bg: '#0a0b0d'
  lowest: '#111316'
  low: '#16181b'
  cont: '#1a1d21'
  high: '#232629'
  hi2: '#2c3035'
  fg: '#f3f4f6'
  fgv: '#d2beb2'
  mut: '#9a9ca4'
  bd: '#34373d'
  bds: '#f3f4f6'
  acc: '#ff6b00'
  accL: '#ff9a52'
  wash: 'rgba(255,107,0,0.14)'
  pos: '#56d99a'
  err: '#ffb4ab'
  idle: '#5e5e5e'
colors-light:
  bg: '#f9f9f9'
  lowest: '#ffffff'
  low: '#f3f3f3'
  cont: '#eeeeee'
  high: '#e8e8e8'
  hi2: '#e2e2e2'
  fg: '#1a1c1c'
  fgv: '#5a4136'
  mut: '#8a8a8a'
  bd: '#e5e5e5'
  bds: '#1a1c1c'
  acc: '#ff6b00'
  accL: '#a04200'
  wash: 'rgba(255,107,0,0.08)'
  pos: '#1f7a45'
  err: '#ba1a1a'
  idle: '#9a9999'
typography:
  display: { family: Inter, size: 48px, weight: '600', lineHeight: '1.1', tracking: -0.03em }
  headline: { family: Inter, size: 36px, weight: '600', lineHeight: '1.2', tracking: -0.03em }
  headline-md: { family: Inter, size: 24px, weight: '600', lineHeight: '1.3', tracking: -0.02em }
  title: { family: Inter, size: 19px, weight: '600', lineHeight: '1.3', tracking: -0.02em }
  body: { family: Inter, size: 14px, weight: '400', lineHeight: '1.5' }
  label-caps: { family: Inter, size: 12px, weight: '700', lineHeight: '1.0', tracking: 0.06em, transform: uppercase }
  mono-data: { family: JetBrains Mono, size: 12px, weight: '400', lineHeight: '1.0', tracking: 0.12em }
spacing: { base: 4px, xs: 4px, sm: 8px, md: 16px, lg: 24px, xl: 48px, gutter: 16px, edge: 24px }
radius: { sm: 2px, DEFAULT: 4px, lg: 8px, full: 9999px, container: 0px }
---

# Career Brain — design system

**Product:** Career Brain — network-first job search
**Tagline:** Your network, working for your career.
**Status:** hackathon build · **dark is canonical**, light is the fallback

Mono Ether: technocratic brutalism. Information density over decoration, structure
carried by 1px borders, one saturated colour reserved for action.

> **This file supersedes two earlier documents.** The original light-only Mono Ether
> export (product name "CRM Brain") is retired — its light ramp and scales survive
> here, nothing else. `mockups/BRANDBOOK.md` is the design-session export and is kept
> for provenance; where the two disagree, this file wins. Token names and dark values
> here match `mockups/Second Brain Mockups.dc.html` exactly, so the canvas, the docs
> and any implementation stay in step.

---

## 1. Positioning

A career brain that remembers every relationship across email, meetings, LinkedIn and
messengers — and answers questions about your own network.

One line for judges: *a job search engine tells you who is hiring, a CRM tells you who
you know — this connects both.*

### Voice

Matter-of-fact, technical, no hype. Copy names the job a thing does, never the vendor
behind it. No exclamation marks, no "powered by AI", no emoji. Interface labels are
uppercase and short; body prose is plain sentences.

---

## 2. Colour

Single point of saturation: **Safety Orange `#FF6B00`**. Everything else is a grey
ramp. Orange marks the primary action, the live state and the introduction path — a
second filled orange element in one region is a bug.

### Dark theme (canonical)

| Token | Value | Use |
|---|---|---|
| `--bg` | `#0A0B0D` | app background |
| `--lowest` | `#111316` | cards, sidebar, top bar |
| `--low` | `#16181B` | sunken areas: search fields, code, logs |
| `--cont` | `#1A1D21` | nested container |
| `--high` | `#232629` | hover, active row, skeleton bars |
| `--hi2` | `#2C3035` | meter track, avatar fallback |
| `--fg` | `#F3F4F6` | primary text, data |
| `--fgv` | `#D2BEB2` | secondary prose (warm variant) |
| `--mut` | `#9A9CA4` | mono metadata, labels, timestamps |
| `--bd` | `#34373D` | 1px structure — the main separator |
| `--bds` | `#F3F4F6` | strong border: secondary button, you-node |
| `--acc` | `#FF6B00` | primary action, live dot, intro path |
| `--accL` | `#FF9A52` | accent text on dark |
| `--wash` | `rgba(255,107,0,0.14)` | active nav, selected row |
| `--pos` | `#56D99A` | opportunity, synced |
| `--err` | `#FFB4AB` | needs reconnect, destructive |
| `--idle` | `#5E5E5E` | cold relationship, disabled source |

Promo frames sit one step deeper: background `#0A0B0D`, card `#131518`, border
`#34373D`. Never crush to pure black — video compression eats it.

### Light theme (fallback)

| Token | Value | Token | Value |
|---|---|---|---|
| `--bg` | `#F9F9F9` | `--bd` | `#E5E5E5` |
| `--lowest` | `#FFFFFF` | `--bds` | `#1A1C1C` |
| `--low` | `#F3F3F3` | `--acc` | `#FF6B00` |
| `--cont` | `#EEEEEE` | `--accL` | `#A04200` |
| `--high` | `#E8E8E8` | `--wash` | `rgba(255,107,0,0.08)` |
| `--hi2` | `#E2E2E2` | `--pos` | `#1F7A45` |
| `--fg` | `#1A1C1C` | `--err` | `#BA1A1A` |
| `--fgv` | `#5A4136` | `--idle` | `#9A9999` |
| `--mut` | `#8A8A8A` | | |

Both themes define the complete set — no token is defined in only one of them, which
is what makes the theme flip a single attribute.

**Relationship heat** rides entirely on this scale: orange is alive, `--idle` grey is
gone cold. Never introduce a second hue for it.

---

## 3. Typography

- **Inter** — all UI and prose. 400 body, 500 emphasis, 600 headings, 700 labels.
- **JetBrains Mono** — timestamps, IDs, counts, handles, system read-outs. Never body.

| Role | Size / weight | Notes |
|---|---|---|
| Promo wordmark | 76px / 600, `-0.035em` | never wraps |
| Promo headline | 40–56px / 600, `-0.03em` | one idea per frame |
| Screen headline | 36–44px / 600, `-0.03em` | one per frame |
| Person name (profile) | 32px / 600, `-0.025em` | |
| Card title | 19px / 600, `-0.02em` | |
| Body | 13–17px / 400, 1.5 | 17px in demo and promo frames |
| Mono label | 12px, `0.12em`, uppercase | metadata, read-outs |
| Button / badge | 12–13px / 700, `0.06em`, uppercase | |
| Hero number | 44px / 700, `-0.03em` | metric tiles |

Minimums: nothing below 12px in a 1440×900 frame; nothing below 17px in a 16:9 promo
frame. Two type sizes per screen region, no more.

---

## 4. Layout

- **8px rhythm** on a 4px base scale (`4 · 8 · 16 · 24 · 48`). Frame padding 24px,
  card padding 16–24px, inter-element 12–16px.
- Structure is drawn with **1px `--bd` borders**, not whitespace and never shadows.
- Shell: sidebar 240px (rail 64px), top bar 56px, right rail 320px.
- Product frames 1440×900; promo frames 16:9 (1440×810, exported 2×).
- Demo and pitch frames centre their content column (1060–1120px) inside the frame;
  utility screens stay left-aligned and document-like.

### Shape

Containers 0px radius. Buttons, inputs, chips 4px. Avatars and status dots round.

### Elevation

No shadows, ever. Hierarchy comes from the grey ramp and 1px borders. Overlays are cut
out with a high-contrast border, not floated with a shadow.

---

## 5. Components

- **Button** — primary: solid orange, white text, 36–44px tall, uppercase 700.
  Secondary: 1px `--bds`. Ghost: text only. Danger: 1px `--err`, error text.
- **Badge / chip** — 1px border, uppercase mono 11–12px. Accent border for the one
  thing that matters (`GONE COLD 14M`, `COLLABUTE SUMMARY`).
- **Card** — 1px `--bd`, `--lowest` fill, header row with a bottom rule.
- **Signal card** — 3px left border: orange for follow-up and cold, green for
  opportunity.
- **Relationship meter** — 6px track on `--hi2`, orange fill, mono value. Cold
  relationships use `--idle`, not orange.
- **Data table** — 1px horizontal rules only, zebra with `--low`, mono for dates and
  source chips.
- **Empty state** — dashed 1px border on `--low`, so it never reads as real content.
- **Graph** — nodes sized by relationship strength, avatar inside the node, orange
  ring on path members, white ring on you. Edges 1px `--bd`; the introduction path is
  a dashed orange edge with a soft glow.

### Icons

Thin-stroke line art on an 18px grid, 1.5px stroke, `currentColor`. No filled icons
except status dots. Channel glyphs are monochrome — colour appears only as an 8px
status dot beside them.

---

## 6. Motion

Motion is functional: it shows arrival, liveness and a path. Decoration never
animates, skeletons never shimmer.

| Name | Use | Timing |
|---|---|---|
| `sbrise` | cards, rows, nodes arriving | 600–700ms, `cubic-bezier(.2,.8,.2,1)`, staggered 150–250ms |
| `sbdash` | introduction path travelling | 1.4–1.6s linear, infinite |
| `sbedge` | accent path / primary action breathing | 3.2–3.4s ease-in-out |
| `sbhalo` | you-node and target node pulse | 3.4s ease-out |
| `sbpulse` | live dot, typing caret | 1.2–1.6s ease-in-out |
| `sbsweep` | scan line across the promo cover | 7s linear |

---

## 7. Imagery and avatars

- **Photographic faces are the default**, as shipped in `mockups/design/avatars/`.
  Square crops, head centred in the upper 60%, slight warm-neutral grade so they sit
  in the dark UI. Circular masks.
- Avatar sizes: 28px (table), 32px (nav), 40–44px (card), 64px (profile hero),
  44–88px (graph nodes).
- **Every avatar is a drop target** — a real photo replaces a placeholder at any time.
- Where no photo exists, fall back to a generated mark rather than a stock face: a
  person the system reconstructed from email metadata has no portrait, and inventing a
  realistic one claims knowledge the product does not have.
- No illustration, no stock office scenes, no 3D, no gradient meshes.

---

## 8. Partners

Partners are named by the job they do, as a system read-out, never as a logo bar. No
partner colour is ever introduced.

| Partner | The job | Status line |
|---|---|---|
| **Convex** | The memory itself. People, edges, timeline entries and signals live here and stream to the UI in real time. | `LIVE · 1.2M DOCS` |
| **Context.dev** | Turns raw threads into the context that answers a question — resolves entities and ranks who is relevant. | `INDEXING · 4,212 THREADS` |
| **Collabute** | Joins the calls this CRM schedules, records and transcribes them, then returns a summary into the timeline. | `NOTETAKER · 96 MEETINGS` |

Placement: provenance strip under the question on *Ask — answered*; read-out in the
Graph, Signals and Profile headers; the *Built on* card at the foot of *Sources*; the
judge-facing *Built on* frame.

**Devin** built the product and never appears in the product UI. It gets two homes
only: the canvas cover and Settings → About, as
`BUILT WITH DEVIN · 34 AGENT SESSIONS`.

---

## 9. Cast (canonical demo data)

| Person | Role | Relationship |
|---|---|---|
| **Alex Ivanov** (you) | marketing business, crypto side project | — |
| **Marta** | VP Product, crypto infrastructure, Dubai | met at TOKEN2049, introduced by Alex, last contact 8 months |
| **Sergey Lapin** | CTO in an AI tech startup, Dubai | met at an AI meetup, hiring and expansion discussed, NDA signed |
| **John** | Investor, digital assets, UAE | strong relationship, portfolio companies hiring in Dubai |
| **Daniel Ruiz** | Ops lead, Palm Logistics, Dubai | Telegram contact, role appeared at his company |
| **Nadia, Omar, Lena, Tom, Ruth** | secondary graph nodes | fill the network, mostly cold |

Names, roles, percentages and dates stay identical across every frame. If two frames
disagree, the Person profile frame wins.

---

## 10. Logo

The mark is a **relationship graph in the shape of a brain** — the product taken
literally. The back of the head is the network you already have, drawn in the grey
ramp (`#585D66` dark / `#B4B4B4` light for the web, `--mut` for the nodes). The
frontal lobe is the path the system found, in `--acc`. Flat: no glow, no gradient, no
bevel, no shadow — a logo that breaks its own system never sits right on a screen
built from that system.

> The edge tone is deliberately not `--bd`. That token is a UI separator and
> disappears against `--bg` at logo scale; the silhouette falls apart with it.

**Primary lockup:** mark, then the wordmark **Career Brain** in Inter 600 at
`-0.035em` in `--fg`, a 4px `--acc` rule beneath it, and the tagline
*Your network, working for your career.* in `--fgv`. Minimum clear space on every side
equals the wordmark's cap height.

**Variants** — all in dark and light, under `logo/`:

| File | Use |
|---|---|
| `career-brain-horizontal-*` | Primary. Default wherever there is horizontal room. |
| `career-brain-horizontal-compact-*` | Top bars — no rule, no tagline. |
| `career-brain-stacked-*` | Square placements: covers, slide title cards, avatars. |
| `career-brain-mark-*` | Mark alone, when the name is already on screen. |
| `career-brain-wordmark-*` | Type only. The one place the split colour is allowed. |
| `career-brain-appicon-*` | 180px rounded square, full mark. |
| `career-brain-monogram-*` | `CB` in a rounded square. |
| `career-brain-favicon-*` | Reduced mark. |

**Sizes.** 48px and up use the full mark. 24–32px use the reduced mark — a different
drawing, not a scaled copy: the closed silhouette plus one orange triangle in the
frontal lobe. The inner web is dropped rather than shrunk, because compressed it reads
as a split rather than a brain. Below 24px use the `CB` monogram.

**The split-colour wordmark** — `Career` in `--fg`, `Brain` in `--acc` — exists only
for placements that carry no mark. Never set it beside the mark: that is two filled
oranges in one region, which §11 forbids.

**Never** recolour the hemispheres (grey is the network you have, orange is the path
found — swapping them inverts the product's claim), add depth of any kind, stretch,
rotate, outline, or place the mark on a busy image.

Regenerate the whole kit with `node build-logo.mjs`; `logo/index.html` is the sheet
with clear space, small sizes and don'ts.

## 11. Don'ts

- No shadows, blurs or glass.
- No second filled orange element in one screen region.
- No hard-coded hex in the UI — every colour resolves through a token, which is what
  makes the theme flip a single attribute.
- No partner logo bars, no "powered by".
- No emoji, no hand-drawn illustration, no shimmering skeletons.
- No centred layouts in utility screens; keep them left-aligned and document-like.
