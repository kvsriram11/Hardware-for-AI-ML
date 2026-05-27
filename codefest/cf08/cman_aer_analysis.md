# Codefest 08 — CMAN: AER Off-Chip Interface Analysis

**Author:** Venkata Sriram Kamarajugadda
**Course:** ECE 410/510 — Hardware for AI/ML (Spring 2026)
**Topic:** Off-chip output interface sizing for a 1024-neuron SNN accelerator using Address-Event Representation (AER)

---

## System parameters

| Symbol | Meaning                          | Value          |
|--------|----------------------------------|----------------|
| `N`    | Number of output neurons         | 1024           |
| `f`    | Mean firing rate per neuron      | 50 Hz          |
| —      | AER packet size (addr + ts + ovh)| 10 + 6 + 4 = **20 bits** |

---

## Task 1 — Mean aggregate spike rate `R`

```
R = N × f
R = 1024 × 50
R = 51,200 spikes/second  (≈ 51.2 kspikes/s)
```

---

## Task 2 — Mean AER bandwidth `B`

```
B = R × 20 bits/packet
B = 51,200 × 20
B = 1,024,000 bits/s
B = 1.024 Mbit/s
```

---

## Task 3 — Interface comparison at mean rate

Required mean bandwidth: **B = 1.024 Mbit/s**

| Interface  | Capacity      | Sustains mean? | Headroom | Complexity |
|------------|---------------|----------------|----------|------------|
| I²C        | ≤ 3.4 Mbit/s  | **YES**        | ~3.3×    | Lowest (2 wires, open-drain) |
| SPI        | ≤ 50 Mbit/s   | **YES**        | ~48.8×   | Low (3–4 wires, simple shift register) |
| AXI4-Lite  | ~100 Mbit/s   | **YES**        | ~97.7×   | Highest (full memory-mapped bus, handshakes, address decoding) |

**Lowest-complexity interface that suffices at the mean rate: I²C** (≤3.4 Mbit/s in High-Speed mode), with ~3.3× headroom over the 1.024 Mbit/s mean.

---

## Task 4 — Burst analysis

A 25% synchronous burst within a 1 ms window:

- Neurons firing in burst: `0.25 × 1024 = 256`
- Bits emitted in window: `256 × 20 = 5120 bits`
- **Peak instantaneous rate:** `5120 bits / 1 ms = 5,120,000 bits/s = 5.12 Mbit/s`

**Burst-to-mean ratio:** `5.12 / 1.024 = 5.0×`

**Can the chosen interface (I²C) absorb the burst?**

| Check                          | I²C (3.4 Mbit/s) | SPI (50 Mbit/s) | AXI4-Lite (100 Mbit/s) |
|--------------------------------|------------------|-----------------|------------------------|
| Peak rate ≤ link rate?         | **NO** (5.12 > 3.4) | YES             | YES                    |
| Buffer required?               | **YES**          | No              | No                     |

I²C **cannot** carry the peak instantaneously. Sizing the FIFO:

- Bits emitted during burst: 5120
- Bits drained by I²C during the same 1 ms: `3.4 Mbit/s × 1 ms = 3400 bits`
- Worst-case residual backlog: `5120 − 3400 = 1720 bits`
- Post-burst drain (link − mean = 3.4 − 1.024 = 2.376 Mbit/s) clears 1720 bits in ≈ **0.72 ms**

**Recommended FIFO depth:** size to hold the full burst payload for safety margin against back-to-back bursts: **≥ 5120 bits ≈ 640 bytes ≈ 256 packets** (round up to 512 B / 256-entry FIFO). If burst frequency is rare and well-spaced, the strict minimum is ~1720 bits (~86 packets), but designing for the full burst is the prudent engineering choice.

**Alternative:** if buffering is undesirable, step up to **SPI** — it carries the 5.12 Mbit/s peak directly with ~10× headroom and needs only a shallow handshake FIFO (a few packets) to smooth phase mismatch.

---

## Task 5 — Frame-based comparison

Conventional frame-based readout: sample all 1024 neurons every 1 ms, 1 bit per neuron.

```
B_frame = N × frame_rate × 1 bit
B_frame = 1024 × 1000 × 1
B_frame = 1,024,000 bits/s
B_frame = 1.024 Mbit/s
```

**AER-to-frame ratio at f = 50 Hz:** `1.024 / 1.024 = 1.000` — they are **exactly equal** at the operating point.

**Crossover firing rate:** set `B_AER = B_frame`

```
N · f · 20  =  N · (1/T_frame) · 1
20 · f      =  1000
f_crossover =  50 Hz
```

**Implication (one sentence):** AER is the right choice only when the mean firing rate is **below ~50 Hz** (i.e., when activity is sparse relative to the frame rate × packet-overhead product); above that, the per-event overhead of AER outweighs the savings from skipping silent neurons and a dense frame-based readout becomes more bandwidth-efficient.

---

## Summary table

| Metric                              | Value           |
|-------------------------------------|-----------------|
| Mean aggregate spike rate `R`       | 51,200 spikes/s |
| Mean AER bandwidth `B`              | 1.024 Mbit/s    |
| Chosen interface (mean)             | **I²C** (lowest complexity, 3.3× headroom) |
| Peak burst bandwidth                | 5.12 Mbit/s     |
| Burst-to-mean ratio                 | 5.0×            |
| Buffering decision                  | FIFO required for I²C (≥ 256 packets / 640 B); SPI eliminates the need |
| Frame-based bandwidth               | 1.024 Mbit/s    |
| AER/frame ratio at f = 50 Hz        | 1.000           |
| Crossover firing rate `f_crossover` | 50 Hz           |
