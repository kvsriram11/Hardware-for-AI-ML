# MAC Code Review — Codefest 4 CLLM
**ECE 410/510 — Spring 2026**

---

## LLM Attribution

| File | LLM | Version |
|---|---|---|
| `mac_llm_A.sv` | Claude | Claude Sonnet 4.6 |
| `mac_llm_B.sv` | ChatGPT Plus | GPT-4o |
| `mac_llm_C.sv` | Google Gemini | Gemini (fill in version) |

A third LLM was added after the initial review found that A and B were nearly identical — Gemini gave more interesting differences to analyze.

---

## Compilation

All three files compiled in QuestaSim without errors.

---

## Simulation Results

All three DUTs produced correct output values:
`0 → 12 → 24 → 36 → 0 (reset) → −10 → −20`

### mac_llm_A simulation log (7/7 PASS)
```
# PASS | after_reset              | out = 0
# PASS | p1_cycle1 (exp: 12)      | out = 12
# PASS | p1_cycle2 (exp: 24)      | out = 24
# PASS | p1_cycle3 (exp: 36)      | out = 36
# PASS | mid_reset (exp: 0)       | out = 0
# PASS | p2_cycle1 (exp: -10)     | out = -10
# PASS | p2_cycle2 (exp: -20)     | out = -20
```

### mac_llm_B simulation log
No printed output — waveform verified manually (see screenshot).

### mac_llm_C simulation log
```
# Time=0     | rst=1 | a=   0 | b=   0 | out=          x
# Time=5000  | rst=1 | a=   0 | b=   0 | out=          0
# Time=25000 | rst=0 | a=   3 | b=   4 | out=          0
# Time=35000 | rst=0 | a=   3 | b=   4 | out=         12
# Time=45000 | rst=0 | a=   3 | b=   4 | out=         24
# Time=55000 | rst=1 | a=   3 | b=   4 | out=         36
# Time=65000 | rst=0 | a=  -5 | b=   2 | out=          0
# Time=75000 | rst=0 | a=  -5 | b=   2 | out=        -10
# Time=85000 | rst=0 | a=  -5 | b=   2 | out=        -20
```

---

## Issues Found

### Issue 1 — GPT-4o testbench has no pass/fail checks

**Offending code:**
```verilog
@(posedge clk); // out = 12
@(posedge clk); // out = 24
@(posedge clk); // out = 36
```

The expected values are only in comments. The testbench never actually checks anything — it just runs and stops. If the DUT produced wrong values, the simulation would still "pass" silently. You'd have to open the waveform every single time to know if anything went wrong.

**Fix:** Add actual checks after each clock edge:
```systemverilog
@(posedge clk); #1;
if (out === 32'sd12)
    $display("PASS | out = %0d", out);
else
    $display("FAIL | expected 12, got %0d", out);
```

---

### Issue 2 — All three designs use a hardcoded number for sign extension

**Offending code (same in A, B, and C):**
```systemverilog
out <= out + {{16{product[15]}}, product};
```

The `16` here is manually calculated as `32 − 16`. If you ever change the bit widths, you have to remember to update this number too — and the compiler won't warn you if you forget.

**Fix:** Let SystemVerilog handle it automatically:
```systemverilog
out <= out + 32'(signed'(product));
```

Same result, but the width is tied directly to `out` so it stays correct if widths change.

---

### Issue 3 — Gemini testbench prints `out = x` at time 0

**Offending output:**
```
# Time=0 | rst=1 | a= 0 | b= 0 | out= x
```

The testbench is printing `out` before the first clock edge happens, so the flip-flop hasn't been initialized yet — `x` just means "unknown". It's not a DUT bug, but it's a testbench bug. Any check against `x` using `==` will silently return false, which could hide real errors.

**Fix:** Wait for the first clock edge before reading or displaying any output.

---

### Issue 4 — Gemini testbench prints on every signal change, not just clock edges

The log shows output at Time=25000 when `a` and `b` just changed, but the clock hasn't ticked yet so `out` still shows the old value. This makes the log confusing — you see intermediate states mixed in with real results.

**Fix:** Only print output right after a clock edge (with a small `#1` delay), not continuously.

---

### Issue 5 — Gemini testbench de-asserts reset and changes inputs at the same time

**From the log:**
```
# Time=65000 | rst=0 | a=-5 | b=2 | out=0
```

Reset goes low and the new inputs `a=−5, b=2` are applied at the exact same moment. It works here, but it's cleaner to separate these — drop reset one cycle, then apply new inputs the next cycle. Otherwise it's hard to tell what was intentional.

---

## Corrected Design — `mac_correct.sv`

Based on `mac_llm_A.sv` with the sign extension fix from Issue 2 applied:

```systemverilog
module mac_correct (
    input  logic                clk,
    input  logic                rst,
    input  logic signed [7:0]   a,
    input  logic signed [7:0]   b,
    output logic signed [31:0]  out
);

    logic signed [15:0] product;
    assign product = a * b;

    always_ff @(posedge clk) begin
        if (rst)
            out <= 32'sd0;
        else
            out <= out + 32'(signed'(product));
    end

endmodule
```

---

## Yosys Synthesis Output

```
=== mac_correct ===
   Number of cells:    683
     $_SDFF_PP0_        32   ← 32 flip-flops for the accumulator
     $_XOR_            170
     $_ANDNOT_         196
     ...
CHECK pass: Found and reported 0 problems.
```

32 flip-flops, no latches, no errors.

---

## Summary

| | A (Claude) | B (GPT-4o) | C (Gemini) |
|---|:---:|:---:|:---:|
| RTL correct | Pass | Pass | Pass |
| Compiles clean | Pass | Pass | Pass |
| Testbench has pass/fail output | Pass | Fail | Fail |
| No `x` values in output | Pass | Pass | Fail |
| Clock-edge aligned checks | Pass | Partial | Fail |
| Clean stimulus ordering | Pass | Pass | Partial |

All three got the hardware right. The differences are entirely in how good the testbench is.
