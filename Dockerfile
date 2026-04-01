FROM python:3.11

WORKDIR /app

# The full python image already has build-essential but just in case:
RUN apt-get update && apt-get install -y wget build-essential && rm -rf /var/lib/apt/lists/*

# Install TA-Lib C library
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xvzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib/ && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    cd .. && \
    rm -rf ta-lib-0.4.0-src.tar.gz ta-lib/

COPY . .

# Force pip to use numpy 1.26.4 in ALL isolated build environments to match requirements
# This prevents the TA-Lib python wrapper from compiling against numpy 2.x and crashing
RUN echo "numpy==1.26.4" > /tmp/constraints.txt
ENV PIP_CONSTRAINT=/tmp/constraints.txt
ENV TA_LIBRARY_PATH=/usr/lib
ENV TA_INCLUDE_PATH=/usr/include

# Install requirements seamlessly
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir flask flask-cors

EXPOSE 5000

CMD ["python", "main.py", "--mode", "web"]
