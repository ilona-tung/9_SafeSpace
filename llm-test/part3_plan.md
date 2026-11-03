# Part 3 Plan: Failure Analysis & Improvement

## Step 3.1: Failure Cases

### Failure 1: Wrong chunk retrieved (sleep question)

**Question:** "I've been having trouble sleeping. What habits can help me sleep better?"
**Store:** medium model + overlapping chunks

| Rank | Score | Retrieved from |
|---|---|---|
| **#1** | 0.657 | **Caring for Your Mental Health** > How can I take care of my mental health? ❌ |
| #2 | 0.652 | Good Sleep for Good Health > Sleep disorders / Getting better sleep |
| #3 | 0.650 | Good Sleep for Good Health > Getting better sleep / Tips for a better night's sleep |

The top result should come from the sleep article. Instead it's a general self-care chunk. Only its first 3 sentences are about sleep ("Make sleep a priority. Stick to a schedule…"); the rest is about relaxation, goals, gratitude and staying connected. It's the only one of the 9 stores that gets this question wrong at rank 1. Note how close the scores are: 0.657 vs 0.652.

**How to show it in the notebook:**
```python
show_results(TEST_QUESTIONS[2]["query"], stores[("medium", "overlapping")])
```

### Failure 2: Weak chunk retrieved because of the query's wording (relaxation question)

**Question:** "I'm feeling overwhelmed. Are there any relaxation tips?"
**Store:** large model + hybrid chunks

| Rank | Score | Retrieved from |
|---|---|---|
| #1 | 0.646 | Feeling Stressed? > Ways to manage stress ✅ |
| **#2** | 0.627 | **Feeling Stressed? > What stress is** ⚠️ |
| #3 | 0.607 | Feeling Stressed? > Just breathe ✅ |

The right article is found, but the #2 chunk **explains what stress is and gives no tips**. It begins: "Have you been feeling more stressed than usual? … The COVID-19 pandemic has many people feeling **overwhelmed**…" It ranks high largely because it contains the user's word "overwhelmed". Meanwhile "Ways to de-stress", a section full of relaxation ideas, doesn't make the top 3 at all.

**How to show it:**
```python
show_results(TEST_QUESTIONS[1]["query"], stores[("large", "hybrid")])
```

### Failure 3: Incomplete context (fixed-length chunks cut topics in half)

Fixed-length chunks stop when they reach about 150 words, wherever that falls in the text. Look at fixed-length chunk #2 from "Caring for Your Mental Health":

> **Learn to say "no" to new tasks** if you start to feel like you're taking on too much. … It may take trial and error to discover what works best for you. **Seek professional help if you are experiencing severe or distressing symptoms that have lasted 2 weeks or more.**

- It **starts mid-list.** The tip before it ("Set goals and priorities. Decide what must get done now…") is in the previous chunk.
- It **ends with the first sentence of the next section**. The list of symptoms that sentence introduces is in the *next* chunk, which starts "These symptoms include…" and so has nothing for "These" to refer to.

**Effect on retrieval:** for the relaxation question ("I'm feeling overwhelmed. Are there any relaxation tips?"), this mixed chunk is the #1 result for **all three** fixed-length stores. The hybrid stores instead return "Feeling Stressed? > Ways to manage stress", which actually lists stress-relief tips. Fixed-length chunking also has the lowest "hits in top 3" of the three strategies (12–13 of 15, against 14 of 15 for hybrid).

**How to show it:**
```python
print(stores[("large", "fixed_length")].chunks[2]["text"])
print(stores[("large", "fixed_length")].chunks[3]["text"][:200])
show_results(TEST_QUESTIONS[1]["query"], stores[("large", "fixed_length")])
show_results(TEST_QUESTIONS[1]["query"], stores[("large", "hybrid")])
```

### Failure 4: Hallucinated answer (off-topic question)

**Question:** "What is a good recipe for pasta carbonara?" (our knowledge base has nothing about cooking)

| Best retrieved chunks | Score |
|---|---|
| Build Social Bonds > Ways to connect with others | 0.39 |
| Good Sleep > Tips for a better night's sleep | 0.37 |
| Build Social Bonds > Who's at risk? | 0.37 |

The system prompt says *"If the context does not contain the answer, say that you don't have information on that topic."* The model ignored this and **wrote a full carbonara recipe** from its own memory. In our first run it even listed "1/4 cup pancetta drippings" three times. The retrieved chunks were about friendship and sleep, so none of the answer came from our sources.

