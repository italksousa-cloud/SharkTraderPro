FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required for TA-Lib C Library
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

# Copy all files
COPY . .

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install flask flask-cors "numpy<2"

# Expose Web Dashboard Port
EXPOSE 5000

# Start Bot in Web Mode
CMD ["python", "main.py", "--mode", "web"]
