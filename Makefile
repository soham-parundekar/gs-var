# Stage 1 needs the network; everything after it runs from what stage 1 and 2
# leave in data/. Set SEC_CONTACT to your own name and email before running
# stage 1, because SEC rejects requests that do not identify the client.

PY := PYTHONPATH=src python3

.PHONY: all data var analysis figures test clean reproduce

all: data var analysis figures

data:
	$(PY) scripts/01_fetch_disclosures.py
	$(PY) scripts/02_build_factors.py

var:
	$(PY) scripts/03_run_var.py

analysis:
	$(PY) scripts/04_backtest.py
	$(PY) scripts/05_regimes_and_convexity.py
	$(PY) scripts/06_robustness.py

figures:
	$(PY) scripts/07_figures.py

test:
	$(PY) -m pytest -q

# Everything derived, from the filings onward. Raw downloads are kept, since
# re-fetching ten filings from EDGAR is slow and they never change once filed.
reproduce: clean all test

clean:
	rm -rf data/interim/* data/processed/* reports/figures/*
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
