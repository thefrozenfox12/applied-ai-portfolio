# Run and deploy Signal

Signal has two entry points:

- `/` — upload and classify reviews with the Python service.
- `/dashboard.html` — inspect the bundled reference analysis. This file also opens offline.

In a standalone HTML file or web preview, the reference dashboard’s Upload reviews button opens setup instructions. When served by this Python application, it opens the upload workspace. A preview URL by itself does not imply that the backend is running.

The upload service accepts UTF-8 CSV files for any product, up to 2 MB and 500 reviews per batch. Users select the review-text column and optional title column. Neither a star rating nor a product identifier is required. Additional columns are discarded before classification. The product/batch name labels the results; it is not passed to the model.

## Configuration

Set these variables in your shell or hosting provider's secret settings:

| Variable | Purpose |
|---|---|
| `REVIEW_BASE_URL` | OpenAI-compatible API base URL, ending in `/v1` |
| `REVIEW_MODEL` | Model identifier with support for the request schema below |
| `REVIEW_API_KEY` | Provider API key, kept only on the server |
| `APP_ACCESS_TOKEN` | Random workspace token of at least 24 characters; given to authorized users |
| `PORT` | HTTP port, default `8000` |
| `ALLOW_HTTP_MODEL` | Set to `1` only to permit a trusted remote HTTP model endpoint; HTTPS is the default requirement |

Generate the workspace token with `python -c "import secrets; print(secrets.token_urlsafe(32))"`. The workspace token is separate from the model API key. It authorizes model usage and access to batch results; share it only with your trusted team. The browser keeps it in memory, not local storage. A page refresh requires reconnecting; the last batch ID is retained in session storage for that browser tab.

The provider must implement `POST /chat/completions`, strict `response_format: json_schema`, and the model request's `seed`, `temperature`, `max_tokens`, and `chat_template_kwargs` settings. The original Qwen-compatible request is retained in `pipeline.py`. Compatibility with a different provider must be checked before deployment; an OpenAI-compatible URL alone does not establish support for every parameter. The reference model name is recorded in the saved results. Do not use a shared educational endpoint as an unrestricted public service.

## Local use — Windows PowerShell

From the extracted project folder:

```powershell
$env:REVIEW_BASE_URL = "https://your-model-provider.example/v1"
$env:REVIEW_MODEL = "your-model-name"
$env:REVIEW_API_KEY = "your-provider-key"
$env:APP_ACCESS_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"
$env:APP_ACCESS_TOKEN
python server.py
```

Open `http://localhost:8000`, enter the workspace token, and upload a CSV. Python 3.10+ is sufficient; no runtime packages are needed for local use. The built-in server binds to localhost and is for local development.

## Local use — macOS/Linux

```sh
export REVIEW_BASE_URL="https://your-model-provider.example/v1"
export REVIEW_MODEL="your-model-name"
export REVIEW_API_KEY="your-provider-key"
export APP_ACCESS_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
printf '%s\n' "$APP_ACCESS_TOKEN"
python server.py
```

Example files use `title,text` headers, but the upload interface lets users map other column names. `example_reviews.csv` contains three explicitly illustrative reviews, not measured evaluation data.

## Docker deployment

Copy `.env.example` to `.env` and replace the placeholders, then:

```sh
docker build -t signal-reviews .
docker run --rm --env-file .env -p 127.0.0.1:8000:8000 signal-reviews
```

For hosting, deploy this Dockerfile as a **single, always-on instance**, add the same environment variables as secrets, and expose the configured port through the host's HTTPS ingress. Use `/healthz` for liveness. It does not verify provider credentials; the workspace connection checks configuration, and a small real batch verifies provider connectivity and schema compatibility. Never expose a non-TLS remote login endpoint. A static-only host can serve the reference dashboard but cannot run upload classification.

The container uses a non-root user and Gunicorn with one process and four request threads. One process is required because jobs live in memory. Do not increase worker count, add replicas, enable automatic worker recycling, or scale to zero while a batch is running. Gunicorn configuration reference: https://docs.gunicorn.org/en/stable/settings.html .

## Batch behavior and limits

- One active batch per workspace; three independent model requests run concurrently.
- Positive/negative is the default. Neutral-enabled requests use a separate prompt and receive no binary answers or history.
- Explicit star phrases are masked with the same heuristic used in the reference analysis.
- Each row is limited to 20,000 combined title/text characters. Invalid files are rejected before inference.
- Progress updates as each review finishes. Failed rows remain failed, and the completed counts exclude them.
- Results CSV includes every row, its status, sentiment, emotion, explanation, and any sanitized error. Export is enabled when processing ends. Potential spreadsheet formulas are escaped.
- Results expire 30 minutes after completion and are removed on the next batch/status request. At most 10 batches are retained. A process restart loses all jobs. There is no database or uploaded-file persistence.
- Closing the page does not cancel the server batch. Reopen the same tab, reconnect, and resume status updates. Provider usage may still be charged for in-flight or retried requests.
- Review text goes to the configured provider; its data-retention terms apply. CSV metadata is not sent to that provider. The server temporarily receives the complete CSV to parse the selected columns.

This is a deployable single-owner/trusted-team service. Public self-service would require individual accounts, durable jobs, per-user quotas, billing controls, and an explicit retention policy before opening access. The access token is a shared workspace credential, not a multi-tenant account system.

Uploaded batches report classifications and emotions, not benchmark accuracy. They do not run the separate NRC lexicon evaluation; that remains in the reference analysis. No uploaded results are fed back into either classifier.

## Verification

```sh
python -m unittest discover -p 'test_*.py' -v
python verify_results.py
python dashboard.py
python report.py
```

`verify_upload.cjs` runs an end-to-end browser check against a local **simulated** model endpoint via the real Python HTTP request path. It covers upload, mapping, both modes, metadata exclusion, progress, failed rows, filtering, export, and mobile layout. Install Playwright and a browser as described in `verify_browser.cjs`, then run `node verify_upload.cjs`. These tests do not validate a hosted provider's uptime or model quality. Before a public deployment, configure your chosen provider and run `example_reviews.csv` once to verify that connection.
