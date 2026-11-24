FROM python:3.11-slim

WORKDIR /app

RUN useradd --create-home --uid 10002 app
COPY publisher/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY publisher/ /app/publisher/
COPY processor/__init__.py processor/validation.py /app/processor/
COPY dataset-IdC-2627/stations.json /app/dataset-IdC-2627/stations.json
RUN mkdir /state && touch /state/.keep && chown -R app:app /app /state
USER app

CMD ["python", "-m", "publisher"]
