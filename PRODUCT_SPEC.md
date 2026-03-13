# BettingByte Product Spec & Roadmap

Last updated: 2026-03-12

---

## 1. Product Vision

**BettingByte** is an NBA player-prop analytics platform that gives bettors a
data-driven edge on pregame and **live** betting markets.

**Core differentiators:**
1. **Player prop niche** - every model, feature, and UI is built around
   individual player stat lines, not game outcomes.
2. **Live betting focus** - real-time signal updates as games progress, not
   just pregame snapshots.
3. **Transparent projections** - users see *why* a projection exists
   (minutes opportunity, usage shift, injury context, pace) rather than a
   black-box number.

**Target users:** Recreational-to-serious NBA bettors who research player
props before placing wagers, and degenerate live bettors who need fast,
trustworthy in-game signals.

---

## 2. Current Backend State (What Exists)

| Layer | Status | Notes |
|-------|--------|-------|
| Database (30+ models) | Stable | Users, games, players, rotations, props, injuries, signals |
| Ingestion pipeline | Stable | NBA API, FanDuel scraper, rotation scraper, injury PDF parser |
| Opportunity model | In progress | Minutes/usage projection, 88.9% start accuracy |
| Points model (v3) | Baseline | MAE 5.08, 14.5k samples, consumes opportunity layer |
| Backtesting framework | Working | MAE/RMSE/bias, miss profiling, injury-aware evaluation |
| API skeleton | Scaffolded | FastAPI routes for auth, games, props, edges |
| Frontend | None | Not started |

---

## 3. Product Architecture

```
                    ┌──────────────────────────────────────┐
                    │           FRONTEND (Next.js)         │
                    │                                      │
                    │  Dashboard  │  Prop Board  │  Live   │
                    │  Social     │  Leaderboard │  Alerts │
                    └────────────────┬─────────────────────┘
                                     │  REST / WebSocket
                    ┌────────────────▼─────────────────────┐
                    │           API LAYER (FastAPI)         │
                    │                                      │
                    │  Auth  │ Games │ Props │ Edges │ Live │
                    │  Social │ Leaderboard │ Alerts       │
                    └────────────────┬─────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────┐
        │                            │                        │
  ┌─────▼──────┐           ┌────────▼────────┐      ┌───────▼───────┐
  │ INGESTION  │           │   ANALYTICS     │      │   DATABASE    │
  │            │           │                 │      │  (Postgres)   │
  │ NBA API    │           │ Opportunity     │      │               │
  │ FanDuel    │──────────▶│ Points Model    │─────▶│ 30+ tables    │
  │ Rotations  │           │ Live Model      │      │ Model signals │
  │ Injuries   │           │ Edge Calculator │      │ User data     │
  │ Context    │           │ Evaluation      │      │               │
  └────────────┘           └─────────────────┘      └───────────────┘
```

---

## 4. Page Map & UX Design

### 4.1 Information Architecture

```
/                           Landing / Marketing page
/login                      Auth (login + signup)
/dashboard                  Home after login (today's slate overview)
│
├── /props                  PROP BOARD - the core product page
│   ├── /props?view=board   Grid view of all today's props
│   ├── /props?view=edges   Filtered to props with edges only
│   └── /props/:id          Single prop deep-dive
│
├── /player/:id             PLAYER PROFILE
│   ├── Stats + history
│   ├── Active props
│   └── Model breakdown
│
├── /live                   LIVE CENTER - real-time during games
│   ├── /live               Active games overview
│   └── /live/:gameId       Single game live tracker
│
├── /picks                  MY PICKS - personal bet tracker
│   ├── /picks/active       Current open picks
│   └── /picks/history      Historical record + P/L
│
├── /community              SOCIAL HUB
│   ├── /community/feed     Public picks feed
│   ├── /community/leaderboard  Top performers
│   └── /community/profile/:id  Public user profile
│
├── /alerts                 ALERT CENTER
│   └── Notification preferences + history
│
└── /settings               Account, subscription, preferences
```

### 4.2 Page Designs

---

