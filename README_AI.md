# System Description


## Data Input
###### How is the user data captured in your app?

1. User data is captured in the chatbot, located in the same tab as the quests, where users can share things like how they're feeling, what their energy levels are, what kind of support they need, etc. (e.g. "I haven't been sleeping well" or "I'm lonely because I moved to a new place recently").
2. The system also uses available quest data and the journals a user fills out to understand the user better and to pull accurate data or options and recommendations available on SafeSpace.

## Preprocessing
######  How do you clean or format data before it is sent to the LLM?

1. The model is fast and compact, so it keeps input lengths capped and strips whitespace characters to maintain clean prompt structures and ensure speedy response times.
2. It follows a structured template defining the persona guide, who is brief, empathetic, and non-judgemental, and strict output formatting so it's responses are structured and short, rather than long and unstructured.
3. There are formatted JSON and/or list summaries of the current quests available included in the system instructions so the model accurately relates prompts to quests.

## Safety Guardrails
###### How are you preventing malicious inputs or handling broken outputs?

1. Input Protections
    1. Users are blocked from trying to "hack" or trick the AI into giving inappropriate answers or ignoring its original instructions.
    2. There are limits on how much text a user can send at once so the AI doesn't get overwhelmed, crash, or run slowly.
2. Output Protections
    1. Because the model is small, it might occasionally give a confusing or broken answer instead of a clean quest recommendation. If that happens, our app automatically catches the error and gives the user a safe, pre-made suggestion (like "Try taking 3 deep breaths") instead of showing broken text.
    2. If the model generates an answer that sounds negative or inappropriate for a self-care app, the system blocks it and replaces it with a gentle, supportive default message, much like the broken text output (like "Try taking 3 deep breaths").

