FROM python:3.13-slim

WORKDIR /app
COPY ml_processor/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY ml_processor/ ./ml_processor/
COPY processor/ ./processor/
COPY database/ ./database/

CMD ["python", "-u", "-m", "ml_processor"]
