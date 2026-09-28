"""Authenticated, bounded batch classification service and static application."""
import csv
import io
import json
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse
from wsgiref.simple_server import make_server

from pipeline import LABELS, call, clean

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 2 * 1024 * 1024
MAX_ROWS = 500
MAX_TEXT = 20000
TTL = 1800
JOBS = {}
LOCK = threading.Lock()
ACTIVE = threading.Lock()


def parse_csv(content, text_column, title_column=''):
    if not isinstance(content, str) or len(content.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Choose a UTF-8 CSV smaller than 2 MB.')
    try:
        reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff')), strict=True)
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)) or any(not h.strip() for h in headers):
            raise ValueError('Column names must be nonempty and unique.')
        if text_column not in headers or (title_column and title_column not in headers):
            raise ValueError('Select valid review text and optional title columns.')
        if text_column == title_column:
            raise ValueError('Title and review text must use different columns.')
        rows = []
        for index, row in enumerate(reader, 1):
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f'CSV row {index} has a different number of columns.')
            title = row.get(title_column, '').strip()
            text = row[text_column].strip()
            if not text:
                raise ValueError(f'CSV row {index} has no review text.')
            if len(title) + len(text) > MAX_TEXT:
                raise ValueError(f'CSV row {index} exceeds 20,000 characters.')
            rows.append({'id': index, 'title': title, 'text': text})
            if len(rows) > MAX_ROWS:
                raise ValueError('Upload at most 500 reviews per batch.')
        if not rows:
            raise ValueError('The CSV contains no reviews.')
        return rows
    except csv.Error as exc:
        raise ValueError('The CSV is malformed. Check quoting and column separators.') from exc


def configuration_error():
    if not all(os.environ.get(k) for k in ('REVIEW_API_KEY', 'REVIEW_BASE_URL', 'REVIEW_MODEL')):
        return 'The server needs its model endpoint, model name, and API key configured.'
    endpoint = urlparse(os.environ['REVIEW_BASE_URL'])
    if endpoint.scheme not in ('http', 'https') or not endpoint.hostname or endpoint.username or endpoint.password:
        return 'The model endpoint is invalid.'
    if endpoint.scheme != 'https' and endpoint.hostname not in ('localhost', '127.0.0.1', '::1') and os.environ.get('ALLOW_HTTP_MODEL') != '1':
        return 'Use HTTPS for the model endpoint, or explicitly enable a trusted HTTP endpoint.'
    return None


def purge():
    for key in list(JOBS):
        if JOBS[key].get('finished_at', float('inf')) < time.time() - TTL:
            del JOBS[key]


def process(job_id):
    try:
        with LOCK:
            job = JOBS[job_id]
            job['status'] = 'running'
            rows, mode = job['rows'], job['mode']
        def classify(row):
            result = call(clean(row['title']), clean(row['text']), mode)
            return result['prediction']
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(classify, row): row for row in rows}
            for future in as_completed(futures):
                row = futures[future]
                try:
                    prediction = future.result()
                    update = {'prediction': prediction, 'status': 'complete'}
                except Exception:
                    update = {'status': 'failed', 'error': 'The model could not classify this review. Retry it in a new batch.'}
                with LOCK:
                    row.update(update)
                    job['completed'] += 1
        with LOCK:
            job['status'] = 'complete' if all(r['status'] == 'complete' for r in rows) else 'partial'
            job['finished_at'] = time.time()
    finally:
        ACTIVE.release()