**How to show it:**
```python
answer, sources = rag_answer("What is a good recipe for pasta carbonara?", min_score=0.0)
print(answer)
print(sources)
```

### Failure 5: Hallucinated details inside on-topic answers

Even when retrieval is correct, the model adds advice that **isn't in any retrieved chunk, or anywhere in our knowledge base**:

| Question | Added by the model | In the knowledge base? |
|---|---|---|
| Self-Care | "Choose an activity you enjoy, like knitting or **gardening**" | "gardening" appears nowhere |
| Relaxation | "engaging in physical activities like yoga or **stretching**" | "stretching" appears nowhere |
| Relaxation (first version of the prompt) | "**Progressive Muscle Relaxation**: tense each muscle group…" | not in the knowledge base |

The advice isn't harmful, but the answer *sounds* as if it comes from NIH sources, and parts of it don't. A user can't tell which sentences are backed by a source.

**How to show it:**
```python
for q in TEST_QUESTIONS:
    answer, sources = rag_answer(q["query"])
    print(q["topic"], "->", answer, "\n")
# Check a suspicious word against the knowledge base:
print("gardening" in raw.lower(), "stretching" in raw.lower())   # False False
```

---

## Step 3.2: Root Cause Analysis

| Failure | Chunking? | Embedding model? | Query formulation? | Main cause |
|---|---|---|---|---|
| 1. Wrong chunk (sleep) | **Yes** | **Yes** | **Yes** | all three contribute |
| 2. Weak chunk (relaxation) | no | partly | **Yes** | query formulation |
| 3. Incomplete context | **Yes** | no | no | chunking |
| 4. Hallucination (off-topic) | no | no | partly | the generator, not retrieval |
| 5. Hallucinated details | no | no | no | the generator and the prompt |

**Failure 1:**
- **Chunking.** The overlap chunk glues a sleep paragraph to a paragraph about goals and gratitude. Its "meaning vector" is a blend: partly sleep, mostly general self-care.
- **Query formulation.** The question asks for *habits*, and the Caring chunk is literally a list of daily habits. "I've been having trouble…" also adds words that match nothing specific. A rewrite such as "What habits help with sleep problems and insomnia?" puts the sleep article first (0.686 vs 0.658).
- **Embedding model.** The small and large models rank the sleep article first on the same chunks; only medium doesn't. With scores 0.005 apart, small differences between models decide the winner.

**Failure 2:**
- **Query formulation.** The user describes a *feeling* ("overwhelmed") instead of the *topic* ("stress relief"). The embedding model rewards the chunk that shares the word "overwhelmed", even though that chunk is a definition. Rewording the query to the topic fixes it (see Option A).
- **Embedding model, partly.** Embeddings capture "what the text is about", not "does it answer the question". A definition of stress and a list of stress tips are both "about stress", so they score close together.
- **Not chunking.** Each hybrid chunk is one clean section; the wrong section simply won.

**Failure 3:**
- **Chunking only.** A fixed word limit ignores where topics start and end, so chunks contain half of one idea plus half of the next. Any embedding model gets a muddled chunk, and the generator gets incomplete context: a symptom list without its intro, or an intro without its list.

**Failure 4:**
- **Not chunking or embedding.** Retrieval actually behaved correctly: every score was below 0.4, far under the 0.6–0.8 that real questions get. That's the system saying "nothing matches."
- **Query formulation, partly:** the question is outside the knowledge base's scope.
- **The real cause:** the pipeline always passes the top-3 chunks to the model, however poor they are, and a 0.5B model doesn't reliably follow "say you don't know." It falls back on what it learned in pretraining.

**Failure 5:**
- **Not chunking, embedding or query.** The right chunks were retrieved.
- **The generator.** A 0.5B model mixes the context with general wellness advice it saw during pretraining. It can't reliably tell "from the context" apart from "things I know".
- **The prompt.** It asks for "only the context" but never asks the model to *show* where each point comes from, so nothing forces it to stay grounded.

---

## Step 3.3: Solution Options (pick at least one)

Each option shows the before/after we measured. Pick one or more; whoever builds it should rerun and use the notebook's own outputs.

### Option A: Refine the query (fixes Failures 1 and 2)
Rewrite the user's question into a short, topic-focused search query before retrieval. Keep the original question for the generator.

