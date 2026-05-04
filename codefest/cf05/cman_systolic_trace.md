# CODEFEST 5 - CMAN

## Systolic array trace

### Given

A = [ 1  2 ]  
    [ 3  4 ]

B = [ 5  6 ]  
        [ 7  8 ]

Expected C = [ 19  22 ]  
             [ 43  50 ]

---

## 1) PE diagram

In weight-stationary dataflow, the weights of B are kept fixed inside the PEs.

|       | Column 0 | Column 1 |
|---|---|---|
| Row 0 | PE[0][0] = 5 | PE[0][1] = 6 |
| Row 1 | PE[1][0] = 7 | PE[1][1] = 8 |

A values stream from the left side.  
Partial sums move downward.

---

## 2) Cycle-by-cycle trace

| Cycle | Row 0 input | Row 1 input | PE[0][0] | PE[0][1] | PE[1][0] | PE[1][1] | Output |
|---|---|---|---|---|---|---|---|
| 0 | 1 | - | 1 x 5 = 5 | - | - | - | - |
| 1 | 3 | 2 | 3 x 5 = 15 | 1 x 6 = 6 | 5 + 2 x 7 = 19 | - | - |
| 2 | - | 4 | - | 3 x 6 = 18 | 15 + 4 x 7 = 43 | 6 + 2 x 8 = 22 | C[0][0] = 19 |
| 3 | - | - | - | - | - | 18 + 4 x 8 = 50 | C[1][0] = 43, C[0][1] = 22 |
| 4 | - | - | - | - | - | - | C[1][1] = 50 |

Final output:

C = [ 19  22 ]  
    [ 43  50 ]

---

## 3) Counts

### a) MAC count

For 2 x 2 matrix multiplication:

Total MAC operations = 2 x 2 x 2 = 8

So, total MAC count = 8.

---

### b) Input reuse count

Each A value is used with two B weights.

A[0][0] = 1 is used 2 times  
A[0][1] = 2 is used 2 times  
A[1][0] = 3 is used 2 times  
A[1][1] = 4 is used 2 times  

Each B value is fixed in one PE and used for two A values.

B[0][0] = 5 is reused 2 times  
B[0][1] = 6 is reused 2 times  
B[1][0] = 7 is reused 2 times  
B[1][1] = 8 is reused 2 times  

---

### c) Off-chip memory accesses

Assuming each value is read or written once:

A has 4 values, so A reads = 4  
B has 4 values, so B reads = 4  
C has 4 values, so C writes = 4  

Total off-chip memory accesses = 4 + 4 + 4 = 12

Partial sums are inside the array, so I am not counting them as off-chip accesses.

---

## 4) Output-stationary answer

In output-stationary dataflow, the C partial sums stay in the PEs until the final C values are completed.
