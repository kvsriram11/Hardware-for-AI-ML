from contextlib import redirect_stdout
from torchvision.models import resnet18
from torchinfo import summary

model = resnet18()
model.eval()

output_file = "codefest/cf01/profiling/resnet18_profile.txt"

with open(output_file, "w", encoding="utf-8") as f:
    with redirect_stdout(f):
        summary(
            model,
            input_size=(1, 3, 224, 224),
            col_names=("input_size", "output_size", "num_params", "mult_adds", "trainable"),
            depth=6,
            verbose=1,
        )

print(f"Saved torchinfo profile to {output_file}")