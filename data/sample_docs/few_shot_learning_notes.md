# Few-Shot Learning — Study Notes

Few-shot learning aims to train models that generalize from only a handful of labeled examples per class.

## Why it matters
Collecting large labeled datasets is expensive. In domains like medical imaging or rare species recognition, you may only have 1–10 samples per class. Few-shot methods reduce annotation cost and speed up adaptation to new categories.

## Common approaches
1. **Metric learning** — learn an embedding space where similar items are close (e.g., Prototypical Networks, Matching Networks).
2. **Transfer learning / fine-tuning** — start from a pretrained backbone, then adapt with few labeled examples.
3. **Meta-learning** — train across many episodes so the model learns how to learn quickly from a support set.
4. **Prompting / foundation models** — use CLIP-style or multimodal LLMs that already align images and text, then adapt with retrieval or light prompting.

## N-way K-shot protocol
- **N** = number of classes in an episode
- **K** = labeled support examples per class
- The model is evaluated on a **query set** from the same classes
- Example: 5-way 1-shot means 5 classes with 1 labeled image each

## Evaluation tips
- Report mean accuracy over many random episodes, not a single split
- Include confidence intervals when possible
- Compare zero-shot vs 1-shot vs 5-shot under the same backbone
- Log hard cases separately (near-duplicate classes, domain shift)

## Relation to VQA
Few-shot Visual Question Answering applies the same limited-label idea to multimodal question answering: the system must answer image questions with only a small support set of examples.
