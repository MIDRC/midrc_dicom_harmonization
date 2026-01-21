#!/usr/bin/env python3
"""
Analyze differences between input StudyDescription/Modality combinations
and the existing mapping table. Output unmapped items to pending directory.
Also provides validation of the mapping table for consistency.

This script compares DICOM metadata from data collection sites against the
harmonized mapping table to identify StudyDescription/Modality combinations
that need LOINC mapping.

In validation mode, it checks the mapping table for:
1. Same Modality/StudyDescription with different LOINC codes
2. Same LOINC code with different L-Long Common Names

Example usage:
    python util/analyze_in_out.py .
    python util/analyze_in_out.py /path/to/repo
    python util/analyze_in_out.py --validate
    python util/analyze_in_out.py --validate /path/to/repo
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


def validate_mapping_table(repo_path):
    """
    Validate the mapping table for inconsistencies.

    Performs two checks:
    1. Identifies rows with same Modality and StudyDescription but different LOINC codes
    2. Identifies rows with same LOINC code but different L-Long Common Names

    Note: This validation works with the original, non-exploded Modality values
    (e.g., "CT,MR" remains as-is, not split into separate rows).

    Args:
        repo_path: Path to repository root directory

    Returns:
        bool: True if validation passes (no issues found), False otherwise
    """
    print("Validating mapping table...")

    # Load the original mapping table (DO NOT explode Modality column)
    mapping_file_path = os.path.join(repo_path, OUTPUT_SUBDIR, MAPPING_FILE)

    if not os.path.exists(mapping_file_path):
        print(f"Error: Mapping file not found: {mapping_file_path}", file=sys.stderr)
        sys.exit(1)

    try:
        mapping_df = pd.read_csv(mapping_file_path, sep='\t')
    except Exception as e:
        print(f"Error reading mapping file: {e}", file=sys.stderr)
        sys.exit(1)

    # Normalize for consistent comparison (but DO NOT explode Modality)
    # Remove all spaces from Modality (including spaces around commas)
    mapping_df["Modality"] = mapping_df["Modality"].str.replace(" ", "")

    # Normalize StudyDescription
    mapping_df["StudyDescription"] = mapping_df["StudyDescription"].str.replace(WHITESPACE_PATTERN, "", regex=True)
    mapping_df["StudyDescription"] = mapping_df["StudyDescription"].str.upper()

    # Normalize LOINC code and L-Long Common Name columns
    mapping_df["LOINC code"] = mapping_df["LOINC code"].str.replace(WHITESPACE_PATTERN, "", regex=True)
    mapping_df["L-Long Common Name"] = mapping_df["L-Long Common Name"].str.replace(WHITESPACE_PATTERN, " ", regex=True)
    mapping_df["L-Long Common Name"] = mapping_df["L-Long Common Name"].str.strip()

    validation_passed = True

    # Check 1: Same Modality and StudyDescription but different LOINC codes
    print("\nCheck 1: Identifying rows with same Modality and StudyDescription but different LOINC codes...")

    duplicates_by_desc_mod = mapping_df.groupby(["Modality", "StudyDescription"])["LOINC code"].nunique()
    inconsistent_desc_mod = duplicates_by_desc_mod[duplicates_by_desc_mod > 1]

    if len(inconsistent_desc_mod) > 0:
        validation_passed = False
        print(f"  ERROR: Found {len(inconsistent_desc_mod)} Modality/StudyDescription combinations with inconsistent LOINC codes:")
        for (modality, study_desc), count in inconsistent_desc_mod.items():
            print(f"\n    Modality: {modality}, StudyDescription: {study_desc}")
            affected_rows = mapping_df[
                (mapping_df["Modality"] == modality) &
                (mapping_df["StudyDescription"] == study_desc)
            ][["Modality", "StudyDescription", "LOINC code", "L-Long Common Name"]]
            print(f"    Different LOINC codes found ({count} unique):")
            for _, row in affected_rows.iterrows():
                print(f"      - LOINC: {row['LOINC code']}, Name: {row['L-Long Common Name']}")
    else:
        print("  PASS: No inconsistencies found for Modality/StudyDescription combinations")

    # Check 2: Same LOINC code but different L-Long Common Names
    print("\nCheck 2: Identifying rows with same LOINC code but different L-Long Common Names...")

    duplicates_by_loinc = mapping_df.groupby("LOINC code")["L-Long Common Name"].nunique()
    inconsistent_loinc = duplicates_by_loinc[duplicates_by_loinc > 1]

    if len(inconsistent_loinc) > 0:
        validation_passed = False
        print(f"  ERROR: Found {len(inconsistent_loinc)} LOINC codes with inconsistent L-Long Common Names:")
        for loinc_code, count in inconsistent_loinc.items():
            print(f"\n    LOINC code: {loinc_code}")
            affected_rows = mapping_df[mapping_df["LOINC code"] == loinc_code][["Modality", "StudyDescription", "LOINC code", "L-Long Common Name"]].drop_duplicates()
            print(f"    Different L-Long Common Names found ({count} unique):")
            for _, row in affected_rows.iterrows():
                print(f"      - Modality: {row['Modality']}, StudyDescription: {row['StudyDescription']}")
                print(f"        L-Long Common Name: {row['L-Long Common Name']}")
    else:
        print("  PASS: No inconsistencies found for LOINC code mappings")

    # Check 3: Same StudyDescription (ignoring Modality) with different LOINC codes
    print("\nCheck 3: Identifying StudyDescriptions with multiple LOINC codes across different Modalities...")

    duplicates_by_desc_only = mapping_df.groupby("StudyDescription")["LOINC code"].nunique()
    inconsistent_desc_only = duplicates_by_desc_only[duplicates_by_desc_only > 1]

    if len(inconsistent_desc_only) > 0:
        print(f"  WARNING: Found {len(inconsistent_desc_only)} StudyDescriptions with multiple LOINC codes across different Modalities:")
        for study_desc, count in inconsistent_desc_only.items():
            print(f"\n    StudyDescription: {study_desc}")
            affected_rows = mapping_df[
                mapping_df["StudyDescription"] == study_desc
            ][["Modality", "StudyDescription", "LOINC code", "L-Long Common Name"]].drop_duplicates()
            print(f"    Different LOINC codes found ({count} unique):")
            for _, row in affected_rows.iterrows():
                print(f"      - Modality: {row['Modality']}, LOINC: {row['LOINC code']}")
                print(f"        Name: {row['L-Long Common Name']}")
    else:
        print("  PASS: No StudyDescriptions with multiple LOINC codes found")

    # Summary
    print("\n" + "="*70)
    if validation_passed:
        print("VALIDATION PASSED: No inconsistencies found in mapping table")
        print("="*70)
        return True
    else:
        print("VALIDATION FAILED: Inconsistencies found in mapping table")
        print("="*70)
        return False


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
  %(prog)s --validate
  %(prog)s --validate /path/to/repo
        """
    )

    parser.add_argument(
        'repo_path',
        nargs='?',
        default='.',
        help='Path to repository root directory (default: current directory)'
    )

    parser.add_argument(
        '--validate',
        action='store_true',
        help='Validate the mapping table for inconsistencies instead of analyzing input/output differences'
    )

    args = parser.parse_args()

    # Validate repository path
    if not os.path.exists(args.repo_path):
        print(f"Error: Repository path does not exist: {args.repo_path}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.repo_path):
        print(f"Error: Repository path is not a directory: {args.repo_path}", file=sys.stderr)
        sys.exit(1)

    # Execute workflow based on mode
    try:
        if args.validate:
            # Run validation mode
            validation_passed = validate_mapping_table(args.repo_path)
            sys.exit(0 if validation_passed else 1)
        else:
            # Run normal analysis mode
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
