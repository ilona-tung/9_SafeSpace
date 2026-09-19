# SafeSpace — Part 4 Notes


- Project: `safespace` 
- Team: 9
- Members: 

## Design principle


## Models (6 total)
- **Quest**: 
- **QuestCompletion**: 
- **Reward**: 
- **Journal**: 
- **Forum**: 
- **Friendship**:

## on_delete choices
- `QuestCompletion.user`, `Reward.user`, `Journal.user`, `Forum.user`,
  `Friendship.user_from/user_to` → **CASCADE**:



## Uniqueness constraints
- `Quest`: unique on `(title, category)` — no duplicate catalog entries.
- `QuestCompletion`: unique on `(user, quest, quest_date)` — no logging
  the same quest twice on the same day.
- `Friendship`: unique on `(user_from, user_to)` — no duplicate friend
  requests in the same direction.

## Ordering
- `Quest`: by category, then title.
- `QuestCompletion`: most recent `quest_date` first.
- `Reward`, `Journal`, `Forum`, `Friendship`: most recent first.


