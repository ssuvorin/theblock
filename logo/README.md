# Career Brain — logo

The mark is the product taken literally: **a relationship graph in the shape of a
brain.** The back of the head is the network you already have, drawn in the grey ramp.
The frontal lobe is the path the system found, in Safety Orange.

Flat throughout — no glow, no gradient, no bevel, no shadow. The brand book forbids
depth in the UI, and a logo that breaks its own system is a logo that will never sit
right on a screen built from it.

Open `index.html` for the full sheet with clear space, small sizes and don'ts.
Regenerate everything with `node ../build-logo.mjs`.

## Files

Every file exists in `-dark` and `-light`.

| File | Use |
|---|---|
| `career-brain-horizontal-*` | **Primary lockup.** Mark + wordmark + rule + tagline. Default everywhere there is horizontal room. |
| `career-brain-horizontal-compact-*` | Top bars and headers — no rule, no tagline. |
| `career-brain-stacked-*` | Square placements: covers, slide title cards, social avatars. |
| `career-brain-mark-*` | The mark alone, when the name is already on screen. |
| `career-brain-wordmark-*` | Type only. The one place the split colour is allowed. |
| `career-brain-appicon-*` | 180px rounded square, full mark. |
| `career-brain-monogram-*` | `CB` in a rounded square. Favicon fallback and avatars at 32px and below. |
| `career-brain-favicon-*` | Reduced mark — closed silhouette, one orange triangle. Use at 32px and below. |

## Sizes

| Size | What to use |
|---|---|
| 48px and up | Full mark — the inner web reads |
| 24–32px | Reduced mark (`favicon`) |
| Below 24px | Monogram |

## Rules

- **One orange per region.** The split-colour wordmark (`Career` grey, `Brain`
  orange) exists only for placements with no mark. Never put it next to the mark —
  that is two oranges fighting in one lockup.
- **Never recolour the hemispheres.** Grey is the network you have, orange is the path
  found. Swapping them inverts the product's whole claim.
- **Never add depth.** No glow, gradient, bevel, outline or drop shadow.
- **Never stretch, rotate or skew** the mark, and never set it on a busy image.
- Minimum clear space on every side equals the cap height of the wordmark.