#### **Dashboard** (`/dashboard`)
The first thing users see after login. Answer: "What should I bet today?"

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  BETTINGBYTE                    🔔  [Avatar ▾]      │
├─────────────────────────────────────────────────────┤
│                                                     │
│  TODAY'S SLATE          March 12, 2026              │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐              │
│  │BOS   │ │LAL   │ │GSW   │ │+3    │              │
│  │@ MIA │ │@ DAL │ │@ PHX │ │more  │              │
│  │7:30  │ │8:00  │ │10:00 │ │      │              │
│  └──────┘ └──────┘ └──────┘ └──────┘              │
│                                                     │
│  TOP EDGES TODAY                    [View All →]    │
│  ┌──────────────────────────────────────────────┐  │
│  │ ★ LeBron James PTS Over 26.5  │ +3.2 edge   │  │
│  │   Proj: 29.7 │ Line: 26.5    │ High conf    │  │
│  ├──────────────────────────────────────────────┤  │
│  │ ★ Jayson Tatum PTS Under 31.5 │ +2.8 edge   │  │
│  │   Proj: 28.1 │ Line: 31.5    │ Med conf     │  │
│  └──────────────────────────────────────────────┘  │
│                                                     │
│  ┌─────────────────┐  ┌────────────────────────┐   │
│  │ INJURY WATCH     │  │ YOUR PICKS TODAY       │   │
│  │ 🔴 Giannis OUT   │  │ 2 active / 1 won      │   │
│  │ 🟡 Curry GTD     │  │ +$45 today             │   │
│  │ 🟢 Doncic PROB   │  │ [View Slip →]          │   │
│  └─────────────────┘  └────────────────────────┘   │
│                                                     │
│  LIVE NOW                           [Live Center →] │
│  ┌──────────────────────────────────────────────┐  │
│  │ BOS 54 - MIA 48  │  Q2 4:32  │  3 live edges│  │
│  └──────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

**Key data points:**
- Today's game cards (teams, time, status)
- Top 5-10 edges ranked by confidence
- Injury alerts affecting props
- User's active picks summary
- Live games with live edge count

---

#### **Prop Board** (`/props`)
The core product page. A scannable, filterable table of all player props.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  PROP BOARD                                         │
│                                                     │
│  Filters:                                           │
│  [All Games ▾] [Points ▾] [Edges Only ☐]           │
│  [All Teams ▾] [Min Conf ▾] [Sort: Edge ▾]         │
│                                                     │
│  ┌─────────────────────────────────────────────────┐│
│  │ Player      │ Prop    │ Line │ Proj │ Edge │ Cf ││
│  ├─────────────────────────────────────────────────┤│
│  │ LeBron      │ PTS O   │ 26.5 │ 29.7 │ +3.2 │ ██││
│  │ Tatum       │ PTS U   │ 31.5 │ 28.1 │ +3.4 │ ██││
│  │ Booker      │ PTS O   │ 24.5 │ 27.0 │ +2.5 │ █ ││
│  │ Edwards     │ PTS O   │ 23.5 │ 25.8 │ +2.3 │ █ ││
│  │ ...         │         │      │      │      │   ││
│  └─────────────────────────────────────────────────┘│
│                                                     │
│  Showing 47 props across 6 games                    │
└─────────────────────────────────────────────────────┘
```

**Features:**
- Sortable/filterable table (game, stat type, edge size, confidence)
- Color-coded edge indicators (green = over, red = under)
- Click any row to expand inline or navigate to deep-dive
- "Edges Only" toggle hides props without a meaningful edge
- Stat type tabs: Points (launch), then Rebounds, Assists, 3s (later)

---

#### **Prop Deep-Dive** (`/props/:id`)
Transparent breakdown of a single projection. This is where BettingByte
earns trust.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  ← Back to Board                                    │
│                                                     │
│  LeBron James  •  PTS Over 26.5  •  LAL @ DAL      │
│  ┌─────────────────────────────────────────────┐    │
│  │  PROJECTION: 29.7    EDGE: +3.2   CONF: Hi │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  WHY THIS EDGE?                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │ Base (PPM × Mins)           │ 25.1  │ ████ │    │
│  │ Recent Form (5g)            │ +1.8  │  ██  │    │
│  │ Usage Shift                 │ +0.9  │  █   │    │
│  │ Opponent DEF Rating         │ +1.2  │  █   │    │
│  │ Pace Adjustment             │ +0.4  │  ▌   │    │
│  │ Context (Home, Rest)        │ +0.3  │  ▌   │    │
│  │ ─────────────────────────────────────────── │    │
│  │ Final Projection            │ 29.7  │      │    │
│  └─────────────────────────────────────────────┘    │
│                                                     │
│  OPPORTUNITY CONTEXT                                │
│  • Projected minutes: 35.2 (season avg: 34.8)      │
│  • Usage rate: 31.2% (up from 29.8% last 5)        │
│  • AD is PROBABLE - no major role shift expected    │
│  • DAL allows 4th-most PPG to SFs this season      │
│                                                     │
│  RECENT HISTORY                                     │
│  ┌──────────────────────────────────────┐           │
│  │  [Sparkline chart: last 10 games]   │           │
│  │  vs Line: ████████░░  (8/10 over)   │           │
│  └──────────────────────────────────────┘           │
│                                                     │
│  [Track This Pick]  [Share]                         │
└─────────────────────────────────────────────────────┘
```

