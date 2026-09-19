"""Root conftest: puts the handler dir on sys.path so `import tools` works, and
ensures OWM_API_KEY exists for import-time (offline tests stub the HTTP layer).
"""

import os

os.environ.setdefault("OWM_API_KEY", "test-key")
