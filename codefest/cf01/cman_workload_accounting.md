# CMAN — Workload Accounting by Hand

**Course:** ECE 410/510 Spring 2026  
**Name:** Venkata Sriram Kamarajugadda  
**Date:** 04/01/2026  

---

## Given

3-layer fully connected network:

784 → 256 → 128 → 10  
Batch size = 1  
Data type = FP32 (4 bytes per value)  
No bias terms  

---

## 1. Per-layer MACs

### Layer 1: 784 → 256
MACs = 784 × 256 = **200,704**

---

### Layer 2: 256 → 128
MACs = 256 × 128 = **32,768**

---

### Layer 3: 128 → 10
MACs = 128 × 10 = **1,280**

---

## 2. Total MACs

Total MACs = 200,704 + 32,768 + 1,280  
= **234,752 MACs**

---

## 3. Trainable Parameters

(Number of weights = same as MACs for FC layers)

Total parameters =  
= 784 × 256 + 256 × 128 + 128 × 10  
= **234,752 parameters**

---

## 4. Weight Memory

Each parameter = 4 bytes (FP32)

Weight memory = 234,752 × 4  
= **939,008 bytes**

---

## 5. Activation Memory

We store:
- Input layer
- All intermediate outputs

Total activations =  
= 784 + 256 + 128 + 10  
= 1,178 values  

Activation memory = 1,178 × 4  
= **4,712 bytes**

---

## 6. Arithmetic Intensity

Formula:

Arithmetic Intensity = (2 × Total MACs) / (Weight bytes + Activation bytes)

Substitute values:

= (2 × 234,752) / (939,008 + 4,712)  
= 469,504 / 943,720  

≈ **0.497 FLOP/byte**

---

## Final Answers

- Total MACs: **234,752**
- Total Parameters: **234,752**
- Weight Memory: **939,008 bytes**
- Activation Memory: **4,712 bytes**
- Arithmetic Intensity: **0.497 FLOP/byte**
