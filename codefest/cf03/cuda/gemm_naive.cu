%%writefile codefest/cf03/cuda/gemm_naive.cu
#include <cstdio>
#include <cstdlib>
#include <cuda_runtime.h>

#define N 1024
#define RUNS 10

__global__ void gemm_naive_kernel(const float *A, const float *B, float *C, int n) {
    int row = blockIdx.y * blockDim.y + threadIdx.y;
    int col = blockIdx.x * blockDim.x + threadIdx.x;

    if (row < n && col < n) {
        float sum = 0.0f;
        for (int k = 0; k < n; k++) {
            sum += A[row * n + k] * B[k * n + col];
        }
        C[row * n + col] = sum;
    }
}

void init_matrix(float *M, int n) {
    for (int i = 0; i < n * n; i++) {
        M[i] = static_cast<float>(rand()) / RAND_MAX;
    }
}

int main() {
    size_t bytes = N * N * sizeof(float);

    float *h_A = (float*)malloc(bytes);
    float *h_B = (float*)malloc(bytes);
    float *h_C = (float*)malloc(bytes);

    init_matrix(h_A, N);
    init_matrix(h_B, N);

    float *d_A, *d_B, *d_C;
    cudaMalloc((void**)&d_A, bytes);
    cudaMalloc((void**)&d_B, bytes);
    cudaMalloc((void**)&d_C, bytes);

    cudaMemcpy(d_A, h_A, bytes, cudaMemcpyHostToDevice);
    cudaMemcpy(d_B, h_B, bytes, cudaMemcpyHostToDevice);

    dim3 blockDim(16, 16);
    dim3 gridDim((N + blockDim.x - 1) / blockDim.x,
                 (N + blockDim.y - 1) / blockDim.y);

    cudaEvent_t start, stop;
    cudaEventCreate(&start);
    cudaEventCreate(&stop);

    gemm_naive_kernel<<<gridDim, blockDim>>>(d_A, d_B, d_C, N);
    cudaDeviceSynchronize();

    float times[RUNS];
    float total_ms = 0.0f;
    float best_ms = 1e30f;

    for (int r = 0; r < RUNS; r++) {
        cudaEventRecord(start);
        gemm_naive_kernel<<<gridDim, blockDim>>>(d_A, d_B, d_C, N);
        cudaEventRecord(stop);
        cudaEventSynchronize(stop);

        float ms = 0.0f;
        cudaEventElapsedTime(&ms, start, stop);
        times[r] = ms;
        total_ms += ms;
        if (ms < best_ms) best_ms = ms;
    }

    cudaMemcpy(h_C, d_C, bytes, cudaMemcpyDeviceToHost);

    float avg_ms = total_ms / RUNS;
    double flops = 2.0 * N * N * N;
    double avg_gflops = flops / (avg_ms / 1000.0) / 1e9;
    double best_gflops = flops / (best_ms / 1000.0) / 1e9;

    printf("Naive GEMM\n");
    printf("Matrix size: %d x %d\n", N, N);
    printf("Runs: %d\n", RUNS);
    for (int r = 0; r < RUNS; r++) {
        printf("Run %2d: %.4f ms\n", r + 1, times[r]);
    }
    printf("Average kernel time: %.4f ms\n", avg_ms);
    printf("Best kernel time: %.4f ms\n", best_ms);
    printf("Average achieved performance: %.2f GFLOP/s\n", avg_gflops);
    printf("Best achieved performance: %.2f GFLOP/s\n", best_gflops);
    printf("C[0] = %f\n", h_C[0]);

    cudaFree(d_A);
    cudaFree(d_B);
    cudaFree(d_C);
    free(h_A);
    free(h_B);
    free(h_C);

    return 0;
}
