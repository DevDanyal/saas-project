# Design System — "Brokerage Editorial"

Warm real-estate premium. The app reads like a well-set brokerage brief on cream
paper: deep forest-green ink and side-rail, bronze-gold accents spent sparingly,
serif headlines over a quiet sans body, and mono reserved for numbers that must
line up (scores, timestamps, prices).

## Palette

| Token | Value | Use |
|---|---|---|
| `--paper` | `#f5f1e6` | App background (cream paper) |
| `--surface` | `#fcfaf4` | Cards, panels |
| `--sunk` | `#eee8d8` | Inputs (sunk cream) |
| `--border` | `#e3dcc9` | Warm hairline rules |
| `--border-strong` | `#c9bfa3` | Input borders, hover rules |
| `--ink` | `#262b20` | Primary text (deep forest ink) |
| `--muted` | `#6f6a55` | Secondary text |
| `--gold` | `#a97c2c` | Accent — CTAs, active nav, focus rings |
| `--gold-strong` | `#bd8f33` | Accent hover |
| `--gold-dark` | `#8a6420` | Accent as text on light surfaces |
| `--gold-weak` | `#f0e5c8` | AI boxes, selected tints |
| `--hot` | `#a4402c` | Brick — hot leads, errors, danger |
| `--warm` | `#8f6410` | Amber — warnings, attention |
| `--ok` | `#57703a` | Moss — positive, done |
| `--sidebar` | `#242a1c` | Deep forest side-rail |
| `--sidebar-text` | `#c6c2ab` | Nav labels on rail |

Aliases kept for legacy/styled-jsx references: `--bg`, `--fg`, `--card`,
`--accent`, `--accent-weak`, `--primary`, `--primary-weak`, `--danger`.

Accent discipline: gold fills appear only on primary CTAs and the active nav
state — never large surfaces, never two competing accent colors per viewport.

## Typography

Three faces, all Google Fonts via `next/font`:

- **Fraunces** (serif, weight 600, roman) — page titles, sidebar wordmark,
  section titles, digest brief. `--font-display`.
- **IBM Plex Sans** (400/500/600) — body, UI, nav. `--font-body`.
- **IBM Plex Mono** (400/600) — outlier only: priority scores, timestamps,
  prices, metrics, eyebrow labels. `--font-mono`.

Rules: no italics in headers. Body 14px. H1 Fraunces 24px. Eyebrows are 11px
uppercase, letter-spacing 0.08em, mono or sans.

## Structure

- **Side-rail (N3):** deep forest green, sticky, 240px. Fraunces wordmark,
  mono eyebrow "Agent workspace", cream nav labels, gold-tinted active state.
- **Workbench pages:** cream background, cards on `--surface` with warm
  hairlines and a barely-there warm shadow. Radius 10px.
- **Page head:** serif H1 + muted sans sub. No duplicated chrome.
- **Chips:** pill, semantic (brick / amber / moss), warm-tinted fills.
- **Buttons:** primary = gold fill with near-black-green text; default =
  hairline outline on surface; danger keeps brick hover.
- **Motion:** 150–220ms eases only. No scroll reveals.

## Signature moments

- The morning digest renders in Fraunces with a gold left rule — reads like a
  printed brokerage brief.

## Exception — auth screen (glassmorphic)

The login/register/reset experience intentionally departs from Brokerage
editorial per a user-specified brief: a deep obsidian stage (`#060B14`) with a
full-screen Canvas-rendered 3D particle wave (perspective-projected cyan mesh,
mouse parallax, `pointer-events: none`, reduced-motion aware), floating glass
security badges (fingerprint bottom-left, key top-right, `y: [-8, 8, -8]`
levitation), and a centered frosted-glass card (`rgba(15,23,42,.55)`,
`backdrop-blur(24px)`, 440px, 28px radius, 1px gradient cyan/white border,
mouse-tracking tilt via Framer Motion springs). Typography is Montserrat
(`--font-auth`); motion is Framer Motion (`motion` package): a `layoutId` pill
glides between SIGN IN / SIGN UP tabs, `AnimatePresence` animates height + field
stagger between views, inline errors slide down, invalid credentials shake
horizontally, and the circular gradient submit orb (`#38BDF8`→`#06B6D4`, neon
glow) slides its arrow on hover, compresses on tap, and morphs into a spinner
while authenticating. A frosted "Continue with Google" button sits below an
"or continue with" divider. The session check runs in the background with a 6s
timeout fallback — the interactive form renders immediately, never a blocking
spinner. Tailwind (utilities only, no preflight) is imported at the top of
`globals.css` so the editorial app styles stay intact. Client-side validation
mirrors the backend (`/auth/login`, `/auth/signup`, 8+ char passwords);
forgot-password posts to the honest backend stub. Everything after login
remains Brokerage editorial.
