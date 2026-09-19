"""Root conftest: puts the handler dir on sys.path so `import handler` works."""

import os

os.environ.setdefault("AWS_REGION", "us-east-1")
