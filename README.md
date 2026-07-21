# md-trend-agent

Knitwear MD trend data collection and analysis pipeline.

## Local testing

### Prerequisites

- Python 3.11 or newer (`requires-python >= 3.11` in `pyproject.toml`)
- Install runtime and dev dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

### Run the tests

```bash
python -m pytest tests
```
