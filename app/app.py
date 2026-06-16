"""
DevOps Monitoring Lab — Sample Flask App
=========================================
A Flask application instrumented with Prometheus metrics
(Counter, Gauge, Histogram, Summary) for the monitoring lab.

Run with Docker Compose:
  docker compose up -d flask-app

App:     http://localhost:8080
Metrics: http://localhost:8080/metrics
"""

import time
import random
import threading
import os
from flask import Flask, jsonify, request
from prometheus_client import (
    Counter, Gauge, Histogram, Summary,
    generate_latest, CONTENT_TYPE_LATEST
)

app = Flask(__name__)
APP_PORT = int(os.environ.get("APP_PORT", 8080))
APP_ENV  = os.environ.get("APP_ENV", "development")

# ============================================================
# METRICS
# ============================================================
REQUEST_COUNT = Counter(
    'app_requests_total', 'Total HTTP requests',
    ['method', 'endpoint', 'status_code']
)
ERROR_COUNT = Counter(
    'app_errors_total', 'Total application errors', ['error_type']
)
ACTIVE_USERS = Gauge('app_active_users', 'Currently active users (simulated)')
IN_FLIGHT_REQUESTS = Gauge('app_in_flight_requests', 'Requests being processed')
REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds', 'Request latency in seconds',
    ['endpoint'], buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0]
)
DB_QUERY_DURATION = Summary(
    'app_db_query_duration_seconds', 'DB query duration', ['query_type']
)
QUEUE_DEPTH = Gauge('app_task_queue_depth', 'Pending tasks in queue')

# ============================================================
# DECORATOR: auto-track every request
# ============================================================
def track_request(f):
    import functools
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        endpoint = request.path
        method = request.method
        IN_FLIGHT_REQUESTS.inc()
        start = time.time()
        status = 200
        try:
            response = f(*args, **kwargs)
            if isinstance(response, tuple):
                status = response[1]
            return response
        except Exception as e:
            status = 500
            ERROR_COUNT.labels(error_type=type(e).__name__).inc()
            raise
        finally:
            duration = time.time() - start
            IN_FLIGHT_REQUESTS.dec()
            REQUEST_COUNT.labels(method=method, endpoint=endpoint, status_code=str(status)).inc()
            REQUEST_LATENCY.labels(endpoint=endpoint).observe(duration)
    return wrapper

# ============================================================
# BACKGROUND SIMULATION
# ============================================================
def simulate_background_activity():
    while True:
        try:
            hour = time.localtime().tm_hour
            base_users = 50 + (30 if 9 <= hour <= 17 else 10)
            ACTIVE_USERS.set(max(0, base_users + random.gauss(0, 10)))
            QUEUE_DEPTH.set(max(0, random.gauss(20, 8)))
            db_duration = random.expovariate(10)
            DB_QUERY_DURATION.labels(query_type='SELECT').observe(db_duration)
        except Exception:
            pass
        time.sleep(1)

# ============================================================
# ROUTES
# ============================================================
@app.route('/')
@track_request
def index():
    time.sleep(random.expovariate(20))
    return jsonify({
        "message": "DevOps Monitoring Lab — Flask App",
        "environment": APP_ENV,
        "endpoints": ["/", "/users", "/slow", "/error", "/health", "/metrics"]
    })

@app.route('/users')
@track_request
def get_users():
    db_time = random.uniform(0.005, 0.05)
    time.sleep(db_time)
    DB_QUERY_DURATION.labels(query_type='SELECT').observe(db_time)
    if random.random() < 0.02:
        ERROR_COUNT.labels(error_type='DatabaseError').inc()
        return jsonify({"error": "Database timeout"}), 500
    users = [{"id": i, "name": f"User {i}"} for i in range(1, random.randint(5, 20))]
    return jsonify({"users": users, "count": len(users)})

@app.route('/slow')
@track_request
def slow_endpoint():
    sleep_time = random.uniform(0.5, 2.0)
    time.sleep(sleep_time)
    return jsonify({"message": f"Slept {sleep_time:.2f}s"})

@app.route('/error')
@track_request
def simulate_error():
    ERROR_COUNT.labels(error_type='SimulatedError').inc()
    return jsonify({"error": "Simulated server error"}), 500

@app.route('/health')
def health():
    return jsonify({"status": "healthy", "environment": APP_ENV}), 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}

# ============================================================
# DEMO TRAFFIC GENERATOR
# ============================================================
def generate_demo_traffic():
    import urllib.request, urllib.error
    time.sleep(3)
    endpoints = [('/', 0.5), ('/users', 0.35), ('/slow', 0.07), ('/error', 0.08)]
    while True:
        try:
            rand = random.random()
            cumulative = 0
            chosen = '/'
            for endpoint, probability in endpoints:
                cumulative += probability
                if rand <= cumulative:
                    chosen = endpoint
                    break
            url = f'http://localhost:{APP_PORT}{chosen}'
            try:
                urllib.request.urlopen(url, timeout=5)
            except Exception:
                pass
        except Exception:
            pass
        time.sleep(random.uniform(0.2, 2.0))

if __name__ == '__main__':
    threading.Thread(target=simulate_background_activity, daemon=True).start()
    threading.Thread(target=generate_demo_traffic, daemon=True).start()
    print(f"Flask app starting on port {APP_PORT} [{APP_ENV}]")
    app.run(host='0.0.0.0', port=APP_PORT, debug=False, threaded=True)