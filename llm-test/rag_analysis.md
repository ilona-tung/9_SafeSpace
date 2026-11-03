# Part 3: Failure Analysis & Improvement

---

## Step 3.1: Failure Cases

Failure Cases before and after are listed at the end of this document and the rag system notebook for clarity!

### Failure 1: Wrong Chunk Retrieved (Sleep Query)
* **Query:** `"I've been having trouble sleeping. What habits can help me sleep better?"`
* **Store Configuration:** Medium embedding model + overlapping chunks (`medium | overlapping`).
* **Observed Behavior:** The top-ranked chunk (#1 rank score: **0.657**) retrieved **"Caring for Your Mental Health > How can I take care of my mental health?"** instead of the dedicated sleep article (*Good Sleep for Good Health*).
* **Why it matters:** Only the first 3 sentences of this general self-care chunk pertain to sleep; the remainder focuses on goals, relaxation, gratitude, and social connection. Out of all 9 store configurations, this was the only one that failed to retrieve the sleep article at rank 1 for this query.

### Failure 2: Weak Chunk Retrieved Due to Query Wording (Relaxation Query)
* **Query:** `"I'm feeling overwhelmed. Are there any relaxation tips?"`
* **Store Configuration:** Large embedding model + hybrid chunks (`large | hybrid`).
* **Observed Behavior:** While the correct article was retrieved, chunk #2 (score: **0.627**) was **"Feeling Stressed? > What stress is"**, a purely descriptive section that defines stress and mentions feeling overwhelmed, but offers zero actionable relaxation tips.
* **Why it matters:** Embedding models measure semantic similarity rather than instructional value. The definition chunk scored highly purely due to keyword overlap with the word *"overwhelmed"*, crowding out actionable guides like *"Ways to de-stress"*.

### Failure 3: Incomplete Context via Fixed-Length Chunking
* **Query:** `"I'm feeling overwhelmed. Are there any relaxation tips?"`
* **Store Configuration:** Large embedding model + fixed-length chunks (`large | fixed_length`).
* **Observed Behavior:** Fixed-length chunking splits text arbitrarily at ~150 words without respecting sentence or section boundaries. Fixed-length chunk #2 from *Caring for Your Mental Health* starts mid-list and ends with a dangling introductory sentence:
  > *"Seek professional help if you are experiencing severe or distressing symptoms that have lasted 2 weeks or more."*
  
  The actual list of symptoms is pushed into chunk #3 (which begins with *"These symptoms include..."*), leaving *"These"* without its preceding context.
* **Why it matters:** This fragmentation caused fixed-length chunking to score lowest overall in top-3 retrieval accuracy (12/15 hits across medium and large models, compared to 14/15 for hybrid).

### Failure 4: Hallucinated Answer on Out-of-Scope Questions
* **Query:** `"What is a good recipe for pasta carbonara?"`
* **Store Configuration:** Large embedding model + hybrid chunks (`large | hybrid`) with `min_score=0.0`.
* **Observed Behavior:** Without a relevance filter, the vector store returned unrelated chunks about social connections and sleep (all scoring low, ≤ 0.39). The unconstrained 0.5B parameter generator model ignored system instructions to admit when context is lacking and generated a full, detailed cooking recipe from pretraining memory.
* **Why it matters:** Unchecked RAG pipelines expose users to ungrounded hallucinations when querying outside the domain scope.

### Failure 5: Hallucinated Details Inside On-Topic Answers
* **Query:** `"I want to build healthier daily habits. What are some self-care practices I can start with?"`
* **Store Configuration:** Large embedding model + hybrid chunks (`large | hybrid`).
* **Observed Behavior:** Even when retrieval successfully fetched correct NIH chunks, the Qwen-0.5B generator inserted plausible-sounding outside advice not present in the source text—such as adding *"gardening"* to self-care suggestions or *"stretching"* and *"Progressive Muscle Relaxation"* to stress-relief answers.
* **Why it matters:** It erodes user trust by mixing unverified external knowledge into answers attributed strictly to trustworthy health publications.

---

## Step 3.2: Root Cause Analysis

| Failure Case | Chunking Bottleneck? | Embedding Model Limit? | Query Formulation? | Generator / Prompt Limit? | Primary Root Cause |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Wrong chunk (Sleep)** | **Yes** | **Yes** | **Yes** | No | **Combined:** Overlapping window blended topics; ambiguous conversational phrasing tied scores closely (0.657 vs 0.652). |
| **2. Weak chunk (Relaxation)** | No | **Yes** | **Yes** | No | **Query & Embedding:** Vector search prioritized exact keyword/topical overlap ("overwhelmed") over instructional intent. |
| **3. Incomplete context** | **Yes** | No | No | No | **Chunking Strategy:** Rigid word count limits cut across sentences and lists without respecting semantic boundaries. |
| **4. Off-topic hallucination** | No | No | **Yes** | **Yes** | **Pipeline & Generator:** Blindly passing low-scoring chunks (≤ 0.4) to a small LLM without a relevance score guardrail. |
| **5. Hallucinated details** | No | No | No | **Yes** | **Generator Model:** Small 0.5B parameter model struggles to strictly enforce negative context-grounding constraints. |

---

## Step 3.3: System Improvements & Before/After Results

### Fix 1: Query Refinement (Resolves Failures 1 & 2)
We introduced a preprocessing step that maps conversational user queries into clean, topic-focused search queries before vector lookup, preserving the original prompt for final generation.

#### Before vs. After (Sleep Query):
* **Before Query:** `"I've been having trouble sleeping. What habits can help me sleep better?"`
* **Before Result (`medium | overlapping`):** Rank #1 was *Caring for Your Mental Health* (Score: **0.657**).
* **After Query:** `"What habits help with sleep problems and insomnia?"`
* **After Result (`medium | overlapping`):** Rank #1 correctly flipped to **Good Sleep > Getting better sleep** (Score: **0.686**).

#### Before vs. After (Relaxation Query):
* **Before Query:** `"I'm feeling overwhelmed. Are there any relaxation tips?"`
* **Before Result (`large | hybrid`):** Included the definition chunk *"What stress is"* at Rank #2 (Score: **0.627**).
* **After Query:** `"How can I relax and reduce stress?"`
* **After Result (`large | hybrid`):** Retrieved strictly actionable sections (*Ways to de-stress*: **0.725**, *Ways to manage stress*: **0.720**, *Just breathe*: **0.692**). The definition chunk was **completely eliminated from the top-3**.

### Fix 2: Relevance Threshold & Prompt Guardrails (Resolves Failure 4)
We enforced a similarity check (`min_score=0.5`) on retrieval scores before invoking the generator.

#### Before vs. After (Pasta Carbonara Query):
* **Before Output (`min_score=0.0`):** Model ignored low similarity scores (≤ 0.39) and hallucinated a complete carbonara recipe.
* **After Output (`min_score=0.5`):** Pipeline detects weak retrieval confidence, bypasses the generator entirely, and safely returns:
  > *"I'm sorry, I don't have information on that topic. I can help with stress, sleep, self-care, social connection, gratitude, and finding mental health support."*
