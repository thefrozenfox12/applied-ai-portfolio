# Publication and deployment boundaries

The public package contains source code, review data, prompts, model responses, statistics, screenshots, and placeholder/test configuration. It must not contain deployment credentials, real environment files, private keys, checkpoints, or provider error logs.

Model-provider keys and workspace access tokens are supplied at runtime. The model key remains on the Python server. The workspace token is intentionally given to authorized users; it allows classification requests and access to that shared workspace. Never use a provider API key as the workspace token.

The inference gateway address is not included in public experiment metadata or as a code default. Configure `REVIEW_BASE_URL` explicitly. A private checkpoint fingerprint detects an endpoint change when resuming work; checkpoints are excluded from publication.

## What remains public

- Fixed random seeds, model identifiers, prompts, request hashes, response IDs, and model-server fingerprints document the experiment. They are not designed as secrets or authentication mechanisms. Never derive a deployment password or access token from these values.
- `.env.example` contains placeholders. Unit and integration fixtures contain clearly marked fake credentials for local simulated services. Neither is a deployment credential.
- Raw model responses are required evidence. The checked-in responses contain no authorization headers or credential-named fields. Empty transfer-related response fields do not grant access.
- Dataset and NRC source URLs are public references and remain cited.

## Server checks

Only explicitly allowlisted interface files are served. Environment files, Python source, test fixtures, result files, arbitrary paths, and traversal paths are not HTTP download routes. Reference results are intentionally public inside `dashboard.html`.

All `/api/` routes require the workspace token, including configuration and job-status routes. Missing/invalid tokens are rejected. Provider errors sent to the browser are replaced with a generic row error. The server does not return its provider key or endpoint in configuration responses.

This is a single-owner or trusted-team service with one shared token, not a system with isolated user accounts. Use HTTPS and a randomly generated workspace token, keep the model credential in hosting secrets, and use a dedicated provider account/credential with appropriate spending limits. Do not deploy using test credentials or a shared course gateway.

## Review limits

The publication review scans the exact deliverable archive and standalone HTML, examines saved response fields, verifies placeholder/test matches, and exercises authentication and static-file boundaries. This is not a guarantee against every possible vulnerability or an audit of the external model gateway itself.

Earlier exported copies are not revoked by replacing these files. If a real credential has reached an unintended audience, remove the exposed copy where possible and have the credential owner rotate/revoke it. Removing an endpoint address alone is not access control.
