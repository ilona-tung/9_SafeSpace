"""
Local LLM quest suggestions.

A user writes how they feel. The local Hugging Face model
(Qwen/Qwen2.5-0.5B-Instruct, chosen in llm-test/ai_prototype.ipynb)
picks ONE quest from our database and writes a short, kind message.

Pipeline:
    1. Preprocess: clean the text, check for crisis words and prompt injection.
    2. Build a few-shot prompt: persona + our quest list + either the journal
       entry the user chose, or excerpts of their 3 most recent entries.
    3. Generate with the local model (loaded once, on the first request).
    4. Check the output: valid JSON, a quest that really exists, a safe message.
       Anything else falls back to a pre-made suggestion.
"""

import difflib
import json
import logging
import re
from functools import lru_cache

from django.conf import settings

from .models import Journal, Quest

logger = logging.getLogger(__name__)


MAX_INPUT_CHARS = 300
JOURNAL_COUNT = 3
JOURNAL_EXCERPT_CHARS = 200
CHOSEN_JOURNAL_CHARS = 400
MAX_MESSAGE_CHARS = 250

FALLBACK_MESSAGE = "Try taking 3 deep breaths. Small steps still count."
FALLBACK_QUEST_TITLE = "Take 3 deep breaths"

CRISIS_MESSAGE = (
    "It sounds like you are going through something really heavy. "
    "You deserve support from a real person right now. "
    "In the US, you can call or text 988 (Suicide & Crisis Lifeline) any time, "
    "or reach out to someone you trust."
)

INJECTION_MESSAGE = (
    "I can only help with self-care quests. "
    "Tell me how you are feeling, and I will suggest one."
)

UNAVAILABLE_MESSAGE = (
    "AI quest suggestions are only available when SafeSpace runs locally "
    "with the AI packages installed."
)

# Never sent to the model: the user is shown CRISIS_MESSAGE instead
CRISIS_PATTERNS = [
    r"\bsuicid",
    r"\bkill (myself|me)\b",
    r"\bend (my|it all)\b",
    r"\bself[- ]?harm",
    r"\bhurt (myself|me)\b",
    r"\bwant to die\b",
    r"\bdon'?t want to (live|be here)\b",
]

# Attempts to make the model ignore its instructions
INJECTION_PATTERNS = [
    r"\bignore (all |the |your |previous |prior |above )+(instructions|rules|prompts?)",
    r"\b(system|developer) prompt\b",
    r"\byou are now\b",
    r"\bact as\b",
    r"\bpretend (to be|you are)\b",
    r"\bjailbreak\b",
    r"\bnew instructions\b",
    r"<\|.*?\|>",
]

# A self-care app should never show these in a suggestion
BLOCKED_OUTPUT_WORDS = [
    "stupid", "idiot", "worthless", "hate", "kill", "die", "suicide",
    "drunk", "alcohol", "drugs", "weapon", "lazy", "fat", "ugly",
]

# Feelings used for the few-shot examples, keyed by quest category
EXAMPLE_FEELINGS = {
    "diet": "I sat at my desk and ate junk food all day.",
    "general": "My mind is racing and I can't relax.",
    "social": "I miss my old friends.",
    "learning": "I feel stuck and want to grow.",
    "exploration": "I have been stuck inside all week.",
    "budgeting": "I spent too much money this week.",
}

EXAMPLE_MESSAGES = {
    "diet": "Your body will thank you for this small step.",
    "general": "Let yourself slow down for a moment.",
    "social": "A short message can mean a lot.",
    "learning": "A few pages can open a new door.",
    "exploration": "A little fresh air can change your whole day.",
    "budgeting": "Looking at your spending is a kind thing to do for future you.",
}


class AIUnavailable(Exception):
    """The AI packages (torch / transformers) are not installed."""


# ============================================================
# 1. Preprocessing
# ============================================================

