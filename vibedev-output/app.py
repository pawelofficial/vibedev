"""
Column Lineage Web App - Flask application entry point.

Creates the Flask instance, registers the route Blueprint, and
provides the dev-server entry point. Schema loading and route
handlers live in schema_service.py and routes.py respectively.
"""

from flask import Flask

from routes import bp

app = Flask(__name__, static_folder='static')
app.register_blueprint(bp)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
