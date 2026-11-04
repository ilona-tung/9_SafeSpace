# SafeSpace RAG Analysis

## Step 1.1: Define the Knowledge Base

**Domain: self-help and mental wellness.** SafeSpace is a wellness app with private journals, community forums, friends, and self-care quests. Its users ask questions like "How can I sleep better?" or "I feel lonely, what can I do?". A RAG assistant for SafeSpace should answer from **trustworthy health sources** instead of from whatever the language model happens to remember, so the knowledge base is built from U.S. government health publications.

**Why these sources**
- **Trustworthy:** written by the National Institutes of Health (NIH) and reviewed by its scientists.
- **Free to reuse:** NIMH content is in the public domain. *NIH News in Health* states: "Our material is not copyrighted. Please acknowledge NIH News in Health as the source." Every document keeps its `Source:` line for credit.
- **Matches SafeSpace's features:** each topic maps to something users do in the app.

| # | Document | Publisher | Date | Words | SafeSpace connection |
|---|---|---|---|---|---|
| 1 | [Caring for Your Mental Health](https://www.nimh.nih.gov/health/topics/caring-for-your-mental-health) | NIMH | web page | 545 | self-care quests, when to get professional help |
| 2 | [Build Social Bonds to Protect Health](https://newsinhealth.nih.gov/2025/03/build-social-bonds-protect-health) | NIH News in Health | Mar 2025 | 1,158 | forums and friends |
| 3 | [Feeling Stressed? Ways to Improve Your Well-Being](https://newsinhealth.nih.gov/2021/01/feeling-stressed) | NIH News in Health | Jan 2021 | 1,088 | stress and relaxation quests |
| 4 | [Good Sleep for Good Health](https://newsinhealth.nih.gov/2021/04/good-sleep-good-health) | NIH News in Health | Apr 2021 | 1,089 | sleep habits |
| 5 | [Warning Signs of Suicide](https://www.nimh.nih.gov/health/publications/warning-signs-of-suicide) | NIMH (OM 25-4316) | rev. 2025 | 191 | safety: recognizing a crisis, 988 |
| 6 | [Practicing Gratitude](https://newsinhealth.nih.gov/2019/03/practicing-gratitude) | NIH News in Health | Mar 2019 | 601 | gratitude journaling |

**Total: 6 documents, 27 sections, 46 paragraphs, 4,672 words** (counted by the parser in Step 1.2).

**How the file was prepared**
- The article text was copied into one plain-text file, `knowledge_base.txt`. Images, captions, links and sidebars were left out.
- Bullet lists were rewritten as full sentences, so every paragraph reads as normal text and can be chunked by sentence.
- The text itself was not reworded. One factual update: the Stress article's old crisis line (1-800-273-TALK) was changed to the current **988** Suicide & Crisis Lifeline, which replaced it in 2022.

**Scope:** this assistant gives general wellness information. It is not a substitute for a therapist or doctor, and Step 1.5 keeps it from answering outside the knowledge base.

---

## Step 1.2: Text Representation & Chunking

**File format of `knowledge_base.txt`:**
- `# Document: <title>` starts a document; the next line is `Source: ...`.
- `## <heading>` starts a section, which is one topic.
- A **blank line ends a paragraph**.

### 1. Load and parse the knowledge base
**How we define a paragraph:** a block of consecutive non-empty lines between blank lines, inside a `##` section. Every paragraph keeps its document title and section heading as metadata. Later this lets each chunk point back to its source, and stops chunks from mixing topics.

| Document | Paragraphs | Words |
|---|---:|---:|
| Caring for Your Mental Health | 6 | 545 |
| Build Social Bonds to Protect Health | 11 | 1,158 |
| Feeling Stressed? Ways to Improve Your Well-Being | 11 | 1,088 |
| Good Sleep for Good Health | 11 | 1,089 |
| Warning Signs of Suicide | 2 | 191 |
| Practicing Gratitude | 5 | 601 |
| **Total** | **46** | **4,672** |

### 2. Sentence splitting
Fixed-length chunking must never cut a sentence in half, so we first split paragraphs into sentences. A sentence ends with `.`, `!` or `?` (possibly followed by a closing quote or bracket), then whitespace and a capital letter. The abbreviation **"Dr."** appears often in these articles, so it is protected and doesn't count as a sentence end.

**Example Output:**
- From an early age, we learn that nutritious foods and physical activity can help us stay healthy.
- Growing evidence now suggests that social connections may also be key to good health.
- Socially connected people tend to live longer.
- They're at lower risk for serious health problems.
- Social bonds are also linked to our mental health, eating habits, and much more.

### 3. Strategy 1: Fixed-length chunking

- **Target size:** about **150 words** per chunk.
- We add **whole sentences** until the next one would go past 150 words, then start a new chunk. Chunks are therefore *close to* 150 words but never cut a sentence.
- Chunks are built **inside one document** and never cross into another article, so a chunk never mixes unrelated topics (for example sleep and gratitude). Inside an article, a chunk may run across a paragraph break or a `##` heading. That is what makes it *fixed-length*: the size rule decides where a chunk ends, not the text's structure.

**Example Output:**
36 fixed-length chunks generated

### 4. Strategy 2: Overlapping paragraph chunking

**How overlap is implemented:** a sliding window of **2 paragraphs** that moves **1 paragraph** at a time (stride 1), so neighbouring chunks share a whole paragraph (50% overlap):

- Chunk 1 = P1 + P2
- Chunk 2 = P2 + P3
- Chunk 3 = P3 + P4

The window slides **inside one document** and restarts at the next document, so it never joins two unrelated articles. A document with only 2 paragraphs (Warning Signs of Suicide) becomes one chunk. If a fact sits near the end of P2, it is retrieved together with the context before it (chunk 1) *and* after it (chunk 2).

**Example Output:** 
40 overlapping chunks

### 5. Strategy 3: Hybrid / strategic (section-based) chunking

Our own strategy follows the **structure the authors gave the articles**:

1. **One `##` section = one chunk.** Each section is one topic (for example "Just breathe" or "Sleep myths and truths"), so every chunk is one complete thought.
2. **Size cap:** if a section is longer than **250 words**, split it **only at paragraph breaks**, packing paragraphs while they fit. This keeps chunks small enough for the embedding models (MiniLM and MPNet read about 256 to 384 tokens).
3. **Context prefix:** start each chunk with `Document title > Section heading`. Short chunks such as "Tips for a better night's sleep" then still say what they are about, which helps both embedding search and the final answer's citations.

**Example Output:**
32 hybrid chunks

### 6. Compare the three strategies
| Strategy | Chunks | Average Words | Minimum Words | Maximum Words | Total Words |
|---|---:|---:|---:|---:|---:|
| fixed_length | 36 | 130 | 42 | 149 | 4,672 |
| overlapping | 40 | 204 | 148 | 303 | 8,158 |
| hybrid | 32 | 156 | 82 | 256 | 4,987 |

`total_words` for the overlapping strategy is much larger than the corpus (4,672 words) because every inner paragraph is stored twice. That repetition is the overlap. The hybrid total is slightly larger because of the heading prefix (the 250-word cap applies to the body, not the prefix).

### 7. Example chunks
The following examples show representative chunks generated by each of the three chunking strategies.

**1. Fixed-length chunking**
- Document: Caring for Your Mental Health
- Section: How can I take care of my mental health?
- Chunk size: 142 words
> *A balanced diet and plenty of water can improve your energy and focus throughout the day. Pay attention to your intake of caffeine and alcohol and how they affect your mood and well-being...*

**2. Overlapping chunking**
- Document: Build Social Bonds to Protect Health
- Section: Social bonds
- Chunk size: 173 words
- Paragraphs: 8 and 9 
> *Recently, the COVID-19 pandemic affected our relationships and feelings of isolation. But the breakdown of social bonds was growing long before the pandemic...*

**3. Hybrid chunking**
- Document: Feeling Stressed? Ways to Improve Your Well-Being
- Section: Just breathe
- Chunk size: 206 words
> *The simple act of controlled breathing can bring stress relief. "It's well known that slow breathing techniques have a positive effect on emotional state," says Dr. Jack Feldman...*

### 8. Automatic rule checks

We check the assignment's three rules in code, not only by eye:

1. **No split sentences:** every chunk ends with sentence punctuation, and every sentence in the corpus appears whole inside at least one chunk.
2. **No merged topics:** every chunk comes from exactly one document, and every hybrid chunk from exactly one `##` section.
3. **Overlap works:** each pair of consecutive overlapping chunks in the same document shares exactly one paragraph.

| Validation Check | Fixed-length | Overlapping | Hybrid |
|---|---|---|---|
| Ends with punctuation | True | True | True |
| All sentences intact | True | True | True |
| One document per chunk | True | True | True |
| One section per chunk | N/A | N/A | True |

**Additional Overlapping Validation:**

- Number of neighbouring pairs checked: 34
- Each pair shares exactly one paragraph: True

### Summary

| Strategy | Unit | Size rule | Overlap | Topic boundary |
|---|---|---|---|---|
| Fixed-length | sentences | about 150 words, never splits a sentence | none | stays inside one document |
| Overlapping paragraphs | paragraphs | 2 paragraphs per chunk | 1 paragraph (stride 1, 50%) | window restarts at each document |
| Hybrid / strategic | sections | 1 section, split at paragraph breaks if over 250 words | none | one section per chunk, with heading prefix |

---

## Step 1.3: Embedding Pipeline

#### The three embedding models

| Size | Model | Dimensions | Parameters |
|---|---|---|---|
| Small | `BAAI/bge-small-en-v1.5` | 384 | 33M |
| Medium | `BAAI/bge-base-en-v1.5` | 768 | 110M |
| Large | `BAAI/bge-large-en-v1.5` | 1024 | 335M |

**Why one family:**
1. **Fair comparison.** All three share the same training recipe and data, so any difference in retrieval quality comes from model size rather than from different training.
2. **No truncation.** All three read up to **512 tokens**. Our longest chunks (about 300 words, roughly 400 tokens) fit completely. Popular alternatives such as `all-MiniLM-L6-v2` (256 tokens) and `all-mpnet-base-v2` (384 tokens) would silently cut the end off our longest chunks. We verify this in code below.

| Size | Model | Dimensions | Parameters (M) | Max Tokens |
|---|---|---:|---:|---:|
| small | BAAI/bge-small-en-v1.5 | 384 | 33 | 512 |
| medium | BAAI/bge-base-en-v1.5 | 768 | 109 | 512 |
| large | BAAI/bge-large-en-v1.5 | 1024 | 335 | 512 |

### Check: does every chunk fit in 512 tokens?

Models read **tokens** (word pieces), not words. We count the tokens in every chunk with the model's own tokenizer. All three BGE models share the same tokenizer, so one check covers all of them.
**Token Length Validation**

| Chunking Strategy | Longest Chunk (Tokens) | Token Limit | Truncated Chunks |
|---|---:|---:|---:|
| fixed_length | 206 | 512 | 0 |
| overlapping | 374 | 512 | 0 |
| hybrid | 327 | 512 | 0 |

### The searchable structure: `VectorStore`

For each **model × chunking strategy** pair we build one `VectorStore`:

- `chunks`: the list of chunk dicts (text plus document and section metadata).
- `embeddings`: a NumPy matrix of shape **(number of chunks, dimensions)**. Row *i* is the vector for chunk *i*.

Each vector is **normalized to length 1** (`normalize_embeddings=True`). Then the **cosine similarity** between a query and every chunk is a single matrix product, `embeddings @ query_vector`. The `search` method returns the top-k most similar chunks and is used in Step 1.4.

With about 30–40 chunks per strategy, an exact NumPy search takes well under a millisecond, so a library such as FAISS isn't needed. The structure would work the same way with FAISS for a much larger knowledge base.

BGE recommends adding a short instruction in front of **queries only** (not chunks) for retrieval, so `search` adds it automatically.

### Embed every chunk: 3 models × 3 strategies = 9 vector stores

| Model | Strategy | Matrix Shape | Time (seconds) |
|---|---|---:|---:|
| small | fixed_length | (36, 384) | 2.71 |
| small | overlapping | (40, 384) | 1.24 |
| small | hybrid | (32, 384) | 0.42 |
| medium | fixed_length | (36, 768) | 0.91 |
| medium | overlapping | (40, 768) | 1.13 |
| medium | hybrid | (32, 768) | 0.66 |
| large | fixed_length | (36, 1024) | 1.70 |
| large | overlapping | (40, 1024) | 3.65 |
| large | hybrid | (32, 1024) | 2.42 |

### What an embedding looks like

Each chunk becomes a vector of 384, 768 or 1024 numbers. Here are the first 8 numbers of the first hybrid chunk, under each model. Each vector has length 1 because of normalization.
**Embedding Normalization Check**

| Model | Dimensions | Vector Length |
|---|---:|---:|
| small | 384 | 1.000 |
| medium | 768 | 1.000 |
| large | 1024 | 1.000 |

---

## Step 1.4: Retrieval System

Retrieval runs in three steps:

1. **Query → embedding:** add BGE's search instruction in front of the query, encode it with the *same* model that embedded the chunks, and normalize it to length 1.
2. **Similarity search:** compute the cosine similarity between the query vector and every chunk vector. All vectors have length 1, so this is one matrix product: `embeddings @ query_vector`.
3. **Top-k retrieval:** sort the scores and keep the **k = 3** highest-scoring chunks.

First we walk through the steps one at a time for a single query.

**Example Retrieval Output:**

**Query Vector Shape:** (1024,)

**Retrieval Details:**
- Total chunks searched: 32
- Similarity score range: 0.444–0.694
- Top-3 chunk indices: [24, 25, 23]

**Top-3 Retrieved Chunks:**

| Rank | Similarity Score | Retrieved Document | Section |
|---|---:|---|---|
| 1 | 0.694 | Good Sleep for Good Health | Getting better sleep |
| 2 | 0.689 | Good Sleep for Good Health | Tips for a better night's sleep |
| 3 | 0.679 | Good Sleep for Good Health | Sleep disorders |

### Test questions

Each question has the document(s) that *should* be retrieved, so retrieval can be checked automatically.

### Compare all 9 vector stores (3 models × 3 chunking strategies)

For every store and question we record:
- **top-1 correct:** the highest-scoring chunk comes from an expected document;
- **hits in top 3:** how many of the 3 retrieved chunks come from an expected document;
- **top score:** the cosine similarity of the best chunk.

### Full Dataset Evaluation Results
#### Overall Retrieval Performance
| Model | Strategy | Top-1 Correct | Hits in Top 3 | Average Top Score |
|---|---|---:|---:|---:|
| small | fixed_length | 5/5 | 13/15 | 0.727 |
| small | overlapping | 5/5 | 14/15 | 0.759 |
| small | hybrid | 5/5 | 14/15 | 0.773 |
| medium | fixed_length | 5/5 | 12/15 | 0.670 |
| medium | overlapping | 4/5 | 13/15 | 0.677 |
| medium | hybrid | 5/5 | 14/15 | 0.714 |
| large | fixed_length | 5/5 | 12/15 | 0.681 |
| large | overlapping | 5/5 | 14/15 | 0.704 |
| large | hybrid | 5/5 | 14/15 | 0.708 |

#### Expected Document Retrieval Accuracy

| Test Question | Small - Fixed | Small - Overlap | Small - Hybrid | Medium - Fixed | Medium - Overlap | Medium - Hybrid | Large - Fixed | Large - Overlap | Large - Hybrid |
|---|---|---|---|---|---|---|---|---|---|
| Social | True | True | True | True | True | True | True | True | True |
| Relaxation | True | True | True | True | True | True | True | True | True |
| Sleep | True | True | True | True | False | True | True | True | True |
| Mental Health | True | True | True | True | True | True | True | True | True |
| Self-Care | True | True | True | True | True | True | True | True | True |

### Top-3 Retrieval Results (Large Model, Hybrid Chunking)

The following results show the top 3 retrieved chunks for each of the five test questions, ranked by cosine similarity score.

**1. Social Connections**

| Rank | Similarity Score | Retrieved Section |
|---|---:|---|
| 1 | 0.758 | New connections |
| 2 | 0.719 | Social bonds |
| 3 | 0.696 | Social bonds |

**2. Relaxation**

| Rank | Similarity Score | Retrieved Section |
|---|---:|---|
| 1 | 0.646 | Ways to manage stress |
| 2 | 0.627 | What stress is |
| 3 | 0.607 | Just breathe |

**3. Sleep**

| Rank | Similarity Score | Retrieved Section |
|---|---:|---|
| 1 | 0.694 | Getting better sleep |
| 2 | 0.689 | Tips for a better night's sleep |
| 3 | 0.679 | Sleep disorders |

**4. Mental Health**

| Rank | Similarity Score | Retrieved Section |
|---|---:|---|
| 1 | 0.752 | How can I find help? |
| 2 | 0.742 | When should I seek professional help? |
| 3 | 0.651 | Overview |

**5. Self-Care**

| Rank | Similarity Score | Retrieved Section |
|---|---:|---|
| 1 | 0.689 | How can I take care of my mental health? |
| 2 | 0.654 | How can I take care of my mental health? |
| 3 | 0.629 | Ways to connect with others |

---

## Step 1.5: Generation Pipeline

### Generator: our A6 model

We generate answers with **`Qwen/Qwen2.5-0.5B-Instruct`**, the model our team chose in A6 (`ai_prototype.ipynb`) and the one the SafeSpace Django app uses. The A7 model (`tiny_transformer.pt`) is a character-level Transformer with a 27-character vocabulary and a 32-character context window. It can't read a prompt containing several retrieved paragraphs, so it isn't usable for RAG generation.

### Prompt structure

The prompt has three parts, combined with Qwen's chat template:

1. **System instruction:** role, rules (answer only from the context, admit when the context doesn't cover something), and a safety note pointing to 988.
2. **Retrieved context:** the top-3 chunks, numbered and labelled with their source.
3. **User query**, followed by a one-line reminder of the main rule. Small models pay most attention to the end of the prompt, so the reminder is repeated there.

**Relevance threshold:** if even the best chunk scores below **0.5** cosine similarity, the knowledge base doesn't cover the question. We then skip generation and return a fixed reply. On-topic test questions score about 0.6–0.76, while unrelated questions score below 0.4.

**Retrieval store used for generation:** large model + hybrid chunks. In our comparison it is among the best stores, and its chunks carry section headings, which makes sources easy to cite. The `store` argument can be changed to any of the 9 stores.

### Generator Model Loading

We used `Qwen/Qwen2.5-0.5B-Instruct` as the generator model. The model and its tokenizer were loaded using Hugging Face Transformers.

The model was loaded in PyTorch float32 format and configured to run on the available MPS device (Apple Silicon). It was then switched to evaluation mode for inference.

**Example output:** `Loaded Qwen/Qwen2.5-0.5B-Instruct on mps`

### Prompt Construction

The retrieved chunks are combined with a system prompt and the user's question to create the input for the generator model.

The system prompt instructs the assistant to:
- Act as SafeSpace's supportive wellness assistant.
- Answer using only the retrieved context.
- Provide 3–6 sentences in a warm, encouraging tone.
- Avoid diagnosing users or acting as a therapist.
- Direct users mentioning self-harm or suicide to call or text 988.
- State when the retrieved context does not contain the answer.

**Example Prompt Input:**

- **System:** SafeSpace supportive wellness assistant instructions.
- **Context:** Top 3 retrieved chunks from *Good Sleep for Good Health*.
- **Question:** "I've been having trouble sleeping. What habits can help me sleep better?"
- **Instruction:** Answer using only the provided context in 3–6 sentences.

### Response Generation and RAG Pipeline

The `generate()` function uses the Qwen generator model to produce responses based on the constructed prompt.

The `rag_answer()` function combines retrieval and generation into one pipeline:

- Retrieves the top 3 most relevant chunks.
- Applies a minimum similarity threshold of 0.5.
- If no sufficiently relevant chunks are found, returns a predefined fallback response instead of allowing the model to guess.
- Otherwise, passes the retrieved context and user question to the generator model.
- Returns the generated answer together with its source documents and similarity scores.

The generator uses deterministic decoding (`do_sample=False`) with a maximum of 250 new tokens.

### RAG answers to the test questions

Decoding is greedy (`do_sample=False`), so the answers are reproducible.

The RAG system was tested using five questions covering social connections, relaxation, sleep, mental health, and self-care. For each question, the system generated an answer using the retrieved context and returned the corresponding source documents.

### 1. Social Connections

**Question:** I feel lonely and want to connect with more people. How can I make more meaningful social connections?

**Generated Answer:**

> To make more meaningful social connections, start by checking in with friends and family regularly. Joining clubs or groups that align with your interests can also help you meet new people...

**Retrieved Sources:**
- New connections (0.76)
- Social bonds (0.72)
- Social bonds (0.70)

### 2. Relaxation

**Question:** I'm feeling overwhelmed. Are there any relaxation tips?

**Generated Answer:**

> Relaxation tips include practicing controlled breathing, which involves focusing on taking slow, deep breaths in through the nose and out through the mouth. This technique helps calm the mind and reduce stress levels...

**Retrieved Sources:**
- Ways to manage stress (0.65)
- What stress is (0.63)
- Just breathe (0.61)

### 3. Sleep

**Question:** I've been having trouble sleeping. What habits can help me sleep better?

**Generated Answer:**

> *Try sticking to a consistent sleep schedule by going to bed and waking up at the same time each day, even on the weekends...*

**Sources:**
- Getting better sleep (0.694)
- Tips for a better night's sleep (0.689)
- Sleep disorders (0.679)

### 4. Mental Health

**Question:** I've been struggling with my mental health. Should I be seeking professional help, and where do I find it if so?

**Generated Answer:**

> *Yes, you should consider seeking professional help if you're experiencing severe or distressing symptoms that have lasted 2 weeks or more... Seeking professional help can involve talking to a primary care provider or a qualified mental health professional...*

**Sources:**
- How can I find help? (0.752)
- When should I seek professional help? (0.742)
- Overview (0.651)

### 5. Self-Care

**Question:** I want to build healthier daily habits. What are some self-care practices I can start with?

**Generated Answer:**

> *Start small by incorporating just 30 minutes of walking each day into your routine. Choose an activity you enjoy, like knitting or gardening, and stick to it regularly...*

**Sources:**
- How can I take care of my mental health? (0.689)
- How can I take care of my mental health? (0.654)
- Ways to connect with others (0.629)

### Out-of-scope question

The knowledge base has nothing about cooking. A grounded assistant should say so instead of inventing an answer. We show the model's output **without** the relevance threshold too: the 0.5B model ignores the system instruction and writes a recipe anyway. That is why the threshold is needed.

**Retrieved Results (Best Matches):**

Although the system retrieved three chunks, all similarity scores were low:

- Ways to connect with others (0.39)
- Tips for a better night's sleep (0.37)
- Who's at risk? (0.37)

**With Similarity Threshold (0.5):**

> *I'm sorry, I don't have information on that topic. I can help with stress, sleep, self-care, social connection, gratitude, and finding mental health support.*

**Without Similarity Threshold:**

> *A great recipe for pasta carbonara is to use fresh eggs, garlic, pancetta, and parmesan cheese... Serve hot with a side of crusty bread.*

### RAG vs. no RAG

The same model and question, with and without retrieved context. Without context the model answers from its general training data, with no sources to check it against.

**Question:** I've been having trouble sleeping. What habits can help me sleep better?

**Without RAG:**

> *Establish a routine by going to bed and waking up at the same time every day. Create a relaxing sleep environment, limit screen exposure before bedtime, exercise regularly, avoid stimulants, and try relaxation techniques...*

**With RAG:**

> *Try sticking to a consistent sleep schedule by going to bed and waking up at the same time each day... Avoid stimulating substances like nicotine and caffeine... Limit screen time before bedtime... Consider seeking professional help if sleep difficulties persist or worsen over time.*

**Retrieved Sources:**
- Getting better sleep (0.69)
- Tips for a better night's sleep (0.69)
- Sleep disorders (0.68)

---

## Results and observations (Part 1)

**Retrieval (Step 1.4)**
- 8 of the 9 stores retrieve a correct document at rank 1 for all 5 test questions (medium + overlapping gets 4 of 5), so the knowledge base and embeddings work.
- **Hybrid chunks** are tied for the most hits in the top 3 (14 of 15) for every model, and get the highest average similarity score for every model. Their heading prefix ("Good Sleep for Good Health > Tips for a better night's sleep") adds topic words that match the question.
- **Fixed-length chunks** score lowest. A chunk can start mid-topic or run across a heading, which blurs its meaning.
- **Bigger isn't automatically better here.** The small model already finds the right document; scores between models aren't directly comparable (each model has its own score scale). With a small, clearly separated knowledge base, all three sizes are good enough; larger models matter more when documents overlap in topic.

**Generation (Step 1.5)**
- With RAG, answers follow the retrieved sources: the sleep answer reuses the NIH tips (consistent sleep schedule, 30 minutes outdoors, avoiding nicotine and caffeine, limiting screens, a cool and quiet room), and the mental-health answer gives the NIMH 2-week symptom rule, then the primary care provider, NIMH and SAMHSA. Compared with the no-RAG answer, the RAG answer is shorter and every tip can be traced to a source.
- Limits of a 0.5B model: it sometimes adds general advice that isn't in the context (for example "gardening" in the self-care answer and "stretching" in the relaxation answer), and it ignored "say you don't know" for an off-topic question. Repeating the rule after the question made answers shorter and more grounded than our first version. The relevance threshold fixes the off-topic case at the retrieval step, before the model can make something up.

---

---

## Part 2: RAG System Evaluation
### Step 2.1: Define Test Queries
To evaluate our RAG system, we created five test questions based on common situations that SafeSpace users might experience. Since SafeSpace focuses on mental wellness, social connections, relaxation, sleep, and self-care, our questions cover these topics.

We selected the following 5 questions:

| Topic | Test Question |
|---|---|
| Social | I feel lonely and want to connect with more people. How can I make more meaningful social connections? |
| Relaxation | I'm feeling overwhelmed. Are there any relaxation tips? |
| Sleep | I've been having trouble sleeping. What habits can help me sleep better? |
| Mental Health | I've been struggling with my mental health. Should I be seeking professional help, and where do I find it if so? |
| Self-Care | I want to build healthier daily habits. What are some self-care practices I can start with? |

Each question was assigned an expected document/set of documents from our knowledge base. This allows us to check whether the retrieval system returned information from the appropriate sources.
These 5 questions were used consistently across all embedding models and chunking strategies to make the comparisons fair.

---

### Step 2.2: Evaluate Retrieval and Answer Quality
We evaluated 9 different RAG configurations by combining 3 embedding models with 3 chunking strategies.

The embedding models were:
- Small: BAAI/bge-small-en-v1.5
- Medium: BAAI/bge-base-en-v1.5
- Large: BAAI/bge-large-en-v1.5

The chunking strategies were:
- Fixed-length chunking
- Overlapping paragraph chunking
- Hybrid (strategic) chunking

This produced 9 configurations. Each configuration was then tested against the same 5 questions, resulting in 45 retrieval tests.

#### Evaluation Metrics
We used the following metrics to evaluate retrieval performance:
- Top-1 Correct: Whether the highest-ranked retrieved chunk came from an expected document.
- Hits in Top 3: The number of retrieved chunks among the top 3 that came from an expected document.
- Average Top Similarity Score: The average cosine similarity score of the highest-ranked chunk across the five questions.
- Average Retrieval Time (measured in milliseconds): The average time required to encode a query and retrieve the top three chunks.

We also considered the relevance of the retrieved information as well as whether it could support a useful answer to the user's question.

#### Retrieval Test Implementation
A total of 45 retrieval tests were performed across 3 embedding models, 3 chunking strategies, and 5 test questions. The following table shows an example of the recorded results.

**Example Output (`tests_full`):**

| model | strategy | topic | top1_doc | top1_section | top1_correct | hits_in_top3 | top_score | response_ms |
|---|---|---|---|---|---|---:|---:|---:|
| large | hybrid | Sleep | Good Sleep for Good Health | Getting better sleep | True | 3 | 0.694 | Example |

The full output contains 45 rows, covering all model, chunking strategy, and question combinations. It records retrieval accuracy, similarity scores, and response times for comparison.

#### Summary of Retrieval Results

The 45 retrieval tests were grouped by embedding model and chunking strategy to compare overall retrieval accuracy, similarity scores, and average response times.

| model | strategy | top1_correct | hits_in_top3 | avg_top_score | avg_ms |
|---|---|---:|---:|---:|---:|
| small | fixed_length | 5 | 13 | 0.728 | 12.58 |
| small | overlapping | 5 | 14 | 0.759 | 9.76 |
| small | hybrid | 5 | 14 | 0.773 | 9.26 |
| medium | fixed_length | 5 | 12 | 0.669 | 17.90 |
| medium | overlapping | 4 | 13 | 0.677 | 16.70 |
| medium | hybrid | 5 | 14 | 0.714 | 16.78 |
| large | fixed_length | 5 | 12 | 0.681 | 24.12 |
| large | overlapping | 5 | 14 | 0.704 | 20.36 |
| large | hybrid | 5 | 14 | 0.708 | 21.02 |

#### Retrieved Chunks & Individual Test Results
The results showed that 8/9 configurations successfully retrieved the expected document  as the highest-ranked result for all 5 test questions. The only exception was the medium embedding model with overlapping chunking, which achieved 4 correct top-1 results out of 5.

The results also showed that hybrid chunking consistently retrieved 14 relevant chunks out of 15 retrieved chunks for each of the top three embedding models. This suggests that the hybrid strategy was effective at preserving useful topic information during retrieval. Including section headings in the chunk may have helped the embedding models identify passages relevant to each question.

---

### Step 2.3: Compare Embedding Models
Our experiment compared 3 embedding models with different sizes and embedding dimensions. The small model uses 384 dimensions, the medium model uses 768 dimensions, and the large model uses 1024 dimensions.

The results showed that the small embedding model performed particularly well. It achieved 5/5 correct top-1 document matches across all 3 chunking strategies. Its hybrid configuration also achieved 14/15 relevant chunks in the top three, with an average top similarity score of 0.773.

The medium and large models produced similar retrieval results, but neither consistently outperformed the small model. The large model achieved 5/5 correct top-1 matches with all 3 chunking strategies, but its top-three results ranged from 12-14 relevant chunks. It also had noticeably longer retrieval times.

For example, with hybrid chunking, the small model averaged 14.42 milliseconds per retrieval, compared with 16.00 milliseconds for the medium model and 57.82 milliseconds for the large model.

These findings suggest that increasing embedding dimensions did not automatically improve retrieval quality. For our relatively small knowledge base, the small embedding model had a strong balance between retrieval accuracy and speed.

Another consideration is that similarity scores are not necessarily directly comparable across different embedding models, as each model can produce its own score distribution. Therefore, we considered top-1 correctness and top-three retrieval results alongside average similarity scores when comparing performance.

Overall, the small embedding model was a strong option for our application. It provided reliable retrieval and consistently had shorter retrieval times than the larger models in our experiments.

---

### Step 2.4: Compare Chunking Strategies

We also compared 3 chunking strategies: fixed-length, overlapping, and hybrid. Each strategy was evaluated with all 3 embedding models using the same 5 questions.

The combined results showed that fixed-length chunking achieved 15/15 correct top-1 document matches and 37 relevant chunks in the top three. Overlapping chunking achieved 14/15 correct top-1 matches and 41 relevant chunks in the top three. Hybrid chunking achieved 15/15 correct top-1 matches and 42 relevant chunks in the top three.

Based on these results, hybrid chunking performed best overall. It retrieved the highest number of relevant chunks in the top 3 while maintaining perfect top-1 accuracy across the 3 models.

Overlapping chunking also performed well. It found more relevant chunks than fixed-length chunking. This may be because overlapping chunking shares some paragraphs between chunks, so it helps preserve context that could be lost at chunk boundaries.

Fixed-length chunking had the fewest relevant top-three results. This may be because dividing information by word count can sometimes separate related information or ideas into different chunks, which makes the information in each chunk less focused.

Hybrid chunking organizes information using document sections and their headings. Including the section headings in each chunk gives the embedding model additional information about what the text is discussing. This can help it find information that better matches the user's question.

For example, if a user asks a question about getting better sleep, the heading "Good Sleep for Good Health: Tips for a better night's sleep" helps show that the chunk contains information about sleep.

Overall, hybrid chunking was the strongest strategy in our experiment. However, the results showed that the differences between the strategies were relatively small. Testing with a larger set of questions would help us determine whether hybrid chunking consistently performs best.

---

### Step 2.5: Data Scaling Experiment
To see how the size of the knowledge base affects retrieval results, we compared the full dataset with a smaller dataset.

The full knowledge base contains 6 documents, 27 sections, 46 paragraphs, and about 4,672 words. For the smaller dataset, we kept only the first half of the paragraphs from each document. This made the dataset smaller while still keeping information from all 6 documents. Next, we created new vector stores using the smaller dataset. We tested all 3 embedding models and all 3 chunking strategies using the same 5 questions.

This gave us another 45 retrieval tests. We could then compare the results from the smaller dataset with the results from the full dataset.

#### Dataset Scaling Implementation
We compared the results using 4 measurements: correct top-1 matches, relevant results in the top 3, average similarity scores, and retrieval times.

The goal of this experiment was to see if using less information would affect how well the system finds relevant content. A smaller dataset might make it easier for the model to find useful information because there are fewer passages to search through. However, it could also remove information that the model needs to answer certain questions.

The full dataset contains more information and covers more of the topics in our test questions. However, having more information does not always mean better results. With more passages available, the model may have a harder time choosing the most relevant ones.

#### Dataset Scaling Results

| Dataset | model | strategy | top1_corre... | hits_in_to... | avg_top_sc... | avg_ms |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: |
| **full** | small | fixed_length | 5 | 13 | 0.728 | 12.58 |
| | | overlapping | 5 | 14 | 0.759 | 9.76 |
| | | hybrid | 5 | 14 | 0.773 | 9.26 |
| | medium | fixed_length | 5 | 12 | 0.669 | 17.90 |
| | | overlapping | 4 | 13 | 0.677 | 16.70 |
| | | hybrid | 5 | 14 | 0.714 | 16.78 |
| | large | fixed_length | 5 | 12 | 0.681 | 24.12 |
| | | overlapping | 5 | 14 | 0.704 | 20.36 |
| | | hybrid | 5 | 14 | 0.708 | 21.02 |
| **small** | small | fixed_length | 4 | 10 | 0.685 | 11.96 |
| | | overlapping | 5 | 11 | 0.693 | 8.96 |
| | | hybrid | 5 | 11 | 0.690 | 8.96 |
| | medium | fixed_length | 5 | 10 | 0.649 | 10.56 |
| | | overlapping | 5 | 12 | 0.658 | 9.60 |
| | | hybrid | 5 | 12 | 0.662 | 9.34 |
| | large | fixed_length | 4 | 12 | 0.661 | 20.62 |
| | | overlapping | 5 | 12 | 0.660 | 18.44 |
| | | hybrid | 5 | 13 | 0.659 | 18.82 |

The results showed that the full dataset performed slightly better overall than the smaller dataset. Across all 9 configurations, the full dataset had 44/45 correct top-1 results, while the smaller dataset had 43/45. The full dataset also retrieved 120 relevant chunks in the top three, compared with 103 for the smaller dataset.

However, the smaller dataset still performed well in some cases. For example, the medium model with overlapping chunking improved from 4/5 to 5/5 correct top-1 results when using the smaller dataset. Even so, the smaller dataset found fewer relevant chunks overall. This suggests that keeping more information in the knowledge base can help the system find useful results.

We also compared how long each dataset took to retrieve results. The smaller dataset was not always faster. For example, the large model with hybrid chunking took 115.08 ms with the smaller dataset, compared with 57.82 ms with the full dataset. This shows that using fewer paragraphs does not always make retrieval faster.

Overall, the full dataset provided slightly better results than the smaller dataset. This suggests that removing information from the knowledge base does not necessarily improve performance and may cause the system to miss useful information. However, since we only tested 5 questions, more testing would be needed to see if these results stay the same with a larger number of questions.

---

### Part 2: Overall Conclusion
Our evaluation compared 3 embedding models and 3 chunking strategies using 5 test questions. This resulted in 45 retrieval tests with the full knowledge base.

The results showed that the small embedding model performed well while also having faster retrieval times. The larger models did not consistently provide better results, even though they generally took longer to process queries.

Out of the 3 chunking strategies, hybrid chunking performed the best overall. It found the highest number of relevant chunks in the top 3 results while maintaining perfect top-1 accuracy across all 3 embedding models.

These results show that using a larger model does not always mean better performance, especially when working with a smaller and well-organized knowledge base. The way information is divided into chunks and organized with headings can also affect how well the system can find relevant information.

The dataset scaling experiment also showed that the size of the knowledge base can affect retrieval results. Overall, these experiments helped us understand how to choose a setup that balances retrieval quality and speed for the SafeSpace application.

---

---

## Part 3: Failure Analysis & Improvement

### Step 3.1: Failure Cases

Failure Cases before and after are listed at the end of this document and the rag system notebook for clarity!

#### Failure 1: Wrong Chunk Retrieved (Sleep Query)
* **Query:** `"I've been having trouble sleeping. What habits can help me sleep better?"`
* **Store Configuration:** Medium embedding model + overlapping chunks (`medium | overlapping`).
* **Observed Behavior:** The top-ranked chunk (#1 rank score: **0.657**) retrieved **"Caring for Your Mental Health > How can I take care of my mental health?"** instead of the dedicated sleep article (*Good Sleep for Good Health*).
* **Why it matters:** Only the first 3 sentences of this general self-care chunk pertain to sleep; the remainder focuses on goals, relaxation, gratitude, and social connection. Out of all 9 store configurations, this was the only one that failed to retrieve the sleep article at rank 1 for this query.

#### Failure 2: Weak Chunk Retrieved Due to Query Wording (Relaxation Query)
* **Query:** `"I'm feeling overwhelmed. Are there any relaxation tips?"`
* **Store Configuration:** Large embedding model + hybrid chunks (`large | hybrid`).
* **Observed Behavior:** While the correct article was retrieved, chunk #2 (score: **0.627**) was **"Feeling Stressed? > What stress is"**, a purely descriptive section that defines stress and mentions feeling overwhelmed, but offers zero actionable relaxation tips.
* **Why it matters:** Embedding models measure semantic similarity rather than instructional value. The definition chunk scored highly purely due to keyword overlap with the word *"overwhelmed"*, crowding out actionable guides like *"Ways to de-stress"*.

#### Failure 3: Incomplete Context via Fixed-Length Chunking
* **Query:** `"I'm feeling overwhelmed. Are there any relaxation tips?"`
* **Store Configuration:** Large embedding model + fixed-length chunks (`large | fixed_length`).
* **Observed Behavior:** Fixed-length chunking splits text arbitrarily at ~150 words without respecting sentence or section boundaries. Fixed-length chunk #2 from *Caring for Your Mental Health* starts mid-list and ends with a dangling introductory sentence:
  > *"Seek professional help if you are experiencing severe or distressing symptoms that have lasted 2 weeks or more."*
  
  The actual list of symptoms is pushed into chunk #3 (which begins with *"These symptoms include..."*), leaving *"These"* without its preceding context.
* **Why it matters:** This fragmentation caused fixed-length chunking to score lowest overall in top-3 retrieval accuracy (12/15 hits across medium and large models, compared to 14/15 for hybrid).

#### Failure 4: Hallucinated Answer on Out-of-Scope Questions
* **Query:** `"What is a good recipe for pasta carbonara?"`
* **Store Configuration:** Large embedding model + hybrid chunks (`large | hybrid`) with `min_score=0.0`.
* **Observed Behavior:** Without a relevance filter, the vector store returned unrelated chunks about social connections and sleep (all scoring low, ≤ 0.39). The unconstrained 0.5B parameter generator model ignored system instructions to admit when context is lacking and generated a full, detailed cooking recipe from pretraining memory.
* **Why it matters:** Unchecked RAG pipelines expose users to ungrounded hallucinations when querying outside the domain scope.

#### Failure 5: Hallucinated Details Inside On-Topic Answers
* **Query:** `"I want to build healthier daily habits. What are some self-care practices I can start with?"`
* **Store Configuration:** Large embedding model + hybrid chunks (`large | hybrid`).
* **Observed Behavior:** Even when retrieval successfully fetched correct NIH chunks, the Qwen-0.5B generator inserted plausible-sounding outside advice not present in the source text—such as adding *"gardening"* to self-care suggestions or *"stretching"* and *"Progressive Muscle Relaxation"* to stress-relief answers.
* **Why it matters:** It erodes user trust by mixing unverified external knowledge into answers attributed strictly to trustworthy health publications.

---

### Step 3.2: Root Cause Analysis

| Failure Case | Chunking Bottleneck? | Embedding Model Limit? | Query Formulation? | Generator / Prompt Limit? | Primary Root Cause |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **1. Wrong chunk (Sleep)** | **Yes** | **Yes** | **Yes** | No | **Combined:** Overlapping window blended topics; ambiguous conversational phrasing tied scores closely (0.657 vs 0.652). |
| **2. Weak chunk (Relaxation)** | No | **Yes** | **Yes** | No | **Query & Embedding:** Vector search prioritized exact keyword/topical overlap ("overwhelmed") over instructional intent. |
| **3. Incomplete context** | **Yes** | No | No | No | **Chunking Strategy:** Rigid word count limits cut across sentences and lists without respecting semantic boundaries. |
| **4. Off-topic hallucination** | No | No | **Yes** | **Yes** | **Pipeline & Generator:** Blindly passing low-scoring chunks (≤ 0.4) to a small LLM without a relevance score guardrail. |
| **5. Hallucinated details** | No | No | No | **Yes** | **Generator Model:** Small 0.5B parameter model struggles to strictly enforce negative context-grounding constraints. |

---

### Step 3.3: System Improvements & Before/After Results

#### Fix 1: Query Refinement (Resolves Failures 1 & 2)
We introduced a preprocessing step that maps conversational user queries into clean, topic-focused search queries before vector lookup, preserving the original prompt for final generation.

##### Before vs. After (Sleep Query):
* **Before Query:** `"I've been having trouble sleeping. What habits can help me sleep better?"`
* **Before Result (`medium | overlapping`):** Rank #1 was *Caring for Your Mental Health* (Score: **0.657**).
* **After Query:** `"What habits help with sleep problems and insomnia?"`
* **After Result (`medium | overlapping`):** Rank #1 correctly flipped to **Good Sleep > Getting better sleep** (Score: **0.686**).

##### Before vs. After (Relaxation Query):
* **Before Query:** `"I'm feeling overwhelmed. Are there any relaxation tips?"`
* **Before Result (`large | hybrid`):** Included the definition chunk *"What stress is"* at Rank #2 (Score: **0.627**).
* **After Query:** `"How can I relax and reduce stress?"`
* **After Result (`large | hybrid`):** Retrieved strictly actionable sections (*Ways to de-stress*: **0.725**, *Ways to manage stress*: **0.720**, *Just breathe*: **0.692**). The definition chunk was **completely eliminated from the top-3**.

#### Fix 2: Relevance Threshold & Prompt Guardrails (Resolves Failure 4)
We enforced a similarity check (`min_score=0.5`) on retrieval scores before invoking the generator.

##### Before vs. After (Pasta Carbonara Query):
* **Before Output (`min_score=0.0`):** Model ignored low similarity scores (≤ 0.39) and hallucinated a complete carbonara recipe.
* **After Output (`min_score=0.5`):** Pipeline detects weak retrieval confidence, bypasses the generator entirely, and safely returns:
  > *"I'm sorry, I don't have information on that topic. I can help with stress, sleep, self-care, social connection, gratitude, and finding mental health support."*

---

## Part 4: System Design Reflection

### 4.1: Cost awareness
In terms of total cost, top-k retrieval and chunk size tend to contribute the most cost. Since the total amount of tokens used is O(kn) where n = chunk size, this creates a high inference cost the more users send prompts to the LLM. Different chunking strategies and top-k retrievals generally had the largest impact on response time, with embedding size having a small overall impact.

### 4.2: RAG and alternatives
Pure prompts: Best for when the model already has the information from training and doesn't need additional modifications. Alternatively, it can work when necessary context is small enough to be included or attached to the prompt, like when uploading an image to a chatGPT message.
RAG: Worked best for cases where the LLM needed to reference a larger set of outside documents. For example, RAG can work for LLMs that can google results or have access to a large datapase. The experiments here showed that RAG allowed the models to get information from the information we provided instead of replying with the generic information the other methods gave us. 
Fine-tuning: Fine tuning seems to work for modifying the LLMs behavior and outputs, but not the information it has. Essentially, it works for modifying the format of an LLMs output for tone or readability, but won't provide the outside context RAG does.

### 4.3: System design
To scale for 10k users, RAG and Fine-tuning would be the best combination on our end, while the user would be responsible for pure prompting, since trying to attach more text to their prompts cannot cover every possible situation. For small requests like a basic description or welcome message, we can use a small local model directly in the app, offloading some of the demand from the cloud system. For larger tasks, like a tech support chatbot, we can test top-k option and various chunk sizes to find the smallest options while maintaining quality. 

```mermaid
graph TD;
    User[Start] --> Query(User asks a question);
    Query --> Embedding(Convert text to vectors);
    Embedding --> Vector Store(Top-k search);
    Vector Store --> Retrieved Content(Top-k chunks);
    Retrieved Content --> LLM(Query + context);
    LLM --> Response(Answer)[end];
```
