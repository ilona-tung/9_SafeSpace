"""
How we picked MIN_FEELING_SCORE in safespace/core/rag.py.

"Ask SafeSpace" should only suggest a quest when the user wrote about how they
feel. We compare the input to FEELING_EXAMPLES with the RAG embedding model
(bge-small) and keep the best cosine similarity. This script scores two
labeled test sets (real feelings vs. off-topic text) and prints how many of
each a threshold keeps or blocks. Nothing is trained: the model is used as is.

Set 2 was written after the threshold was chosen on set 1, as a held-out check.

Run from the repo root:
    .venv/bin/python llm-test/relevance_check.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "safespace"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "safespace.settings.development")

import django  # noqa: E402

django.setup()

from core import ai, rag  # noqa: E402

TEST_SETS = {
    "set 1 (tuning)": {
        "feeling": [
            "sad", "tired", "stressed about exams next week", "I failed my midterm and feel awful",
            "kinda meh today", "nothing much, just a normal day", "I'm so happy I got the internship!",
            "can't focus on homework", "my roommate is annoying me", "I miss home",
            "too much coffee, I'm jittery", "I feel like nobody texts me back", "I'm worried about money",
            "headache all day", "I procrastinated again", "had a fight with my boyfriend",
            "I feel lazy and unproductive", "sooo tired after classes", "I'm excited but nervous for tomorrow",
            "life is a lot right now",
        ],
        "off_topic": [
            "what is the capital of France", "2+2", "write my essay about World War 2", "how do I install python",
            "banana", "tell me a joke", "the weather in Chicago", "who won the super bowl",
            "translate hello into Spanish", "best pizza near me", "hello", "test", "lorem ipsum dolor sit amet",
            "how many legs does a spider have", "recommend a laptop under 1000 dollars", "what time is it",
            "explain quantum physics", "my cat is orange", "SELECT * FROM users", "convert 5 miles to km",
        ],
    },
    "set 2 (held out)": {
        "feeling": [
            "ugh mondays", "I'm proud of myself today", "can't stop overthinking", "lonely weekend",
            "my back hurts from sitting", "I cried in the bathroom", "feeling grateful", "work is crushing me",
            "I skipped breakfast again", "I don't know what to do with my life", "my sister is sick and I'm scared",
            "I couldn't get out of bed", "everything is fine I guess", "I ate too much pizza", "exhausted",
            "I want to be more social", "I keep forgetting to drink water", "I feel ignored by my friends",
            "I spent all my paycheck", "I'm bored in my dorm",
        ],
        "off_topic": [
            "how to make pancakes", "what's the square root of 144", "summarize this article", "hi there",
            "is it going to rain tomorrow", "best movies of 2025", "asdf jkl", "ok", "list 5 countries in Asia",
            "write a python function to sort a list", "who is the president", "dogs or cats",
            "chemistry homework answers", "my phone is an iPhone 15", "what does HTML stand for", "good morning",
            "how far is the moon", "spell necessary", "the quick brown fox jumps over the lazy dog", "help",
        ],
    },
}


def blocked(text, threshold):
    """The full check in core/ai.py: junk rules first, then the similarity score."""
    return ai.is_junk(text) or rag.feeling_score(text) < threshold


for name, data in TEST_SETS.items():
    print(f"\n=== {name}")
    for label in ("feeling", "off_topic"):
        scores = sorted((rag.feeling_score(text), text) for text in data[label])
        print(f"  {label}: lowest {scores[0][0]:.2f} ({scores[0][1]!r}), highest {scores[-1][0]:.2f} ({scores[-1][1]!r})")

    print("  threshold   feelings kept   off-topic blocked   accuracy")
    for threshold in (0.56, 0.58, 0.60, 0.62, 0.64, 0.66, 0.68, 0.70):
        kept = sum(not blocked(text, threshold) for text in data["feeling"])
        stopped = sum(blocked(text, threshold) for text in data["off_topic"])
        total = len(data["feeling"]) + len(data["off_topic"])
        mark = "  <- used" if threshold == rag.MIN_FEELING_SCORE else ""
        print(f"  {threshold:.2f}        {kept:2d}/{len(data['feeling'])}           "
              f"{stopped:2d}/{len(data['off_topic'])}               {(kept + stopped) / total:.0%}{mark}")
