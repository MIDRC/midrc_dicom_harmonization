import pandas as pd
import sys, os
import re

contributors = ["ACR", "RSNA", "TCIA"]

in_content = {}

out_df = pd.read_csv(os.path.join(sys.argv[1], "out", "StudyDescription_mapping_table.csv"))

all_diffs = None

pattern = r"^\s+|\s+$|\s+(?=\s)"

for contributor in contributors:
    print(f"Loading {contributor}")
    if contributor == "TCIA":
      print("Parse TCIA")
      in_df = pd.read_csv(os.path.join(sys.argv[1], "in", f"StudyDescriptions_{contributor}.tsv"), sep="\t")
    else:
      in_df = pd.read_csv(os.path.join(sys.argv[1], "in", f"StudyDescriptions_{contributor}.csv"))

    # clean up spaces
    in_df["StudyDescription"] = in_df["StudyDescription"].str.replace(pattern, " ")
    out_df["StudyDescription"] = out_df["StudyDescription"].str.replace(pattern, " ")

    # capitalize
    in_df['StudyDescription'] = in_df['StudyDescription'].str.upper()
    out_df['StudyDescription'] = out_df['StudyDescription'].str.upper()

    diff_df = pd.merge(in_df, out_df, on=["StudyDescription", "Modality"], how="outer", indicator=True)
    diff_df = diff_df[diff_df["_merge"] == "left_only"]

    #print("Merge result")
    #print(diff_df)
    diff_df["Contributor"] = contributor

    print(diff_df)

    if not "frequency" in diff_df.columns:
      diff_df["frequency"] = "N/A"

    if all_diffs is None:
      all_diffs = diff_df[["StudyDescription", "Modality_x", "frequency", "Contributor"]]
    else:
      all_diffs = pd.concat([all_diffs, diff_df[['StudyDescription', 'Modality_x','frequency', 'Contributor']]])

# rename columns
all_diffs = all_diffs.rename(columns={"frequency_x": "frequency"})
all_diffs = all_diffs.rename(columns={"Modality_x": "Modality"})

all_diffs.sort_values(by=["frequency"], inplace=True)

all_diffs.to_csv(os.path.join(sys.argv[1], "pending", "StudyDescription_diffs.csv"), index=False)
