FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data
VOLUME ["/app/data"]

ENV SECRET_KEY=change-me-to-random-string
ENV HOST=0.0.0.0
ENV PORT=3210
ENV DATA_DIR=/app/data

EXPOSE 3210

CMD ["python", "main.py"]
