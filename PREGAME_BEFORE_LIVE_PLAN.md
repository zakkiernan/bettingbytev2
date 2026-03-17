# Pregame Before Live Plan

## Goal

Ship a stats-first pregame system that is transparent, operationally reliable, and measurable before we add live-state complexity.

## Phase 1: Readiness Gates

Objective: only issue pregame recommendations when the supporting data is fresh enough and complete enough.

Steps:
- Add explicit readiness status to every signal card.
- Block recommendations when the signal is using fallback logic, has too little recent sample, or is built on stale line captures.
- Surface readiness counts in health so we can see how many signals are truly ready vs limited vs blocked.

Exit criteria:
- Board/detail responses explain why a signal is blocked or limited.
- Health endpoint shows ready, limited, blocked, and fallback counts.
- Scheduler failures show up as recommendation suppression instead of silent bad picks.

## Phase 2: Signal Audit Trail

Objective: make every generated recommendation inspectable after the fact.

Steps:
- Persist the stats-first signal outputs we show to the API.
- Store the readiness status, breakdown, and the source snapshot timestamps used for the card.
- Add a simple historical lookup for what we recommended and why.

Exit criteria:
- We can answer "what did we recommend for this player before tip?"
- We can audit misses without reconstructing state from logs.

## Phase 3: Backtest And Calibration

Objective: measure whether the stats-first heuristics are directionally useful and where they are overconfident.

Steps:
- Replay historical pregame lines through the current stats-first runtime logic.
- Track recommendation rate, win rate, confidence-bucket calibration, and performance by player profile.
- Tune thresholds only after the baseline metrics are stable.

Exit criteria:
- Confidence buckets are measurable.
- Recommendation thresholds are tied to observed results, not guesswork.

## Phase 4: Product States And Ops Guardrails

Objective: make the product honest about signal quality and keep the slate operationally clean.

Steps:
- Expose clear states such as ready, limited, and blocked in the API/UI contract.
- Add stale-data alerts for lines, injuries, and pregame context.
- Add a lightweight catch-up path for missed windows instead of relying on manual repairs.

Exit criteria:
- The app can distinguish "no pick" from "not enough trusted data."
- Ops can spot when the slate is degraded before users do.

## Phase 5: Pregame Reliability Soak

Objective: let the pregame system run across enough slates that it becomes boring.

Steps:
- Run the scheduler untouched across early tips, split slates, and late injury windows.
- Review health and readiness counts daily.
- Fix the recurring misses before adding any new scope.

Exit criteria:
- Several consecutive clean slates.
- No recurring stale-data class remains unowned.

## Phase 6: Live Design Spike

Objective: define live as its own system instead of stretching pregame assumptions into in-game logic.

Steps:
- Define live freshness rules, latency budget, and game-state dependencies.
- Decide which pregame signals carry forward and which must be recomputed from live data.
- Build a minimal live prototype only after the pregame system passes the earlier phases.

Exit criteria:
- Live requirements are explicit.
- We are extending a trusted pregame system, not compounding uncertainty.
