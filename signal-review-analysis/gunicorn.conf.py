"""One process preserves the in-memory batch registry; threads serve polling."""
import os
bind = '0.0.0.0:' + os.environ.get('PORT', '8000')
workers = 1
worker_class = 'gthread'
threads = 4
timeout = 60
graceful_timeout = 30
accesslog = None
errorlog = '-'
