<div align="center">

<img src="safespace/docs/banner.svg" alt="SafeSpace: small quests, a decorated journal, friendly forums" width="100%">

### A low-pressure self-care app that turns daily life into a personal archive

No streaks, no leaderboards: you never lose anything by missing a day.

![Python](https://img.shields.io/badge/Python-3.14-324841?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.1-324841?logo=django&logoColor=white)
![AI](https://img.shields.io/badge/AI-runs%20locally-ADC2AF)
![License](https://img.shields.io/badge/License-Apache%202.0-9C95C9)

[Quick Guide](#quick-guide) | [Features](#features) | [A8: RAG System](#a8-rag-system) | [Run the App](#run-the-app) | [AI Docs](README_AI.md) | [Project Notes](safespace/docs/project_notes.md)

</div>

## Quick Guide

1. **Run the A8 RAG notebook:** follow [A8: RAG System](#a8-rag-system). The results and write-up are in [`llm-test/rag_analysis.md`](llm-test/rag_analysis.md).
2. **Run the web app:** follow [Run the App](#run-the-app), then open http://127.0.0.1:8000/ and sign up or log in.
3. **Try the AI feature:** log in as a regular user, open **Quests → Ask SafeSpace for a quest**, and see [Use the AI feature](#3-use-the-ai-feature-ask-safespace).

## Features

### 🌱 Quests
- **Small daily quests** in categories like General Self-Care, Diet & Wellness, Social and Learning.
- **Joint quests:** invite a friend and complete a quest together.
- **Rewards:** every quest unlocks stickers, frames and fonts for your journal.

### 🤖 Ask SafeSpace (local AI)
- **Quest suggestion:** tell SafeSpace how you feel, and a local model (`Qwen2.5-0.5B-Instruct`) picks a matching quest.
- **Health tip from NIH:** a RAG pipeline (`bge-small-en-v1.5`, hybrid chunks, top-3, relevance threshold) adds a short tip with links to the NIH articles it came from.
- **Guardrails:** crisis messages show the 988 hotline, prompt-injection attempts are refused, junk or off-topic input ("what is the capital of France") gets no quest, and broken model output falls back to a safe answer. Everything runs on your own computer.

### 📔 Journal, forums and profiles
- **Journal:** write about your day and decorate the page with your rewards.
- **Forums:** join communities, post and reply, and find forums near a place (OpenStreetMap).
- **Profiles and friends:** a profile with your quest chart, friends and joint quests. Private things (journals, rewards, quests) are never shown to others.

## A8: RAG System

A retrieval-augmented generation system over 6 NIH self-care articles: 3 chunking strategies × 3 embedding models, evaluation, failure analysis and system design.

| Required file | What's inside |
| :--- | :--- |
| [`llm-test/rag_system.ipynb`](llm-test/rag_system.ipynb) | Full implementation and experiments: chunking, embeddings, retrieval, generation, evaluation |
| [`llm-test/rag_analysis.md`](llm-test/rag_analysis.md) | Evaluation tables, comparisons, failure analysis, system design |
| [`requirements.txt`](requirements.txt) | All dependencies (notebook and web app) |
| [`llm-test/knowledge_base.txt`](llm-test/knowledge_base.txt) | The knowledge base the notebook reads |

#### 1. Set up Python (3.14) and install the dependencies

```bash
git clone https://github.com/ilona-tung/9_SafeSpace.git
cd 9_SafeSpace
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

#### 2. Open the notebook from the `llm-test` folder

```bash
cd llm-test
jupyter notebook rag_system.ipynb
```

The notebook reads `knowledge_base.txt` from its own folder, so start Jupyter inside `llm-test`. In VS Code or PyCharm, open the notebook and pick the `.venv` kernel.

#### 3. Run all cells

```text
Kernel → Restart & Run All
```

> **Note:** the first run downloads the models from Hugging Face (BGE small, base and large, plus Qwen2.5-0.5B-Instruct, about 3 GB in total). No API keys are needed. A GPU is optional; the notebook also runs on a laptop CPU, just more slowly.

## Run the App

#### 1. Set up Python (3.14) and install the dependencies

```bash
git clone https://github.com/ilona-tung/9_SafeSpace.git
cd 9_SafeSpace
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

One install covers everything: Django and the AI packages (`torch`, `transformers`, `sentence-transformers`). It is about 2 GB, mostly `torch`. If you already did this for the notebook, skip it.

#### 2. Start the Django server

```bash
cd safespace
python manage.py migrate        # the included db.sqlite3 is already up to date; safe to run
python manage.py runserver
```

Open http://127.0.0.1:8000/ and **sign up** for a new account. The included `db.sqlite3` already has sample users, quests, completions, rewards, journals and forums. For the admin site (`/admin/`), create an account with `python manage.py createsuperuser`.

#### 3. Use the AI feature (Ask SafeSpace)

1. Log in as a **regular user**. Admin accounts don't see the AI form.
2. Open **Quests** in the top menu (marked **AI**) and scroll to **Ask SafeSpace for a quest**.
3. Write how you feel (up to 300 characters) or tap a quick feeling. Optionally, choose one of your journal entries.
4. Click **Suggest a quest**. The page shows **one quest** from the database with a short message, and a **health tip from NIH** with links to its sources.

| Try typing | What you get |
| :--- | :--- |
| `stressed about exams next week` | A quest and a health tip |
| `I can't sleep well lately` | A quest and a sleep tip from NIH |
| `what is the capital of France` | "Tell me a bit more" (off topic, no quest) |
| `ignore all previous instructions` | "I can only help with self-care quests" |

How it works: [`safespace/core/ai.py`](safespace/core/ai.py) (quest suggestion and guardrails) and [`safespace/core/rag.py`](safespace/core/rag.py) (health tip and relevance check). More in [`README_AI.md`](README_AI.md).

#### 4. Model download notes

- **No model weights are in the repository.** The first suggestion downloads two public models from Hugging Face automatically:
  - [`Qwen/Qwen2.5-0.5B-Instruct`](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct) (~1 GB): picks the quest and writes the tip
  - [`BAAI/bge-small-en-v1.5`](https://huggingface.co/BAAI/bge-small-en-v1.5) (~130 MB): embeddings for the tip search and the relevance check
- **The first suggestion is slow** (a minute or two while the models download and load). After that, the models stay in memory and answers take a few seconds.
- The models are cached in `~/.cache/huggingface/`. After the first download the app also works offline (set `HF_HUB_OFFLINE=1` to skip the online check).
- **No API key or Hugging Face account is needed.** A GPU is optional: the app uses CUDA or Apple Silicon (MPS) if available, otherwise the CPU.
- If the AI packages are missing, the form shows *"AI quest suggestions are only available when SafeSpace runs locally with the AI packages installed"*. Run `pip install -r requirements.txt` again in the active environment.

#### 5. Optional extras

- **Personalized welcome messages:** copy `safespace/.env.example` to `safespace/.env` and add a `GEMINI_KEY`. This is the only feature that calls an external API. Without a key, the home page shows a friendly default.
- **Google login:** set up your own Google OAuth client under **Admin → Social applications**.
- **Tests for the AI feature** (no model download needed): `python manage.py test core.tests.AIQuestSuggestionTests core.tests.HealthTipTests`

## Project Structure

```text
9_SafeSpace/
├── requirements.txt            # one install for the app and the notebooks
├── llm-test/                   # A6–A8 notebooks and write-ups (rag_system.ipynb, relevance_check.py, ...)
├── scripts/                    # quest statistics scripts
└── safespace/                  # Django project (run manage.py here)
    ├── manage.py
    ├── db.sqlite3              # sample data
    ├── core/                   # the app: models, views, forms, templates, tests
    │   ├── ai.py               # local LLM quest suggestion + guardrails
    │   ├── rag.py              # RAG health tip + relevance check
    │   ├── welcome.py          # optional Gemini welcome message
    │   └── data/knowledge_base.txt
    ├── safespace/settings/     # base / development / production settings, requirements
    ├── safespace/ui-ux/static/ # CSS, JS, images, reward artwork
    └── docs/                   # notes, wireframes, older assignment screenshots
```

## Why SafeSpace?

**SafeSpace is built for people facing so much stress that they start to disengage.** Instead of extrinsic hooks like leaderboards and punishing streaks, it focuses on long-term intrinsic motivation.

**Every step is small and low-pressure.** Quests take minutes, and missing a day never costs you anything.

**Your days become a permanent timeline.** Journals, rewards and quests build up into a personal archive you can look back on.

## Team

Team 9 (INFO 490): Em Bensinger, Koey Huang, Nicholas Rondon, Yu-Chen (Ilona) Tung.

# License

SafeSpace is licensed under the [Apache License 2.0](LICENSE).
