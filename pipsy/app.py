import os
import logging

import boto
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import url_for

logging_handler = logging.StreamHandler()

APP = Flask(__name__)

PIPSY_BUCKET = os.getenv('PIPSY_BUCKET')
PIPSY_SIMPLE_ROOT = os.getenv('PIPSY_SIMPLE_ROOT')


class FlaskException(Exception):

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv

SIMPLE_TEMPLATE = """
<html>
<head>
  <title>Simple Index</title>
  <meta name="api-version" value="2" />
</head>
<body>
{body}
</body>
</html>
"""

PKG_TEMPLATE = """
<html>
<head>
  <title>Links for {package_name}</title>
  <meta name="api-version" value="2" />
</head>
<body>
<h1>Links for {package_name}</h1>
{body}
</body>
</html>
"""

s3_conn = boto.connect_s3()
s3_bucket = s3_conn.get_bucket(PIPSY_BUCKET)


@APP.errorhandler(FlaskException)
def handle_flask_error(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@APP.route('/', methods=['GET'], defaults={'path': ''})
@APP.route('/<path:path>')
def root_route(path):
    keys = []
    path_with_seperator = "{0}/".format(path)
    pipsy_simple_root = "{0}/".format(PIPSY_SIMPLE_ROOT)
    possible_pkg_name = os.path.basename(path[:-1])
    possible_pkg_path = "{0}/{1}/".format(PIPSY_SIMPLE_ROOT, possible_pkg_name)

    for key in s3_bucket.list(prefix=path, delimiter='/'):
        keys.append(key.name)

    if not keys:
        return _404('Not found')

    if len(keys) == 1 and keys[0] == path_with_seperator:
        return redirect(path_with_seperator)

    if path == pipsy_simple_root:
        return _simple_root(keys)
    elif path == possible_pkg_path:
        return _package_root(keys, path, possible_pkg_name)
    else:
        return _404('Not found')


def _package_root(keys, path, package_name):
    body = []
    for key in keys:
        if key != path:
            package_key = s3_bucket.get_key(key)
            package_hash = package_key.etag.strip('"')
            body.append("<a href='{0}#md5={1}' rel='internal'>{0}</a><br/>".format(os.path.basename(key), package_hash))

    return PKG_TEMPLATE.format(body="\n".join(body), package_name=package_name)


def _simple_root(keys):
    body = []
    for key in keys:
        body.append("<a href='{0}'>{0}</a><br/>".format(os.path.basename(key[:-1])))

    return SIMPLE_TEMPLATE.format(body="\n".join(body))


def _404(message):
    return message, 404


def main():
    APP.run()

if __name__ == "__main__":
    main()
