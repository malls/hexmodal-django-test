# Hexmodal Design System & Brand Guidelines

> **All visual and interactive elements must conform to this specification.** This includes frontend applications, UI components, API documentation, dashboards, and any client-facing interfaces. See example in `design-system.html`.

---

## Color Palette

### Primary Colors

**Slate** — Core brand identity, trust, technical depth
```
Slate-50    #f8fafc    Background, very light UI
Slate-100   #f1f5f9    Secondary background, borders
Slate-200   #e2e8f0    Border, divider
Slate-300   #cbd5e1    Secondary border
Slate-400   #94a3b8    Tertiary text
Slate-500   #64748b    Secondary text (muted)
Slate-600   #475569    Primary text (body)
Slate-700   #334155    Emphasized text
Slate-800   #1e293b    Dark text, headings
Slate-900   #0f172a    Darkest text (high contrast)
```

**Indigo** — Primary action, focus, interactive elements
```
Indigo-50   #eef2ff    Background tint
Indigo-100  #e0e7ff    Light interactive
Indigo-200  #c7d2fe    Border hover
Indigo-300  #a5b4fc    Focus ring
Indigo-400  #818cf8    Interactive hover
Indigo-500  #6366f1    PRIMARY BUTTON, links
Indigo-600  #4f46e5    Interactive pressed
Indigo-700  #4338ca    Dark mode primary
Indigo-800  #3730a3    Very dark primary
```

### Semantic Colors

**Success** — Positive actions, passing status, confirmation
```
Success-50    #f0fdf4
Success-100   #dcfce7
Success-500   #22c55e    Primary success green
Success-600   #16a34a
Success-700   #15803d    Dark mode success
```

**Warning** — Caution, degraded service, attention needed
```
Warning-50    #fffbeb
Warning-100   #fef3c7
Warning-500   #eab308    Primary warning yellow
Warning-600   #ca8a04
Warning-700   #a16207    Dark mode warning
```

**Error** — Failure, blocking issue, danger
```
Error-50      #fef2f2
Error-100     #fee2e2
Error-500     #ef4444    Primary error red
Error-600     #dc2626
Error-700     #b91c1c    Dark mode error
```

**Info** — Informational, contextual hints
```
Info-50       #f0f9ff
Info-100      #e0f2fe
Info-500      #0ea5e9    Primary info blue
Info-600      #0284c7
Info-700      #0369a1    Dark mode info
```

### Neutral & Background

```
White         #ffffff   Surfaces, cards, inputs
Black         #000000   Maximum contrast

// Dark mode backgrounds
Dark-900      #111827   Primary dark background
Dark-800      #1f2937   Secondary dark background
Dark-700      #374151   Tertiary dark background
```

---

## Typography

### Font Families

```
System Font Stack (Preferred):
  -apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue", sans-serif

Monospace (Code):
  "SF Mono", Monaco, "Inconsolata", "Fira Mono", monospace
```

### Type Scale

All sizes in `px`, based on `16px` root font size.

| Use Case | Size | Line Height | Weight | Letter Spacing |
|----------|------|-------------|--------|---|
| **H1** — Page title | `36px` | `1.2` (43px) | `700 Bold` | `-0.01em` |
| **H2** — Section title | `28px` | `1.3` (36px) | `700 Bold` | `-0.005em` |
| **H3** — Subsection | `24px` | `1.35` (32px) | `600 Semi-bold` | `0` |
| **H4** — Minor heading | `20px` | `1.4` (28px) | `600 Semi-bold` | `0` |
| **Body Large** — Lead text | `18px` | `1.6` (29px) | `400 Regular` | `0` |
| **Body** — Standard text | `16px` | `1.6` (26px) | `400 Regular` | `0` |
| **Body Small** — Secondary text | `14px` | `1.6` (22px) | `400 Regular` | `0` |
| **Caption** — Metadata, labels | `12px` | `1.5` (18px) | `500 Medium` | `0.02em` |
| **Code** | `14px` | `1.6` (22px) | `400 Regular` | `0` |

### Text Colors

```
Primary Text (Headings, emphasis):      Slate-900
Secondary Text (Body, standard):        Slate-600
Tertiary Text (Muted, metadata):        Slate-500
Disabled Text:                          Slate-400
Links:                                  Indigo-600 (hover: Indigo-700)
```

