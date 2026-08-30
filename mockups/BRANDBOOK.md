# Career Brain — Brand book

> **Provenance copy.** This is the brand book as it came out of the design session
> that produced the canvas in this directory. The canonical design system lives at
> [`../DESIGN.md`](../DESIGN.md), which merges this document with the earlier
> light-theme Mono Ether system. Where the two disagree, `DESIGN.md` wins; this file
> is kept so the export stays intact and reviewable.

**Product:** Career Brain — network-first job search
**Tagline:** Your network, working for your career.
**Design system:** Mono Ether — technocratic brutalism, dark-first
**Status:** hackathon build · dark theme is canonical, light is fallback

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

### Dark theme (canonical — used in every deliverable)

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

### Light theme (secondary)
`--bg #F9F9F9` · `--lowest #FFFFFF` · `--low #F3F3F3` · `--high #E8E8E8` ·
`--fg #1A1C1C` · `--fgv #5A4136` · `--mut #8A8A8A` · `--bd #E5E5E5` ·
`--acc #FF6B00` · `--accL #A04200` (darker, for contrast on white).

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

- 8px grid. Frame padding 24px, card padding 16–24px, inter-element 12–16px.
- Structure is drawn with **1px `--bd` borders**, not whitespace or shadows.
- Shell: sidebar 240px (rail 64px), top bar 56px, right rail 320px.
- Product frames 1440×900; promo frames 16:9 (1440×810, exported 2×).
- Demo and pitch frames centre their content column (1060–1120px) inside the frame;
  utility screens stay left-aligned.

### Shape
Containers 0px radius. Buttons, inputs, chips 4px. Avatars and status dots round.

### Elevation
No shadows, ever. Hierarchy comes from the grey ramp and 1px borders. Overlays are
cut out with a high-contrast border, not floated with a shadow.

---

## 5. Components

- **Button** — primary: solid orange, white text, 36–44px tall, uppercase 700.
  Secondary: 1px `--bds`. Ghost: text only. Danger: 1px `--err`, error text.
- **Badge / chip** — 1px border, uppercase mono 11–12px. Accent border for the one
  thing that matters (`GONE COLD 14M`, `COLLABUTE SUMMARY`).
- **Card** — 1px `--bd`, `--lowest` fill, header row with a bottom rule.
- **Signal card** — 3px left border: orange for follow-up and cold, green for
  opportunity.
- **Relationship meter** — 6px track on `--hi2`, orange fill, mono value.
  Cold relationships use `--idle`, not orange.
- **Data table** — 1px horizontal rules only, zebra with `--low`, mono for dates and
  source chips.
- **Empty state** — dashed 1px border on `--low`, so it never reads as real content.
- **Graph** — nodes sized by relationship strength, avatar inside the node, orange
  ring on path members, white ring on you. Edges 1px `--bd`; the introduction path is
  a dashed orange edge with a soft glow.

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

## 7. Imagery

- Faces only, square crops, head centred in the upper 60%, slight warm-neutral grade
  so they sit in the dark UI. Circular masks.
- Avatar sizes: 28px (table), 32px (nav), 40–44px (card), 64px (profile hero),
  44–88px (graph nodes).
- No illustration, no stock office scenes, no 3D, no gradient meshes.
- Every avatar is a drop target — real photos can replace a placeholder at any time.

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

Wordmark: **Career Brain**, Inter 600, `-0.035em`, `--fg`, with a 4px `--acc` rule
under it and the tagline *Your network, working for your career.* below in `--fgv`. An orange
square (20–44px) can precede the wordmark as the mark. Minimum clear space equals the
cap height. Never on a busy image, never in another colour, never outlined.

---

## 11. Don'ts

- No shadows, blurs or glass.
- No second filled orange element in one screen region.
- No hard-coded hex in the UI — every colour resolves through a token, which is what
  makes the theme flip a single attribute.
- No partner logo bars, no "powered by".
- No emoji, no hand-drawn illustration, no shimmering skeletons.
- No centred layouts in utility screens; keep them left-aligned and document-like.
