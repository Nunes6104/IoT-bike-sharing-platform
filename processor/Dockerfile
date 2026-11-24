FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --uid 10001 app
COPY processor/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY processor/ /app/processor/
COPY database/ /app/database/
COPY dataset-IdC-2627/stations.json /app/dataset-IdC-2627/stations.json
RUN chown -R app:app /app
USER app

CMD ["python", "-m", "processor", "run"]
