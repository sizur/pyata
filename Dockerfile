FROM python:3

WORKDIR /usr/src/app

RUN pip install poetry

COPY . .

RUN poetry install

ENTRYPOINT ["poetry", "run", "pytest", "-m", "smoke",  "./tests/python3.12/smoke.py"]
