import os
import torch
import pandas as pd
import numpy as np

# =========================================================
# SETTINGS
# =========================================================

PT_FILE = "video_1.pt"
EXCEL_FILE = "Auslan-Daily_Communication.xlsx"

OUTPUT_FOLDER = "extracted_keypoints"

# =========================================================
# CREATE OUTPUT FOLDER
# =========================================================

os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# =========================================================
# LOAD PT FILE
# =========================================================

print("\nLoading PT file...")

pt_data = torch.load(
    PT_FILE,
    map_location="cpu",
    weights_only=False
)

print("PT file loaded successfully.")

print("\nNumber of clips in PT file:", len(pt_data))

# =========================================================
# LOAD EXCEL FILE
# =========================================================

print("\nLoading Excel file...")

df = pd.read_excel(EXCEL_FILE)

print("Excel loaded successfully.")

print("\nExcel columns:")
print(df.columns.tolist())

# =========================================================
# CHECK REQUIRED COLUMN
# =========================================================

required_columns = ["Video_Clip_Name", "Subtitle"]

for column in required_columns:
    if column not in df.columns:
        raise ValueError(
            f"Column '{column}' was not found in Excel file.\n"
            f"Available columns: {df.columns.tolist()}"
        )

# =========================================================
# SHOW PT STRUCTURE
# =========================================================

print("\n" + "=" * 60)
print("FIRST PT CLIP STRUCTURE")
print("=" * 60)

first_clip_name = list(pt_data.keys())[0]
first_clip = pt_data[first_clip_name]

print("\nFirst clip:")
print(first_clip_name)

print("\nTop-level keys:")
print(first_clip.keys())

if "Annotation" in first_clip:
    print("\nAnnotation keys:")
    print(first_clip["Annotation"].keys())

    if "Signer" in first_clip["Annotation"]:
        print("\nSigner keys:")
        print(first_clip["Annotation"]["Signer"].keys())

# =========================================================
# EXTRACT ALL CLIPS
# =========================================================

summary_rows = []

print("\n" + "=" * 60)
print("EXTRACTING CLIPS")
print("=" * 60)

for clip_name, clip in pt_data.items():

    print("\n----------------------------------")
    print("Clip:", clip_name)

    # -----------------------------------------------------
    # FIND SUBTITLE FROM EXCEL
    # -----------------------------------------------------

    matching_rows = df[df["Video_Clip_Name"].astype(str) == str(clip_name)]

    if len(matching_rows) > 0:
        subtitle = str(matching_rows.iloc[0]["Subtitle"])
    else:
        subtitle = "NOT FOUND"

    print("Subtitle:", subtitle)

    # -----------------------------------------------------
    # ACCESS KEYPOINTS
    # -----------------------------------------------------

    try:
        signer_data = clip["Annotation"]["Signer"]

        kps = signer_data["KPS"]

    except KeyError as e:
        print("Could not find KPS:", e)
        continue

    # -----------------------------------------------------
    # CONVERT TO NUMPY
    # -----------------------------------------------------

    if torch.is_tensor(kps):
        kps = kps.detach().cpu().numpy()

    else:
        kps = np.asarray(kps)

    print("KPS shape:", kps.shape)

    # -----------------------------------------------------
    # READ SHAPE
    # -----------------------------------------------------

    if len(kps.shape) == 3:

        frames = kps.shape[0]
        keypoints = kps.shape[1]
        values = kps.shape[2]

        print("Frames:", frames)
        print("Keypoints per frame:", keypoints)
        print("Values per keypoint:", values)

    else:

        frames = len(kps)
        keypoints = "unknown"
        values = "unknown"

    # -----------------------------------------------------
    # SAVE KEYPOINTS
    # -----------------------------------------------------

    output_file = os.path.join(
        OUTPUT_FOLDER,
        f"{clip_name}.npy"
    )

    np.save(output_file, kps)

    print("Saved:", output_file)

    # -----------------------------------------------------
    # BBOX IF AVAILABLE
    # -----------------------------------------------------

    bbox_shape = None

    if "BBOX" in signer_data:

        bbox = signer_data["BBOX"]

        if torch.is_tensor(bbox):
            bbox = bbox.detach().cpu().numpy()

        else:
            bbox = np.asarray(bbox)

        bbox_shape = str(bbox.shape)

        print("BBOX shape:", bbox.shape)

    # -----------------------------------------------------
    # SAVE SUMMARY INFO
    # -----------------------------------------------------

    summary_rows.append({

        "Video_Clip_Name": clip_name,

        "Subtitle": subtitle,

        "Frames": frames,

        "Keypoints": keypoints,

        "Values_Per_Keypoint": values,

        "KPS_Shape": str(kps.shape),

        "BBOX_Shape": bbox_shape,

        "NPY_File": output_file

    })

# =========================================================
# SAVE SUMMARY CSV
# =========================================================

summary_df = pd.DataFrame(summary_rows)

summary_file = "clip_summary.csv"

summary_df.to_csv(
    summary_file,
    index=False
)

print("\n" + "=" * 60)
print("FINISHED")
print("=" * 60)

print("\nSummary saved to:")
print(summary_file)

print("\nKeypoints saved inside:")
print(OUTPUT_FOLDER)

# =========================================================
# PRINT FIRST 20 MATCHES
# =========================================================

print("\n" + "=" * 60)
print("FIRST 20 CLIPS")
print("=" * 60)

print(
    summary_df[
        [
            "Video_Clip_Name",
            "Subtitle",
            "Frames",
            "KPS_Shape"
        ]
    ].head(20).to_string(index=False)
)

# =========================================================
# LOOK AT ONE SPECIFIC CLIP
# =========================================================

TARGET_CLIP = "video_1_0"

print("\n" + "=" * 60)
print("TARGET CLIP")
print("=" * 60)

if TARGET_CLIP in pt_data:

    clip = pt_data[TARGET_CLIP]

    kps = clip["Annotation"]["Signer"]["KPS"]

    if torch.is_tensor(kps):
        kps = kps.detach().cpu().numpy()

    else:
        kps = np.asarray(kps)

    row = df[
        df["Video_Clip_Name"].astype(str)
        == TARGET_CLIP
    ]

    if len(row) > 0:
        subtitle = str(row.iloc[0]["Subtitle"])
    else:
        subtitle = "NOT FOUND"

    print("Clip:", TARGET_CLIP)
    print("Subtitle:", subtitle)
    print("Shape:", kps.shape)

    print("\nFirst frame:")
    print(kps[0])

    if len(kps) > 1:

        print("\nSecond frame:")
        print(kps[1])

else:

    print(
        TARGET_CLIP,
        "was not found in the PT file."
    )