#!/usr/bin/env python3
"""
Extract rows from specified Excel sheets where LOINC LCN column is non-empty.
Outputs the collated results to a TSV file.
Supports comparison with earlier version for duplicate detection and merging.

Example usage:

* merge with the diff mapping in a specific sheet of an Excel spreadsheet:

   python ./util/xlsx2tsv.py -p ./out/StudyDescription_mapping_table.tsv --merged mapping_merged.tsv --sheets StudyDescription_diffs ./out/Mapping\ StudyDescription_diffs\ 2025-12-10.xlsx

* merge with the per-modality mapping in an Excel spreadsheet:

    python ./util/xlsx2tsv.py -p ./out/StudyDescription_mapping_table.tsv --merged mapping_merged.tsv ./out/pending_StudyDescription_diffs_by_modality.xlsx    
"""

import pandas as pd
import argparse
import sys
import os


# Hardcoded list of sheet names to process (based on modalities)
DEFAULT_SHEETS = [
    "XR",
    "CT",
    "MR", 
    "NM,PT",
    "US",
    "MG",
    "XA",
    "RF"
]


def load_previous_mapping(previous_file):
    """
    Load previous version of the mapping file.
    
    Args:
        previous_file: Path to previous TSV/CSV file
        
    Returns:
        DataFrame with previous mapping data, or None if file doesn't exist
    """
    if not previous_file or not os.path.exists(previous_file):
        return None
    
    try:
        # Detect file format from extension
        if previous_file.endswith('.tsv'):
            df = pd.read_csv(previous_file, sep='\t')
        else:
            df = pd.read_csv(previous_file)
        print(f"Loaded previous mapping from: {previous_file}")
        print(f"  Rows in previous mapping: {len(df)}")
        return df
    except Exception as e:
        print(f"Warning: Could not load previous mapping file: {e}", file=sys.stderr)
        return None


def validate_column_compatibility(new_df, previous_df):
    """
    Validate that column names and order are identical in both dataframes.
    
    Args:
        new_df: DataFrame with newly extracted data
        previous_df: DataFrame with previous mapping data
        
    Returns:
        True if columns match, False otherwise. Prints detailed error messages.
    """
    new_cols = list(new_df.columns)
    prev_cols = list(previous_df.columns)
    
    if new_cols != prev_cols:
        print(f"Error: Column mismatch between new and previous mappings.", file=sys.stderr)
        print(f"\nNew mapping columns: {new_cols}", file=sys.stderr)
        print(f"Previous mapping columns: {prev_cols}", file=sys.stderr)
        
        # Identify differences
        missing_in_prev = set(new_cols) - set(prev_cols)
        missing_in_new = set(prev_cols) - set(new_cols)
        
        if missing_in_prev:
            print(f"\nColumns in new but not in previous: {list(missing_in_prev)}", file=sys.stderr)
        if missing_in_new:
            print(f"Columns in previous but not in new: {list(missing_in_new)}", file=sys.stderr)
        
        # Check order mismatch even if same columns
        common_cols = set(new_cols) & set(prev_cols)
        if new_cols != prev_cols and common_cols == set(new_cols) == set(prev_cols):
            print(f"\nColumn order mismatch detected.", file=sys.stderr)
        
        return False
    
    return True


def find_duplicates(new_df, previous_df):
    """
    Identify rows in new_df that match rows in previous_df.
    Matching is based on all columns being identical.
    
    Args:
        new_df: DataFrame with newly extracted data
        previous_df: DataFrame with previous mapping data
        
    Returns:
        Tuple of (duplicate_rows_df, unique_rows_df)
    """
    if previous_df is None or len(previous_df) == 0:
        return pd.DataFrame(), new_df
    
    # Ensure both dataframes have the same columns (use new_df's columns as reference)
    cols_to_compare = [col for col in new_df.columns if col in previous_df.columns]
    
    # Create a merged dataframe to identify matches
    merged = pd.merge(
        new_df,
        previous_df[cols_to_compare],
        on=cols_to_compare,
        how='left',
        indicator=True
    )
    
    # Rows that exist in both are marked as "both"
    duplicates = merged[merged['_merge'] == 'both'].drop(columns=['_merge'])
    unique_new = merged[merged['_merge'] == 'left_only'].drop(columns=['_merge'])
    
    # Reset indices
    duplicates = duplicates.reset_index(drop=True)
    unique_new = unique_new.reset_index(drop=True)
    
    return duplicates, unique_new


