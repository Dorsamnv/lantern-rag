# Transformers and Self-Attention

Transformers are neural network architectures built around attention instead of recurrence.

## Self-attention in one idea
Self-attention lets each token look at other tokens in the sequence and decide what matters for the current representation.
For every token, the model builds **queries (Q)**, **keys (K)**, and **values (V)**.
Attention weights come from comparing queries with keys; those weights mix the values.

## Why Transformers matter
- Capture long-range dependencies better than simple RNNs
- Parallelize training across sequence positions
- Power modern NLP, multimodal models, and many vision backbones (ViT)

## Multi-head attention
Instead of one attention pattern, the model runs several heads in parallel.
Each head can specialize (syntax, coreference, local phrases, etc.), then the outputs are concatenated and projected.

## Practical notes
- Positional encodings (or relative positions) inject order information
- Computational cost grows with sequence length
- For long documents, chunking + retrieval is often more practical than stuffing everything into one context window
