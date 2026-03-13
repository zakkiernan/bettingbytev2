# BettingByte Frontend Spec

Hand this document to the frontend team. It contains everything needed to
build the BettingByte web application: design system, page specs, component
catalog, API contracts, and implementation guidance.

Last updated: 2026-03-12

---

## Table of Contents

1. [Tech Stack](#1-tech-stack)
2. [Design System](#2-design-system)
3. [Page Specifications](#3-page-specifications)
4. [Component Catalog](#4-component-catalog)
5. [API Contracts](#5-api-contracts)
6. [Real-Time Architecture](#6-real-time-architecture)
7. [Authentication & Authorization](#7-authentication--authorization)
8. [Responsive Strategy](#8-responsive-strategy)
9. [Performance Requirements](#9-performance-requirements)
10. [Accessibility](#10-accessibility)
11. [Implementation Order](#11-implementation-order)

---

## 1. Tech Stack

| Concern | Choice | Notes |
|---------|--------|-------|
| Framework | **Next.js 15** (App Router) | SSR for landing/SEO, client components for live data |
| Language | **TypeScript** (strict mode) | No `any` types in production code |
| Styling | **Tailwind CSS v4** + **shadcn/ui** | Dark-first design, component primitives |
| Charts | **Recharts** | Lightweight, React-native. Used for sparklines, waterfalls, pace trackers |
| Real-time | **WebSocket** (native) | FastAPI WS support — no Socket.io needed |
| Data fetching | **TanStack Query v5** | Caching, refetch intervals, optimistic updates |
| Auth | **NextAuth.js v5** or **Clerk** | JWT flow matching FastAPI `/auth` endpoints |
| State | **Zustand** | Lightweight global state for picks, user prefs, live subscriptions |
| Fonts | **Inter** (body) + **JetBrains Mono** (data) | Google Fonts |
| Icons | **Lucide React** | Consistent, tree-shakeable icon set |
| Hosting | **Vercel** | Frontend only. Backend hosted separately (Railway/Fly/VPS) |
| Testing | **Vitest** + **Playwright** | Unit + E2E |

---

## 2. Design System

### 2.1 Color Palette

The visual identity is **"Data Terminal"** — dark, precise, analytical. Purple
brand with cyan live accents and green/red edge signals.

#### Core Palette (CSS custom properties)

```css
:root {
  /* === Backgrounds === */
  --bg-base:        #0B0E17;   /* Page background */
  --bg-surface:     #141827;   /* Cards, panels */
  --bg-surface-alt: #1C2137;   /* Hover, active, secondary cards */
  --bg-elevated:    #242842;   /* Modals, dropdowns, tooltips */

  /* === Brand === */
  --brand-primary:      #7C5CFC;   /* Logo, primary buttons, key highlights */
  --brand-primary-hover:#6B4FE0;   /* Button hover state */
  --brand-subtle:       #A78BFA;   /* Secondary accents, links */
  --brand-muted:        #4C3D99;   /* Inactive tabs, disabled brand elements */
  --brand-glow:         rgba(124, 92, 252, 0.15);  /* Subtle glow behind featured cards */

  /* === Semantic === */
  --edge-positive:    #00E68A;   /* Over edges, wins, positive signals */
  --edge-negative:    #FF5C5C;   /* Under edges, losses, negative signals */
  --live-accent:      #00D4FF;   /* Live indicators, real-time pulse, LIVE badge */
  --warning:          #FFBB38;   /* Injury watch, GTD status, caution */

  /* === Text === */
  --text-primary:     #E8ECF4;   /* Body text */
  --text-secondary:   #7A829E;   /* Labels, captions */
  --text-tertiary:    #4A5068;   /* Disabled text, placeholders */
  --text-inverse:     #0B0E17;   /* Text on light backgrounds (buttons) */

  /* === Borders & Dividers === */
  --border-default:   #1E2338;   /* Card borders */
  --border-hover:     #2A3050;   /* Hover state borders */
  --border-focus:     #7C5CFC;   /* Focus rings — matches brand */

  /* === Status Colors (injury report) === */
  --status-out:           #FF5C5C;   /* OUT */
  --status-doubtful:      #FF8A5C;   /* Doubtful */
  --status-questionable:  #FFBB38;   /* Questionable / GTD */
  --status-probable:      #00E68A;   /* Probable / Available */
}
```

#### Tailwind Config Extension

```js
// tailwind.config.ts
export default {
  theme: {
    extend: {
      colors: {
        bg: {
          base: '#0B0E17',
          surface: '#141827',
          'surface-alt': '#1C2137',
          elevated: '#242842',
        },
        brand: {
          DEFAULT: '#7C5CFC',
          hover: '#6B4FE0',
          subtle: '#A78BFA',
          muted: '#4C3D99',
        },
        edge: {
          positive: '#00E68A',
          negative: '#FF5C5C',
        },
        live: '#00D4FF',
        warning: '#FFBB38',
        text: {
          primary: '#E8ECF4',
          secondary: '#7A829E',
          tertiary: '#4A5068',
        },
        border: {
          DEFAULT: '#1E2338',
          hover: '#2A3050',
          focus: '#7C5CFC',
        },
        status: {
          out: '#FF5C5C',
          doubtful: '#FF8A5C',
          questionable: '#FFBB38',
          probable: '#00E68A',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
      borderRadius: {
        card: '12px',
        btn: '8px',
      },
    },
  },
}
```

### 2.2 Typography

| Role | Font | Weight | Size | Class |
|------|------|--------|------|-------|
| Page title | Inter | 700 | 28px / 1.75rem | `text-[28px] font-bold` |
| Section heading | Inter | 600 | 20px / 1.25rem | `text-xl font-semibold` |
| Card title | Inter | 600 | 16px / 1rem | `text-base font-semibold` |
| Body text | Inter | 400 | 14px / 0.875rem | `text-sm` |
| Caption / label | Inter | 400 | 12px / 0.75rem | `text-xs text-text-secondary` |
| **Data values** | **JetBrains Mono** | **500** | **16px** | `font-mono font-medium` |
| **Large data** | **JetBrains Mono** | **700** | **24px** | `font-mono text-2xl font-bold` |
| **Small data** | **JetBrains Mono** | **400** | **12px** | `font-mono text-xs` |

**Critical rule:** ALL numerical data (projections, edges, lines, stats,
percentages, odds) MUST use `font-mono`. This is the signature "Byte"
visual identity.

### 2.3 Spacing & Layout

- Page max-width: `1400px`, centered
- Page padding: `24px` (desktop), `16px` (mobile)
- Card padding: `20px` (desktop), `16px` (mobile)
- Card gap in grids: `16px`
- Section vertical spacing: `32px`
- Use **CSS Grid** for bento-style dashboard layouts
- Use **Flexbox** for inline card content

### 2.4 Card Design

All cards follow a consistent pattern:

```
┌─[3px left border: edge color]────────────────────────┐
│                                                       │
│  bg: var(--bg-surface)                               │
│  border: 1px solid var(--border-default)             │
│  border-radius: 12px                                 │
│  padding: 20px                                       │
│                                                       │
│  Hover: bg → var(--bg-surface-alt)                   │
│         border → var(--border-hover)                 │
│                                                       │
│  NO box-shadows on dark backgrounds.                 │
│  Use border brightness shifts instead.               │
│                                                       │
└───────────────────────────────────────────────────────┘
```

- Prop cards with an edge get a **3px left border** in `--edge-positive`
  (over) or `--edge-negative` (under)
- Featured/highlighted cards get a subtle `box-shadow` using `--brand-glow`
- Live cards get a pulsing `--live-accent` left border

### 2.5 Interactive Elements

**Buttons:**
| Variant | Background | Text | Border | Usage |
|---------|-----------|------|--------|-------|
| Primary | `--brand-primary` | `--text-inverse` | none | Main CTAs |
| Secondary | transparent | `--brand-subtle` | `--brand-muted` | Secondary actions |
| Ghost | transparent | `--text-secondary` | none | Tertiary actions |
| Danger | `--edge-negative` | white | none | Destructive actions |

**Inputs:** Dark background (`--bg-surface-alt`), `--border-default` border,
`--border-focus` on focus. No outer glow, just border color change.

**Tabs:** Underline style with `--brand-primary` active indicator. No
background pills.

### 2.6 Data Visualization Colors

When charting multiple data series, use this ordered palette:

```
1. #7C5CFC  (brand purple)
2. #00D4FF  (cyan)
3. #00E68A  (green)
4. #FFBB38  (amber)
5. #FF5C5C  (red)
6. #A78BFA  (lavender)
```

For single-series sparklines: use `--brand-primary` with a
`rgba(124, 92, 252, 0.1)` fill underneath.

### 2.7 Motion & Transitions

- Card hover transitions: `150ms ease`
- Page transitions: `200ms ease`
- Data updates (live): `300ms ease` with a brief highlight flash
- Live pulse indicator: CSS animation, `2s infinite`
- Skeleton loaders: animated shimmer (subtle brightness sweep on
  `--bg-surface-alt`), never static gray blocks

---

## 3. Page Specifications

### 3.0 Global Layout Shell

```
┌─────────────────────────────────────────────────────────┐
│ TOPBAR                                                  │
│ ┌──────┐                                ┌──┐ ┌──────┐ │
│ │ Logo │  [Dashboard] [Props] [Live]    │🔔│ │Avatar│ │
│ └──────┘  [Picks] [Community]           └──┘ └──────┘ │
├─────────────────────────────────────────────────────────┤
│                                                         │
│                    PAGE CONTENT                          │
│                    max-width: 1400px                     │
│                    centered                              │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

- **Desktop:** Horizontal top nav bar (not sidebar — betting apps are
  content-dense, sidebars waste horizontal space)
- **Mobile:** Bottom tab bar with 5 icons (Dashboard, Props, Live, Picks, More)
- Logo: "BettingByte" in Inter Bold + a subtle `</>` or pixel-byte icon
  in `--brand-primary`
- Notification bell shows unread count badge in `--live-accent`

---

### 3.1 Landing Page (`/`)

**Purpose:** Convert visitors to signups. Not behind auth.

**Sections:**
1. **Hero** — "Player Props. Powered by Data." with a live demo screenshot
   of the prop board. Primary CTA: "Start Free". Secondary: "See How It Works"
2. **Value Props** (3 cards) — "Transparent Models", "Live Edges",
   "Track & Compete"
3. **Live Demo** — Embedded (read-only) version of today's top 3 edges
   with real data. Blurred remaining rows → "Sign up to see all"
4. **Social Proof** — Aggregate stats ("12,847 edges surfaced this season")
5. **Pricing** — Tier comparison table (Free / Premium / Pro)
6. **Footer** — Links, responsible gambling disclaimer, legal

**Tech:** Server-rendered. No auth required. Can be a separate static route.

---

### 3.2 Dashboard (`/dashboard`)

**Purpose:** Daily command center. Answer: "What should I bet today?"

**Auth:** Required. All tiers.

**Bento grid layout (desktop):**

```
┌────────────────────┬──────────────────────────────────┐
│                    │                                  │
│  TODAY'S SLATE     │   TOP EDGES                      │
│  (GameSlateCard    │   (EdgeCard list)                │
│   x N games)      │   Sorted by confidence           │
│                    │   Free: top 3 only               │
│  2 cols of game    │   Premium+: all                  │
│  cards             │                                  │
│                    │                                  │
├─────────┬──────────┼──────────────────────────────────┤
│         │          │                                  │
│ INJURY  │ MY PICKS │  LIVE NOW                        │
│ WATCH   │ SUMMARY  │  (only visible during games)     │
│         │          │  Shows active games + edge count  │
│         │          │                                  │
└─────────┴──────────┴──────────────────────────────────┘
```

**Mobile:** Single column stack: Slate (horizontal scroll) → Top Edges →
Injury Watch → My Picks → Live Now

**Data required from API:**
- `GET /api/games/today` → game cards
- `GET /api/edges/today?sort=confidence&limit=10` → top edges
- `GET /api/injuries/today` → injury alerts
- `GET /api/picks/active` → user's current picks (authed)
- `GET /api/live/active` → live game summaries (if games in progress)

---

### 3.3 Prop Board (`/props`)

**Purpose:** The core product. Scannable, filterable table of all player props.

**Auth:** Required. Free tier sees limited rows (top 5 with blurred rest).

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  PROP BOARD                                [Edges Only] │
│                                                         │
│  Filters:                                               │
│  [All Games ▾] [Points ▾] [All Teams ▾] [Sort: Edge ▾] │
│                                                         │
│  ┌─────────────────────────────────────────────────────┐│
│  │ PLAYER       PROP     LINE    PROJ    EDGE   CONF   ││
│  ├─────────────────────────────────────────────────────┤│
│  │▌LeBron James  PTS O   26.5   29.7   +3.2    ▓▓▓▓░ ││
│  │▌Jayson Tatum  PTS U   31.5   28.1   +3.4    ▓▓▓░░ ││
│  │ Devin Booker  PTS O   24.5   27.0   +2.5    ▓▓▓░░ ││
│  │ Ant Edwards   PTS O   23.5   25.8   +2.3    ▓▓░░░ ││
│  │ ...                                                 ││
│  └─────────────────────────────────────────────────────┘│
│                                                         │
│  Showing 47 props across 6 games  │  Updated 30s ago   │
└─────────────────────────────────────────────────────────┘
```

**Table columns:**

| Column | Type | Notes |
|--------|------|-------|
| Player | text + avatar | Player name, team badge. Click → `/player/:id` |
| Prop | badge | "PTS O" / "PTS U" colored green/red |
| Line | mono number | The sportsbook line |
| Proj | mono number | Model projection — bold, primary text |
| Edge | mono number | Projection - Line. Color-coded green/red. Prefix +/- |
| Conf | bar | 5-segment confidence bar (filled segments) |
| Actions | icon | Expand chevron, track pick icon |

**Expandable row (on click or hover-expand on desktop):**

```
┌─────────────────────────────────────────────────────────┐
│▌LeBron James  PTS O   26.5   29.7   +3.2    ▓▓▓▓░     │
│ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ │
│  Key factor: AD Questionable → +2.1 min projected      │
│  Last 10 hit rate: ●●●●●●●●○○ (8/10 over)             │
│  Over prob: 63.2%  │  Season avg: 26.8                 │
│                                                         │
│  [Track Pick]  [Full Breakdown →]                       │
└─────────────────────────────────────────────────────────┘
```

**Filters (query params):**
- `game` — filter to one game (dropdown of today's games)
- `stat_type` — "Points" (default), later: "Rebounds", "Assists", "3PT"
- `team` — filter to one team
- `sort` — "edge" (default), "confidence", "line", "projection"
- `edges_only` — boolean toggle, hides props with edge < 1.0

**Data:** `GET /api/props/board?date=today&stat_type=points&sort=edge`

**Refresh:** TanStack Query with `refetchInterval: 30000` (30s). Show
"Updated Xs ago" timestamp.

---

### 3.4 Prop Deep-Dive (`/props/:signalId`)

**Purpose:** Full transparent breakdown. Where BettingByte earns trust.

**Auth:** Required. Free tier: 2 deep-dives per day. Premium+: unlimited.

**Layout:**

```
┌─────────────────────────────────────────────────────────┐
│  ← Back to Board                                       │
│                                                         │
│  ┌────────────────────────────────────────────────────┐ │
│  │  [Headshot]  LeBron James  •  LAL  •  SF  •  #6   │ │
│  │              PTS Over 26.5  •  LAL @ DAL  •  8pm   │ │
│  │                                                    │ │
│  │  ┌──────────────┐  ┌────────────┐  ┌───────────┐  │ │
│  │  │ PROJECTION   │  │    EDGE    │  │   CONF    │  │ │
│  │  │    29.7      │  │   +3.2     │  │  ▓▓▓▓░    │  │ │
│  │  └──────────────┘  └────────────┘  └───────────┘  │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ PROJECTION BREAKDOWN (Waterfall) ────────────────┐ │
│  │                                                    │ │
│  │  Base (PPM x Min)         25.1  ████████████████  │ │
│  │  Recent Form (5g)         +1.8  ███               │ │
│  │  Minutes Adjustment       +0.4  █                 │ │
│  │  Usage Shift              +0.9  ██                │ │
│  │  Efficiency               +0.2  ▌                 │ │
│  │  Opponent DEF             +1.2  ███               │ │
│  │  Pace                     +0.4  █                 │ │
│  │  Context (Home, Rest)     +0.3  █                 │ │
│  │  ─────────────────────────────                    │ │
│  │  TOTAL                    29.7                    │ │
│  │                                                    │ │
│  └────────────────────────────────────────────────────┘ │
│                                                         │
│  ┌─ OPPORTUNITY CONTEXT ──┐ ┌─ MATCHUP CONTEXT ──────┐ │
│  │                        │ │                         │ │
│  │ Proj minutes:  35.2    │ │ DAL DEF rating: 112.3   │ │
│  │ Season avg:    34.8    │ │ League avg:     111.8   │ │
│  │ Usage rate:    31.2%   │ │ Opp pace:       100.2   │ │
│  │ Start conf:    98%     │ │ Expected pace:  101.1   │ │
│  │                        │ │                         │ │
│  │ AD: PROBABLE            │ │ DAL vs SF PPG:  24.2   │ │
│  │ No major role shift     │ │ League avg SF:  22.1   │ │
│  │ expected                │ │                         │ │
│  └────────────────────────┘ └─────────────────────────┘ │
│                                                         │
│  ┌─ RECENT GAME LOG ────────────────────────────────┐   │
│  │                                                   │   │
│  │  [Sparkline: last 10 games vs line]              │   │
│  │  Line: 26.5 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─       │   │
│  │                                                   │   │
│  │  Date   Opp   MIN   PTS   REB   AST   Result     │   │
│  │  3/10   PHX   36    31    8     9     ● HIT      │   │
│  │  3/8    SAC   34    28    6     7     ● HIT      │   │
│  │  3/6    DEN   38    33    10    6     ● HIT      │   │
│  │  ...                                              │   │
│  │                                                   │   │
│  │  Hit rate vs this line: 8/10 (80%)               │   │
│  └───────────────────────────────────────────────────┘   │
│                                                         │
│  [Track This Pick]         [Share]                      │
└─────────────────────────────────────────────────────────┘
```

**Waterfall chart:** Horizontal bar chart. Base is a full bar, each
adjustment extends right (positive) or left (negative). Color: adjustments
use `--brand-primary`, total bar uses `--brand-subtle`. Hover each bar for
a tooltip explaining what it means.

**Waterfall data fields** (from `PregamePointsBreakdown`):

| Field | Display Label | Tooltip |
|-------|---------------|---------|
| `base_scoring` | Base (PPM x Min) | Points-per-minute weighted average times projected minutes |
| `recent_form_adjustment` | Recent Form | Performance trend vs season average (last 5 and 10 games) |
| `minutes_adjustment` | Minutes Shift | Projected minutes differ from season average |
| `usage_adjustment` | Usage Shift | Usage rate, FGA, FTA, and touch trends |
| `efficiency_adjustment` | Efficiency | True shooting and FG% trends vs season |
| `opponent_adjustment` | Opponent DEF | Opponent defensive rating vs league average |
| `pace_adjustment` | Pace | Expected game pace vs league average |
| `context_adjustment` | Context | Home/away, rest days, back-to-back |
| `projected_points` | **TOTAL** | Sum of all adjustments |

**Opportunity context fields** (from `PregameOpportunityBreakdown`):

| Field | Display Label |
|-------|---------------|
| `expected_minutes` | Projected Minutes |
| `expected_usage_pct` | Projected Usage % |
| `expected_start_rate` | Start Probability |
| `expected_close_rate` | Close Probability |
| `role_stability` | Role Stability |
| `opportunity_score` | Opportunity Score |
| `availability_modifier` | Availability Impact |
| `vacated_minutes_bonus` | Vacated Minutes Bonus |

**Data:**
- `GET /api/props/:signalId` → full projection with breakdown
- `GET /api/players/:playerId/game-log?last=10` → recent game log

---

### 3.5 Player Profile (`/player/:playerId`)

**Purpose:** Player-centric view. Stats, game log, active props.

**Auth:** Required. All tiers.

**Sections:**
1. **Player header** — Headshot, name, team, position, jersey number
2. **Season averages** — PPG, RPG, APG, MPG, FG%, 3P%, USG% (mono font)
3. **Active props** — List of current props with projections/edges
4. **Game log table** — Last 20 games with full box score, sortable
5. **Trends chart** — Line chart of points last 20 games with prop lines
   overlaid (showing hit/miss visually)
6. **Model insights** — Text summary of opportunity context

**Data:**
- `GET /api/players/:playerId` → profile + season averages
- `GET /api/players/:playerId/props` → active props
- `GET /api/players/:playerId/game-log?last=20` → game log
- `GET /api/players/:playerId/trends` → charting data

---

### 3.6 Live Center (`/live`)

**Purpose:** Real-time prop tracking during games. The flagship differentiator.

**Auth:** Required. **Premium+ only.** Free sees a blurred preview with
upgrade CTA.

**Layout (during active games):**

```
┌─────────────────────────────────────────────────────────┐
│  LIVE CENTER                                    ● LIVE  │
│                                                         │
│  Game selector: [BOS @ MIA ▾]  Q2 4:32                  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ BOS  54         │    Q2  4:32     │         MIA 48│  │
│  │ ████████████████│                 │████████████████│  │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌──────────────────────────────────────────────────┐   │
│  │ Player       Prop   Line  Curr  Proj   Pace  Edge│  │
│  ├──────────────────────────────────────────────────┤   │
│  │ Tatum        PTS O  28.5   14   30.1  29.3  +1.6│   │
│  │ Brown        PTS O  22.5   11   23.8  23.1  +1.3│   │
│  │ Butler       PTS U  21.5    8   17.2  16.8  +4.3│   │
│  │ ...                                              │   │
│  └──────────────────────────────────────────────────┘   │
│                                                         │
│  ┌── LIVE ALERTS ────────────────────────────────────┐  │
│  │ 🔥 Butler cold start — PTS U 21.5 edge widened   │  │
│  │ ⚡ Tatum hot — 14 pts in Q1+Q2, pace tracking up │  │
│  │ 📊 Game pace 104 (expected 98.5)                  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  Other games: [LAL @ DAL Q1] [GSW @ PHX Pre]           │
└─────────────────────────────────────────────────────────┘
```

**Live table columns:**

| Column | Source | Notes |
|--------|--------|-------|
| Player | `LivePlayerSnapshot.player_name` | |
| Prop | `PlayerPropSnapshot.stat_type` | Over/Under badge |
| Line | `PlayerPropSnapshot.line` (live) | Current live line if available |
| Curr | `LivePlayerSnapshot.points` (etc) | Current actual stat total |
| Proj | Live model re-projection | Updated projection based on current game state |
| Pace | Linear extrapolation | `current_stat * (48 / minutes_played)` as simple pace |
| Edge | `Proj - Line` | Color-coded, updates in real-time |

**Live data flow:**
- WebSocket connection: `ws://api/ws/live/:gameId`
- Server pushes updates every 5-10 seconds during active games
- Client-side: TanStack Query + WebSocket integration (see Section 6)

**When no games are active:** Show "No live games right now" with next
game countdown timer + a CTA to browse the pregame prop board.

---

### 3.7 My Picks (`/picks`)

**Purpose:** Personal bet tracker and performance dashboard.

**Auth:** Required. Free tier: 3 active picks max. Premium+: unlimited.

**Tabs:**
1. **Active** — Current open picks with live status
2. **History** — Resolved picks with results
3. **Stats** — Performance dashboard

**Active picks card:**

```
┌─[left border: brand purple]─────────────────────────────┐
│  LeBron James PTS Over 26.5                             │
│  LAL @ DAL  •  8:00 PM  •  ⏳ Pregame                   │
│                                                         │
│  Proj: 29.7  │  Edge: +3.2  │  Conf: ▓▓▓▓░             │
│                                                         │
│  [Remove Pick]                                          │
└─────────────────────────────────────────────────────────┘
```

**During live games, active picks show:**
- Current stat total
- Pace to hit
- Updated edge
- Status: "On Track ●" / "Behind ●" / "Hit! ●" / "Missed ●"

**Stats dashboard:**
- Win/Loss record (e.g., "47-31")
- Win rate percentage
- ROI (if user inputs bet amounts — optional)
- Current streak
- Performance by confidence tier
- Performance chart over time

**Data:**
- `GET /api/picks/active` → active picks
- `GET /api/picks/history?page=1&limit=20` → paginated history
- `GET /api/picks/stats` → aggregate performance metrics
- `POST /api/picks` → add a pick
- `DELETE /api/picks/:pickId` → remove a pick
- `PATCH /api/picks/:pickId/resolve` → server auto-resolves after game ends

---

### 3.8 Community (`/community`)

**Purpose:** Social engagement and competitive retention.

**Auth:** Required. Free: view only. Premium+: full participation.

**Tabs:**
1. **Leaderboard** — Top performers, rolling 30-day window
2. **Feed** — Public picks stream
3. **My Profile** — Public-facing user profile

**Leaderboard rules:**
- Minimum 20 tracked picks to qualify
- Rolling 30-day window (prevents camping)
- Sortable by: Win %, ROI, Record, Streak
- Separate leaderboards by stat type (later)
- Top 3 get visual badges (gold/silver/bronze)

**Feed:**
- Reverse chronological stream of public picks
- Each pick shows: user avatar, username, the pick, optional commentary,
  upvote count, timestamp
- Users can upvote picks (one per pick)
- Can filter by: following, popular, recent

**Data:**
- `GET /api/community/leaderboard?period=30d&sort=win_pct` → leaderboard
- `GET /api/community/feed?page=1&limit=20` → public picks feed
- `POST /api/community/picks/:pickId/upvote` → upvote a pick
- `GET /api/community/profile/:userId` → public profile

---

### 3.9 Settings (`/settings`)

**Purpose:** Account management.

**Sections:**
1. **Account** — Email, password change
2. **Subscription** — Current tier, upgrade/downgrade, billing (Stripe portal)
3. **Preferences** — Default stat type filter, notification preferences
4. **Notifications** — Toggle alerts (injury, live edge, pick resolution)
5. **Display** — Theme override (always dark by default, optional light)

---

## 4. Component Catalog

### 4.1 Core Components

| Component | Props | Notes |
|-----------|-------|-------|
| `<GameCard>` | `game: Game` | Shows teams, time, status. Click → game props |
| `<PropRow>` | `signal: ModelSignal, expandable: bool` | Table row with edge coloring |
| `<PropCard>` | `signal: ModelSignal` | Card variant for mobile/dashboard |
| `<EdgeBadge>` | `edge: number, side: "over" \| "under"` | Colored pill: "+3.2 OVER" |
| `<ConfidenceBar>` | `confidence: number` | 5-segment filled bar |
| `<PlayerAvatar>` | `playerId: string, size: "sm" \| "md" \| "lg"` | Circular headshot, team color ring |
| `<InjuryBadge>` | `status: InjuryStatus` | Colored pill: "OUT" / "GTD" / "PROB" |
| `<DataValue>` | `value: number, format?: string` | Monospace formatted number |
| `<Sparkline>` | `data: number[], line?: number` | Tiny line chart with optional threshold line |
| `<HitDots>` | `results: boolean[]` | ●●●●●○○ hit/miss indicator |
| `<WaterfallChart>` | `breakdown: PointsBreakdown` | Horizontal waterfall of model adjustments |
| `<LivePulse>` | none | Pulsing cyan dot, always animated |
| `<Timestamp>` | `at: Date` | "Updated 30s ago" relative time |

### 4.2 Layout Components

| Component | Notes |
|-----------|-------|
| `<BentoGrid>` | CSS Grid wrapper with responsive column config |
| `<PageHeader>` | Title + subtitle + optional actions slot |
| `<FilterBar>` | Horizontal filter row with dropdowns and toggles |
| `<DataTable>` | Sortable, expandable table built on TanStack Table |
| `<TierGate>` | Wraps premium content. Shows blur + upgrade CTA for insufficient tier |
| `<EmptyState>` | Illustrated empty state for no data scenarios |
| `<SkeletonCard>` | Animated loading placeholder matching card dimensions |

### 4.3 Reusable Patterns

**Stat Display Pattern:**
```tsx
<div className="flex flex-col gap-1">
  <span className="text-xs text-text-secondary">Projected</span>
  <span className="font-mono text-2xl font-bold text-text-primary">29.7</span>
</div>
```

**Edge Display Pattern:**
```tsx
<span className={cn(
  "font-mono font-medium",
  edge > 0 ? "text-edge-positive" : "text-edge-negative"
)}>
  {edge > 0 ? "+" : ""}{edge.toFixed(1)}
</span>
```

**Injury Status Badge Pattern:**
```tsx
const statusColors = {
  OUT:          "bg-status-out/20 text-status-out",
  Doubtful:     "bg-status-doubtful/20 text-status-doubtful",
  Questionable: "bg-status-questionable/20 text-status-questionable",
  Probable:     "bg-status-probable/20 text-status-probable",
}
```

---

## 5. API Contracts

The backend is FastAPI (Python). All responses are JSON.
Base URL: `https://api.bettingbyte.com/api` (or `/api` in development proxy).

### 5.1 Authentication

```
POST /api/auth/register
  Body: { email: string, password: string }
  Response: { user: UserResponse, token: string }

POST /api/auth/login
  Body: { email: string, password: string }
  Response: { user: UserResponse, token: string }

GET /api/auth/me
  Headers: Authorization: Bearer <token>
  Response: UserResponse
```

```ts
type UserResponse = {
  id: number
  email: string
  tier: "FREE" | "PREMIUM" | "PRO"
  is_active: boolean
  created_at: string  // ISO 8601
}
```

### 5.2 Games

```
GET /api/games/today
  Response: GameResponse[]

GET /api/games/:gameId
  Response: GameDetailResponse
```

```ts
type GameResponse = {
  game_id: string
  season: string
  game_date: string              // ISO 8601
  game_time_utc: string          // ISO 8601
  home_team: TeamBrief
  away_team: TeamBrief
  game_status: number            // 1=Scheduled, 2=InProgress, 3=Final
  status_text: string            // "7:30 PM ET" / "Q2 4:32" / "Final"
}

type TeamBrief = {
  team_id: string
  abbreviation: string           // "LAL", "BOS"
  full_name: string              // "Los Angeles Lakers"
  city: string
  nickname: string
}

type GameDetailResponse = GameResponse & {
  home_team_score: number | null
  away_team_score: number | null
  period: number | null
  game_clock: string | null
  prop_count: number              // Number of props available for this game
  edge_count: number              // Number of props with edges
}
```

### 5.3 Props & Edges

```
GET /api/props/board
  Query: {
    date?: string            // "today" | "YYYY-MM-DD", default "today"
    stat_type?: string       // "points" | "rebounds" | "assists" | "threes"
    game_id?: string         // Filter to one game
    team?: string            // Filter to one team abbreviation
    sort?: string            // "edge" | "confidence" | "line" | "projection"
    edges_only?: boolean     // Only show props with |edge| >= 1.0
  }
  Response: PropBoardResponse

GET /api/props/:signalId
  Response: PropDetailResponse
```

```ts
type PropBoardResponse = {
  props: PropBoardRow[]
  meta: {
    total_count: number
    game_count: number
    updated_at: string        // ISO 8601
    stat_types_available: string[]
  }
}

type PropBoardRow = {
  signal_id: number
  game_id: string
  game_time_utc: string
  home_team_abbreviation: string
  away_team_abbreviation: string
  player_id: string
  player_name: string
  team_abbreviation: string
  stat_type: string
  line: number
  over_odds: number           // American odds, e.g. -110
  under_odds: number
  projected_value: number
  edge_over: number
  edge_under: number
  over_probability: number
  under_probability: number
  confidence: number
  recommended_side: "OVER" | "UNDER" | null
  // Quick-glance context (avoid needing a second API call)
  recent_hit_rate: number | null  // e.g. 0.80 = 8/10 games over
  recent_games_count: number | null
  key_factor: string | null       // One-line summary, e.g. "AD OUT +3.2 min"
}

type PropDetailResponse = PropBoardRow & {
  breakdown: PointsBreakdown
  opportunity: OpportunityContext
  features: FeatureSnapshot
  recent_game_log: GameLogEntry[]  // Last 10 games
}

type PointsBreakdown = {
  base_scoring: number
  recent_form_adjustment: number
  minutes_adjustment: number
  usage_adjustment: number
  efficiency_adjustment: number
  opponent_adjustment: number
  pace_adjustment: number
  context_adjustment: number
  expected_minutes: number
  expected_usage_pct: number
  points_per_minute: number
  projected_points: number
}

type OpportunityContext = {
  expected_minutes: number
  season_minutes_avg: number
  expected_usage_pct: number
  expected_start_rate: number
  expected_close_rate: number
  role_stability: number
  opportunity_score: number
  opportunity_confidence: number
  availability_modifier: number
  vacated_minutes_bonus: number
  vacated_usage_bonus: number
  // Injury context
  injury_entries: InjuryEntry[]   // Relevant injuries for this game
}

type InjuryEntry = {
  player_name: string
  team_abbreviation: string
  current_status: "Out" | "Doubtful" | "Questionable" | "Probable"
  reason: string
}

type FeatureSnapshot = {
  team_abbreviation: string
  opponent_abbreviation: string
  is_home: boolean
  days_rest: number | null
  back_to_back: boolean
  sample_size: number
  season_points_avg: number | null
  last10_points_avg: number | null
  last5_points_avg: number | null
  season_minutes_avg: number | null
  last10_minutes_avg: number | null
  last5_minutes_avg: number | null
  season_usage_pct: number | null
  opponent_def_rating: number | null
  opponent_pace: number | null
  team_pace: number | null
}

type GameLogEntry = {
  game_id: string
  game_date: string
  opponent: string
  is_home: boolean
  minutes: number
  points: number
  rebounds: number
  assists: number
  steals: number
  blocks: number
  turnovers: number
  threes_made: number
  field_goals_made: number
  field_goals_attempted: number
  free_throws_made: number
  free_throws_attempted: number
  plus_minus: number
}
```

### 5.4 Players

```
GET /api/players/:playerId
  Response: PlayerProfileResponse

GET /api/players/:playerId/game-log
  Query: { last?: number }    // Default 20
  Response: GameLogEntry[]

GET /api/players/:playerId/props
  Response: PropBoardRow[]

GET /api/players/:playerId/trends
  Query: { stat?: string, last?: number }
  Response: TrendPoint[]
```

```ts
type PlayerProfileResponse = {
  player_id: string
  full_name: string
  first_name: string
  last_name: string
  team_abbreviation: string
  team_full_name: string
  // Season averages (computed)
  season_averages: {
    games_played: number
    ppg: number
    rpg: number
    apg: number
    mpg: number
    fg_pct: number
    three_pct: number
    ft_pct: number
    usage_pct: number
    ts_pct: number
  }
  // Active props
  active_props: PropBoardRow[]
}

type TrendPoint = {
  game_date: string
  value: number           // The stat value
  line: number | null     // Prop line if one existed for that game
  hit: boolean | null     // Did they go over the line?
}
```

### 5.5 Live

```
GET /api/live/active
  Response: LiveGameSummary[]

GET /api/live/:gameId
  Response: LiveGameDetail

WebSocket: ws://api/ws/live/:gameId
  Server pushes: LiveUpdate (every 5-10s)
```

```ts
type LiveGameSummary = {
  game_id: string
  home_team: TeamBrief
  away_team: TeamBrief
  home_score: number
  away_score: number
  period: number
  game_clock: string
  live_edge_count: number     // Props with live edges
  updated_at: string
}

type LiveGameDetail = LiveGameSummary & {
  players: LivePlayerRow[]
  alerts: LiveAlert[]
  pace: {
    current_pace: number
    expected_pace: number
    scoring_impact_pct: number
  }
}

type LivePlayerRow = {
  player_id: string
  player_name: string
  team_abbreviation: string
  stat_type: string
  line: number
  current_stat: number        // Actual stat so far
  live_projection: number     // Re-projected final total
  pace_projection: number     // Simple linear pace
  live_edge: number           // live_projection - line
  pregame_projection: number  // Original pregame projection
  on_court: boolean
  minutes_played: number
  fouls: number
}

type LiveAlert = {
  id: string
  type: "edge_emerged" | "cold_start" | "hot_start" | "pace_shift" | "foul_trouble"
  player_name: string
  message: string
  edge_value: number | null
  created_at: string
}

type LiveUpdate = {
  type: "score" | "player_stats" | "alert" | "period_change"
  data: LiveGameDetail       // Full state on each update
}
```

### 5.6 Picks

```
GET /api/picks/active
  Response: PickResponse[]

GET /api/picks/history
  Query: { page?: number, limit?: number }
  Response: { picks: PickResponse[], total: number }

GET /api/picks/stats
  Response: PickStatsResponse

POST /api/picks
  Body: { signal_id: number, notes?: string, is_public?: boolean }
  Response: PickResponse

DELETE /api/picks/:pickId
  Response: { success: boolean }
```

```ts
type PickResponse = {
  id: number
  signal_id: number
  player_name: string
  team_abbreviation: string
  stat_type: string
  side: "OVER" | "UNDER"
  line: number
  projected_value: number
  edge: number
  confidence: number
  game_id: string
  game_date: string
  game_time_utc: string
  home_team_abbreviation: string
  away_team_abbreviation: string
  // Resolution
  status: "active" | "won" | "lost" | "push" | "void"
  actual_value: number | null
  resolved_at: string | null
  // Social
  is_public: boolean
  notes: string | null
  upvote_count: number
  created_at: string
}

type PickStatsResponse = {
  total_picks: number
  wins: number
  losses: number
  pushes: number
  win_rate: number           // 0.0 - 1.0
  current_streak: number     // Positive = win streak, negative = loss streak
  best_streak: number
  by_confidence: {
    high: { wins: number, losses: number, win_rate: number }
    medium: { wins: number, losses: number, win_rate: number }
    low: { wins: number, losses: number, win_rate: number }
  }
}
```

### 5.7 Community

```
GET /api/community/leaderboard
  Query: { period?: "7d" | "30d" | "season", sort?: "win_pct" | "roi" | "record" }
  Response: LeaderboardEntry[]

GET /api/community/feed
  Query: { page?: number, limit?: number, filter?: "popular" | "recent" }
  Response: { picks: PublicPickEntry[], total: number }

POST /api/community/picks/:pickId/upvote
  Response: { upvote_count: number }

GET /api/community/profile/:userId
  Response: PublicProfileResponse
```

```ts
type LeaderboardEntry = {
  rank: number
  user_id: number
  username: string
  avatar_url: string | null
  record: { wins: number, losses: number }
  win_rate: number
  streak: number
  total_picks: number
}

type PublicPickEntry = PickResponse & {
  user_id: number
  username: string
  avatar_url: string | null
}

type PublicProfileResponse = {
  user_id: number
  username: string
  avatar_url: string | null
  member_since: string
  stats: PickStatsResponse
  recent_picks: PickResponse[]  // Last 10 public picks
}
```

### 5.8 Injuries

```
GET /api/injuries/today
  Response: InjuryAlertResponse[]
```

```ts
type InjuryAlertResponse = {
  player_name: string
  player_id: string | null
  team_abbreviation: string
  current_status: string        // "Out", "Questionable", "Doubtful", "Probable"
  reason: string
  game_id: string
  game_date: string
  opponent_abbreviation: string
  report_datetime: string
  // Impact context
  affected_props_count: number  // How many props this injury might impact
}
```

---

## 6. Real-Time Architecture

### 6.1 WebSocket Connection

```
Client                        Server (FastAPI)
  │                              │
  │  ws://api/ws/live/:gameId    │
  │ ─────────────────────────►   │
  │                              │
  │  ◄── LiveUpdate (JSON) ───   │  every 5-10s during game
  │  ◄── LiveUpdate (JSON) ───   │
  │  ◄── LiveUpdate (JSON) ───   │
  │                              │
  │  ── ping ──────────────►     │  keepalive every 30s
  │  ◄── pong ─────────────      │
  │                              │
  │  (game ends)                 │
  │  ◄── { type: "game_final" }  │
  │                              │
```

### 6.2 Client-Side Integration

```ts
// Pseudocode pattern for TanStack Query + WebSocket
function useLiveGame(gameId: string) {
  const queryClient = useQueryClient()

  // Initial data load via REST
  const query = useQuery({
    queryKey: ['live', gameId],
    queryFn: () => fetchLiveGame(gameId),
    refetchInterval: 10_000, // Fallback polling
  })

  // WebSocket overlay for real-time updates
  useEffect(() => {
    const ws = new WebSocket(`ws://api/ws/live/${gameId}`)
    ws.onmessage = (event) => {
      const update = JSON.parse(event.data)
      queryClient.setQueryData(['live', gameId], update.data)
    }
    return () => ws.close()
  }, [gameId])

  return query
}
```

### 6.3 Data Freshness Strategy

| Data Type | Refresh Strategy | Interval |
|-----------|-----------------|----------|
| Prop board | TanStack polling | 30s |
| Dashboard | TanStack polling | 60s |
| Live game | WebSocket + REST fallback | 5-10s WS / 10s polling |
| Injuries | TanStack polling | 5 min |
| Player profile | TanStack stale-while-revalidate | On navigation |
| Leaderboard | TanStack polling | 5 min |
| User picks | TanStack invalidation on mutation | On change |

---

## 7. Authentication & Authorization

### 7.1 Auth Flow

1. User registers/logs in → server returns JWT token
2. Token stored in httpOnly cookie (preferred) or localStorage
3. Token sent on every API request via `Authorization: Bearer <token>`
4. Token expires after 24h → refresh flow or re-login
5. FastAPI middleware validates token and attaches user to request context

### 7.2 Tier Gating

The `<TierGate>` component wraps premium content:

```tsx
<TierGate requiredTier="PREMIUM" feature="Full Prop Board">
  <PropBoard />
</TierGate>
```

When the user's tier is insufficient:
- Content renders blurred/dimmed
- Overlay with: "Upgrade to Premium to unlock the full Prop Board"
- CTA button → `/settings#subscription`

**Tier gate map:**

| Feature | FREE | PREMIUM | PRO |
|---------|------|---------|-----|
| Dashboard | Full | Full | Full |
| Prop board rows | 5 visible | All | All |
| Prop deep-dive | 2/day | Unlimited | Unlimited |
| Live Center | Blurred preview | Full | Full |
| Pick tracker | 3 active max | Unlimited | Unlimited |
| Community | View only | Full | Full |
| API access | No | No | Yes |

### 7.3 API Error Handling

```ts
// Standard error response from FastAPI
type APIError = {
  detail: string
  code: string          // "AUTH_REQUIRED" | "TIER_INSUFFICIENT" | "NOT_FOUND" | etc.
  required_tier?: string // Present when code = "TIER_INSUFFICIENT"
}
```

Handle globally in a TanStack Query error handler:
- `401` → redirect to `/login`
- `403` with `TIER_INSUFFICIENT` → show upgrade modal
- `429` → show rate limit toast
- `500` → show error toast with retry button

---

## 8. Responsive Strategy

### 8.1 Breakpoints

```css
/* Tailwind defaults are fine */
sm:  640px   /* Large phones landscape */
md:  768px   /* Tablets */
lg:  1024px  /* Small laptops */
xl:  1280px  /* Desktops */
2xl: 1536px  /* Large desktops */
```

### 8.2 Mobile Adaptations

| Desktop | Mobile |
|---------|--------|
| Top nav bar | Bottom tab bar (5 icons) |
| Bento grid dashboard | Single column stack |
| Prop board table | Card list (stacked `<PropCard>`) |
| Expanded prop row | Full-screen slide-up sheet |
| Side-by-side context panels | Stacked accordion sections |
| Waterfall chart (horizontal) | Waterfall chart (vertical, narrower) |
| Live game table | Card list with swipe between players |

### 8.3 Bottom Tab Bar (Mobile)

```
┌────────┬────────┬────────┬────────┬────────┐
│  Home  │ Props  │  Live  │ Picks  │  More  │
│   🏠   │   📊   │   ⚡   │   🎯   │   ☰   │
└────────┴────────┴────────┴────────┴────────┘
```

Use Lucide icons (outlined style), not emoji. Active tab gets
`--brand-primary` color fill.

---

## 9. Performance Requirements

| Metric | Target | Measurement |
|--------|--------|-------------|
| First Contentful Paint | < 1.5s | Lighthouse |
| Largest Contentful Paint | < 2.5s | Lighthouse |
| Time to Interactive | < 3.0s | Lighthouse |
| Cumulative Layout Shift | < 0.1 | Lighthouse |
| Prop board render (50 rows) | < 100ms | React profiler |
| Live update paint | < 16ms (60fps) | Chrome DevTools |
| WebSocket message handling | < 50ms | Performance.now() |

### 9.1 Optimization Strategy

- **Skeleton loaders** for all data-fetching states (animated shimmer)
- **Virtualized lists** for prop board (50+ rows) — use TanStack Virtual
- **Image optimization** — Next.js `<Image>` for player headshots, lazy loaded
- **Code splitting** — Route-based splitting via Next.js App Router
- **Bundle size** — Monitor with `@next/bundle-analyzer`, target < 200KB first load JS
- **Prefetching** — Prefetch prop deep-dive data on row hover
- **Memoization** — Memoize expensive chart renders, confidence bar calculations

---

## 10. Accessibility

- All interactive elements must be keyboard navigable
- Focus ring: 2px `--border-focus` outline on `:focus-visible`
- Color contrast: all text meets WCAG AA (4.5:1 for body, 3:1 for large)
- Edge colors (green/red) are ALSO differentiated by icon/text ("+3.2 OVER"
  not just color alone) — color-blind safe
- Data tables have proper `<th scope>` and `aria-sort` attributes
- Live updates announce via `aria-live="polite"` region
- All images have `alt` text
- Skip navigation link on every page
- Reduced motion: respect `prefers-reduced-motion` for animations/sparklines

---

## 11. Implementation Order

Build the frontend in this order. Each phase is independently shippable.

### Phase A: Shell & Auth (Week 1)
- [ ] Next.js project scaffolding with Tailwind + shadcn
- [ ] Design system tokens (colors, fonts, spacing) in `tailwind.config.ts`
- [ ] Global layout shell (top nav, responsive bottom tabs, page container)
- [ ] Auth pages (login, register)
- [ ] Auth integration (JWT flow with FastAPI)
- [ ] `<TierGate>` component
- [ ] Protected route middleware

### Phase B: Prop Board & Deep-Dive (Week 2-3)
- [ ] `<PropRow>` and `<PropCard>` components
- [ ] `<EdgeBadge>`, `<ConfidenceBar>`, `<DataValue>` primitives
- [ ] `<FilterBar>` with dropdowns
- [ ] `<DataTable>` with sorting and expansion
- [ ] Prop Board page with TanStack Query integration
- [ ] `<WaterfallChart>` component (Recharts)
- [ ] `<Sparkline>` component
- [ ] `<HitDots>` component
- [ ] Prop Deep-Dive page
- [ ] Player Profile page

### Phase C: Dashboard (Week 3-4)
- [ ] `<GameCard>` component
- [ ] `<InjuryBadge>` and injury watch card
- [ ] Dashboard bento grid layout
- [ ] Top edges section
- [ ] My picks summary card
- [ ] Responsive mobile layout

### Phase D: Live Center (Week 5-6)
- [ ] WebSocket client integration
- [ ] `<LivePulse>` indicator
- [ ] Live game scoreboard component
- [ ] Live player stats table
- [ ] Live alert cards
- [ ] Pace tracker visualization
- [ ] Live → Dashboard integration (live now widget)
- [ ] Fallback polling for WebSocket failures

### Phase E: Pick Tracking (Week 6-7)
- [ ] Pick CRUD operations
- [ ] Active picks list with live status
- [ ] Pick history with pagination
- [ ] Performance stats dashboard
- [ ] Performance charts

### Phase F: Community (Week 7-8)
- [ ] Leaderboard table with rank badges
- [ ] Public picks feed
- [ ] Upvote interaction
- [ ] Public user profiles
- [ ] Share pick functionality

### Phase G: Polish (Week 8-9)
- [ ] Landing page
- [ ] Stripe subscription integration
- [ ] Skeleton loaders for all loading states
- [ ] Error boundaries and error states
- [ ] Empty states with illustrations
- [ ] Onboarding flow for new users
- [ ] Responsible gambling disclaimers
- [ ] Performance audit and optimization
- [ ] Accessibility audit
- [ ] E2E test coverage for critical flows

---

## Appendix: Backend Data Model Reference

These are the actual database models (SQLAlchemy ORM) the API layer reads
from. Included here so the frontend team understands what data exists and
what the API is assembling from.

### Key Models

| Model | Table | Purpose |
|-------|-------|---------|
| `ModelSignal` | `model_signals` | Generated predictions — the primary data behind the prop board |
| `PlayerPropSnapshot` | `player_prop_snapshots` | Current market lines from FanDuel |
| `Game` | `games` | Game schedule, teams, status |
| `Player` | `players` | Player reference data |
| `Team` | `teams` | Team reference data |
| `HistoricalGameLog` | `historical_game_logs` | Box score history (points, reb, ast, min, etc.) |
| `HistoricalAdvancedLog` | `historical_advanced_logs` | Advanced stats (usage%, pace, TS%, etc.) |
| `LiveGameSnapshot` | `live_game_snapshots` | Real-time game scores |
| `LivePlayerSnapshot` | `live_player_snapshots` | Real-time player stats during games |
| `OfficialInjuryReportEntry` | `official_injury_report_entries` | Injury report data |
| `PregameContextSnapshot` | `pregame_context_snapshots` | Lineup/availability context |
| `User` | `users` | User accounts with tier |
| `Subscription` | `subscriptions` | Stripe subscription management |

### Analytics Output Dataclasses

These are the Python dataclasses the backend produces. The API serializes
these into the response types defined in Section 5.

**`PregamePointsBreakdown`** — The waterfall chart data:
- `base_scoring`, `recent_form_adjustment`, `minutes_adjustment`,
  `usage_adjustment`, `efficiency_adjustment`, `opponent_adjustment`,
  `pace_adjustment`, `context_adjustment`
- `expected_minutes`, `expected_usage_pct`, `points_per_minute`
- `opportunity_score`, `opportunity_confidence`, `role_stability`
- `projected_points`

**`PregamePointsProjection`** — The full signal:
- `projected_value`, `distribution_std`
- `over_probability`, `under_probability`
- `edge_over`, `edge_under`
- `confidence`, `recommended_side`

**`PregameOpportunityBreakdown`** — The opportunity context:
- `expected_minutes`, `expected_rotation_minutes`
- `expected_usage_pct`, `expected_est_usage_pct`
- `expected_touches`, `expected_passes`
- `expected_start_rate`, `expected_close_rate`
- `availability_modifier`, `vacated_minutes_bonus`, `vacated_usage_bonus`
- `role_stability`, `rotation_role_score`
- `offensive_role_score`, `matchup_environment_score`
- `opportunity_score`, `confidence`
