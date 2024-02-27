FROM python:3.12-slim

WORKDIR /usr/src/app

RUN pip install --no-cache-dir poetry==1.8.1

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_CACHE_DIR=/tmp/poetry_cache

COPY pyproject.toml poetry.lock setup.cfg README.md ./

RUN poetry install --no-root && rm -rf $POETRY_CACHE_DIR

COPY src src
COPY tests tests

RUN poetry install

ENTRYPOINT ["poetry", "run", "pytest", "-m", "smoke",  "./tests/python3.12/smoke.py"]
