# External import source

Terraria Color uses an external community spreadsheet as a catalog import source,
including a dedicated `Walls` sheet. The workbook is not the project maintainer's
own work and is **not redistributed with this repository**.

Users who want to rerun import tools must obtain the spreadsheet separately and
place their local Excel copy at:

```text
source/all_items_terraria_145.xlsx
```

The workbook is ignored by Git. This README is versioned; do not force-add the
workbook. Normal website use does not require the workbook or any import step.

## External resources and provenance

- Original external resource identified by the maintainer:
  [Google Sheet](https://docs.google.com/spreadsheets/d/1hAqhW9MsFDNWKiZHKZpic_pVkG1La5Ic6ezRObr-aK0/edit?usp=sharing).
- Related resource:
  [Steam guide — Terraria All items spreadsheet](https://steamcommunity.com/sharedfiles/filedetails/?id=3424697275),
  published by `carrotm0nster`.

The Steam guide links to the Google Sheet above. This supports the association
between the resources, but does not establish that the local workbook is an
unaltered export of a particular online revision. The Google Sheet contents
could not be independently inspected during this documentation update.

## Optional reproducibility reference

The following is the **SHA-256 of the current local workbook version used by
the maintainer**, recorded on 2026-09-30. It is not a checksum published by the
external resource's author and does not identify the latest online version.

```text
CF1C1ADB1B9053EFE7467CE1B656F7CBBA6CAAFA459C4D82A9E035EEF0A8EB62
```

To compare your own local copy in PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath source/all_items_terraria_145.xlsx
```

A different export or revision can have a different checksum. The filename is
the path expected by this project, not independent proof of the contents' version.

## Rights and terms

The external spreadsheet is not covered by any Terraria Color source-code
license. Terraria / Re-Logic assets and external community resources have their
own rights and applicable terms, which must be checked with their respective
sources. Linking to these resources does not grant redistribution permission.

This repository makes no claim of ownership over the spreadsheet and no claim
that permission to redistribute it has been verified. See [NOTICE.md](../NOTICE.md)
for the project's broader attribution and licensing status.
