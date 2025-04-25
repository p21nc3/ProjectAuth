FROM mcr.microsoft.com/playwright/python:v1.35.0-jammy

# Install additional dependencies for xvfb and fix segmentation faults
RUN apt-get update && apt-get install -y --no-install-recommends \
    xvfb \
    libxcursor1 \
    libxdamage1 \
    libxi6 \
    libxtst6 \
    libnss3 \
    libcups2 \
    libxss1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libgbm1 \
    && rm -rf /var/lib/apt/lists/*

# install pipenv
RUN pip install pipenv
ENV PIPENV_VENV_IN_PROJECT=1

# create app directory
RUN mkdir -p /app
WORKDIR /app

# install python dependencies
ADD Pipfile .
ADD Pipfile.lock .
RUN pipenv install --system

# copy app
COPY . .

# Make start.sh executable
RUN chmod +x /app/start.sh

# Set up the default display
ENV DISPLAY=:99

# Set memory management environment variables to avoid segfaults
ENV NODE_OPTIONS="--max-old-space-size=4096"
ENV PYTHONMALLOC=malloc

# Increase browser limits
ENV PLAYWRIGHT_BROWSERS_PATH_ENV_VAR=/ms-playwright
ENV PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