def merge_mappings(new_df, previous_df, duplicates):
    """
    Merge new and previous mappings, with new entries added.
    
    Args:
        new_df: DataFrame with newly extracted data
        previous_df: DataFrame with previous mapping data
        duplicates: DataFrame with duplicate rows
        
    Returns:
        Merged DataFrame containing both previous and new unique data
    """
    if previous_df is None:
        return new_df
    
    # Get unique new rows (not in duplicates)
    unique_new = new_df[~new_df.index.isin(duplicates.index)]
    
    # Combine previous with new unique rows
    merged = pd.concat([previous_df, unique_new], ignore_index=True)
    
    return merged


def extract_excel_sheets(input_file, output_file, target_column, sheet_names, 
                        previous_file=None, merged_output=None):
    """
    Extract rows from specified Excel sheets where target column is non-empty.
    
    Args:
        input_file: Path to input Excel file
        output_file: Path to output TSV file for extracted data
        target_column: Name of column to check for non-empty values
        sheet_names: List of sheet names to process
        previous_file: Optional path to previous version for duplicate detection
        merged_output: Optional path to save merged mapping
    
    Returns:
        Tuple of (extracted_df, merged_df or None)
    """
    
    if not os.path.exists(input_file):
        print(f"Error: Input file '{input_file}' not found.", file=sys.stderr)
        sys.exit(1)
    
    # Read Excel file to get available sheets
    try:
        excel_file = pd.ExcelFile(input_file)
        available_sheets = excel_file.sheet_names
        print(f"Found {len(available_sheets)} sheets in '{input_file}'")
    except Exception as e:
        print(f"Error reading Excel file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Collect data from all sheets
    all_data = []
    processed_count = 0
    skipped_count = 0
    
    for sheet_name in sheet_names:
        if sheet_name not in available_sheets:
            print(f"Warning: Sheet '{sheet_name}' not found in Excel file. Skipping.")
            skipped_count += 1
            continue
        
        try:
            # Read the sheet
            df = pd.read_excel(input_file, sheet_name=sheet_name)
            
            if target_column not in df.columns:
                print(f"Warning: Column '{target_column}' not found in sheet '{sheet_name}'. Skipping.")
                skipped_count += 1
                continue
            
            # Filter rows where target column is non-empty
            # Check for both NaN and empty strings
            mask = df[target_column].notna() & (df[target_column].astype(str).str.strip() != '')
            filtered_df = df[mask].copy()
            
            # rename column "Suggested LOINC Code" to "LOINC Code" and
            # "LOINC LCN" to "L-Long Common Name"
            if 'Suggested LOINC code' in filtered_df.columns:
                filtered_df.rename(columns={'Suggested LOINC code': 'LOINC code'}, inplace=True)
            if 'LONIC code' in filtered_df.columns:
                filtered_df.rename(columns={'LONIC code': 'LOINC code'}, inplace=True)
            if 'LOINC LCN' in filtered_df.columns:
                filtered_df.rename(columns={'LOINC LCN': 'L-Long Common Name'}, inplace=True)
            
            # Add a column to track which sheet the data came from
            filtered_df['Source_Sheet'] = sheet_name
            
            rows_extracted = len(filtered_df)
            if rows_extracted > 0:
                all_data.append(filtered_df)
                print(f"Extracted {rows_extracted} rows from sheet '{sheet_name}'")
                processed_count += 1
            else:
                print(f"No non-empty '{target_column}' values found in sheet '{sheet_name}'")
                
        except Exception as e:
            print(f"Error processing sheet '{sheet_name}': {e}", file=sys.stderr)
            skipped_count += 1
            continue
    
    # Combine all data
    if not all_data:
        print("Error: No data extracted from any sheets.", file=sys.stderr)
        sys.exit(1)
    
    combined_df = pd.concat(all_data, ignore_index=True)

    print(combined_df.columns)
    # drop all columns except "LOINC Code", "L-Long Common Name", "Modality" and "StudyDescription"
    columns_to_keep = ['Modality', 'StudyDescription', 'LOINC code', 'L-Long Common Name']
    combined_df = combined_df[[col for col in columns_to_keep if col in combined_df.columns]]
    
    print(f"\nExtraction Summary:")
    print(f"  Sheets processed: {processed_count}")
    print(f"  Sheets skipped: {skipped_count}")
    print(f"  Total rows extracted: {len(combined_df)}")
    
    # Load previous mapping if provided
    previous_df = load_previous_mapping(previous_file)
    merged_df = None
    
    # Detect duplicates if previous file exists
    if previous_df is not None:
        # Validate column compatibility before proceeding with merge
        if not validate_column_compatibility(combined_df, previous_df):
            print(f"\nError: Cannot proceed with merge due to column mismatch.", file=sys.stderr)
            print(f"Aborting merge operation.", file=sys.stderr)
            return combined_df, None
        
        duplicates, unique_new = find_duplicates(combined_df, previous_df)
        
        print(f"\nDuplicate Detection Summary:")
        print(f"  Rows already in previous mapping (duplicates): {len(duplicates)}")
        print(f"  New unique rows: {len(unique_new)}")
        
        # Report duplicates as warnings
        if len(duplicates) > 0:
            print(f"\nDuplicate entries found:")
            for idx, row in duplicates.iterrows():
                print(f"  Warning: Duplicate found - Modality: '{row.get('Modality', 'N/A')}', "
                      f"StudyDescription: '{row.get('StudyDescription', 'N/A')}'")
        
        # Create merged mapping
        if merged_output:
            merged_df = merge_mappings(combined_df, previous_df, duplicates)
            print(f"\nMerged mapping created:")
            print(f"  Total rows in merged mapping: {len(merged_df)}")
    
    # Save extracted data to TSV
    try:
        combined_df.to_csv(output_file, sep='\t', index=False)
        print(f"\nExtracted data saved to: {output_file}")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Save merged mapping if applicable
    if merged_df is not None and merged_output:
        try:
            merged_df.to_csv(merged_output, sep='\t', index=False)
            print(f"Merged mapping saved to: {merged_output}")
        except Exception as e:
            print(f"Error writing merged output file: {e}", file=sys.stderr)
            sys.exit(1)
    
    return combined_df, merged_df


def main():
    parser = argparse.ArgumentParser(
        description='Extract rows from Excel sheets where specified column is non-empty. '
                    'Optionally compare with previous version to detect duplicates and merge.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s input.xlsx
  %(prog)s input.xlsx --output results.tsv
  %(prog)s input.xlsx --column "LOINC code" --output custom_output.tsv
  %(prog)s input.xlsx --previous out/previous_mapping.tsv --merged out/merged_mapping.tsv
        """
    )
    
    parser.add_argument(
        'input',
        help='Path to input Excel file'
    )
    
    parser.add_argument(
        '--output', '-o',
        default='out/extracted_studydescriptions.tsv',
        help='Path to output TSV file for extracted data (default: out/extracted_studydescriptions.tsv)'
    )
    
    parser.add_argument(
        '--column', '-c',
        default='LOINC LCN',
        help='Name of column to check for non-empty values (default: LOINC LCN)'
    )
    
    parser.add_argument(
        '--sheets', '-s',
        #nargs='+',
        default=",".join(DEFAULT_SHEETS),
        help=f'List of sheet names to process (default: {",".join(DEFAULT_SHEETS)})'
    )
    
    parser.add_argument(
        '--previous', '-p',
        help='Path to previous version of mapping file for duplicate detection'
    )
    
    parser.add_argument(
        '--merged', '-m',
        help='Path to save merged mapping (previous + new unique rows). Requires --previous.'
    )
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(args.output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Validate merged output argument
    if args.merged and not args.previous:
        print("Error: --merged requires --previous to be specified.", file=sys.stderr)
        sys.exit(1)
    
    # Process the Excel file
    extract_excel_sheets(
        input_file=args.input,
        output_file=args.output,
        target_column=args.column,
        sheet_names=args.sheets.split(","),
        previous_file=args.previous,
        merged_output=args.merged
    )


if __name__ == '__main__':
    main()
