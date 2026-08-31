# PTA at NeurIPS 2026 short paper

This directory contains the anonymized four-page workshop manuscript.

- `main.tex`: paper source using the official NeurIPS 2026 double-blind workshop option.
- `neurips_2026.sty`: the official style supplied for this submission.
- `references.bib`: cited primary papers and model reports.
- `make_figures.py`: rebuilds the operation-profile figure from ignored canonical results.
- `figures/`: generated vector/raster figures.

The official PTA call explicitly says the NeurIPS paper checklist is not required, so
`checklist.tex` is intentionally not included. The supplied `neurips_2026.sty` is
included locally; one non-semantic trailing space was removed for repository hygiene.

Build from this directory on the repository's result-bearing workspace:

```powershell
python make_figures.py
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```
