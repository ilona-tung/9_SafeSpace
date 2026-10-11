# A5 Notes: Design Logic & Deployment

## 1. Core principle: SafeSpace is not a competition

SafeSpace is a self-care app. Users should never feel compared to others.

- No streaks, no leaderboards, nothing is lost by missing a day.
- Regular users only see **their own** data.
- Stats about many users (reports, user lists, completion counts per user) are **admin-only**.

Almost every access decision below comes from this rule.

---

## 2. Roles

| Role | Can do | Cannot do/access                                 |
|---|---|--------------------------------------------------|
| **Logged out** | Home page, quest chart on the home page, Log in / Sign up | Anything personal                                |
| **Regular user** | Quests (mark completed), Rewards, Journal, Forums Nearby | Reports, Users, Vega-Lite page, completion stats |
| **Admin** (`is_staff`) | Reports, Users, Vega-Lite, exports, system-wide reward stats | Journal, completing quests                       |

---
## 3. Part 3: APIs + Vega-Lite

### APIs
**`/api/quest-summary/`** is the only public API.

- All other APIs stay protected (`completion-timeline` is admin-only; `location` and `forum-nearby` need login).

