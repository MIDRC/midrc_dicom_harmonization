# MIDRC DICOM metadata harmonization

## Background

This repository is intended to maintain the resources related to harmonization of DICOM attributes as part of MIDRC Data Quality and Harmonization working group.

Content and structure of the repository are open for revisions and suggestions. This is just an experiment in an attempt to improve communication between the parties involved in the harmonization effort, and facilitate visibility into the current status, per discussion at the DQH meeting on August 11, 2021.

## Organization

Folders and their designations:

* `in`: folder containing source values observed in the DICOM data by the data collecting sites. One comma- or tab-delimited file is expected for each of the data collecting sites. Suggested file names are `<DICOM attribute name>_<data collection site>.csv`. Date does not need to be present in the file name, as the modification date will be maintained via revision history.

* `out`: folder containing output artifacts mapping the selected DICOM attributes into harmonized values or codes. Suggested file nameing conventions: `<DICOM attribute name>_filtering_values.csv` and `<DICOM attribute name>_mapping_table.csv`.

## Contact

This repository was initially populated by Andrey Fedorov `fedorov@bwh.harvard.edu`. DQH lead contact Paul Kinahan `kinahan@uw.edu`.