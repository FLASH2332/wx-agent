build-AgentFunction:
	uv pip install -r ../../agent_service/requirements.txt --target "$(ARTIFACTS_DIR)" --python-platform x86_64-manylinux2014 --python-version 3.12 --only-binary=:all:
	cp handler.py "$(ARTIFACTS_DIR)"
	cp -r ../../agent_service "$(ARTIFACTS_DIR)/agent_service"
	rm -rf "$(ARTIFACTS_DIR)/agent_service/tests" "$(ARTIFACTS_DIR)/agent_service/__pycache__" "$(ARTIFACTS_DIR)/agent_service/.cache"
