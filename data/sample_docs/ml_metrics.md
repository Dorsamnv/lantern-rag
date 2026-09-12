# Classification Metrics: Precision, Recall, F1

Accuracy alone is often misleading on imbalanced datasets.

## Definitions
- **Precision:** of the predicted positives, how many are actually positive  
  `TP / (TP + FP)`
- **Recall (sensitivity):** of the actual positives, how many did we find  
  `TP / (TP + FN)`
- **F1 score:** harmonic mean of precision and recall  
  `2 * precision * recall / (precision + recall)`

## When to prefer which
- High **precision** when false alarms are costly (e.g., unnecessary expensive follow-up)
- High **recall** when missing a positive is costly (e.g., disease screening)
- **F1** when you need a balance and class distribution is skewed

## Confusion matrix reminder
TP = true positives, FP = false positives, TN = true negatives, FN = false negatives.

## Reporting tip
Always state the dataset split, class balance, and decision threshold when comparing models.
