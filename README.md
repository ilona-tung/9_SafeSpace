# SafeSpace

- Project: `safespace` 
- Team: 9
- Members: Em Bensinger, Koey Huang, Nicholas Rondon, Yu-Chen (Ilona) Tung

## Design principle
SafeSpace is a self-care app designed to combat burnout by transforming daily life into a personal archive. 
Developed for individuals who are facing external stresses to the point of disengagement, SafeSpace deliberately focuses less on traditional extrinsic hooks, 
such as leaderpoints and punishing streak mechanics; instead, it focuses on long-term intrinsic motivation. 
Through low-pressure tasks and activities, mindful journaling, and having a permanent timeline, 
this app acts as a sanctuary for users to create small but effective habits to make their every day more enjoyable.

## UI-UX
The files are configured referencing the class zip follow-along for ease of understanding and use, this means there are three basic sheets that the files follow for basic styling. The color palette is meant to feel relaxing which is why the basic colors are green and white with some subtle purple tones (the background is a very light shade of purple and the darkest text is a very dark shade of purple. The color palette is based on the colors Dark Slate Grey, Ash Grey, Lavender, Ghost White, and Shadow Grey which are easy on the eyes.

## API desc
The app uses GET calls to get information on quests and search for users. POST calls handle account registration by adding new users to the database. They are protected with csrf tokens.

## Other notes for P1-A3
safespace/docs/P1-A3 Organized Notes

## How to run locally
```bash
git clone https://github.com/ilona-tung/9_SafeSpace.git
cd 9_SafeSpace
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r safespace/safespace/settings/requirements.txt
cd safespace
python manage.py migrate        # already up to date in the included db.sqlite3; safe to run
python manage.py runserver
```
Open http://127.0.0.1:8000/. The included `db.sqlite3` has sample users, quests, completions, rewards and journals.

**AI quest suggestions (optional, local only):** from the `safespace` folder, `pip install -r safespace/settings/requirements-ai.txt`
(torch + transformers). The model `Qwen/Qwen2.5-0.5B-Instruct` downloads automatically on the first suggestion.
Log in as a regular user and open **Quests → Ask SafeSpace for a quest**. See `README_AI.md` for details.

**Google login:** the Google client secret is not stored in the repository.
To use it, add your own key under Admin → Social applications.