def application(environ, start_response):
    def respond(status, body, mime='application/json'):
        data = json.dumps(body, ensure_ascii=False).encode() if mime == 'application/json' else body
        start_response(status, [('Content-Type', mime), ('Content-Length', str(len(data))),
                                ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'),
                                ('Referrer-Policy', 'no-referrer'), ('X-Frame-Options', 'DENY')])
        return [data]

    path, method = environ.get('PATH_INFO', '/'), environ.get('REQUEST_METHOD', 'GET')
    if not path.startswith('/api/'):
        files = {'/': ('upload.html', 'text/html; charset=utf-8'), '/upload.html': ('upload.html', 'text/html; charset=utf-8'),
                 '/dashboard.html': ('dashboard.html', 'text/html; charset=utf-8'), '/upload.js': ('upload.js', 'text/javascript; charset=utf-8'),
                 '/app.css': ('app.css', 'text/css; charset=utf-8'), '/example_reviews.csv': ('example_reviews.csv', 'text/csv; charset=utf-8')}
        if path == '/healthz' and method == 'GET':
            return respond('200 OK', {'status': 'ok'})
        if method != 'GET' or path not in files:
            return respond('404 Not Found', {'error': 'Not found.'})
        file, mime = files[path]
        body = (ROOT / file).read_bytes()
        if file == 'dashboard.html':
            body = body.replace(b'<meta name="signal-workspace" content="offline">',
                                b'<meta name="signal-workspace" content="connected">', 1)
        return respond('200 OK', body, mime)

    token = os.environ.get('APP_ACCESS_TOKEN', '')
    provided = environ.get('HTTP_AUTHORIZATION', '')
    if len(token) < 24:
        return respond('503 Service Unavailable', {'error': 'The server needs an access token of at least 24 characters.'})
    if not secrets.compare_digest(provided.encode(), ('Bearer ' + token).encode()):
        return respond('401 Unauthorized', {'error': 'Enter a valid workspace access token.'})
    if path == '/api/config' and method == 'GET':
        error = configuration_error()
        return respond('200 OK', {'ready': error is None, 'message': error, 'max_rows': MAX_ROWS, 'max_bytes': MAX_BYTES})
    if path.startswith('/api/jobs/') and method == 'GET':
        with LOCK:
            purge()
            job = JOBS.get(path[len('/api/jobs/'):])
            if job is None:
                return respond('404 Not Found', {'error': 'This batch expired or the server restarted. Upload again to classify.'})
            return respond('200 OK', job)
    if path == '/api/jobs' and method == 'POST':
        error = configuration_error()
        if error:
            return respond('503 Service Unavailable', {'error': error})
        try:
            length = int(environ.get('CONTENT_LENGTH') or 0)
            if not 0 < length <= MAX_BYTES * 3:
                return respond('413 Payload Too Large', {'error': 'The upload is too large.'})
            data = json.loads(environ['wsgi.input'].read(length))
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object.')
            mode = data.get('mode', 'binary')
            if mode not in LABELS:
                raise ValueError('Choose binary or three-class classification.')
            name = data.get('name', 'Uploaded reviews')
            if not isinstance(name, str) or len(name) > 120:
                raise ValueError('The product name must be 120 characters or fewer.')
            rows = parse_csv(data.get('csv'), data.get('text_column'), data.get('title_column', ''))
        except (ValueError, TypeError, UnicodeError) as exc:
            # Validation messages never include source review content or provider credentials.
            message = str(exc) if type(exc) is ValueError else 'Invalid upload. Check the CSV and column selections.'
            return respond('400 Bad Request', {'error': message})
        if not ACTIVE.acquire(blocking=False):
            return respond('409 Conflict', {'error': 'A batch is already running. Wait for it to finish before starting another.'})
        job_id = secrets.token_urlsafe(24)
        with LOCK:
            purge()
            while len(JOBS) >= 10:
                del JOBS[next(iter(JOBS))]
            JOBS[job_id] = {'id': job_id, 'name': name.strip() or 'Uploaded reviews', 'mode': mode,
                            'status': 'queued', 'total': len(rows), 'completed': 0, 'created_at': time.time(),
                            'rows': [{**r, 'status': 'pending'} for r in rows]}
        threading.Thread(target=process, args=(job_id,), daemon=True).start()
        return respond('202 Accepted', {'id': job_id})
    return respond('404 Not Found', {'error': 'Not found.'})


if __name__ == '__main__':
    from socketserver import ThreadingMixIn
    from wsgiref.simple_server import WSGIServer
    class ThreadedServer(ThreadingMixIn, WSGIServer):
        daemon_threads = True
    port = int(os.environ.get('PORT', '8000'))
    print(f'Signal: http://127.0.0.1:{port} (local development server)', flush=True)
    with make_server('127.0.0.1', port, application, server_class=ThreadedServer) as httpd:
        httpd.serve_forever()