---

## Spacing System

Use multiples of `4px` for all spacing. This creates rhythm and predictable layouts.

```
2px    (0.5 unit)  — Fine adjustments only
4px    (1 unit)    — Minimal spacing
8px    (2 units)   — Compact spacing
12px   (3 units)   — Small spacing
16px   (4 units)   — Standard spacing
20px   (5 units)   — Medium spacing
24px   (6 units)   — Large spacing
32px   (8 units)   — Extra large spacing
40px   (10 units)  — XL spacing
48px   (12 units)  — 2XL spacing
64px   (16 units)  — 3XL spacing
```

### Application

- **Padding inside components**: `12px` (small), `16px` (standard), `20px` (large)
- **Margin between elements**: `16px` (standard), `24px` (sections)
- **Gaps in grids/flex**: `16px` (standard), `12px` (dense), `24px` (loose)

---

## Border Radius

Subtle curvature for a modern, precise feel.

```
0px     (0)        — Sharp corners (use sparingly, e.g., code blocks)
2px     (sm)       — Minimal rounding (small badges, pills)
4px     (base)     — Standard rounding (inputs, buttons, small cards)
6px     (md)       — Medium rounding (dialog panels, cards)
8px     (lg)       — Large rounding (main containers, modals)
12px    (xl)       — Extra large (large cards, sections)
16px    (2xl)      — Hero elements, feature cards
```

### Component Guidelines

| Component | Border Radius |
|-----------|---|
| Input fields, text areas | `4px` |
| Buttons (standard) | `4px` |
| Buttons (pill/icon) | `6px` |
| Cards, panels | `8px` |
| Modals, dialogs | `12px` |
| Large containers | `16px` |
| Avatar circles | `50%` |
| Status badges | `4px` |
| Chips/tags | `4px` |

---

## Shadows & Elevation

Layered shadows create depth and visual hierarchy. All using `box-shadow`.

```
// Subtle elevation (hover states, lifted cards)
Shadow-sm   0 1px 2px 0 rgba(0, 0, 0, 0.05)

// Base elevation (cards, panels)
Shadow-md   0 4px 6px -1px rgba(0, 0, 0, 0.1), 
            0 2px 4px -1px rgba(0, 0, 0, 0.06)

// Medium elevation (floating UI)
Shadow-lg   0 10px 15px -3px rgba(0, 0, 0, 0.1), 
            0 4px 6px -2px rgba(0, 0, 0, 0.05)

// Strong elevation (modals, dropdowns)
Shadow-xl   0 20px 25px -5px rgba(0, 0, 0, 0.1), 
            0 10px 10px -5px rgba(0, 0, 0, 0.04)

// Heavy elevation (focus overlays, alerts)
Shadow-2xl  0 25px 50px -12px rgba(0, 0, 0, 0.25)
```

### Usage

| Element | Shadow |
|---------|--------|
| Hover states (buttons, links) | Shadow-sm |
| Cards, panels (default) | Shadow-md |
| Floating UI (tooltips, popovers) | Shadow-lg |
| Modals, dropdowns, menus | Shadow-xl |
| Full-screen overlays, focus states | Shadow-2xl |

---

## Component Specifications

### Buttons

#### Primary Button
```
Background:   Indigo-600
Text:         White
Padding:      12px 16px (compact), 16px 20px (standard)
Border radius: 4px
Border:       None
Font:         Body (16px), Semi-bold (600)
Shadow:       None (default), Shadow-sm (hover)
Transitions:  all 150ms ease-in-out

States:
  Default     Background: Indigo-600, Cursor: pointer
  Hover       Background: Indigo-700, Shadow: Shadow-sm
  Active      Background: Indigo-800, Transform: scale(0.98)
  Disabled    Background: Slate-300, Color: Slate-500, Cursor: not-allowed, Opacity: 0.6
  Focus       Outline: 2px solid Indigo-300, Outline-offset: 2px
```

#### Secondary Button
```
Background:   Slate-100
Text:         Slate-700
Border:       1px solid Slate-300
Padding:      12px 16px
Border radius: 4px

States:
  Hover       Background: Slate-200, Border: Slate-400
  Active      Background: Slate-300
  Disabled    Background: Slate-100, Color: Slate-400, Opacity: 0.5
```