**Key features:**
- Waterfall chart showing each model adjustment
- Opportunity context (minutes, usage, injuries, matchup)
- Recent hit rate vs this line
- Sparkline of last 10 game actuals
- One-click pick tracking

---

#### **Live Center** (`/live`)
The flagship differentiator. Real-time prop tracking during games.

**Layout:**
```
┌─────────────────────────────────────────────────────┐
│  LIVE CENTER                                 ● LIVE │
│                                                     │
│  ┌──────────────────────────────────────────────┐   │
│  │ BOS 54 - MIA 48       Q2 4:32    Pace: 102  │   │
│  ├──────────────────────────────────────────────┤   │
│  │ Player    │Prop   │Line│ Curr│ Proj│ Pace │Edge│ │
│  │ Tatum     │PTS O  │28.5│ 14  │ 30.1│ 29.3│+1.6│ │
│  │ Brown     │PTS O  │22.5│ 11  │ 23.8│ 23.1│+1.3│ │
│  │ Butler    │PTS U  │21.5│  8  │ 17.2│ 16.8│+4.3│ │
│  │ ...                                          │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  ┌──────────────────┐  ┌────────────────────────┐   │
│  │ PACE TRACKER      │  │ LIVE ALERTS            │   │
│  │ Game pace: 102    │  │ 🔥 Butler cold start   │   │
│  │ Expected: 98.5    │  │    PTS U 21.5 → +4.3  │   │
│  │ Impact: +3.2%     │  │ ⚡ Tatum on fire       │   │
│  │ scoring           │  │    PTS O 28.5 → +1.6  │   │
│  └──────────────────┘  └────────────────────────┘   │
│                                                     │
│  Other Live Games:                                  │
│  [LAL @ DAL  Q1 8:02]  [GSW @ PHX  Not Started]    │
└─────────────────────────────────────────────────────┘
```

**Key features:**
- WebSocket-driven real-time updates (2-5 second refresh)
- Current stats vs projected pace to hit the line
- Re-projected final totals based on current performance
- Live edge recalculation as the game evolves
- Alerts for emerging edges (cold/hot starts, pace changes, foul trouble)
- Game pace tracker (actual vs expected, scoring impact)

---

#### **Player Profile** (`/player/:id`)

```
┌─────────────────────────────────────────────────────┐
│  LeBron James  │  LAL  │  SF  │  #6                 │
│                                                     │
│  Season Averages                                    │
│  PPG: 26.8 │ RPG: 7.2 │ APG: 8.1 │ MPG: 34.8      │
│                                                     │
│  ACTIVE PROPS                                       │
│  ┌──────────────────────────────────────────────┐   │
│  │ PTS O/U 26.5  │ Proj: 29.7  │ Edge: +3.2    │   │
│  │ REB O/U 7.5   │ Proj: --    │ Coming soon   │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  GAME LOG (last 10)                                 │
│  ┌──────────────────────────────────────────────┐   │
│  │ Date   │ Opp │ MIN │ PTS │ REB │ AST │ USG% │   │
│  │ 3/10   │ PHX │ 36  │ 31  │ 8   │ 9   │ 32.1 │   │
│  │ 3/8    │ SAC │ 34  │ 28  │ 6   │ 7   │ 30.5 │   │
│  │ ...    │     │     │     │     │     │      │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  MODEL INSIGHTS                                     │
│  • Opportunity: Stable starter, 34-36 min range     │
│  • Recent form: +1.8 above season avg (last 5)      │
│  • Key matchup: Favorable vs DAL SF defense         │
└─────────────────────────────────────────────────────┘
```

