# Frontend Dockerfile for Development and Testing
# Uses node:20-slim (not alpine) to support Playwright E2E tests

FROM node:20-slim

# Install Playwright dependencies (required for E2E tests)
RUN apt-get update && apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Install Playwright browsers (for E2E tests)
RUN npx playwright install chromium

# Copy application files
COPY . .

# Expose Vite dev server port (5174)
EXPOSE 5174

# Default command: run dev server on all interfaces
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
