# LSA extraction methodology: code, schema, prompt and audit verdicts

Code, schema, prompt and audit verdicts for the paper

> Falanga, G. N. (2026). *Extracting sign parameters from a printed Argentine Sign Language dictionary with a multimodal LLM: schema validation and a blind audit* [Manuscript submitted for publication].

The paper describes how a multimodal LLM (Gemini 3.1 Pro) extracted the phonological parameters of the signs of a 1997 Argentine Sign Language (LSA) dictionary into JSON, how the output was validated, and how a stratified sample of 150 signs was audited blind against the printed page.

## What is here

| Folder | Content |
|---|---|
| `prompt/` | The extraction prompt as it ran in its last revision, with the worked examples replaced by text written for this release, and the list of prompt revisions made during the run |
| `schema/` | The JSON Schema (draft-07) in force at the last scan |
| `examples/` | A constructed sign (not an LSA sign) in the extraction-time format |
| `code/audit/` | Scripts that prepared the audit and the external checks |
| `code/analysis/` | Scripts that computed the results of the paper |
| `code/viewer/` | The audit tool (Streamlit) and schema validator, as they were at the last scan of the run |
| `audit/` | Verdicts by opaque sign id: the audit, the first spreadsheet pass, the second auditor, and the auditor's own check of the assistant's comparison |
| `results/` | Aggregated audit results |
| `conformance/` | Schema validity of each batch against the schema of its date |

## Code

| Script | What it does |
|---|---|
| `audit/sample_audit_signs.py` | Draws the stratified audit sample (150 signs and a 10-sign pilot, seed 20261029) |
| `audit/build_audit_sheet.py` | Builds the blind audit workbook |
| `audit/build_audit_pack.py` | Builds the pages the auditor sees, with the entry framed and no extracted values |
| `audit/score_audit_text.py` | Parses the printed description of each entry and scores the written fields |
| `audit/build_assistant_check_sheet.py` | Builds the sheet for the auditor's own comparison of 30 signs and scores it against the assistant's |
| `audit/build_external_packs.py` | Builds the second auditor's pack (blind and value-in-view arms) and the annotation-from-scratch pack |
| `analysis/audit_results.py` | Accuracy by field and group, sign level, error types, calibration, prompt version, timing, anchoring |
| `analysis/second_auditor_results.py` | Agreement with the second auditor and the randomized anchoring test |
| `analysis/annotation_timing.py` | Time to annotate from scratch compared with the time to audit, per hand |
| `analysis/second_model_run.py` | Runs a second model (Claude Opus 5.5) in isolation on the audited pages and scores it against the same reference values as the first |
| `analysis/robustness.py` | Accuracy by provenance of each value, sign-level bootstrap intervals, sensitivity without the audit's equivalences, agreement between the model and both auditors, calibration (AUROC) and the effect of re-scanned batches |
| `analysis/schema_conformance.py` | Validity of each batch against the schema of its date |
| `analysis/text_layer.py` | Whether the model followed the image or the noisy embedded text layer |
| `analysis/trace_raw_ocr_history.py` | Rebuilds the last scan of each batch from version control (the evaluation baseline) |
| `analysis/baseline_numbers.py` | Recomputes the baseline figures quoted in the paper |
| `analysis/paper_figures.py` | Draws the figures of the paper |

Some strings in the code are in Spanish on purpose. The text parser matches the dictionary's own Spanish terms (the mapping is in Appendix A of the paper), and the sheets given to the second auditor, a Spanish speaker, were labelled in Spanish.

## What is not here, and why

The source dictionary (*Diccionario Lengua de Señas Argentina – Español*, Ministerio de Cultura y Educación de la Nación, 1997) is not reproduced. There are no pages, drawings, crops or text from it. The derived dataset is not released with this repository, because authorization to publish it was requested from the rights holder. For the same reason the verdicts carry only an opaque sign id, the field name and the verdict, never the gloss or the parameter values. The scripts expect the private data layout and will not run on this repository alone. Paths under `work/` and `data/` in the code stand for that private working data. They are released so that every number in the paper can be traced to the code that produced it.

## Licence

CC BY-NC 4.0 (see `LICENSE`). Non-commercial use only, with attribution. Commercial use requires a separate written licence from the author.

## Citation

See `CITATION.cff`.
