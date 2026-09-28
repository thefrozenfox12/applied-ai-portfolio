"""Generate a review analysis report from the saved numerical evidence."""
from pipeline import ROOT, read
from experiments import EXPERIMENTS


def pct(value):
    return f'{100 * value:.1f}%'


def matrix_table(run):
    labels = run['metrics']['labels']
    rows = run['metrics']['matrix']
    return ('| Actual / Predicted | ' + ' | '.join(c.title() for c in labels) + ' |\n'
            + '|---|' + '---:|' * len(labels) + '\n'
            + '\n'.join('| ' + c.title() + ' | ' + ' | '.join(map(str, row)) + ' |'
                        for c, row in zip(labels, rows)))


def build():
    runs = {name: read(ROOT / f'results/{name}.json') for name in EXPERIMENTS}
    analysis = read(ROOT / 'results/analysis.json')
    dataset = read(ROOT / 'results/dataset.json')
    binary, three = runs['binary'], runs['three_class']
    bm, tm = binary['metrics'], three['metrics']
    sensitivity = analysis['runs']['three_class']['emotion_sensitivity']
    interval = analysis['runs']['three_class']['uncertainty']['intervals']['accuracy']
    comparisons = '| Sample | Task | Role | Agreement | Majority baseline | Macro F1 |\n|---|---|---|---:|---:|---:|\n'
    for name in ['binary', 'three_class_first100', 'binary_balanced', 'three_class']:
        item = analysis['runs'][name]
        m = item['metrics']
        comparisons += f"| {'First 100' if item['sample_key'] == 'binary' else 'Stratified 150'} | {'Binary' if item['mode'] == 'binary' else 'Three-class'} | {item['role']} | {pct(m['accuracy'])} | {pct(m['majority_baseline'])} | {m['macro_f1']:.3f} |\n"
    first_three = runs['three_class_first100']['metrics']
    balanced_binary = runs['binary_balanced']['metrics']
    pair = analysis['paired']['balanced150']
    emotion = three['emotion_metrics']
    neutral = tm['matrix'][1]
    examples = [r for r in three['rows'] if r['actual'] != r['prediction']['sentiment']][:2]
    example_text = '\n'.join(f"- **{r['id']} — {r['title']}**: rating-derived {r['actual'].lower()}, predicted {r['prediction']['sentiment'].lower()}. The saved explanation says: {r['prediction']['reason']}" for r in examples)
    content = f'''# Signal — review sentiment & emotion

**Classify product reviews from their text, inspect sentiment and emotion, and export the results.** Python handles classification; the browser provides the workspace. Developed with AI assistance and retained model evidence.

## Run the workspace

The upload workspace accepts a UTF-8 CSV for any product, with a required review-text column and optional title column. Binary mode is the default; three-class mode adds neutral. Only the selected text fields enter model requests. Batch progress, failed-row status, search, sentiment filters, and CSV export are included.

Configure the model connection and workspace access token, then run `python server.py` and open `http://localhost:8000`. A Dockerfile and Gunicorn configuration provide a deployable single-instance service. See [deployment and configuration](docs/DEPLOYMENT.md). The provider must support the existing structured-output request schema.

Uploaded data is kept temporarily in memory; this version targets a single owner or trusted team. It does not include individual accounts or durable job storage. No provider credentials are exposed to the browser.

![Upload workspace with illustrative input](assets/upload-workspace.png)

## Reference analysis

Open [dashboard.html](dashboard.html) in a browser. It opens with binary (positive/negative) results for the first 100 reviews: sentiment totals, a compact rating-agreement and class-error summary, common emotions, and searchable reviews. Classification and sample selectors remain visible in both views, including the optional three-class mode. A separate Validation view contains experiment comparisons, scoring, and technical evidence. The reference dashboard works offline; uploaded-review classification uses the Python server and a model connection. Python performs sampling, model requests, scoring, emotion analysis, and report/dashboard generation; HTML/CSS/JavaScript provide the interface.

![Signal dashboard](assets/dashboard-desktop.png)

## Main finding

The reference binary run achieves **{pct(bm['accuracy'])}** rating agreement, but simply predicting the majority class achieves **{pct(bm['majority_baseline'])}**. The reference balanced three-class run achieves **{pct(tm['accuracy'])}**, with only **{neutral[1]}/50** neutral reviews correctly identified. The useful result is the pattern of failures, not the headline accuracy alone.

The dataset contains **{dataset['total']:,}** reviews; **{pct((dataset['ratings']['4'] + dataset['ratings']['5']) / dataset['total'])}** have four or five stars. The first 100 contain **{bm['per_class']['POSITIVE']['support']}** positives and **{bm['per_class']['NEGATIVE']['support']}** negatives. Negative recall is **{bm['per_class']['NEGATIVE']['correct']}/{bm['per_class']['NEGATIVE']['support']} ({pct(bm['per_class']['NEGATIVE']['recall'])})**, while negative precision is **{pct(bm['per_class']['NEGATIVE']['precision'])}**. An apparently strong accuracy therefore coexists with less convincing minority-class performance.

## Reference results and error directions

Ratings define the evaluation benchmark: binary 4–5 → positive and 1–3 → negative; three-class 4–5 → positive, 3 → neutral, and 1–2 → negative. **Ratings never enter model requests.** Rows below are rating-derived labels; columns are predictions.

**First 100, binary**

{matrix_table(binary)}

**Stratified 150, three-class**

{matrix_table(three)}

Of the 50 neutrals, **{neutral[0]}** become positive and **{neutral[2]}** become negative. Positive and negative recall are each **{tm['per_class']['POSITIVE']['correct']}/50** and **{tm['per_class']['NEGATIVE']['correct']}/50**, respectively. Equal sampling makes neutral-class failure visible. It does not establish whether a mismatch is a model error or a disagreement between the review’s language and its star rating.

Illustrative mismatches follow. Model explanations are generated claims to inspect, not verified reasons:

{example_text}

## Controlled supplementary comparison

The original prompts are frozen and run independently on both identical samples. The two original reference outputs are preserved. No request receives the other task’s answers, and no human labels are required.

{comparisons}
The 150-review sample contains 50 reviews per **three-class rating label**. Under binary scoring, it has 50 positives and 100 negatives, hence a different majority baseline. This comparison holds the sample constant when changing task, and the task constant when changing sample. The scoring targets still differ; the table is not a leaderboard of interchangeable classifiers.

Holding the binary task fixed, agreement is **{pct(bm['accuracy'])}** on the first sample and **{pct(balanced_binary['accuracy'])}** on the stratified sample. For three-class scoring, it is **{pct(first_three['accuracy'])}** versus **{pct(tm['accuracy'])}**. Crucially, the high first-100 three-class score hides **{first_three['per_class']['NEUTRAL']['correct']}/{first_three['per_class']['NEUTRAL']['support']}** neutral reviews correctly identified. The extra runs expose a specific neutral-class weakness rather than treating every difference as an effect of balancing.

On the same stratified reviews, **{pair['same_polarity']}** retain their polarity, **{pair['to_neutral']}** become neutral, and **{pair['opposite_polarity']}** switch between positive and negative when moving from the binary prompt to the three-class prompt. These are paired prediction descriptions, not causal estimates; calls used the same named model/settings at different times.

The three-class agreement’s approximate **95% sampling interval is {pct(interval['low'])}–{pct(interval['high'])}**, using 10,000 bootstrap resamples within the original rating strata, seed 6419. Per-class intervals appear in the dashboard. They assume independent reviews within strata and describe the designed mixture, not population-prevalence accuracy, benchmark validity, or model-run variability. No population intervals are reported for the ordered first-100 sample. [Method and limitations](docs/DECISIONS.md).

## Emotion comparison and tie sensitivity

On the reference balanced run, exact primary-emotion agreement is **{emotion['agreement_count']}/150 ({pct(emotion['agreement_rate'])})**. NRC produces **{emotion['ties']}** maximum-score ties and **{emotion['no_signal']}** no-signal reviews. It counts word occurrences across eight emotions without stemming, negation, or sarcasm handling; the LLM considers context. Alphabetical tie-breaking selects a single NRC primary label, and no matched emotion word produces `none`.

Restricting **both** sensitivity measures to the **{sensitivity['signal_n']}** reviews with NRC signal, exact agreement is **{sensitivity['exact_signal_count']}/{sensitivity['signal_n']} ({pct(sensitivity['exact_signal_rate'])})**. Accepting any tied highest-scoring emotion raises compatibility to **{sensitivity['top_set_count']}/{sensitivity['signal_n']} ({pct(sensitivity['top_set_rate'])})**: **{sensitivity['tie_break_only_count']}** additional cases depend on which tied label is selected. This relaxed measure is not emotion accuracy and does not replace the required primary-label comparison. Neither method has human emotion ground truth.

## Engineering choices, issues, and checks

Explicit rating phrases are masked in title/text; original text and exact masked input remain inspectable. The binary prompt uses a documented negative fallback for genuinely balanced/factual/no-evidence reviews. Temperature 0 and fixed seeds improve repeatability, while saved responses remain authoritative because inference can still vary.

An initial response failed schema validation despite JSON-object mode. We switched to strict output enums/schema and reran both original experiments consistently. Checkpoint handling was fixed to retain completed work when another review fails. A browser installer returned a truncated archive; a working browser binary enabled real interface testing. Browser assertions separately read confusion-cell counts and percentages to avoid concatenating them during validation.

Python checks verify request isolation, masks, mappings, raw responses, all four samples, tie behavior, paired transitions, and reproducible uncertainty. Reference-dashboard browser checks compare displayed figures and filters against saved output, inspect small bars and mobile overflow, and confirm zero network requests. Separate upload tests exercise the browser-to-Python-to-provider request path using a local simulated endpoint. GitHub Actions is configured to verify and rebuild the saved project without credentials; remote CI status is only established after publication.

See the [requirements review](docs/REQUIREMENTS_REVIEW.md) for the evidence checklist and remaining publication/author-review steps.

Publication notes and deployment boundaries are documented in [SECURITY.md](SECURITY.md). The inference endpoint is configured privately; public experiment metadata omits its address.

## Reproduce and inspect

```sh
python -m unittest discover -p 'test_*.py' -v
python verify_results.py
python dashboard.py
python report.py
```

Python 3.10+; local use and offline analysis require no third-party Python dependencies. Linux deployment uses the pinned server dependency in `requirements-server.txt`. [Full reproduction instructions and file map](docs/REPRODUCING.md) · [Decision log and architecture](docs/DECISIONS.md). Upload calls use an explicitly configured model endpoint and environment-supplied key. Downloaded source data, the NRC lexicon, credentials, and checkpoints are excluded from the repository.

The upload service is tested with a local simulated provider. A real provider connection must be configured and verified before hosting; no live deployment is claimed.

## Sources

- McAuley Lab, UC San Diego: [Amazon Reviews ’23](https://amazon-reviews-2023.github.io/) and [Gift Cards source file](https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Gift_Cards.jsonl.gz). Hou et al. (2024), *Bridging Language and Items for Retrieval and Recommendation*.
- This project uses the [NRC Word-Emotion Association Lexicon](https://saifmohammad.com/WebPages/NRC-Emotion-Lexicon.htm), created by Saif M. Mohammad and Peter D. Turney at the National Research Council Canada. Mohammad & Turney (2013), *Crowdsourcing a Word–Emotion Association Lexicon*, Computational Intelligence 29(3), 436–465. The lexicon is downloaded separately for educational use and is not redistributed.
'''
    (ROOT / 'README.md').write_text(content, encoding='utf-8')
    print('README.md regenerated from saved evidence.')

if __name__ == '__main__':
    build()
