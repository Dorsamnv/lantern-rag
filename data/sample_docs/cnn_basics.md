# Convolutional Neural Networks (CNNs)

CNNs are neural networks designed for grid-like data such as images.

## Core building blocks
- **Convolution:** local filters detect edges, textures, and patterns
- **Nonlinearity:** usually ReLU after convolutions
- **Pooling / striding:** reduce spatial size and increase receptive field
- **Fully connected / classifier head:** map features to labels

## Why CNNs work well on images
Nearby pixels are strongly related. Convolutions reuse the same filter across locations (weight sharing), which reduces parameters and improves sample efficiency compared with dense layers on raw pixels.

## Common applications
- Image classification
- Object detection
- Semantic segmentation
- Medical imaging triage
- Fine-grained recognition (e.g., plant species)

## Modern context
Transformers (ViT) are competitive in vision, but CNN ideas remain useful in hybrid architectures, efficient mobile models, and detection pipelines.