def clean_text(text, limit):
    """
    Remove control characters and extra whitespace, then cut to `limit` characters.
    """

    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()

    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "..."

    return text


def matches_any(text, patterns):
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def is_crisis(text):
    return matches_any(text, CRISIS_PATTERNS)


def is_injection(text):
    return matches_any(text, INJECTION_PATTERNS)


def recent_journal_excerpts(user):
    """
    Short excerpts of the user's own 3 most recent journal entries.
    Entries that look like prompt injection are skipped.
    """

    excerpts = []

    for journal in Journal.objects.filter(user=user).order_by("-time")[:JOURNAL_COUNT]:
        text = clean_text(journal.content, JOURNAL_EXCERPT_CHARS)

        if text and not is_injection(text):
            excerpts.append(f"{journal.time:%b %d}: \"{text}\"")

    return excerpts


def chosen_journal_text(journal):
    """
    The overall message and an excerpt of the journal entry the user chose.
    """

    lines = []

    if journal.summary:
        lines.append(f"Overall message: {clean_text(journal.summary, 150)}")

    lines.append(f"Entry: \"{clean_text(journal.content, CHOSEN_JOURNAL_CHARS)}\"")

    return "\n".join(lines)


# ============================================================
# 2. Prompt
# ============================================================

def system_prompt(quests):
    quest_list = [
        {"quest": quest.title, "category": quest.display_category()}
        for quest in quests
    ]

    return (
        "You are SafeSpace, a brief, gentle and non-judgemental self-care assistant. "
        "Read how the user feels and choose ONE quest from this list:\n"
        f"{json.dumps(quest_list)}\n"
        "Base your choice on how the user feels now and on the journal entry they chose. "
        "Recent journal notes are background only. "
        "Answer ONLY with a JSON object with exactly these keys: "
        "\"quest\" (the exact quest title from the list) and "
        "\"message\" (one short, kind sentence). No other text."
    )


def few_shot_examples(quests):
    """
    Up to 3 worked examples that use real quests from the database,
    one per category, so the model copies the exact JSON format.
    """

    examples = []
    used_categories = set()

    for quest in quests:
        if quest.category in EXAMPLE_FEELINGS and quest.category not in used_categories:
            used_categories.add(quest.category)
            answer = {"quest": quest.title, "message": EXAMPLE_MESSAGES[quest.category]}
            examples.append((EXAMPLE_FEELINGS[quest.category], json.dumps(answer)))

        if len(examples) == 3:
            break

    return examples


def build_messages(feeling, journal_excerpts, quests, chosen_journal=None):
    """
    Chat messages for the model. When the user chose a journal entry,
    that entry is the focus; otherwise recent excerpts are background.
    """

    messages = [{"role": "system", "content": system_prompt(quests)}]

    for example_feeling, example_answer in few_shot_examples(quests):
        messages.append({"role": "user", "content": example_feeling})
        messages.append({"role": "assistant", "content": example_answer})

    parts = []

    if feeling:
        parts.append(f"How I feel now: {feeling}")

    if chosen_journal is not None:
        parts.append(
            "Suggest a quest based on this journal entry I wrote:\n"
            f"{chosen_journal_text(chosen_journal)}"
        )
    elif journal_excerpts:
        notes = "\n".join(f"- {excerpt}" for excerpt in journal_excerpts)
        parts.append(f"My recent journal notes (background only):\n{notes}")

    messages.append({"role": "user", "content": "\n\n".join(parts)})

    return messages


# ============================================================
# 3. Local model
# ============================================================

@lru_cache(maxsize=1)
def load_model():
    """
    Load the tokenizer and model once and keep them in memory.
    transformers downloads the weights automatically the first time.
    """

    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise AIUnavailable from exc

    if torch.cuda.is_available():
        device = "cuda"
    elif torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"

    dtype = torch.float32 if device == "cpu" else torch.float16

    tokenizer = AutoTokenizer.from_pretrained(settings.AI_MODEL_NAME)
    model = AutoModelForCausalLM.from_pretrained(settings.AI_MODEL_NAME, dtype=dtype).to(device)
    model.eval()

    return tokenizer, model


