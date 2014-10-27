# About

pipsy is a proxy that resembles pypi, but uses s3 as the backend storage.

# Installing

$ pip install pipsy

# Running under gunicorn

(pipsy)$ gunicorn -b 127.0.0.1:5000 -w 2 -k gevent pipsy.app:APP
