<div align="center">

# 🌿 SafeSpace

### A low-pressure self-care app that turns daily life into a personal archive

Small quests, a decorated journal, and friendly forums. No streaks, no leaderboards: you never lose anything by missing a day.

![Python](https://img.shields.io/badge/Python-3.14-324841?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-6.1-324841?logo=django&logoColor=white)
![AI](https://img.shields.io/badge/AI-runs%20locally-ADC2AF)
![License](https://img.shields.io/badge/License-Apache%202.0-9C95C9)

[Quick Guide](#quick-guide) | [Features](#features) | [A8: RAG System](#a8-rag-system) | [Run the App](#run-the-app) | [AI Docs](README_AI.md) | [Project Notes](safespace/docs/project_notes.md)

</div>

## Quick Guide

1. **Run the A8 RAG notebook:** follow [A8: RAG System](#a8-rag-system). The results and write-up are in [`llm-test/rag_analysis.md`](llm-test/rag_analysis.md).
2. **Run the web app:** follow [Run the App](#run-the-app), then open http://127.0.0.1:8000/ and sign up or log in.

## Features

### 🌱 Quests
- **Small daily quests** in categories like General Self-Care, Diet & Wellness, Social and Learning.
- **Joint quests:** invite a friend and complete a quest together.
- **Rewards:** every quest unlocks stickers, frames and fonts for your journal.

### 🤖 Ask SafeSpace (local AI)
- **Quest suggestion:** tell SafeSpace how you feel, and a local model (`Qwen2.5-0.5B-Instruct`) picks a matching quest.
- **Health tip from NIH:** a RAG pipeline (`bge-small-en-v1.5`, hybrid chunks, top-3, relevance threshold) adds a short tip with links to the NIH articles it came from.
- **Guardrails:** crisis messages show the 988 hotline, prompt-injection attempts and off-topic questions get no tip, and broken model output falls back to a safe answer. Everything runs on your own computer.

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

#### 1. Install the dependencies (same as above)

```bash
pip install -r requirements.txt
```

#### 2. Start the server

```bash
cd safespace
python manage.py migrate        # the included db.sqlite3 is already up to date; safe to run
python manage.py runserver
```

Open http://127.0.0.1:8000/. The included `db.sqlite3` has sample users, quests, completions, rewards and journals.

#### 3. Optional extras

- **AI quest suggestions:** log in as a regular user and open **Quests → Ask SafeSpace for a quest**. The models download on the first suggestion. See [`README_AI.md`](README_AI.md).
- **Personalized welcome messages:** set `GEMINI_KEY` in the environment or in `safespace/.env.local`. Without it, the home page shows a friendly default.
- **Google login:** the client secret is not in the repository. Add your own under **Admin → Social applications**.

## Why SafeSpace?

**SafeSpace is built for people facing so much stress that they start to disengage.** Instead of extrinsic hooks like leaderboards and punishing streaks, it focuses on long-term intrinsic motivation.

**Every step is small and low-pressure.** Quests take minutes, and missing a day never costs you anything.

**Your days become a permanent timeline.** Journals, rewards and quests build up into a personal archive you can look back on.

## Team

Team 9 (INFO 490): Em Bensinger, Koey Huang, Nicholas Rondon, Yu-Chen (Ilona) Tung.

# License

SafeSpace is licensed under the [Apache License 2.0](LICENSE).
