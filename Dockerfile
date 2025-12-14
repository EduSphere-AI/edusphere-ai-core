FROM python:3.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml ./
COPY main.py ./
COPY config.py ./
COPY models/ ./models/
COPY services/ ./services/
COPY utils/ ./utils/

# Install Python dependencies
RUN pip install --no-cache-dir -e .

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
