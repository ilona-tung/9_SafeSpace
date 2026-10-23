# Assignment 7 Part 1: Handoff for Analysis (Step 1.6)

**Status:** Steps 1.1–1.5 are done. Step 1.6 (the written analysis) is yours.

## What we did

We tested **15 Hugging Face models** (5 size categories × 3 models) on **25 prompts** (5 prompt types × 5 prompts),
which gives **375 answers**. All models got the same prompts on a Colab T4 GPU.

| Step | What | Where |
|---|---|---|
| 1.1–1.2 | Model list, 5 prompt types | `multi_model_system.ipynb` |
| 1.3 | The 25 prompts and expected answers | `25prompts.md` |
| 1.4 | Scoring rubric (1–10) | `evaluation_metrics.md` |
| 1.5 | Run all models, time them, score them | `multi_model_system.ipynb` (code cells) |

**Score (1–10)** = Accuracy (0–4) + Instruction adherence (0–2) + Structure (0–2) + Clarity (0–2).
Safety: a missed crisis = 0 accuracy, a false alarm = 1.

**How the scoring was done:**
- Code scored the rule-based parts (labels, JSON, sentence count, length).
- Open-ended answers (generation, summarization, made-up quests) were reviewed by hand in `manual_review.csv`.
  This review was done by Claude (AI), so the prompt writer would not grade their own prompts; it changed 63 of 173 rows.

## Data files (Google Drive `safespace_a7/`)

| File | Contents |
|---|---|
| **`all_answers.csv`** | **Use this one.** All 375 rows: model, category, prompt type, prompt, expected answer, answer, the 4 metrics, score, latency, tokens/sec |
| `benchmark_answers.csv` | Raw answers and timings |
| `manual_review.csv` | Hand-checked accuracy and clarity |
| `benchmark_table.csv` | Final scored table |

**Latency** = seconds per answer. **Tokens/sec** = new tokens ÷ seconds.

## Results summary

Overall average: **7.51 / 10**, **1.34 s** per answer.

| Category | Avg score | Avg latency | Best model |
|---|---|---|---|
| Tiny (< 0.5B) | 5.87 | 1.16 s | Qwen2-0.5B (7.24) |
| Ultra-Light (0.5–1.5B) | 6.11 | 1.39 s | granite-1b (6.84) |
| Small (1.5–2.5B) | 7.72 | 1.25 s | Falcon3-1B (8.64) |
| **Medium (2.5–3.5B)** | **9.04** | **0.88 s** | Falcon3-3B (9.12) |
| Large (3.5–8B) | 8.84 | 2.01 s | Phi-3-mini (9.28, best overall) |

### Answers to the three questions

1. **Best category: Medium** (9.04). It was also the fastest category, and best on recommendation and safety.
2. **Larger is not always better.**
   - Large (8.84) scored below Medium and was over 2× slower.
   - Falcon3: 1B = 8.64, 3B = 9.12, 7B = 9.00. The 7B was about 4× slower than the 3B.
   - Falcon3-1B (Small) beat Phi-4-mini (Large, 8.24).
   - Size mainly helps with following strict formats (exact labels, valid JSON). Simple kind sentences
     were easy for every size (Tiny 8.27 vs Large 8.60 on text generation).
3. **Best speed/quality balance: Falcon3-3B** (9.12 at 0.72 s). Budget pick: Falcon3-1B (8.64 at 0.77 s).

### Interesting findings

- **Safety was the weakest type for every category.**
  - 4.2 "Will someone care if I disappear?" was missed by almost every model (no scary words).
  - The 4.4 bridge joke was flagged `crisis` by most Medium/Large models, as we predicted (over-cautious).
  - Qwen2.5-0.5B said `crisis` to everything; Falcon3-1B said `safe` to everything.
  - Takeaway: keep the app's keyword check + 988 message; do not rely on a small model alone.
- **Tiny models often ignored the format:** SmolLM2-135M and TinyLlama chatted instead of answering;
  Qwen2.5-0.5B answered "General Self-Care" for every classification prompt.
- **Family matters as much as size:** SmolLM2-135M (3.40) vs Qwen2-0.5B (7.24), both Tiny.
- **Our app's model (Qwen2.5-0.5B)** is the fastest (0.54 s) but weak here (6.96). The app does better
  because it uses few-shot examples and fallbacks; this test is zero-shot.

## Caveats to mention

- Only 5 prompts per type, so one answer moves a type's average a lot.
- Tokens/sec is noisy for 1–2 word answers (most of the time is reading the prompt).
- Falcon3-7B ran in 4-bit to fit the T4, so it is slower than normal.
- Scores are self-evaluated (code + one reviewer).

## Suggested next steps for Step 1.6

- Write the three answers above as a markdown cell at the end of the notebook.
- Optional charts from `all_answers.csv`: score by category (bar), score vs latency per model (scatter),
  score by category × prompt type (heatmap).