#### Danger Button
```
Background:   Error-600
Text:         White
Padding:      12px 16px

States:
  Hover       Background: Error-700
  Active      Background: Error-800
```

### Input Fields

```
Background:     White
Border:         1px solid Slate-300
Border radius:  4px
Padding:        12px 16px
Font:           Body Small (14px), Regular (400)
Text color:     Slate-600
Placeholder:    Slate-400

States:
  Focus         Border: Indigo-500, Box-shadow: 0 0 0 3px Indigo-50
  Hover         Border: Slate-400
  Disabled      Background: Slate-50, Color: Slate-400, Border: Slate-200
  Error         Border: Error-500, Box-shadow: 0 0 0 3px Error-50
  Success       Border: Success-500
```

### Cards

```
Background:     White
Border:         None (use shadow) or 1px solid Slate-100
Border radius:  8px
Padding:        20px
Shadow:         Shadow-md
Transition:     box-shadow 150ms ease-in-out

States:
  Hover         Shadow: Shadow-lg (if interactive)
  Active        Shadow: Shadow-lg
```

### Badges & Status Indicators

**Small Badge** (metadata, tags)
```
Padding:        4px 8px
Border radius:  2px
Font:           Caption (12px), Medium (500)
Background:     Slate-100
Text:           Slate-700

Variants:
  Success       Background: Success-100, Text: Success-700
  Warning       Background: Warning-100, Text: Warning-700
  Error         Background: Error-100, Text: Error-700
  Info          Background: Info-100, Text: Info-700
```

**Status Indicator** (device status)
```
Size:           8px circle
Border radius:  50%
Glow:           0 0 8px rgba([color], 0.5) on hover

Colors:
  Passing       Success-500 (#22c55e)
  Failing       Error-500 (#ef4444)
  Unknown       Slate-400 (#94a3b8)
  Processing    Info-500 (#0ea5e9)
```

---

## Dark Mode

Invert the color logic for dark backgrounds while maintaining contrast ratios ≥ 4.5:1 (WCAG AA standard).

### Dark Mode Palette

```
Background Primary:    #111827 (Dark-900)
Background Secondary:  #1f2937 (Dark-800)
Background Tertiary:   #374151 (Dark-700)
Surface:               #1f2937
Surface Hover:         #374151

Text Primary:          #f3f4f6 (Slate-50)
Text Secondary:        #d1d5db (Slate-300)
Text Tertiary:         #9ca3af (Slate-400)

Border:                #4b5563 (Slate-700 adjusted)
```

### Components in Dark Mode

- **Buttons**: Same logic, but backgrounds are darker; ensure text is light
- **Cards**: Shadow increases (visual depth on dark), background: Dark-800
- **Inputs**: Background: Dark-800, Border: Dark-700, Text: Slate-50
- **Focus rings**: Indigo-300 (maintain brightness)

---

## Motion & Transitions

Create fluidity without distraction.

```
Fast:       150ms   ease-in-out     Quick interactions (button hover, small state changes)
Standard:   250ms   ease-in-out     Normal transitions (panel opens, alerts appear)
Slow:       400ms   ease-in-out     Slower feedback (modal enter, major layout shifts)
Entrance:   300ms   cubic-bezier(0.16, 1, 0.3, 1)     Spring-like entrance
Exit:       200ms   cubic-bezier(0.7, 0, 0.84, 0)     Quick exit
```

### Easing Functions

- **ease-in-out**: General purpose, natural
- **cubic-bezier(0.16, 1, 0.3, 1)**: Spring entrance (feels responsive)
- **cubic-bezier(0.7, 0, 0.84, 0)**: Exit easing (quick but not jarring)

### Motion Principles

1. **Meaningful**: Only animate state changes that matter to the user
2. **Fast**: Prefer snappy (150–250ms) over sluggish (>500ms)
3. **Consistent**: Same element always animates the same way
4. **Accessible**: Respect `prefers-reduced-motion`

---

## Accessibility

### Contrast Ratios

