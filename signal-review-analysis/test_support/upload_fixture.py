"""Local simulated provider used only by verify_upload.cjs; never loaded by server.py."""
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from wsgiref.simple_server import make_server
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

captured = []
class Model(BaseHTTPRequestHandler):
    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        captured.append(data)
        review = json.loads(data['messages'][1]['content'])
        time.sleep(.05)
        if 'FAIL_TEST' in review['text']:
            self.send_response(503); self.end_headers(); self.wfile.write(b'private upstream failure'); return
        labels = data['response_format']['json_schema']['schema']['properties']['sentiment']['enum']
        sentiment = 'NEGATIVE' if 'broken' in review['text'].lower() else 'NEUTRAL' if 'factual' in review['text'].lower() and 'NEUTRAL' in labels else 'POSITIVE'
        prediction = {'sentiment': sentiment, 'emotion': 'none', 'reason': 'Simulated model response for an integration test.'}
        body = json.dumps({'choices': [{'message': {'content': json.dumps(prediction)}}]}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    def log_message(self, *args): pass

provider = ThreadingHTTPServer(('127.0.0.1', 0), Model)
threading.Thread(target=provider.serve_forever, daemon=True).start()
os.environ.update(REVIEW_BASE_URL=f'http://127.0.0.1:{provider.server_port}/v1', REVIEW_API_KEY='test-only-provider-key', REVIEW_MODEL='simulated-model', APP_ACCESS_TOKEN='test-token-for-local-tests-only-12345')
def app(env, start):
    if env['PATH_INFO'] == '/__test_requests':
        body = json.dumps(captured).encode(); start('200 OK', [('Content-Type', 'application/json')]); return [body]
    return server.application(env, start)
with make_server('127.0.0.1', 0, app) as httpd:
    print(json.dumps({'url': f'http://127.0.0.1:{httpd.server_port}'}), flush=True)
    httpd.serve_forever()
