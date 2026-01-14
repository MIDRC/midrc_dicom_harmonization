import pandas as pd
import sys, os
import re

in_content = {}

# read mapped values of StudyDescription/Modality combinations
out_df = pd.read_csv(os.path.join(sys.argv[1], "out", "StudyDescription_mapping_table.tsv"),sep='\t')

# remove spaces in Modality column
out_df["Modality"] = out_df["Modality"].str.replace(" ", "")

# Save original dataframe with comma-separated Modality values
out_df_original = out_df.copy()

# split Modality column into array by comma
out_df["Modality"] = out_df["Modality"].str.split(",")

# explode Modality column into multiple rows
out_df_exploded = out_df.explode("Modality")

# Union: combine original and exploded dataframes
out_df = pd.concat([out_df_original, out_df_exploded], ignore_index=True)

# Remove any duplicate rows
out_df = out_df.drop_duplicates()



all_diffs = None

# pattern to match leading, trailing, and multiple spaces
pattern = r"^\s+|\s+$|\s+(?=\s)"

   
fileName = os.path.join(sys.argv[1], "in", f"StudyDescriptions_Gen3.tsv")

if os.path.exists(fileName):
  
  print(f"Loading ...")
  in_df = pd.read_csv(fileName, sep="\t")

  """
  print("Initial in_df")
  print(in_df[in_df['StudyDescription'] == "XR CHEST 2 VIEWS"])
  print("Matches in out_df")
  print(out_df[out_df['StudyDescription'] == "XR CHEST 2 VIEWS"])

  out_df = out_df[out_df['StudyDescription'] == "XR CHEST 2 VIEWS"]
  in_df = in_df[in_df['StudyDescription'] == "XR CHEST 2 VIEWS"]
  """

  # clean up spaces
  in_df["StudyDescription"] = in_df["StudyDescription"].str.replace(pattern, "")
  in_df["Modality"] = in_df["Modality"].str.replace(pattern, "")
  out_df["StudyDescription"] = out_df["StudyDescription"].str.replace(pattern, "")

  # capitalize
  in_df['StudyDescription'] = in_df['StudyDescription'].str.upper()
  out_df['StudyDescription'] = out_df['StudyDescription'].str.upper()

  # merge to find differences
  diff_df = pd.merge(in_df, out_df, on=["StudyDescription", "Modality"], how="outer", indicator=True)
  diff_df = diff_df[diff_df["_merge"] == "left_only"]

  #print("Merge result")
  #print(diff_df)
  diff_df["Contributor"] = "Gen3"

  print(diff_df)

  if not "frequency" in diff_df.columns:
    diff_df["frequency"] = "N/A"

  if all_diffs is None:
    all_diffs = diff_df[["StudyDescription", "Modality", "frequency", "Contributor"]]
  else:
    all_diffs = pd.concat([all_diffs, diff_df[['StudyDescription', 'Modality','frequency', 'Contributor']]])

# rename columns if all_diffs is not empty only
if not all_diffs.empty:
  all_diffs = all_diffs.rename(columns={"frequency_x": "frequency"})

  all_diffs.sort_values(by=["frequency"], inplace=True, ascending=False)

  all_diffs.to_csv(os.path.join(sys.argv[1], "pending", "StudyDescription_diffs.csv"), index=False)
