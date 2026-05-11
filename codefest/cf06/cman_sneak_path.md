# CMAN: Sneak Paths in a 2x2 Resistive Crossbar

**Author:** Venkata Sriram Kamarajugadda
**Course:** ECE 410/510, Spring 2026
**File:** `codefest/cf06/cman_sneak_path.md`

## Setup

The 2x2 crossbar has the following cell resistances:

| Cell | R | State |
|------|------|----|
| R[0][0] | 1 kOhm | on |
| R[0][1] | 2 kOhm | off |
| R[1][0] | 2 kOhm | off |
| R[1][1] | 1 kOhm | on |

We apply 1 V to row 0 and read the current at column 0. Ideally, this current should correspond to the weight stored at R[0][0]. All work is done in V, mA, and kOhm so that V/kOhm gives mA.

## (a) Ideal read

Row 1 and column 1 are grounded along with column 0 (held at virtual ground). The only cell that connects a driven row to the sensed column with a voltage difference across it is R[0][0]. Cell R[1][0] has both terminals at 0 V, so it carries no current.

```
I_col0 = (1 V - 0 V) / 1 kOhm = 1.0 mA
```

This matches the expected MVM result for input [1, 0] and weight column [1 mS, 0.5 mS].

## (b) Floating node voltages (KCL)

Now row 1 and column 1 are left floating. Let V_a be the voltage at row 1 and V_b at column 1. Row 0 is still at 1 V and column 0 is still at 0 V (virtual ground).

Applying KCL at row 1, the two cells connecting to it are R[1][0] (from col 0) and R[1][1] (from col 1):

```
(0 - V_a)/2  +  (V_b - V_a)/1  =  0
```

This simplifies to V_a = (2/3) * V_b.

Applying KCL at column 1, the two cells connecting to it are R[0][1] (from row 0) and R[1][1] (from row 1):

```
(1 - V_b)/2  +  (V_a - V_b)/1  =  0
```

This simplifies to 2*V_a - 3*V_b = -1.

Substituting the first into the second:

```
2*(2/3)*V_b - 3*V_b = -1
       -(5/3)*V_b   = -1
              V_b   = 0.6 V
              V_a   = 0.4 V
```

So **V_row1 = 0.4 V** and **V_col1 = 0.6 V**.

Sanity check at row 1: current from col 0 is (0 - 0.4)/2 = -0.2 mA, and current from col 1 is (0.6 - 0.4)/1 = +0.2 mA. These cancel, confirming the solution.

## (c) Actual I_col0 with sneak path

With row 1 floating at 0.4 V, cell R[1][0] now carries a non-zero current into column 0. The two contributions are:

| Source | Calculation | Current |
|--------|-------------|---------|
| R[0][0] (intended) | (1 - 0)/1 | +1.0 mA |
| R[1][0] (sneak) | (0.4 - 0)/2 | +0.2 mA |
| **Total** | | **1.2 mA** |

The measured current is 1.2 mA instead of the ideal 1.0 mA, a 20 percent error. The sense amplifier cannot distinguish the sneak contribution from the intended signal.

## (d) Implications for MVM

The crossbar is supposed to compute I_j = sum over i of G_ij * V_i, with one term per driven row. Sneak paths introduce extra terms from undriven rows whose floating voltages depend on the rest of the stored weights. The measured column current is therefore a data-dependent corruption of the intended dot product rather than the dot product itself.

In a 256x256 array, each column has 255 other rows that can contribute sneak current. The error scales with array size and weight pattern, which is why practical crossbars use a 1T1R structure (access transistor per cell) or a 1S1R structure (selector diode per cell) to break sneak paths and isolate the selected row.
