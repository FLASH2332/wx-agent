build-AlertFunction:
	uv pip install -r requirements.txt --target "$(ARTIFACTS_DIR)" --python-platform x86_64-manylinux2014 --python-version 3.12 --only-binary=:all:
	cp handler.py "$(ARTIFACTS_DIR)"
