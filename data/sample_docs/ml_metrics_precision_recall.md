# Classification Metrics: Precision, Recall, and F1

Evaluating classifiers needs more than accuracy alone, especially on imbalanced datasets.

## Definitions
- **True Positive (TP):** predicted positive, actually positive
- **False Positive (FP):** predicted positive, actually negative
- **False Negative (FN):** predicted negative, actually positive
- **True Negative (TN):** predicted negative, actually negative

## Precision
Precision = TP / (TP + FP)

High precision means: when the model says "yes", it is usually correct.
Useful when false positives are costly (e.g., marking innocent emails as spam carefully).

## Recall
Recall = TP / (TP + FN)

High recall means: the model finds most of the real positives.
Useful when missing a positive is costly (e.g., disease screening).

## F1 score
F1 is the harmonic mean of precision and recall:

F1 = 2 * (precision * recall) / (precision + recall)

It balances the two when you need a single summary number.

## Accuracy trap
If 95% of samples are class A, a model that always predicts A gets 95% accuracy but is useless for class B. Prefer precision/recall/F1 (or AUROC) for skewed data.
