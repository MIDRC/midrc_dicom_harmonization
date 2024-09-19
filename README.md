# MIDRC DICOM metadata harmonization

## Background

This repository is intended to maintain the resources related to harmonization of DICOM attributes as part of MIDRC Data Quality and Harmonization working group.

Content and structure of the repository are open for revisions and suggestions. This repository was set up following the discussion and decisons made at the MIDRC DQH meeting on August 11, 2021.

The MIDRC-LOINC mapping table provides a means of normalizing DICOM metadata, including unstructured character string fields, for the purposes of secondary cohort selection or other analysis. The primary purpose of DICOM (Digital Imaging and Communications in Medicine) medical images are for local clinical interpretation. MIDRC (Medical Image and Data Resource Center) is an NIBIB-funded collection of de-identified DICOM images collected for secondary research uses, including AI research. The mapping table is used to convert the pair of Modality and Study Description terms in a DICOM-format image to a LOINC (Logical Observation Identifiers Names and Codes) code and its associated Long Common Name, which is unique. Long Common Name then acts a normalized study description. The LOINC code also provides other attributes for cohort selection, including body region (with allowed modifiers), presence and/or absence of contrast, and other information. The MIDRC-LOINC mapping table is publicly available on Github and is updated by the MIDRC Data Quality and Harmonization (DQH) subcommittee.

## Organization

Folders and their designations:

* `in`: folder containing source values observed in the DICOM data by the data collecting sites. One comma- or tab-delimited file is expected for each of the data collecting sites. Suggested file names are `<DICOM attribute name>_<data collection site>.csv`. Date does not need to be present in the file name, as the modification date will be maintained via revision history.

* `out`: folder containing output artifacts mapping the selected DICOM attributes into harmonized values or codes. Suggested file nameing conventions: `<DICOM attribute name>_filtering_values.csv` and `<DICOM attribute name>_mapping_table.csv`.

* `pending`: folder containing `StudyDescription` values that are not mapped.

## Contact

This repository was initially populated by Andrey Fedorov `fedorov@bwh.harvard.edu`. DQH lead contact Paul Kinahan `kinahan@uw.edu`.
