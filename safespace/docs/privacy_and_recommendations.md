# Privacy, Data Storage & Recommendations — Presentation Notes

Notes for the final presentation Q&A. Not legal advice; this is how we reasoned about it as a class project.

---

## 1. What user data does SafeSpace store?

| Data | Where | Sensitivity |
|---|---|---|
| Username, email, password | Django `auth_user` (passwords hashed with PBKDF2 by Django) | Medium |
| Journal pages (text, one-line summary, stickers, layout) | `Journal`, `JournalSticker` | **High** — feelings / mental wellness |
| Forum posts, replies, forum memberships | `Post`, `Reply`, `Forum.members` | Medium (public to members) |
| Location text on forums / posts | City-level text only, typed by the user | Medium |
| "Near me" searches | Geocoded with Nominatim **for that request only, never saved** | Low |
| Quest completions, rewards, friends, profile bio | `QuestCompletion`, `UserReward`, `Friendship`, `Profile` | Low–medium |

**Who else sees it**
- **Google Gemini**: the home-page welcome message sends the user's 3 latest journal entries (`core/welcome.py`).
- **Local AI model** (transformers, runs on our server): quest suggestions read the chosen journal entry (`core/ai.py`). Nothing leaves the server.
- **Admins** through Django admin.

---

## 2. Which laws apply?

| Law | Applies to us? | Why it matters |
|---|---|---|
| **HIPAA** | No | Only covers healthcare providers, insurers and their business associates. A wellness journal isn't one. |
| **FTC Act §5 + Health Breach Notification Rule** (updated 2024) | Yes, in spirit | Non-HIPAA health/wellness apps must not mislead users about sharing, and must report breaches of health data. Mood journals count. |
| **Illinois PIPA** | Yes | Breach notification; covers username/email + password. |
| **Washington My Health My Data Act** | If WA users | Covers "mental wellness" data; opt-in consent before collecting or sharing it. |
| **COPPA** | If under-13 users | We should require users to be 13+. |
| **GDPR** | If EU users | Feelings = special-category health data → explicit consent, right to export and delete. |
| **CCPA/CPRA** | No (revenue/size thresholds) | Still a good model: right to know, delete, opt out. |

---

## 3. How should user data be stored? (our plan)

1. **Keep secrets and the database out of the public repo.** `SECRET_KEY` and API keys live only in `.env`; `db.sqlite3` is not tracked, and only test data goes in it.
2. **Consent before third-party AI.** Sending journals to Gemini is an opt-in switch that explains what is sent. The local model is the default because data never leaves our server.
3. **Privacy page.** What we store, who sees it, how long we keep it, how to delete it.
4. **User rights.** Download my data (JSON) and delete my account (cascades to journals, posts, stickers). Deleting a single journal page already works.
5. **Encrypt journals at rest.** Field-level encryption of `content` and `summary` with a key in `.env`, so a leaked DB file or backup is unreadable. Not end-to-end, because the server-side AI must read entries.
6. **Data minimization.** City-level location only, no GPS coordinates; geocoding results are not saved.
7. **Secure transport and cookies in production.** HTTPS redirect, HSTS, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`.
8. **Limit staff access.** Journals hidden or read-only in Django admin.

**Why SQLite?** It is fine at class-project scale on PythonAnywhere. The risks above are about access and consent, not the database engine.

---

## 4. What recommendation algorithms can we use?

### How the laws shape recommendations

| Rule | Region | Effect on SafeSpace |
|---|---|---|
| GDPR profiling rules | EU | Recommending from mood/journal data = profiling on health data → explicit opt-in. |
| Digital Services Act (recommender transparency) | EU | Explain why something is recommended; very large platforms must offer a non-profiled feed (we copy this). |
| Washington MHMDA | WA | Using wellness data beyond the requested feature needs consent. |
| NY SAFE for Kids Act; similar CA/UT laws | US minors | No "addictive" personalized feeds for under-18s without parental consent → newest-first feed for teens. |
| State privacy laws (CO, CT, VA, …) | US | Users can opt out of profiling. |

**Design principle:** behavior data (quests done, forums joined) is low-risk; feeling/journal data is high-risk. Every recommendation shows *why*, and there is a "turn off personalization" switch.

### Algorithms, simplest first

1. **Popularity with time decay** — no personal data.
   Score = recent posts + replies ÷ `(age_in_hours + 2)^1.5` (Hacker News style). Used for trending forums, new users (cold start), and when personalization is off.
2. **Content-based** — quest history.
   Count the categories of quests a user completed and boost forums in those categories. Explainable: *"Because you did 6 Outdoors quests."*
3. **Item-item collaborative filtering** — forum memberships.
   *"People who joined Morning Walkers also joined Plant Swap."* Jaccard similarity between forums' member sets; works with small data, no ML library.
4. **Social** — forums your friends are in (only if memberships are already visible to friends).
5. **Location** — distance to a place the user types + popularity. Per request, city-level, never stored (what we already do).
6. **Mood/journal-based (LLM)** — only when the user clicks for it, on the local model, never used to rank the forum feed. This is how quest suggestions already work.

**Not used:** matrix factorization / deep-learning recommenders — not enough users to beat 2 and 3, and harder to explain.

**Proposed "Forums to discover":** weighted mix of 1 + 2 + 3, with a one-line reason under each forum and a settings switch.

### Safety rules for a wellness app

- Rank for relevance, not engagement or time spent; mix categories so users don't see only one kind.
- Never push crisis-related content; point to help resources instead (`is_crisis` in `core/ai.py`).
- No infinite scroll; the feed has a fixed size (`FEED_SIZE`).

---

## 5. Likely questions — short answers

- **"Is SafeSpace HIPAA compliant?"** HIPAA doesn't apply to us (not a healthcare provider), but we follow FTC health-app guidance: no hidden sharing, breach notification, user control.
- **"Does the AI see my journal?"** The local model reads the entry you choose, on our server. Gemini only gets entries if you opt in.
- **"Can I delete my data?"** Yes — single pages now; full account deletion and export are part of the plan.
- **"How do you recommend forums without being creepy?"** Behavior-based signals only, with a visible reason and an off switch. Feelings are never used to rank feeds.
- **"What about minors?"** 13+ only; under-18s get a newest-first feed, not a personalized one.
