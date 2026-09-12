# Prompt Engineering Basics for Grounded Assistants

Prompt engineering is the practice of shaping instructions so a language model behaves reliably.

## Principles for RAG systems
1. Tell the model to use **only** provided sources
2. Require citations like [S1], [S2]
3. Allow abstaining when evidence is missing
4. Ask for structured answers (bullets, short sections)
5. Keep the user question clearly separated from retrieved context

## Anti-patterns
- Vague instructions ("be helpful") without grounding rules
- Dumping huge unrelated context
- Asking for confident answers even when retrieval is weak
- Mixing system policy and user content carelessly

## Temperature
Lower temperature (e.g., 0.1–0.3) usually helps factual, source-grounded answering.
Higher temperature can help brainstorming, but increases drift from sources.

## Portfolio tip
In demos, show both the retrieved passages and the final answer. Transparency builds trust faster than a perfect-looking paragraph with no evidence.
