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

# Set environment variables for TA-Lib compilation
ENV TA_LIBRARY_PATH=/usr/lib
ENV TA_INCLUDE_PATH=/usr/include

# Pre-Install build dependencies
RUN pip install --no-cache-dir "numpy<2" setuptools wheel Cython

# Explicitly install TA-Lib without build isolation to use the global numpy headers
RUN pip install --no-cache-dir --no-build-isolation TA-Lib==0.4.28

# Install remaining Python requirements
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install flask flask-cors

# Expose Web Dashboard Port
EXPOSE 5000

# Start Bot in Web Mode
CMD ["python", "main.py", "--mode", "web"]
