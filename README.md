# oauth-proxy-mcp-server-client

## Install

Either load the project with PyCharm or create and install your environment:
```bash
python3 -m venv .venv && \
source .venv/bin/activate && \
pip install --upgrade pip && \
pip install -r requirements.txt
```

## Server

```
python server/cli.py --port 8001 --gravitee-am $AM_HOST/$AM_DOMAIN --transport streamable-http
```

## Client

```
python server/cli.py
```
