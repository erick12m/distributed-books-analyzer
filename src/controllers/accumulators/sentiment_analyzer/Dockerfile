FROM python:3.11-slim
RUN pip install --upgrade pip && pip3 install pika && pip3 install -U textblob && python3 -m textblob.download_corpora

COPY src/controllers/accumulators/sentiment_analyzer /
COPY src/shared /shared
ENTRYPOINT ["/bin/sh"]