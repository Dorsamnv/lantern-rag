# Responsible AI Checklist (Short)

Responsible AI means building systems that are useful while reducing preventable harm.

## Practical checklist
- **Data provenance:** know where documents and labels come from
- **Bias checks:** inspect failure cases across groups or domains
- **Transparency:** show sources, uncertainty, and model limits
- **Privacy:** do not upload secrets to third-party APIs without consent
- **Human oversight:** keep a human in the loop for high-stakes decisions
- **Evaluation:** measure retrieval quality and answer groundedness, not only fluency

## For document assistants like Lantern
- Prefer citation-first answers
- Make it easy to inspect retrieved chunks
- Warn users that OCR / PDF extraction can be imperfect
- Separate demo corpora from private personal data

## One-sentence summary
A trustworthy AI assistant should make its evidence visible, its limits explicit, and its failures measurable.
