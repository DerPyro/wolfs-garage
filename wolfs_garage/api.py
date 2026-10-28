"""Standalone HTTP API. Authentication belongs to the trusted reverse proxy."""
import ipaddress
import os
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException

from . import __version__
from .store import Conflict, NotFound, Store, ValidationError


def public_origin(value):
    parsed = urlsplit(value)
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query
            or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("GARAGE_PUBLIC_ORIGIN must be a single HTTP(S) origin")
    if parsed.scheme == "http":
        try:
            local = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            local = parsed.hostname == "localhost"
        if not local:
            raise ValueError("HTTP is allowed only for a loopback development origin")
    elif parsed.scheme != "https":
        raise ValueError("GARAGE_PUBLIC_ORIGIN requires HTTPS outside localhost")
    try:
        parsed.port
    except ValueError as exc:
        raise ValueError("Invalid public origin port") from exc
    return f"{parsed.scheme}://{parsed.netloc.lower()}"


def create_app(config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_mapping(
        GARAGE_DB=os.environ.get("GARAGE_DB", "data/garage.sqlite3"),
        GARAGE_PUBLIC_ORIGIN=os.environ.get("GARAGE_PUBLIC_ORIGIN", "http://localhost:8080"),
        GARAGE_FRONTEND=os.environ.get("GARAGE_FRONTEND", str(Path(__file__).resolve().parent.parent / "frontend")),
        MAX_CONTENT_LENGTH=65536,
    )
    if config:
        app.config.update(config)
    origin = public_origin(app.config["GARAGE_PUBLIC_ORIGIN"])
    host = urlsplit(origin).netloc
    store = Store(app.config["GARAGE_DB"])
    app.extensions["garage_store"] = store

    @app.before_request
    def request_boundary():
        if request.path == "/healthz" and request.method in {"GET", "HEAD"}:
            return None
        if request.host.lower() != host:
            return jsonify(error="Diese Adresse entspricht nicht dem konfigurierten Origin."), 400
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if (request.headers.get("Origin") != origin
                    or request.headers.get("X-Garage-Request") != "1"
                    or request.headers.get("Sec-Fetch-Site", "same-origin") != "same-origin"):
                return jsonify(error="Anfrage nicht erlaubt."), 403
            if request.mimetype != "application/json":
                return jsonify(error="JSON-Anfrage erforderlich."), 415
        return None

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        )
        return response

    def payload():
        data = request.get_json()
        if not isinstance(data, dict):
            raise ValidationError("JSON-Objekt erforderlich.")
        return data

    @app.errorhandler(ValidationError)
    def invalid(error):
        return jsonify(error=str(error)), 400

    @app.errorhandler(NotFound)
    def missing(_error):
        return jsonify(error="Fahrzeug oder Eintrag nicht gefunden."), 404

    @app.errorhandler(Conflict)
    def conflict(_error):
        return jsonify(error="Der Datenstand wurde inzwischen geändert. Bitte neu laden."), 409

    @app.errorhandler(sqlite3.Error)
    def unavailable(_error):
        app.logger.error("Garage database unavailable; verify the configured persistent volume and schema.")
        return jsonify(error="Der Datenspeicher ist nicht verfügbar."), 503

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify(error=error.name), error.code

    @app.get("/")
    def index():
        return send_from_directory(app.config["GARAGE_FRONTEND"], "index.html")

    @app.get("/garage-assets/<path:filename>")
    def asset(filename):
        return send_from_directory(app.config["GARAGE_FRONTEND"], filename)

    @app.get("/healthz")
    def health():
        store.list_vehicles()
        return jsonify(status="ok")

    @app.get("/garage-api/capabilities")
    def capabilities():
        return jsonify(backend="standalone", version=__version__, apiVersion=1,
                       features=["vehicles", "status", "odometer", "records", "recordCorrections", "history"])

    @app.get("/garage-api/vehicles")
    def vehicles():
        return jsonify(vehicles=store.list_vehicles())

    @app.post("/garage-api/vehicles")
    def create_vehicle():
        return jsonify(store.create_vehicle(payload())), 201

    @app.get("/garage-api/vehicles/<int:vehicle_id>")
    def vehicle(vehicle_id):
        return jsonify(store.get_vehicle(vehicle_id))

    @app.put("/garage-api/vehicles/<int:vehicle_id>")
    def update_vehicle(vehicle_id):
        return jsonify(store.update_vehicle(vehicle_id, payload()))

    @app.get("/garage-api/vehicles/<int:vehicle_id>/summary")
    def summary(vehicle_id):
        return jsonify(store.get_summary(vehicle_id))

    @app.get("/garage-api/vehicles/<int:vehicle_id>/status")
    def status(vehicle_id):
        return jsonify(store.get_status(vehicle_id))

    @app.put("/garage-api/vehicles/<int:vehicle_id>/status")
    def update_status(vehicle_id):
        return jsonify(store.update_status(vehicle_id, payload()))

    @app.get("/garage-api/vehicles/<int:vehicle_id>/odometer")
    def readings(vehicle_id):
        return jsonify(readings=store.list_odometer(vehicle_id))

    @app.post("/garage-api/vehicles/<int:vehicle_id>/odometer")
    def add_reading(vehicle_id):
        return jsonify(store.add_odometer(vehicle_id, payload())), 201

    @app.get("/garage-api/vehicles/<int:vehicle_id>/records")
    def records(vehicle_id):
        return jsonify(records=store.get_summary(vehicle_id)["services"])

    @app.get("/garage-api/vehicles/<int:vehicle_id>/records/<int:record_id>")
    def record(vehicle_id, record_id):
        return jsonify(store.get_record(vehicle_id, record_id))

    @app.put("/garage-api/vehicles/<int:vehicle_id>/records/<int:record_id>")
    def correct_record(vehicle_id, record_id):
        return jsonify(store.correct_record(vehicle_id, record_id, payload()))

    @app.post("/garage-api/vehicles/<int:vehicle_id>/records")
    def add_record(vehicle_id):
        return jsonify(store.add_record(vehicle_id, payload())), 201

    @app.get("/garage-api/vehicles/<int:vehicle_id>/history")
    def history(vehicle_id):
        return jsonify(events=store.list_history(vehicle_id))

    return app
