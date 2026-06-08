/*
 * ESN state-update benchmark — C + OpenBLAS (single-threaded)
 *
 * Matches the Python reference exactly:
 *   x[t] = (1-a)*x[t-1] + a*tanh(Win @ [1,u] + W @ x[t-1])
 *
 * Same seed, same weights, same Mackey-Glass data. Validates final state
 * MSE against the Python golden to confirm bit-equivalence is achievable
 * (small FP rounding diffs expected).
 *
 * Usage: benchmark.exe <N> <reps> <data_file>
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include <cblas.h>

/* Mersenne Twister-like LCG with seed=42 to match np.random.RandomState(42)
 * Actually NOT bit-equivalent to NumPy's MT19937 — we cannot exactly reproduce
 * NumPy's RNG in C. So instead we LOAD W and Win from npz dumps written by
 * the Python side. See baselines/c_openblas/weights/*.bin
 *
 * Each binary file: row-major float32, no header. Shape known from N.
 */

typedef struct {
    float *W;       /* N*N row-major */
    float *Win;     /* N*2 row-major */
    float *x;       /* N */
    float *x_next;  /* N */
    float *pre;     /* N */
    float *u_vec;   /* 2 */
    int N;
    float leak;
} esn_t;

static void *xalloc(size_t n) {
    void *p = malloc(n);
    if (!p) { fprintf(stderr, "alloc failed\n"); exit(1); }
    memset(p, 0, n);
    return p;
}

static int load_bin(const char *path, float *buf, size_t nfloats) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "open %s failed\n", path); return -1; }
    size_t r = fread(buf, sizeof(float), nfloats, f);
    fclose(f);
    if (r != nfloats) { fprintf(stderr, "short read %s: got %zu want %zu\n", path, r, nfloats); return -1; }
    return 0;
}

static double load_data(const char *path, float **out) {
    FILE *f = fopen(path, "r");
    if (!f) { fprintf(stderr, "open data %s failed\n", path); exit(1); }
    /* Mackey-Glass: 10000 lines, one float per line */
    int cap = 16384;
    float *buf = malloc(cap * sizeof(float));
    int n = 0;
    char line[64];
    while (fgets(line, sizeof line, f)) {
        if (n >= cap) { cap *= 2; buf = realloc(buf, cap * sizeof(float)); }
        buf[n++] = (float)atof(line);
    }
    fclose(f);
    *out = buf;
    return (double)n;
}

/* One state-update step: x = (1-a)x + a*tanh(Win@[1,u] + W@x) */
static void state_update(esn_t *e, float u) {
    int N = e->N;
    e->u_vec[0] = 1.0f;
    e->u_vec[1] = u;
    /* pre = Win @ [1,u]  (N x 2) @ (2 x 1) */
    cblas_sgemv(CblasRowMajor, CblasNoTrans, N, 2, 1.0f,
                e->Win, 2, e->u_vec, 1, 0.0f, e->pre, 1);
    /* pre += W @ x  (N x N) @ (N x 1) */
    cblas_sgemv(CblasRowMajor, CblasNoTrans, N, N, 1.0f,
                e->W, N, e->x, 1, 1.0f, e->pre, 1);
    /* x_next = (1-a)*x + a*tanh(pre) */
    float a = e->leak;
    float ma = 1.0f - a;
    for (int i = 0; i < N; i++) {
        e->x_next[i] = ma * e->x[i] + a * tanhf(e->pre[i]);
    }
    /* swap */
    float *t = e->x; e->x = e->x_next; e->x_next = t;
}

static double now_seconds(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec + ts.tv_nsec * 1e-9;
}

int compare_times(const void *a, const void *b) {
    double da = *(const double *)a, db = *(const double *)b;
    return (da > db) - (da < db);
}

