#!/usr/bin/env python3
"""
Analyze differences between input StudyDescription/Modality combinations
and the existing mapping table. Output unmapped items to pending directory.

This script compares DICOM metadata from data collection sites against the
harmonized mapping table to identify StudyDescription/Modality combinations
that need LOINC mapping.

Example usage:
    python util/analyze_in_out.py .
    python util/analyze_in_out.py /path/to/repo
    python util/analyze_in_out.py . --help
"""

import pandas as pd
import argparse
import sys
import os
import re


# File paths
INPUT_SUBDIR = "in"
OUTPUT_SUBDIR = "out"
PENDING_SUBDIR = "pending"
INPUT_FILE = "StudyDescriptions_Gen3.tsv"
MAPPING_FILE = "StudyDescription_mapping_table.tsv"
OUTPUT_FILE = "StudyDescription_diffs.csv"

# Data processing
WHITESPACE_PATTERN = r"^\s+|\s+$|\s+(?=\s)"
CONTRIBUTOR_NAME = "Gen3"
DEFAULT_FREQUENCY = "N/A"

# Columns
COLUMNS_OUTPUT = ["StudyDescription", "Modality", "frequency", "Contributor"]


def load_and_prepare_mapping_table(repo_path):
    """
    Load and prepare the mapping table for comparison.

    Handles comma-separated Modality values by creating both the original
    rows and exploded rows (one per modality). This ensures matching works
    for both single modalities and multi-modality entries.

    Args:
        repo_path: Path to repository root directory

    Returns:
        DataFrame with prepared mapping data (whitespace normalized,
        uppercase StudyDescription)

    Raises:
        SystemExit: If mapping file cannot be read
    """
    mapping_file_path = os.path.join(repo_path, OUTPUT_SUBDIR, MAPPING_FILE)

    if not os.path.exists(mapping_file_path):
        print(f"Error: Mapping file not found: {mapping_file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        print(f"Loading mapping table from: {mapping_file_path}")
        mapping_df = pd.read_csv(mapping_file_path, sep='\t')
    except Exception as e:
        print(f"Error reading mapping file: {e}", file=sys.stderr)
        sys.exit(1)

    # Remove spaces in Modality column
    mapping_df["Modality"] = mapping_df["Modality"].str.replace(" ", "")

    # Save original dataframe with comma-separated Modality values
    mapping_df_original = mapping_df.copy()

    # Split Modality column into array by comma
    mapping_df["Modality"] = mapping_df["Modality"].str.split(",")

    # Explode Modality column into multiple rows
    mapping_df_exploded = mapping_df.explode("Modality")

    # Union: combine original and exploded dataframes
    mapping_df = pd.concat([mapping_df_original, mapping_df_exploded], ignore_index=True)

    # Remove any duplicate rows
    mapping_df = mapping_df.drop_duplicates()

    # Normalize whitespace and case
    mapping_df["StudyDescription"] = mapping_df["StudyDescription"].str.replace(WHITESPACE_PATTERN, "", regex=True)
    mapping_df["StudyDescription"] = mapping_df["StudyDescription"].str.upper()

    print(f"  Loaded {len(mapping_df)} mapping entries (including exploded modalities)")

    return mapping_df


def load_and_clean_input_data(repo_path):
    """
    Load and clean input data from data collection site.

    Args:
        repo_path: Path to repository root directory

    Returns:
        DataFrame with cleaned input data, or None if file doesn't exist

    Raises:
        SystemExit: If file exists but cannot be read
    """
    input_file_path = os.path.join(repo_path, INPUT_SUBDIR, INPUT_FILE)

    if not os.path.exists(input_file_path):
        print(f"Input file not found: {input_file_path}")
        print("No input data to process.")
        return None

    try:
        print(f"Loading input data from: {input_file_path}")
        input_df = pd.read_csv(input_file_path, sep="\t")
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        sys.exit(1)

    # Clean up spaces
    input_df["StudyDescription"] = input_df["StudyDescription"].str.replace(WHITESPACE_PATTERN, "", regex=True)
    input_df["Modality"] = input_df["Modality"].str.replace(WHITESPACE_PATTERN, "", regex=True)

    # Capitalize for case-insensitive comparison
    input_df["StudyDescription"] = input_df["StudyDescription"].str.upper()

    print(f"  Loaded {len(input_df)} input records")

    return input_df


def find_unmapped_combinations(input_df, mapping_df):
    """
    Find StudyDescription/Modality combinations in input that are not in mapping.

    Uses outer merge with indicator to identify records that exist only in
    the input data (left_only).

    Args:
        input_df: DataFrame with input data from data collection site
        mapping_df: DataFrame with harmonized mapping table

    Returns:
        DataFrame with unmapped combinations
    """
    print("Finding unmapped StudyDescription/Modality combinations...")

    # Merge to find differences
    merged_df = pd.merge(
        input_df,
        mapping_df,
        on=["StudyDescription", "Modality"],
        how="outer",
        indicator=True
    )

    # Keep only records that exist in input but not in mapping
    unmapped_df = merged_df[merged_df["_merge"] == "left_only"].copy()

    # Add contributor information
    unmapped_df["Contributor"] = CONTRIBUTOR_NAME

    # Ensure frequency column exists
    if "frequency" not in unmapped_df.columns:
        unmapped_df["frequency"] = DEFAULT_FREQUENCY

    # Select and order output columns
    unmapped_df = unmapped_df[COLUMNS_OUTPUT]

    print(f"  Found {len(unmapped_df)} unmapped combinations")

    return unmapped_df


def save_differences(differences_df, repo_path):
    """
    Save unmapped combinations to pending directory.

    Args:
        differences_df: DataFrame with unmapped combinations
        repo_path: Path to repository root directory

    Raises:
        SystemExit: If output file cannot be written
    """
    if differences_df.empty:
        print("No differences found - all combinations are mapped!")
        return

    # Rename columns if needed (handle potential merge artifacts)
    if "frequency_x" in differences_df.columns:
        differences_df = differences_df.rename(columns={"frequency_x": "frequency"})

    # Sort by frequency (descending)
    differences_df = differences_df.sort_values(by=["frequency"], ascending=False)

    # Ensure output directory exists
    output_dir = os.path.join(repo_path, PENDING_SUBDIR)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Save to CSV
    output_file_path = os.path.join(output_dir, OUTPUT_FILE)

    try:
        differences_df.to_csv(output_file_path, index=False)
        print(f"\nUnmapped combinations saved to: {output_file_path}")
        print(f"  Total records: {len(differences_df)}")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)


def main():
    """
    Main entry point for the script.
    """
    parser = argparse.ArgumentParser(
        description='Analyze differences between input DICOM metadata and harmonized mapping table.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This script identifies StudyDescription/Modality combinations from data collection
sites that do not yet have LOINC mappings in the harmonized mapping table.

Examples:
  %(prog)s .
  %(prog)s /path/to/repo
        """
    )

    parser.add_argument(
        'repo_path',
        nargs='?',
        default='.',
        help='Path to repository root directory (default: current directory)'
    )

    args = parser.parse_args()

    # Validate repository path
    if not os.path.exists(args.repo_path):
        print(f"Error: Repository path does not exist: {args.repo_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.repo_path):
        print(f"Error: Repository path is not a directory: {args.repo_path}", file=sys.stderr)
        sys.exit(1)

    # Execute workflow
    try:
        # Load and prepare mapping table
        mapping_df = load_and_prepare_mapping_table(args.repo_path)

        # Load and clean input data
        input_df = load_and_clean_input_data(args.repo_path)

        # If no input data, exit gracefully
        if input_df is None:
            return

        # Find unmapped combinations
        differences_df = find_unmapped_combinations(input_df, mapping_df)

        # Save results
        save_differences(differences_df, args.repo_path)

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