---

#### **My Picks** (`/picks`)
Personal bet tracking and performance history.

```
┌─────────────────────────────────────────────────────┐
│  MY PICKS                                           │
│                                                     │
│  [Active]  [History]  [Stats]                       │
│                                                     │
│  ACTIVE PICKS (3)                                   │
│  ┌──────────────────────────────────────────────┐   │
│  │ LeBron PTS O 26.5  │ Proj 29.7 │ ⏳ 7:30 PM │   │
│  │ Tatum PTS U 31.5   │ Proj 28.1 │ ⏳ 7:30 PM │   │
│  │ Butler PTS O 20.5  │ Proj 22.3 │ 🔴 LIVE    │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  PERFORMANCE                                        │
│  Record: 47-31 (60.3%)  │  ROI: +8.2%              │
│  Streak: W3  │  Best edge tier: High conf (67%)     │
│                                                     │
│  [Export CSV]                                       │
└─────────────────────────────────────────────────────┘
```

---

#### **Community / Leaderboard** (`/community`)

```
┌─────────────────────────────────────────────────────┐
│  COMMUNITY                                          │
│                                                     │
│  [Feed]  [Leaderboard]  [My Profile]                │
│                                                     │
│  LEADERBOARD (Last 30 Days)                         │
│  ┌──────────────────────────────────────────────┐   │
│  │ #  │ User        │ Record  │ ROI    │ Streak │   │
│  │ 1  │ SharpShark  │ 52-28   │ +14.2% │ W7     │   │
│  │ 2  │ PropKing    │ 48-31   │ +11.8% │ W3     │   │
│  │ 3  │ NBAEdge     │ 45-30   │ +10.1% │ L1     │   │
│  │ ...│             │         │        │        │   │
│  └──────────────────────────────────────────────┘   │
│                                                     │
│  PUBLIC PICKS FEED                                  │
│  ┌──────────────────────────────────────────────┐   │
│  │ 🏀 SharpShark picked LeBron PTS O 26.5      │   │
│  │    "Minutes should be up with AD questionable"│   │
│  │    👍 12  │  2h ago                           │   │
│  ├──────────────────────────────────────────────┤   │
│  │ 🏀 PropKing picked Tatum PTS U 31.5         │   │
│  │    "MIA defense has been elite lately"        │   │
│  │    👍 8   │  3h ago                           │   │
│  └──────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

**Leaderboard rules:**
- Only tracked picks (through BettingByte) count
- Minimum 20 picks to qualify
- Rolling 30-day window (prevents one hot streak from camping #1)
- Separate leaderboards by confidence tier and stat type
- Optional: verified picks via sportsbook API integration later

---

## 5. Subscription Tiers

| Feature | Free | Premium | Pro |
|---------|------|---------|-----|
| Today's top 3 edges | Yes | Yes | Yes |
| Full prop board | No | Yes | Yes |
| Prop deep-dive breakdowns | Limited (2/day) | Yes | Yes |
| Live Center | No | Yes | Yes |
| Live alerts | No | 5/game | Unlimited |
| Pick tracker | 3 active | Unlimited | Unlimited |
| Community / leaderboard | View only | Full access | Full access |
| Historical backtests | No | No | Yes |
| API access | No | No | Yes |
| Stat types | Points only | All available | All available |

---

## 6. Data Display Strategy

### 6.1 How to Show Edges
- **Edge = Projection - Line**. Always show both numbers.
- Color scale: green (favorable), yellow (marginal), gray (no edge).
- Confidence bars (not just numbers) to convey uncertainty visually.
- Never show a naked number without context. Always pair projection with
  the breakdown that produced it.

### 6.2 How to Show Model Transparency
- **Waterfall charts** for projection breakdowns (base + adjustments).
- **Tooltip/expand** for each adjustment factor explaining what it means.
- **Injury/context badges** inline on prop cards (e.g., "AD OUT +3.2 min").
- **Hit rate indicators** on the prop board (e.g., "8/10 over last 10").

### 6.3 How to Show Live Data
- **Pace-to-hit trackers** - "On pace for 28.4" vs line of 26.5.
- **Re-projected totals** - Model re-runs with current game state.
- **Time-series sparklines** - Running stat totals plotted live.
- **Alert cards** that pop in when new edges emerge mid-game.

### 6.4 Data Freshness Indicators
- Timestamp on every data card ("Updated 2s ago", "Pregame snapshot").
- Stale data warnings if ingestion is delayed.
- Connection status indicator for live WebSocket feeds.

---

## 7. Technical Frontend Stack (Recommendation)

| Concern | Choice | Rationale |
|---------|--------|-----------|
| Framework | Next.js 15 (App Router) | SSR for SEO landing pages, client components for live data |
| Styling | Tailwind CSS + shadcn/ui | Fast iteration, consistent dark-mode support |
| Charts | Recharts or Tremor | Lightweight, React-native, good for sparklines/waterfalls |
| Real-time | WebSocket (native) | FastAPI supports WS natively; no need for Socket.io overhead |
| State | React Query (TanStack) | Caching, refetching, optimistic updates for prop data |
| Auth | NextAuth.js or Clerk | JWT flow matching your FastAPI auth middleware |
| Hosting | Vercel (frontend) + Railway/Fly (backend) | Simple deployment, good DX |

---

## 8. Development Roadmap

### Phase 4: Finish Opportunity Model (Current - in progress)
**Goal:** Improve player-level availability matching so the opportunity
backbone is trustworthy enough to ship.

- [ ] Improve player-specific injury matching coverage (currently 1.9%)
- [ ] Make injury features stronger only when player/role-specific
- [ ] Add denser near-tip historical injury snapshots for backtest fidelity
- [ ] Target: Minutes MAE < 4.5, Start accuracy > 90%

**Gate:** Opportunity model backtests show meaningful improvement from
injury/availability features.

---

### Phase 5: Expand Stat Engines
**Goal:** Add rebounds, assists, and 3-pointers stat engines on top of the
shared opportunity backbone.

- [ ] `analytics/rebounds_model.py` - Rebounds projection engine
- [ ] `analytics/assists_model.py` - Assists projection engine
- [ ] `analytics/threes_model.py` - 3-pointers projection engine
- [ ] `analytics/features_rebounds.py` - Rebound-specific features
- [ ] `analytics/features_assists.py` - Assist-specific features
- [ ] `analytics/features_threes.py` - 3PT-specific features
- [ ] Backtest each stat engine independently
- [ ] Wire all stat engines into the edge calculator

**Gate:** Each stat engine has a baseline backtest with documented MAE.

---

### Phase 6: API Hardening & Historical Lines
**Goal:** Make the API production-ready and build a historical prop line
archive for edge validation.

- [ ] Flesh out all FastAPI route handlers (games, props, edges, player)
- [ ] Add response schemas (Pydantic models for all API responses)
- [ ] Add rate limiting and error handling middleware
- [ ] Schedule prop line snapshots (capture FanDuel lines at -4h, -1h, tip)
- [ ] Build historical line archive (needed for edge backtest validity)
- [ ] Add a second sportsbook adapter (DraftKings or BetMGM)
- [ ] Production database migration plan (SQLite -> PostgreSQL)

**Gate:** API serves all data the frontend needs. Historical line archive
has 30+ days of coverage.

---

### Phase 7: Frontend MVP (Pregame)
**Goal:** Ship the first usable version. Pregame only.

- [ ] Project scaffolding (Next.js + Tailwind + shadcn)
- [ ] Auth flow (login, signup, JWT integration with FastAPI)
- [ ] Dashboard page (today's slate, top edges, injury watch)
- [ ] Prop Board page (sortable/filterable table)
- [ ] Prop Deep-Dive page (waterfall breakdown, context, history)
- [ ] Player Profile page (stats, game log, active props)
- [ ] Dark mode (default dark - it's a betting app)
- [ ] Mobile responsive (prop board must work on phone)
- [ ] Subscription tier gating (free vs premium content)

**Gate:** A friend or beta tester can log in, browse props, understand
an edge, and want to come back tomorrow.

---

### Phase 8: Live Betting Engine
**Goal:** Build the live model and real-time data pipeline.

- [ ] `analytics/live_model.py` - Live re-projection engine
  - Inputs: current stats, time remaining, game pace, foul trouble
  - Output: updated projection + live edge vs current live lines
- [ ] Live ingestion: WebSocket or polling for in-game scores/stats
- [ ] Live prop line ingestion (FanDuel live lines)
- [ ] Live edge calculator (pregame projection vs live re-projection)
- [ ] Alert engine: detect emerging edges above threshold
- [ ] Backtest framework for live model (replay historical games)

**Gate:** Live model can re-project during a game with < 5s latency
and the alert engine fires meaningful signals.

---

### Phase 9: Frontend - Live Center
**Goal:** Ship the live experience.

- [ ] WebSocket integration (FastAPI -> Next.js)
- [ ] Live Center page (active games, real-time prop tracking)
- [ ] Live game drill-down (pace tracker, re-projected totals, alerts)
- [ ] Live alert notifications (in-app, optional push)
- [ ] Smooth real-time UI updates (no jank, optimistic rendering)
- [ ] Live edge cards on the Dashboard

**Gate:** Users can watch a game while BettingByte surfaces live edges
they wouldn't have found themselves.

---

### Phase 10: Pick Tracking & Social
**Goal:** Add engagement and retention features.

- [ ] Pick tracker (add/remove picks, auto-resolve from game results)
- [ ] Personal performance dashboard (record, ROI, streaks)
- [ ] Public pick sharing (opt-in per pick)
- [ ] Community feed (public picks with optional commentary)
- [ ] Leaderboard (rolling 30-day, min 20 picks, by tier)
- [ ] User profiles (public stats, pick history)
- [ ] Social interactions (upvotes on picks, follow users)

**Gate:** Users engage with the community features and the leaderboard
drives competitive retention.

---

### Phase 11: Polish & Scale
**Goal:** Production hardening for growth.

- [ ] Performance optimization (CDN, caching, DB indexing)
- [ ] Monitoring and alerting (ingestion health, model drift, uptime)
- [ ] Stripe integration for subscriptions
- [ ] Email notifications (daily edge digest, live alerts)
- [ ] Onboarding flow for new users
- [ ] Landing page / marketing site
- [ ] Analytics / usage tracking
- [ ] Additional sportsbook adapters
- [ ] Legal / responsible gambling disclosures

---

## 9. Priority Matrix

| High Impact + Low Effort | High Impact + High Effort |
|--------------------------|---------------------------|
| Prop Board page | Live betting engine |
| Prop Deep-Dive transparency | WebSocket infrastructure |
| Dashboard top edges | Multi-stat expansion |
| Injury badges | Community / leaderboard |

| Low Impact + Low Effort | Low Impact + High Effort |
|--------------------------|---------------------------|
| Dark mode | API access tier |
| Mobile responsive | Sportsbook API verification |
| Pick export CSV | Email notification system |

---

## 10. Key Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model accuracy not good enough to sell | Fatal | Focus on transparency over accuracy claims. Users trust *why* more than the number. |
| FanDuel scraper breaks | High | Add DraftKings adapter. Abstract behind provider layer (already done). |
| Live data latency too high | High | Start with 5-10s polling, upgrade to WebSocket. Good enough for casual live bettors. |
| Legal / gambling regulations | Medium | Add responsible gambling disclosures. Position as "analytics" not "picks". Don't guarantee outcomes. |
| Leaderboard gaming | Medium | Minimum pick count, rolling window, flag suspicious patterns. |
| Historical line archive too thin | Medium | Start snapshotting now. 30 days needed before edge claims are credible. |

---

## 11. Immediate Next Actions

1. **Finish Phase 4** - get the opportunity model to a trustworthy state.
2. **Start snapshotting prop lines NOW** - even before the frontend exists,
   schedule automated line captures at multiple time points. You need this
   historical data for edge validation and it takes real calendar time to
   accumulate.
3. **Scaffold the Next.js project** - even a blank project with auth flow
   removes the "where do I start" friction when Phase 7 arrives.
4. **Design the API response contracts** - define Pydantic response models
   for every endpoint before building the frontend. This is the handshake
   between your backend and frontend.
