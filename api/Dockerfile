FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Non-root user (required: Claude CLI refuses --dangerously-skip-permissions as root)
RUN useradd -m -s /bin/bash agent
RUN mkdir -p /workspace && chown agent:agent /workspace

WORKDIR /src
ENV PYTHONPATH=/src

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

RUN chown -R agent:agent /src

USER agent

ENTRYPOINT ["/entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
