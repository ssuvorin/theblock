---
name: Mono Ether
colors:
  surface: '#f9f9f9'
  surface-dim: '#dadada'
  surface-bright: '#f9f9f9'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f3f3'
  surface-container: '#eeeeee'
  surface-container-high: '#e8e8e8'
  surface-container-highest: '#e2e2e2'
  on-surface: '#1a1c1c'
  on-surface-variant: '#5a4136'
  inverse-surface: '#2f3131'
  inverse-on-surface: '#f1f1f1'
  outline: '#8e7164'
  outline-variant: '#e2bfb0'
  surface-tint: '#a04100'
  primary: '#a04100'
  on-primary: '#ffffff'
  primary-container: '#ff6b00'
  on-primary-container: '#572000'
  inverse-primary: '#ffb693'
  secondary: '#5e5e5e'
  on-secondary: '#ffffff'
  secondary-container: '#e2e2e2'
  on-secondary-container: '#646464'
  tertiary: '#5e5e5e'
  on-tertiary: '#ffffff'
  tertiary-container: '#9a9999'
  on-tertiary-container: '#313131'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#ffdbcc'
  primary-fixed-dim: '#ffb693'
  on-primary-fixed: '#351000'
  on-primary-fixed-variant: '#7a3000'
  secondary-fixed: '#e2e2e2'
  secondary-fixed-dim: '#c6c6c6'
  on-secondary-fixed: '#1b1b1b'
  on-secondary-fixed-variant: '#474747'
  tertiary-fixed: '#e4e2e2'
  tertiary-fixed-dim: '#c7c6c6'
  on-tertiary-fixed: '#1b1c1c'
  on-tertiary-fixed-variant: '#464747'
  background: '#f9f9f9'
  on-background: '#1a1c1c'
  surface-variant: '#e2e2e2'
typography:
  display-lg:
    fontFamily: Inter
    fontSize: 48px
    fontWeight: '700'
    lineHeight: '1.1'
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: Inter
    fontSize: 32px
    fontWeight: '600'
    lineHeight: '1.2'
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: '1.3'
  body-lg:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: '1.6'
  body-md:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: '1.5'
  body-sm:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: '1.4'
  label-caps:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '700'
    lineHeight: '1.0'
    letterSpacing: 0.05em
  mono-data:
    fontFamily: monospace
    fontSize: 13px
    fontWeight: '400'
    lineHeight: '1.0'
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  base: 4px
  xs: 4px
  sm: 8px
  md: 16px
  lg: 24px
  xl: 48px
  gutter: 16px
  margin-edge: 24px
---

## Brand & Style

The design system is a high-utility, minimalist framework designed for "CRM Brain." It adopts a **Technocratic Brutalist** aesthetic, prioritizing information density and structural clarity over decorative flourishes. The personality is disciplined, efficient, and transparent, aimed at power users who manage complex data relationships.

The visual narrative is built on the concept of a "digital blueprint." It utilizes a strictly monochromatic environment where meaning is conveyed through line weight, spatial grouping, and a single high-visibility action color. By eliminating depth metaphors like shadows and blurs, the UI achieves a raw, "on-the-metal" feel that emphasizes speed and architectural precision.

## Colors

The palette is anchored by **Safety Orange (#FF6B00)**, reserved exclusively for primary actions, critical alerts, and active states. This singular point of saturation ensures that the user's eye is immediately drawn to the most important task-oriented elements.

The remainder of the system is strictly grayscale. 
- **Neutral High-Contrast:** Backgrounds are pure white or very light gray to provide a sterile, lab-like environment.
- **Structural Grays:** Borders and dividers use specific gray increments to define the layout without adding visual weight.
- **Text Hierarchy:** Deep blacks are used for data and headers, while medium grays are reserved for labels and secondary metadata.

## Typography

This design system utilizes **Inter** for all UI elements to maintain a systematic, utilitarian feel. The typographic scale is designed for legibility in data-dense environments. 

- **Display & Headlines:** Use tight tracking and heavier weights to anchor pages.
- **Data Labels:** Small-caps are used for field labels to distinguish them from the actual user data.
- **Mono-Data:** While the primary face is Inter, monospaced fonts (system default) should be used for IDs, timestamps, and technical metadata to reinforce the high-tech, precise nature of the CRM.

## Layout & Spacing

The layout is governed by a **Strict 12-Column Grid** with 1px borders acting as the primary separators. 

- **Structural Borders:** Instead of using whitespace alone to separate regions (like sidebars from main content), use explicit 1px #E5E5E5 borders.
- **Density:** The system favors a "Compact" density. Gutters are kept narrow (16px) to maximize the amount of visible data on a single screen.
- **Alignment:** Everything must snap to the grid. Avoid centered layouts; use left-aligned structures to maintain a rigorous, document-like flow.
- **Responsive Flow:** On mobile, columns collapse into a single stack, but the 1px horizontal dividers remain to maintain the structural integrity.

## Elevation & Depth

This design system explicitly **rejects depth**. 
- **No Shadows:** Do not use box-shadows or ambient occlusions.
- **Layering:** Hierarchy is established through "Inlay" and "Overlay" logic. An active modal or dropdown does not float with a shadow; instead, it is contained within a high-contrast 1px black border (#000000) to "cut" through the background.
- **Tonal Stepping:** Use slightly darker background grays (#F2F2F2) to denote "sunken" areas like search bars or code blocks, and pure white for the primary "raised" interaction surface.

## Shapes

The shape language is primarily **rectilinear**. 
- **Soft Corners:** A subtle 0.25rem (4px) radius is applied to buttons and input fields to prevent the UI from feeling overly aggressive or "sharp," maintaining a professional enterprise balance.
- **Containers:** Large layout containers (cards, sidebars) should remain at 0px radius where they hit the screen edge to emphasize the architectural grid.
- **Icons:** Use thin-stroke (1px or 1.5px) line art icons. Avoid filled icons unless they represent an active "On" state.

## Components

### Buttons
- **Primary:** Solid Safety Orange background (#FF6B00) with white text. No gradient. Rectangular with 4px corners.
- **Secondary:** White background, 1px black border, black text.
- **Ghost:** No background or border, black text. Used for low-priority utility actions.

### Input Fields
- 1px border (#E5E5E5). On focus, the border changes to 1px Safety Orange. 
- Use a monospaced font for data entry where precision is required (e.g., phone numbers, IDs).

### Cards & Modules
- No shadows. Use a 1px border (#E5E5E5). 
- Headers within cards should have a 1px bottom-border to separate the title from the content.

### Status Indicators
- **Active:** Safety Orange dot.
- **Inactive/Draft:** Medium gray dot.
- **Error:** High-contrast black box with white "X".

### Data Tables
- The core of the CRM. Use 1px horizontal dividers only. 
- Alternating row zebra-striping is permitted using a very faint gray (#FAFAFA) for high-density readability.