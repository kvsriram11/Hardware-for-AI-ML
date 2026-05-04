# CF05 CMAN trace

## Deliverable 1: 2 x 2 weight-stationary PE array

In weight-stationary dataflow, the weights from matrix B are preloaded into the PEs and stay fixed.

A = [ [1, 2],
      [3, 4] ]

B = [ [5, 6],
      [7, 8] ]

PE array:

|        | Column 0 | Column 1 |
|---|---|---|
| Row 0 | PE[0][0] = B[0][0] = 5 | PE[0][1] = B[0][1] = 6 |
| Row 1 | PE[1][0] = B[1][0] = 7 | PE[1][1] = B[1][1] = 8 |

Inputs from A stream from the left.

Partial sums move downward.

Final C values come out from the bottom row.


## Deliverable 2: Cycle-by-cycle trace

In this array:

Array row 0 stores B[0][j], so it receives values from column 0 of A.

Array row 1 stores B[1][j], so it receives values from column 1 of A.

Correct input skew:

| Cycle | Input to row 0 | Input to row 1 | PE partial sums | Output C values |
|---|---|---|---|---|
| 0 | 1 | - | PE[0][0]: 1x5 = 5, PE[0][1]: 1x6 = 6 | No final output yet |
| 1 | 3 | 2 | PE[0][0]: 3x5 = 15, PE[0][1]: 3x6 = 18, PE[1][0]: 5 + 2x7 = 19, PE[1][1]: 6 + 2x8 = 22 | C[0][0] = 19, C[0][1] = 22 computed |
| 2 | - | 4 | PE[1][0]: 15 + 4x7 = 43, PE[1][1]: 18 + 4x8 = 50 | C[1][0] = 43, C[1][1] = 50 computed |
| 3 | - | - | Array drains, no new MACs | Final outputs available if outputs are registered |

Final output:

C = [ [19, 22],
      [43, 50] ]


## Deliverable 3: MAC count, reuse, and off-chip accesses

Each output C value needs 2 MAC operations.

There are 4 output values.

Total MAC operations:

4 x 2 = 8 MAC operations

Each weight in B is reused 2 times.

Each input value in A is reused 2 times.

Without reuse:

A reads = 8

B reads = 8

C writes = 4

Total off-chip accesses = 8 + 8 + 4 = 20

With weight-stationary reuse:

A reads = 4

B reads = 4

C writes = 4

Total off-chip accesses = 4 + 4 + 4 = 12

So weight-stationary dataflow reduces total off-chip accesses from 20 to 12.


## Deliverable 4: Output-stationary answer

In output-stationary dataflow, the partial sum for each output C element stays fixed inside a PE until the full dot product is completed, and only the final C value is written out.
