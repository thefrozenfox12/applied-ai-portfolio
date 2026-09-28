# Requirements review

Reviewed 2026-09-28 against **MBAX 6418 Assignment 1.pdf**, seven pages. This review covers the original reference-analysis deliverable and distinguishes the optional upload service from it. Application screens retain product-oriented wording.

## Findings

The reference-analysis code and dashboard cover the seven technical stages. The upload extension has not replaced the scoring, NRC comparison, balanced results, or evidence files. The personal public repository has now been created. The author’s review of the report and Canvas submission remain separate steps.

| Requirement | Finding | Evidence |
|---|---|---|
| Python classification/scoring; OpenAI-compatible endpoint (p. 1) | Implemented | `pipeline.py` performs requests and scoring; saved configurations identify the model; endpoint addresses are withheld from public artifacts. HTML is an explicitly permitted interface. |
| Read the Gift Cards dataset (pp. 1–2) | Verified | Original compressed file SHA-256 and all 152,410 rating counts match `results/dataset.json`. The first 100 saved rows match the source. |
| Structured binary prompt; title/text only; obvious-example checks (p. 2) | Verified | `prompts/binary.txt`; strict JSON sentiment enums; four saved positive/negative spot checks in `results/spotchecks.json`. No neutral label is allowed in binary output. |
| Score 100 rows, rating ≥4 positive and otherwise negative (pp. 2–3) | Verified | `results/binary.json`: 94/100 agree, versus 93% majority baseline. Matrix rows/columns positive, negative: `[[88,5],[1,6]]`. Rating fields are absent from all reconstructed requests. |
| Polished dashboard, headline quality and class errors (p. 3) | Implemented and browser-checked | Overview includes agreement, baseline, correct counts by class, and most common error direction. Validation adds matrices and detailed metrics. Dark/green theme has an accent picker under Method. |
| Correct/mismatched filtering and live counts (p. 3) | Browser-checked | Reviews → Show rating comparison exposes agreement filters. Matrix cells also filter reviews. Displayed counts match saved rows in all four runs. |
| Independent LLM and NRC emotion predictions; agreement and divergence (pp. 3–4) | Verified | `emotions.py` independently calculates word counts and deterministic primary labels. All 500 saved NRC calculations were recalculated from the downloaded lexicon and matched exactly. Both emotion labels, aggregate comparisons, ties, and examples remain under Validation. |
| Three classes and reproducible balanced selection (p. 4) | Verified | `results/three_class.json` has 50 positive, 50 neutral, and 50 negative rating labels, selected from the whole source using seed 6418. Reconstructing selection from the source reproduces exactly the saved ordered IDs. Ratings map 4–5 / 3 / 1–2. |
| Carry three-class mode through prompt, scoring, and display (p. 4) | Verified | Three-class selector updates all counts, filters, quality summaries, matrices, emotion comparisons, and exports. Matrix: `[[48,2,0],[6,12,32],[0,2,48]]`; 108/150 agree (72%). Of 50 neutral reviews, 32 are classified negative and 6 positive. |
| Descriptive/prediction visuals, browser checks, small bars (p. 4) | Verified | Rating distributions, predicted sentiment shares, confusion matrices, per-class recall, and the overview quality summary use saved metrics. Browser checks cover data agreement and nonzero rating bars. |
| README report, screenshots, sources, prompts/code/generator/raw balanced output (p. 5) | Present | Root `README.md`, `assets/`, both prompts, `pipeline.py`, `emotions.py`, `dashboard.py`, and `results/three_class.json` are included. Each balanced row retains the raw provider response. README discusses imbalance, matrix error directions, emotion differences, and development issues; data sources are cited. |
| Author checks and rewrites the report in their own voice (p. 5) | Still required | Automated evidence checks support review; they cannot establish that Donovan personally reviewed and owns the interpretation. |
| Personal GitHub repository and shareable Canvas submission link (pp. 5–7) | Repository created; Canvas submission remains | The project is being published at https://github.com/thefrozenfox12/applied-ai-portfolio/tree/main/signal-review-analysis . The author must verify the final link and submit it through Canvas. |

## Upload-link defect and fix

The previous upload control was a relative link to `upload.html`. Its fallback handled only `file:` URLs. An HTTPS file preview therefore attempted navigation to a page that was not part of that preview, consistent with the reported blocked-site message.

The control is now a button. In a standalone file or web preview, it opens an in-page explanation of how to start the Python workspace and does not request another page. The Python service marks the dashboard response as connected; only that served version navigates to the real upload route. This avoids mistaking a hosted HTML preview for a running backend.

The behavior was tested both in a simulated HTTPS preview (no outbound navigation) and through the actual Python service (upload page loads). The user's exact preview host was not directly inspected.

## Scope of the upload extension

Uploading reviews is additional functionality, not a replacement for the evaluated reference runs. Uploaded CSVs use the same independent sentiment/emotion prompts and rating-phrase masking. They do not calculate rating agreement or NRC emotions: those features remain in the reference analysis. No accuracy or emotion-validation claim is made for arbitrary uploaded products. The configured provider must be tested before hosting; browser upload tests use a local simulated provider through the actual Python HTTP request path.

Public hosting is not a submission requirement. An offline dashboard is explicitly permitted. Conversely, running or hosting the upload service does not satisfy the separate GitHub-repository requirement.

## Checks completed

- 17 Python unit/service tests passed.
- 159 reference-dashboard browser assertions passed, including all four run selections and preview-safe upload navigation; zero external requests or JavaScript errors.
- 38 upload browser assertions passed against a local simulated provider, including navigation from the Python-served reference dashboard.
- All 500 saved model requests, predictions, output hashes, scoring metrics, paired comparisons, and seeded uncertainty estimates verified.
- Original dataset hash/counts, first-100 row identity, full-source fixed-seed balanced selection, all NRC row calculations, and four saved prompt spot checks independently verified.

No new model calls to a real provider were needed for this review. The saved original predictions and reported results are unchanged. Public endpoint metadata is redacted; see SECURITY.md for the publication review.
