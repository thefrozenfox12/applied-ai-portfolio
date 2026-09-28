"""Offline service tests; model responses are simulated explicitly."""
import io
import json
import os
import time
import unittest
from unittest.mock import patch
import server
from pipeline import payload

ENV = {'APP_ACCESS_TOKEN': 'test-token-for-local-tests-only-12345', 'REVIEW_API_KEY': 'test-key',
       'REVIEW_BASE_URL': 'https://model.example/v1', 'REVIEW_MODEL': 'test-model'}


def request(path, method='GET', data=None, authenticated=True):
    encoded = json.dumps(data).encode() if data is not None else b''
    env = {'PATH_INFO': path, 'REQUEST_METHOD': method, 'CONTENT_LENGTH': str(len(encoded)),
           'wsgi.input': io.BytesIO(encoded)}
    if authenticated:
        env['HTTP_AUTHORIZATION'] = 'Bearer ' + ENV['APP_ACCESS_TOKEN']
    status = []
    body = b''.join(server.application(env, lambda s, h: status.append(s)))
    return int(status[0].split()[0]), body


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        server.JOBS.clear()

    def tearDown(self):
        self.env.stop()

    def test_csv_mapping_ignores_metadata(self):
        rows = server.parse_csv('\ufefftitle,review,rating,product\n"Nice, clear","Five stars!\nGreat sound",5,headphones\n', 'review', 'title')
        self.assertEqual(rows, [{'id': 1, 'title': 'Nice, clear', 'text': 'Five stars!\nGreat sound'}])

    def test_bad_files(self):
        for content in ['text,text\na,b', 'text\n', 'title,text\na,b,c', 'text\n"unclosed', 'title,text\nhello,']:
            with self.subTest(content=content), self.assertRaises(ValueError):
                server.parse_csv(content, 'text')
        with self.assertRaises(ValueError):
            server.parse_csv('text\n' + 'review\n' * 501, 'text')
        with self.assertRaises(ValueError):
            server.parse_csv('text\n' + 'a' * 20001, 'text')

    def test_auth_and_static_allowlist(self):
        self.assertEqual(request('/api/config', authenticated=False)[0], 401)
        self.assertEqual(request('/api/jobs/missing', authenticated=False)[0], 401)
        self.assertEqual(request('/api/jobs', 'POST', {'csv': 'text\nreview', 'text_column': 'text'}, authenticated=False)[0], 401)
        config_body = request('/api/config')[1].decode()
        for private in ['REVIEW_API_KEY', 'REVIEW_BASE_URL', 'APP_ACCESS_TOKEN']:
            self.assertNotIn(ENV[private], config_body)
        self.assertEqual(request('/.env')[0], 404)
        self.assertEqual(request('/server.py')[0], 404)
        self.assertEqual(request('/test_support/upload_fixture.py')[0], 404)
        self.assertEqual(request('/results/binary.json')[0], 404)
        self.assertEqual(request('/.env.local')[0], 404)
        self.assertEqual(request('/../pipeline.py')[0], 404)
        self.assertEqual(request('/')[0], 200)
        self.assertIn(b'<meta name="signal-workspace" content="connected">', request('/dashboard.html')[1])
        self.assertEqual(request('/healthz')[0], 200)

    def test_server_configuration(self):
        with patch.dict(os.environ, {'REVIEW_API_KEY': ''}):
            self.assertFalse(json.loads(request('/api/config')[1])['ready'])
        with patch.dict(os.environ, {'REVIEW_BASE_URL': 'http://remote.example/v1'}):
            self.assertIsNotNone(server.configuration_error())

    def test_modes_and_request_boundary(self):
        for mode in ('binary', 'three_class'):
            captured = []
            def fake_call(title, text, selected):
                body = payload(title, text, selected)
                captured.append(body)
                return {'prediction': {'sentiment': 'POSITIVE' if selected == 'binary' else 'NEUTRAL', 'emotion': 'none', 'reason': 'Test response'}}
            with patch.object(server, 'call', side_effect=fake_call):
                status, body = request('/api/jobs', 'POST', {'csv': 'title,text,rating\nFive Stars,Good sound,1\n', 'text_column': 'text', 'title_column': 'title', 'mode': mode})
                self.assertEqual(status, 202)
                job_id = json.loads(body)['id']
                for _ in range(100):
                    job = json.loads(request('/api/jobs/' + job_id)[1])
                    if job['status'] == 'complete': break
                    time.sleep(.01)
                self.assertEqual(job['status'], 'complete')
                user = json.loads(captured[0]['messages'][1]['content'])
                self.assertEqual(user, {'title': '[rating omitted]', 'text': 'Good sound'})
                self.assertEqual(len(captured[0]['messages']), 2)
                self.assertEqual(captured[0]['response_format']['json_schema']['schema']['properties']['sentiment']['enum'], server.LABELS[mode])

    def test_failed_rows_and_capacity(self):
        with patch.object(server, 'call', side_effect=RuntimeError('private provider details')):
            status, body = request('/api/jobs', 'POST', {'csv': 'text\nA review\n', 'text_column': 'text'})
            job_id = json.loads(body)['id']
            for _ in range(100):
                job = json.loads(request('/api/jobs/' + job_id)[1])
                if job['status'] == 'partial': break
                time.sleep(.01)
            self.assertEqual(job['status'], 'partial')
            self.assertNotIn('private provider details', json.dumps(job))
            self.assertNotIn('prediction', job['rows'][0])
        server.ACTIVE.acquire()
        try:
            self.assertEqual(request('/api/jobs', 'POST', {'csv': 'text\nreview', 'text_column': 'text'})[0], 409)
        finally:
            server.ACTIVE.release()
        server.JOBS['expired'] = {'finished_at': time.time() - server.TTL - 1}
        self.assertEqual(request('/api/jobs/expired')[0], 404)

    def test_invalid_api_inputs(self):
        for data in [{}, {'csv': 'text\nreview', 'text_column': 'text', 'mode': 'other'}, []]:
            self.assertEqual(request('/api/jobs', 'POST', data)[0], 400)


if __name__ == '__main__':
    unittest.main()
