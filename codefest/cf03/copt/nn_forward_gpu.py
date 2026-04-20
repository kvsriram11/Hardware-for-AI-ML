%%writefile codefest/cf03/copt/nn_forward_gpu.py
import sys
import torch
import torch.nn as nn

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

if device.type != "cuda":
    print("No CUDA GPU found. Exiting.")
    sys.exit(0)

print("CUDA GPU is available.")
print("Device name:", torch.cuda.get_device_name(0))
print()

model = nn.Sequential(
    nn.Linear(4, 5),
    nn.ReLU(),
    nn.Linear(5, 1)
).to(device)

x = torch.randn(16, 4).to(device)

output = model(x)

print("Input tensor shape: ", x.shape)
print("Output tensor shape:", output.shape)
print()

print("Input is on GPU: ", x.is_cuda)
print("Output is on GPU:", output.is_cuda)
