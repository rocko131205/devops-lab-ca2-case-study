"""Catalog service: a small streaming-catalog API used to demo the DevOps pipeline.

The /recommendations route pretends to call a flaky downstream engine, so the
Grafana dashboard has real latency and error data to show.
"""
import os
import random
import time

from flask import Flask, Response, abort, g, jsonify, request
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

APP_VERSION = os.getenv("APP_VERSION", "v1")
FAILURE_RATE = float(os.getenv("FAILURE_RATE", "0.05"))

app = Flask(__name__)

REQUESTS = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
LATENCY = Histogram(
    "http_request_duration_seconds", "Request latency in seconds", ["endpoint"]
)
APP_INFO = Gauge("app_info", "Running app version", ["version"])
APP_INFO.labels(version=APP_VERSION).set(1)

TITLES = [
    {"id": 1, "title": "The Last Deploy", "genre": "Thriller", "year": 2024},
    {"id": 2, "title": "Chaos Monkey Chronicles", "genre": "Documentary", "year": 2023},
    {"id": 3, "title": "Pipeline Dreams", "genre": "Drama", "year": 2025},
    {"id": 4, "title": "Zero Downtime", "genre": "Action", "year": 2022},
    {"id": 5, "title": "Rollback", "genre": "Sci-Fi", "year": 2026},
]


@app.before_request
def start_timer():
    g.start = time.perf_counter()


@app.after_request
def record_metrics(response):
    if request.path != "/metrics":
        endpoint = request.url_rule.rule if request.url_rule else "unknown"
        LATENCY.labels(endpoint=endpoint).observe(time.perf_counter() - g.start)
        REQUESTS.labels(request.method, endpoint, str(response.status_code)).inc()
    return response


@app.route("/")
def home():
    return jsonify(service="catalog-service", version=APP_VERSION)


@app.route("/health")
def health():
    return jsonify(status="ok"), 200


@app.route("/titles")
def list_titles():
    return jsonify(TITLES)


@app.route("/titles/<int:title_id>")
def get_title(title_id):
    for title in TITLES:
        if title["id"] == title_id:
            return jsonify(title)
    abort(404)


@app.route("/recommendations")
def recommendations():
    # Simulated call to a downstream recommendation engine
    time.sleep(random.uniform(0.05, 0.3))
    if random.random() < FAILURE_RATE:
        return jsonify(error="recommendation engine unavailable"), 503
    return jsonify(random.sample(TITLES, 3))


@app.route("/metrics")
def metrics():
    return Response(generate_latest(), mimetype=CONTENT_TYPE_LATEST)
