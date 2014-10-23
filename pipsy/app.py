import os
import logging

import boto
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import url_for

from flask_sslify import SSLify

logging_handler = logging.StreamHandler()

APP = Flask(__name__)
sslify = SSLify(APP)

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

SIMPLE_TEMPLATE="""
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

PKG_TEMPLATE="""
<html>
<head>
  <title>Links for {pkg_name}</title>
  <meta name="api-version" value="2" />
</head>
<body>
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
    for key in s3_bucket.list(prefix=path,delimiter="/"):
        keys.append(key.name)
    if len(keys) == 1:
        if keys[0] == path+"/":
            return redirect(path+"/")
        elif not keys[0].endswith("/"):
            return "Not Found", 404
    if path == PIPSY_SIMPLE_ROOT+"/":
        body = ""
        for key in keys:
            body+="<a href='%s'>%s</a><br/>\n" % (os.path.basename(key[:-1]), os.path.basename(key[:-1]))
        return SIMPLE_TEMPLATE.format(body=body)
    body = ""
    pkg_name = os.path.basename(path[:-1])
    for key in keys:
        if key != path:
            body+="<a href='%s'>%s</a><br/>\n" % (os.path.basename(key), os.path.basename(key))
    return PKG_TEMPLATE.format(body=body, pkg_name=pkg_name)

def main():
    APP.run(debug=True)

if __name__ == "__main__":
    main()
