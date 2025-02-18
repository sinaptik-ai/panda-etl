FROM python:3.11-slim

WORKDIR /app

# Install Poetry
RUN pip install poetry

# Copy application code
COPY . .

# Configure poetry to not create a virtual environment
RUN poetry config virtualenvs.create false

# Install dependencies
RUN poetry install

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["poetry", "run", "uvicorn", "app.main:app", "--workers", "2", "--host", "0.0.0.0", "--port", "8000"]