- **Text on background**: Minimum 4.5:1 (WCAG AA) for body text, 3:1 for large text
- **Interactive elements**: 3:1 minimum against adjacent colors
- **Verify**: Use [WebAIM Contrast Checker](https://webaim.org/resources/contrastchecker/)

### Focus States

All interactive elements must have a visible focus state:

```
Focus Ring:     2px solid Indigo-300
Outline Offset: 2px
```

### Color Alone

Never convey information using color alone:
- Use icons + color for status (✓ green, ✗ red, etc.)
- Add text labels to badges
- Provide patterns or textures for colorblind accessibility

### Keyboard Navigation

All components must be accessible via keyboard. Maintain logical tab order.

---

## Usage Guidelines

### When to Use Each Color

| Color | Use Case | Example |
|-------|----------|---------|
| **Indigo** | Primary actions, focus, links | Buttons, links, highlights |
| **Slate** | Neutral elements, text, structure | Text, backgrounds, borders |
| **Green** | Success, positive feedback | ✓ Status, alerts, confirmations |
| **Red** | Errors, warnings, danger | ✗ Validation errors, deletions |
| **Yellow** | Cautions, degraded states | ⚠ API slowness, warnings |
| **Blue** | Info, neutral feedback | ⓘ Hints, informational messages |

### Do's & Don'ts

✅ **DO:**
- Use semantic colors (Success for passing, Error for failing)
- Maintain consistent spacing between elements
- Pair sans-serif fonts with monospace only in code blocks
- Use the full color palette for rich, accessible interfaces
- Test all states (hover, focus, active, disabled)

❌ **DON'T:**
- Use pure black (#000000) or pure white (#ffffff) for text — use Slate-900 or Slate-50
- Mix multiple unrelated font families
- Rely on color alone to convey meaning
- Create focus states with `outline: none` without a replacement
- Use shadows to simulate focus (shadows fade; outlines persist)
- Embed brand colors in components; reference from this system

---

## Implementation

### CSS/Tailwind Integration

If using Tailwind CSS, map these values to your config:

```javascript
module.exports = {
  theme: {
    extend: {
      colors: {
        slate: { 50: '#f8fafc', /* ... */ 900: '#0f172a' },
        indigo: { 50: '#eef2ff', /* ... */ 800: '#3730a3' },
        success: { 50: '#f0fdf4', 500: '#22c55e', 700: '#15803d' },
        warning: { 50: '#fffbeb', 500: '#eab308', 700: '#a16207' },
        error: { 50: '#fef2f2', 500: '#ef4444', 700: '#b91c1c' },
        info: { 50: '#f0f9ff', 500: '#0ea5e9', 700: '#0369a1' },
      },
      fontSize: {
        h1: ['36px', { lineHeight: '1.2' }],
        h2: ['28px', { lineHeight: '1.3' }],
        h3: ['24px', { lineHeight: '1.35' }],
        h4: ['20px', { lineHeight: '1.4' }],
        'body-lg': ['18px', { lineHeight: '1.6' }],
        body: ['16px', { lineHeight: '1.6' }],
        'body-sm': ['14px', { lineHeight: '1.6' }],
        caption: ['12px', { lineHeight: '1.5' }],
      },
      spacing: {
        0.5: '2px', 1: '4px', 2: '8px', 3: '12px', 4: '16px',
        5: '20px', 6: '24px', 8: '32px', 10: '40px', 12: '48px',
        16: '64px',
      },
      borderRadius: {
        sm: '2px', DEFAULT: '4px', md: '6px', lg: '8px',
        xl: '12px', '2xl': '16px',
      },
      boxShadow: {
        sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
        lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
        xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
        '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
      },
      transitionDuration: {
        fast: '150ms',
        DEFAULT: '250ms',
        slow: '400ms',
      },
    },
  },
};
```

---

## Version & Maintenance

**Current Version**: 1.0  
**Last Updated**: July 30, 2026  
**Next Review**: January 2027

When updating the design system:
1. Increment the version number
2. Document changes in a changelog section below this line
3. Notify all teams of updates
4. Update implementation files (Tailwind config, CSS variables, etc.)

### Changelog

- **v1.0** (2026-07-30): Initial release — color palette, typography, spacing, components, accessibility, dark mode support
