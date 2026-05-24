# Hello-World Flask App

A minimal Flask application exposing a single `GET /hello` route that returns the JSON response `{"message": "Hello, World!"}`. Install the dependency, run the app, and hit the endpoint. Requires Python 3.8+.

```bash
pip install -r requirements.txt
python app.py
# In another terminal:
curl http://localhost:5000/hello
# -> {"message":"Hello, World!"}
```
