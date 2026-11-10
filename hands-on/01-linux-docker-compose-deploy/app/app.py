import os

import redis
from flask import Flask

app = Flask(__name__)

r = redis.Redis(
    host=os.environ.get("REDIS_HOST", "127.0.0.1"),
    port=int(os.environ.get("REDIS_PORT", "6379")),
    decode_responses=True,
)


@app.route("/")
def index():
    n = r.incr("visits")
    return f"<h1>你是第 {n} 个访问者</h1>\n"


@app.route("/health")
def health():
    return {"status": "ok", "redis": r.ping()}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
