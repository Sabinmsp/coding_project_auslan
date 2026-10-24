import torch

data = torch.load(
    "video_55.pt",
    map_location="cpu",
    weights_only=False
)

print("Clips inside video_55.pt:")

for clip_name in data.keys():
    print(clip_name)