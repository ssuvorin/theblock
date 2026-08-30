# Career Brain — mockups

Claude Design export of the hackathon UI. Dark theme is canonical; light is the
fallback. Visual language is Mono Ether — technocratic brutalism, grey ramp with one
saturated action colour (Safety Orange `#FF6B00`).

## What's here

| Path | What it is |
|---|---|
| `BRANDBOOK.md` | Provenance copy of the design-session brand book. The canonical system is [`../DESIGN.md`](../DESIGN.md). |
| `Second Brain Mockups.dc.html` | The live canvas — every artboard, pan/zoom, dark/light toggle. |
| `design/*.png` | Exported frames at full resolution. |
| `design/avatars/*.png` | Cast avatars referenced by the canvas. |
| `support.js`, `image-slot.js` | Claude Design runtime the canvas needs to render. |

## Opening the canvas

`Second Brain Mockups.dc.html` loads `./support.js`, `./image-slot.js` and
`design/avatars/*.png` by relative path, so keep this directory intact and serve it
over HTTP rather than opening the file directly:

```
python3 -m http.server 8080
```

Then open <http://localhost:8080/mockups/Second%20Brain%20Mockups.dc.html>.

## Frames

| File | Screen |
|---|---|
| `00-cover-graph-dark.png` | Cover — graph with the demo cast. Promo thumbnail. |
| `01-ask-empty-dark.png` | Ask, landing state |
| `02-ask-answered-dark.png` | Ask, ranked answers |
| `03-ask-thinking-dark.png` | Ask, loading |
| `04-profile-sergey-dark.png` | Person profile with the unified timeline |
| `05-graph-dark.png` | Relationship graph with the introduction path |
| `06-signals-dark.png` | Signals / inbox |
| `13-logo-lockup-dark.png` | Wordmark lockup |

Frame numbering is the canvas's own and is not contiguous — gaps are artboards that
exist on the canvas but have not been exported as PNG yet.
