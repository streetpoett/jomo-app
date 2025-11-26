# 1. Base Image
FROM python:3.10-slim

# 2. Environment Variables
ENV PYTHONUNBUFFERED=1

# 3. Install System Dependencies
RUN apt-get update && apt-get install -y \
    wget \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Google Chrome Stable
RUN wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb \
    && apt-get update \
    && apt-get install -y ./google-chrome-stable_current_amd64.deb \
    && rm google-chrome-stable_current_amd64.deb \
    && rm -rf /var/lib/apt/lists/*

# 5. Work Directory
WORKDIR /app

# 6. Install Python Dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 7. Copy Application Code
COPY . .

# 8. Expose Port
EXPOSE 8000

# 9. Run Command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]