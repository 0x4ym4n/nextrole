.PHONY: test api web demo fixtures figures
test:
	.venv/bin/python scripts/verify.py
	.venv/bin/python -m unittest scripts.test_evaluation -v
api:
	cd api && NEXTROLE_DATA=../data/demo_embeddings.json go run .
web:
	cd web && npm run dev
demo:
	.venv/bin/python scripts/dev.py --dataset demo
fixtures:
	.venv/bin/python scripts/prepare_data.py
	.venv/bin/python scripts/embeddings.py --corpus data/demo.json
figures:
	.venv/bin/python scripts/figures.py