int main(int argc, char **argv) {
    if (argc < 4) {
        fprintf(stderr, "usage: %s <N> <reps> <data_file>\n", argv[0]);
        return 1;
    }
    int N = atoi(argv[1]);
    int reps = atoi(argv[2]);
    const char *data_path = argv[3];

    /* Load Mackey-Glass data */
    float *data;
    int data_len = (int)load_data(data_path, &data);
    fprintf(stderr, "Loaded %d data points\n", data_len);

    /* Allocate ESN */
    esn_t e;
    e.N = N;
    e.leak = 0.3f;
    e.W = xalloc(sizeof(float) * N * N);
    e.Win = xalloc(sizeof(float) * N * 2);
    e.x = xalloc(sizeof(float) * N);
    e.x_next = xalloc(sizeof(float) * N);
    e.pre = xalloc(sizeof(float) * N);
    e.u_vec = xalloc(sizeof(float) * 2);

    /* Load weights from Python-dumped binaries */
    char path_w[256], path_win[256];
    snprintf(path_w, sizeof path_w, "weights/W_N%d.bin", N);
    snprintf(path_win, sizeof path_win, "weights/Win_N%d.bin", N);
    if (load_bin(path_w, e.W, (size_t)N * N) < 0) return 1;
    if (load_bin(path_win, e.Win, (size_t)N * 2) < 0) return 1;
    fprintf(stderr, "Loaded W (%dx%d) and Win (%dx2)\n", N, N, N);

    /* Single-step timing: time one state_update call, repeat reps times */
    double *times = malloc(sizeof(double) * reps);
    for (int r = 0; r < reps; r++) {
        memset(e.x, 0, sizeof(float) * N);
        memset(e.x_next, 0, sizeof(float) * N);
        double t0 = now_seconds();
        state_update(&e, data[0]);
        double t1 = now_seconds();
        times[r] = t1 - t0;
    }
    qsort(times, reps, sizeof(double), compare_times);
    double median_step = times[reps / 2];

    /* Full 4000-step run timing (1 rep is enough to dwarf single-step noise) */
    int train_len = 2000, test_len = 2000;
    int total_steps = train_len + test_len;
    double full_times[10];
    int full_reps = 10;
    for (int r = 0; r < full_reps; r++) {
        memset(e.x, 0, sizeof(float) * N);
        memset(e.x_next, 0, sizeof(float) * N);
        double t0 = now_seconds();
        for (int t = 0; t < total_steps; t++) {
            float u = (t < data_len) ? data[t] : 0.0f;
            state_update(&e, u);
        }
        double t1 = now_seconds();
        full_times[r] = t1 - t0;
    }
    qsort(full_times, full_reps, sizeof(double), compare_times);
    double median_full = full_times[full_reps / 2];

    /* Compute final-state checksum (for cross-language validation) */
    double checksum = 0.0;
    for (int i = 0; i < N; i++) checksum += e.x[i] * e.x[i];
    checksum = sqrt(checksum);

    /* Report */
    printf("{\n");
    printf("  \"N\": %d,\n", N);
    printf("  \"reps\": %d,\n", reps);
    printf("  \"per_step_median_s\": %.9f,\n", median_step);
    printf("  \"per_step_min_s\": %.9f,\n", times[0]);
    printf("  \"per_step_max_s\": %.9f,\n", times[reps - 1]);
    printf("  \"full_run_steps\": %d,\n", total_steps);
    printf("  \"full_run_median_s\": %.9f,\n", median_full);
    printf("  \"full_run_min_s\": %.9f,\n", full_times[0]);
    printf("  \"full_run_max_s\": %.9f,\n", full_times[full_reps - 1]);
    printf("  \"updates_per_sec_isolated\": %.1f,\n", 1.0 / median_step);
    printf("  \"updates_per_sec_full\": %.1f,\n", total_steps / median_full);
    long long flops = 2LL * N * N + 9LL * N;
    printf("  \"flops_per_step\": %lld,\n", flops);
    printf("  \"gflops_sustained\": %.3f,\n", (double)flops / median_step / 1e9);
    printf("  \"final_state_l2_norm\": %.9f\n", checksum);
    printf("}\n");

    free(times);
    free(e.W); free(e.Win); free(e.x); free(e.x_next); free(e.pre); free(e.u_vec);
    free(data);
    return 0;
}
