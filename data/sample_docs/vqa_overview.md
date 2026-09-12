# Visual Question Answering (VQA) — Overview

Visual Question Answering is the task of answering a natural-language question about an image.

Example:
- Image: a kitchen scene
- Question: "How many red cups are on the table?"
- Answer: "2"

## Pipeline
1. Encode the image with a vision model
2. Encode the question with a language model
3. Fuse both modalities (attention, cross-attention, or joint encoder)
4. Predict an answer (classification over answer vocabulary, or free-form generation)

## Challenges
- **Language bias:** models may ignore the image and answer from question priors
- **Compositionality:** questions can require counting, relations, attributes, and logic
- **Limited labels:** annotated VQA data can be scarce for specialized domains
- **Evaluation ambiguity:** multiple answers may be acceptable for open-ended questions

## Few-shot VQA
Few-shot VQA studies how systems answer visual questions when only a small support set is available.
Useful strategies include:
- retrieving similar support examples at inference time
- freezing large multimodal backbones and adapting lightly
- confidence-based answer selection or abstention when uncertain
- using vision-language models in zero-shot / few-shot prompting setups

## Practical checklist
- Choose a clear dataset split and report it
- Log qualitative failure cases (counting, rare objects, OCR-heavy images)
- Compare zero-shot vs 1-shot vs 5-shot settings
- Prefer grounded answers with evidence when building RAG-style assistants
