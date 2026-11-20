FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY processor/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY processor/ /app/processor/
COPY database/schema.sql /app/database/

# Default command: placeholder
CMD ["python", "-m", "processor", "--help"]