def generate(messages, max_new_tokens=120):
    tokenizer, model = load_model()  # raises AIUnavailable without torch / transformers

    import torch

    inputs = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        return_tensors="pt",
        return_dict=True,
    ).to(model.device)

    with torch.no_grad():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )

    new_tokens = output[0][inputs["input_ids"].shape[1]:]

    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


# ============================================================
# 4. Output checks
# ============================================================

def parse_answer(answer):
    """
    The JSON object inside the model's answer, or None.
    Code fences and text around the object are ignored.
    """

    start, end = answer.find("{"), answer.rfind("}")

    if start == -1 or end == -1:
        return None

    try:
        data = json.loads(answer[start:end + 1])
    except json.JSONDecodeError:
        return None

    return data if isinstance(data, dict) else None


def match_quest(title, quests):
    """
    The quest whose title matches the model's answer (exactly, or very closely).
    """

    if not isinstance(title, str):
        return None

    by_title = {quest.title.lower(): quest for quest in quests}
    close = difflib.get_close_matches(title.strip().lower(), by_title, n=1, cutoff=0.8)

    return by_title[close[0]] if close else None


def safe_message(message):
    """
    The model's message if it is short and kind, otherwise None.
    """

    if not isinstance(message, str):
        return None

    message = clean_text(message, MAX_MESSAGE_CHARS)

    if not message or matches_any(message, [rf"\b{word}\b" for word in BLOCKED_OUTPUT_WORDS]):
        return None

    return message


def fallback_quest(quests):
    """
    A calm default quest: "Take 3 deep breaths" if it exists,
    otherwise the first General Self-Care quest, or any quest.
    """

    for quest in quests:
        if quest.title == FALLBACK_QUEST_TITLE:
            return quest

    for quest in quests:
        if quest.category == "general":
            return quest

    return quests[0] if quests else None


# ============================================================
# Main entry point (used by the view)
# ============================================================

def suggest_quest(user, feeling, journal=None):
    """
    Suggest one quest for how the user feels and/or a journal entry they chose.

    Returns a dict:
        status:  "ok", "fallback", "crisis", "injection" or "unavailable"
        quest:   a Quest or None
        message: the text shown to the user
    """

    feeling = clean_text(feeling, MAX_INPUT_CHARS)
    # Only quests one person can do alone: Together quests need a friend
    quests = list(Quest.objects.exclude(category=Quest.TOGETHER))

    # Everything the user wrote that would reach the model
    user_text = feeling

    if journal is not None:
        user_text += " " + chosen_journal_text(journal)

    if is_crisis(user_text):
        return {"status": "crisis", "quest": None, "message": CRISIS_MESSAGE}

    if is_injection(user_text):
        return {"status": "injection", "quest": None, "message": INJECTION_MESSAGE}

    fallback = {"status": "fallback", "quest": fallback_quest(quests), "message": FALLBACK_MESSAGE}

    if not quests:
        return fallback

    excerpts = [] if journal is not None else recent_journal_excerpts(user)
    messages = build_messages(feeling, excerpts, quests, chosen_journal=journal)

    try:
        answer = generate(messages)
    except AIUnavailable:
        return {"status": "unavailable", "quest": None, "message": UNAVAILABLE_MESSAGE}
    except Exception:
        logger.exception("Local AI model failed")
        return fallback

    data = parse_answer(answer)

    if data is None:
        logger.warning("AI answer was not JSON: %r", answer)
        return fallback

    quest = match_quest(data.get("quest"), quests)
    message = safe_message(data.get("message"))

    if quest is None or message is None:
        logger.warning("AI answer failed checks: %r", answer)
        return fallback

    return {"status": "ok", "quest": quest, "message": message}
