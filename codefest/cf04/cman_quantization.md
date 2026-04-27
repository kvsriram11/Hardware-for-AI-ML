# CMAN: Manual INT8 Symmetric Quantization
**ECE 410/510 — Codefest 4 — Spring 2026**

---

## Given FP32 Weight Matrix

$$
W =
\begin{bmatrix}
0.85 & -1.20 & 0.34 & 2.10 \\
-0.07 & 0.91 & -1.88 & 0.12 \\
1.55 & 0.03 & -0.44 & -2.31 \\
-0.18 & 1.03 & 0.77 & 0.55
\end{bmatrix}
$$

---

## 1. Scale Factor

For symmetric per-tensor quantization:

$$S = \frac{\max(|W|)}{127}$$

Scanning all 16 elements, the largest absolute value is $|{-2.31}| = 2.31$.

$$S = \frac{2.31}{127} = 0.01818898$$

---

## 2. Quantized INT8 Matrix

$$W_q = \text{round}\!\left(\frac{W}{S}\right), \quad \text{clamped to } [-128,\ 127]$$

$$
W_q =
\begin{bmatrix}
47 & -66 & 19 & 115 \\
-4 & 50 & -103 & 7 \\
85 & 2 & -24 & -127 \\
-10 & 57 & 42 & 30
\end{bmatrix}
$$

No values hit the clamp boundary — all elements are within $[-128, 127]$.

---

## 3. Dequantized FP32 Matrix

$$W_{deq} = W_q \times S$$

$$
W_{deq} =
\begin{bmatrix}
0.854882 & -1.200472 & 0.345591 & 2.091732 \\
-0.072756 & 0.909449 & -1.873465 & 0.127323 \\
1.546063 & 0.036378 & -0.436535 & -2.310000 \\
-0.181890 & 1.036772 & 0.763937 & 0.545669
\end{bmatrix}
$$

---

## 4. Error Analysis

$$\text{Error} = |W - W_{deq}|$$

$$
|W - W_{deq}| =
\begin{bmatrix}
0.004882 & 0.000472 & 0.005591 & 0.008268 \\
0.002756 & 0.000551 & 0.006535 & 0.007323 \\
0.003937 & 0.006378 & 0.003465 & 0.000000 \\
0.001890 & 0.006772 & 0.006063 & 0.004331
\end{bmatrix}
$$

**Largest error:** $W[0][3] = 2.10$, dequantized to $2.091732$

$$|2.10 - 2.091732| = 0.008268$$

**Mean Absolute Error (MAE):**

$$MAE = \frac{1}{16}\sum|W - W_{deq}| = 0.004326$$

---

## 5. Bad Scale Experiment

Using $S_{bad} = 0.01$:

$$W_{q,bad} = \text{round}\!\left(\frac{W}{S_{bad}}\right), \quad \text{clamped to } [-128,\ 127]$$

$$
W_{q,bad} =
\begin{bmatrix}
85 & -120 & 34 & 127 \\
-7 & 91 & -128 & 12 \\
127 & 3 & -44 & -128 \\
-18 & 103 & 77 & 55
\end{bmatrix}
$$

$$
W_{deq,bad} =
\begin{bmatrix}
0.85 & -1.20 & 0.34 & 1.27 \\
-0.07 & 0.91 & -1.28 & 0.12 \\
1.27 & 0.03 & -0.44 & -1.28 \\
-0.18 & 1.03 & 0.77 & 0.55
\end{bmatrix}
$$

$$MAE_{bad} = 0.171250$$

**Observation:** When the scale factor is too small, large weight values exceed the INT8 range and get clamped to $-128$ or $127$, causing saturation and much larger dequantization error — the $MAE$ increased by roughly $40\times$ compared to the correct scale.
