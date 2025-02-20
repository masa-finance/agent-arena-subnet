run-miner:
	python scripts/run_miner.py

run-validator:
	python scripts/run_validator.py

run-tests:
	pytest tests/ --log-cli-level=INFO

# test-metagraph-unit:
# 	pytest tests/test_metagraph_unit.py

# test-metagraph-e2e:
# 	pytest tests/test_metagraph_e2e.py --log-cli-level=INFO

# test-metagraph:
# 	$(MAKE) test-metagraph-unit
# 	$(MAKE) test-metagraph-e2e

# test-weights-unit:
# 	pytest tests/test_weights_unit.py

# test-weights-e2e:
# 	pytest tests/test_weights_e2e.py --log-cli-level=INFO

