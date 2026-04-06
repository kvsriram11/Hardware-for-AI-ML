# ResNet-18 Analysis

## Top 5 MAC-Heavy Layers

| Layer Name | MACs | Parameters |
|---|---:|---:|
| Conv2d: 1-1 (conv1) | 118,013,952 | 9,408 |
| Conv2d: 3-1 | 115,605,504 | 36,864 |
| Conv2d: 3-4 | 115,605,504 | 36,864 |
| Conv2d: 3-7 | 115,605,504 | 36,864 |
| Conv2d: 3-10 | 115,605,504 | 36,864 |

---

## Arithmetic Intensity of Most MAC-Intensive Layer

We choose **Conv2d: 1-1 (conv1)** as it has the highest MAC count.

### Layer details

- Input: 1 × 3 × 224 × 224
- Output: 1 × 64 × 112 × 112
- Kernel: 7 × 7
- Parameters: 9,408
- MACs: 118,013,952

---

### Memory calculation (FP32 = 4 bytes)

#### Weights
= 9,408 × 4 = 37,632 bytes

#### Input activations
= (1 × 3 × 224 × 224) × 4  
= 150,528 × 4 = 602,112 bytes

#### Output activations
= (1 × 64 × 112 × 112) × 4  
= 802,816 × 4 = 3,211,264 bytes

---

### Total memory

= 37,632 + 602,112 + 3,211,264  
= 3,851,008 bytes

---

### Arithmetic Intensity

AI = (2 × MACs) / total bytes  

= (2 × 118,013,952) / 3,851,008  
= 236,027,904 / 3,851,008  

≈ **61.29 FLOP/byte**

---

## Final Answer

Arithmetic Intensity ≈ **61.29 FLOP/byte**