**Failure 1:**

| Query sent to medium + overlapping | #1 result | Sleep chunks in top 3 |
|---|---|---|
| Before: "I've been having trouble sleeping. What habits can help me sleep better?" | Caring for Your Mental Health ❌ (0.657) | 2 / 3 |
| After: "What habits help with sleep problems and insomnia?" | Good Sleep > Getting better sleep ✅ (0.686) | 2 / 3 |
| After: "How can I sleep better?" | Good Sleep > Why sleep matters ✅ (0.663) | **3 / 3** |

**Failure 2:**

| Query sent to large + hybrid | Top 3 sections | Definition chunk in top 3? |
|---|---|---|
| Before: "I'm feeling overwhelmed. Are there any relaxation tips?" | Ways to manage stress, **What stress is**, Just breathe | yes ⚠️ |
| After: "How can I relax and reduce stress?" | Ways to de-stress (0.725), Ways to manage stress (0.720), Just breathe (0.692) | **no** ✅ |

- **Pros:** easy to code, clear before/after, and it matches the "refine query" option in the assignment.
- **Cons:** we write the rewrites by hand. An automatic version (letting Qwen rewrite the query first) is possible but more work.

### Option B: Adjust chunk size or chunk boundaries (fixes Failure 3)
Results for fixed-length chunks, shown as relevant chunks in the top 3, out of 15:

| Version | Chunks | small | medium | large |
|---|---|---|---|---|
| Before: 150 words, may cross headings | 36 | 13 | 12 | 12 |
| 100 words | 52 | 10 | 10 | 12 |
| **250 words** | 22 | 13 | **13** | **13** |
| 150 words, **never crosses a heading** | 47 | 12 | 12 | **13** |

- With "never cross a heading", chunk #2 no longer ends with the stray "Seek professional help…" sentence, and for the small model the relaxation question's #1 becomes "Ways to manage stress" ✅.
- **Pros:** fixes the root cause of Failure 3 directly, and matches "adjust chunk size".
- **Cons:** the improvement is real but small (12 → 13 of 15), and the relaxation question is still wrong for medium and large. Be honest about that in the write-up.

### Option C: Change top-k (helps Failures 1 and 3)
More chunks give the generator more context, even when #1 is wrong.

| top-k (medium + overlapping, sleep question) | Sleep chunks given to the model |
|---|---|
| k = 1 | 0 / 1 ❌ (the model only sees the wrong chunk) |
| k = 3 (current) | 2 / 3 |
| k = 5 | 4 / 5 |

- **Pros:** a one-number change and easy to show.
- **Cons:** it doesn't fix the ranking itself, and longer prompts make the 0.5B model slower and more likely to drift.

### Option D: Improve the prompt + add a relevance threshold (fixes Failure 4, reduces Failure 5)
1. **Relevance threshold:** if the best chunk scores below 0.5, skip the model and reply "I don't have information on that topic."
2. **Better prompt:** repeat "Answer using only the context above, in 3 to 6 sentences" *after* the question, because small models pay most attention to the end of the prompt.

| | Carbonara question | 5 test questions |
|---|---|---|
| Before | writes a made-up recipe | long answers, some cut off, extra advice not in the sources |
| After | "I'm sorry, I don't have information on that topic…" ✅ | 3–8 sentences, mostly drawn from the sources |

- **Pros:** **the code already exists in Step 1.5** (`rag_answer(..., min_score=0.5)` and `build_messages`). For "before", call with `min_score=0.0` and the old prompt.
- **Cons:** the "before" prompt has to be added back as a second function for the comparison. The threshold value (0.5) was picked from only 5 questions.
- **Failure 5 is reduced, not solved.** The new prompt removed "Progressive Muscle Relaxation", but "gardening" and "stretching" still slip in. A further prompt idea to try: ask the model to cite a context number for each tip, e.g. "(Source [2])". Fully fixing it would need a larger generator model.

### Our suggestion
- **Least work:** Option D, since the code is already there.
- **Strongest retrieval story:** Option A (fixes two failures) or B, because they fix a retrieval failure and show before/after tables.
- Doing **D plus one of A or B** covers both a generation failure and a retrieval failure.

---

**Working on the notebook:** only one person should edit `rag_system.ipynb` at a time. Pull before you start, push when you're done, and tell the team. Notebooks merge badly in git.
