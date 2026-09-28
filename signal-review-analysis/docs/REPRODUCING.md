# Reproduce the project

## View or verify without credentials

Open `dashboard.html` directly in a browser. Everything it needs is embedded; the page makes no network requests. It starts in Overview with binary (positive/negative) classifications on the first 100 reviews. The classification and sample selectors are always available above both views; choose Three-class to include neutral. Use Validation for performance metrics, uncertainty, NRC comparisons, prompts, and source details. The review table has an optional rating-comparison checkbox; technical evidence in each review opens on demand.

Python 3.10+ is sufficient for all analysis and saved-output checks. There are no third-party Python dependencies. From the project folder:

```sh
python -m unittest discover -p 'test_*.py' -v
python verify_results.py
python dashboard.py
python report.py
```

The verifier reconstructs all request bodies, checks 500 request hashes, checks sample identities, recalculates metrics and tie sensitivity, and reproduces the seeded bootstrap intervals. This path does not download data, load an API key, or make model calls.

The GitHub Actions workflow repeats these checks and checks that generated HTML/README files match the committed outputs. It is configured for Python 3.10, 3.12, and 3.13. A local pass is not a claim that the remote workflow has run; consult the repository's Actions tab after publication.

## Make new model calls

Set `REVIEW_API_KEY` to your model provider key. Also set `REVIEW_BASE_URL`; `REVIEW_MODEL` is optional for the offline pipeline; see `.env.example`. No environment file is automatically loaded. Do not commit credentials.

Windows PowerShell: run `./run.ps1` and enter the class key when prompted.

macOS/Linux: set `REVIEW_API_KEY` in the shell, then run `./run.sh`.

The equivalent steps are:

```sh
python pipeline.py prepare
python pipeline.py spotcheck
python pipeline.py binary
python pipeline.py three_class
python experiments.py all
python emotions.py all
python analysis.py
python verify_results.py
python dashboard.py
python report.py
```

`prepare` downloads the original Gift Cards gzip, validates fields, and recreates the original first-100 and fixed-seed stratified samples. `experiments.py` adds binary on the stratified sample and three-class on the first 100. No prompt includes previous outputs.

Checkpoints live in `results/*_checkpoint.json`. With identical settings they resume missing reviews. To intentionally rerun every request, archive/remove the relevant checkpoints first. A changed prompt or script/configuration causes a checkpoint mismatch, rather than silently mixing experiments. If changing the model, prompts, or dataset, regenerate all four runs to preserve comparable settings, and retain the prior snapshot separately.

The official NRC lexicon is downloaded as needed. It is not included in the repository because its terms prohibit redistribution. The full Amazon source file is also excluded; selected reviews are included with the predictions so the dashboard can be inspected without downloading the source.

After rerunning, inspect every report conclusion and recapture screenshots. Changing a prompt based on evaluation errors requires a separate development sample and an untouched test sample if claiming improvement.

## Browser verification and screenshots

Node.js and Playwright are optional development dependencies:

```sh
npm install --no-save playwright
npx playwright install chromium
node verify_browser.cjs
```

For an existing Chromium installation, set `CHROME_EXECUTABLE` to its executable path. The script checks all four experiment views, displayed metrics, filters, matrix cells, detail dialogs, exported files, interval labels, comparison transitions, and mobile overflow. It also captures the screenshots in `assets/`. `results/browser_checks.json` records the local test result.

## Main files

| File | Purpose |
|---|---|
| `server.py`, `upload.html`, `upload.js`, `app.css` | Authenticated upload workspace and batch classification |
| `Dockerfile`, `gunicorn.conf.py` | Single-instance deployment |
| `pipeline.py` | Source loading, masks, samples, model requests and required scoring |
| `experiments.py` | Supplementary calls with frozen prompts and identical samples |
| `emotions.py` | Independent NRC occurrence-count scoring |
| `analysis.py` | Tie sensitivity, paired transitions and stratified uncertainty |
| `dashboard.py`, `dashboard.html.template` | Offline interface generation |
| `report.py` | Report generation from saved evidence |
| `prompts/` | Two exact classification prompts |
| `results/` | Samples, source provenance, raw responses, metrics and checks |
| `test_pipeline.py`, `test_analysis.py`, `verify_results.py` | Python integrity checks |
| `verify_browser.cjs` | Browser assertions and screenshot capture |

## Submit

Publish the project folder's contents to your own GitHub repository, including README, code, saved results, screenshots, and workflow. Do not include `data/`, credentials, checkpoints, or environment dependencies. Use the README as the project entry point and review its interpretation before publishing.

## Classify uploaded reviews

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Python upload workspace, server configuration, Docker deployment, and limits. Reference analysis remains reproducible independently of the upload service.
