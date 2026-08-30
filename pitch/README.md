# Pitch

`career-brain-pitch-deck.html` — the pitch deck. Open it in a browser; nothing to
install and nothing to serve. 5.7 MB, fully self-contained: fonts, images and the
runtime are all inside the file.

## Contents

Thirteen slides at 16:9 — ten in the main run, three backups after the close.

| | |
|---|---|
| 01 | Person |
| 02 | The gap |
| 03 | The answer |
| 04 | Why Marta |
| 05 | The message |
| 06 | Continuity |
| 07 | The stack |
| 08 | Roadmap |
| 09 | Business model |
| 10 | Close |
| A | Introduction path *(backup)* |
| B | Status *(backup)* |
| C | Pilot *(backup)* |

Speaker notes travel with the deck: every slide carries them in its
`data-speaker-notes` attribute.

## Exporting to PDF

The deck shows one slide at a time, so printing straight from the browser yields a
single page. Each slide has to be forced visible and given its own page first:

```js
// paste into the console before printing
document.querySelectorAll('deck-stage section').forEach((s) => {
  s.style.cssText += 'position:relative!important;opacity:1!important;visibility:visible!important;break-after:page;'
})
document.querySelector('deck-stage').style.cssText += 'position:static!important;height:auto!important;'
```

Then print with backgrounds on, margins none, paper 1732 × 974 px.

## Related

- [`../DESIGN.md`](../DESIGN.md) — the design system the deck follows
- [`../DEMO-FLOW.md`](../DEMO-FLOW.md) — the narrative the slides walk through
- [`../promo/`](../promo) — the 30-second cut
- [`../mockups/`](../mockups) — the frames both are built from
