import json
import os
import re
import sys

import aiobotocore
from aiohttp import web

PIPSY_BUCKET = os.getenv('PIPSY_BUCKET', default="zapier-pipsy-test")
PIPSY_SIMPLE_ROOT = os.getenv('PIPSY_SIMPLE_ROOT', default="")
PIPSY_PROXY_INDEX = os.getenv('PIPSY_PROXY_INDEX', default='https://pypi.org/simple')
PIPSY_PROXY_PYPI = os.getenv('PIPSY_PROXY_PYPI', default=True)
PIPSY_CACHE_PYPI = os.getenv('PIPSY_CACHE_PYPI', default=True)

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


def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


class IndexHandler(web.View):

    async def get(self):

        data = {}
        keys = []
        path = self.request.match_info.get('path', '')
        parts = [part for part in path.split('/') if part]

        if len(parts) == 0:
            session = aiobotocore.get_session()
            async with session.create_client('s3') as client:
                paginator = client.get_paginator('list_objects_v2')
                async for result in paginator.paginate(Bucket=PIPSY_BUCKET, Prefix=PIPSY_SIMPLE_ROOT, Delimiter="/"):
                    for k in result.get('CommonPrefixes', []):
                        keys.append(k['Prefix'])


        if len(parts) == 1:
            if normalize(parts[0]) != parts[0]:
                return web.HTTPFound(f'/simple/{normalize(parts[0])}/')
            pkg_name = parts[0]

            if PIPSY_SIMPLE_ROOT:
                prefix = '/'.join([PIPSY_SIMPLE_ROOT, pkg_name])
            else:
                prefix = pkg_name

            session = aiobotocore.get_session()
            async with session.create_client('s3') as client:
                paginator = client.get_paginator('list_objects_v2')
                async for result in paginator.paginate(Bucket=PIPSY_BUCKET, Prefix=prefix):
                    for k in result.get('Contents', []):
                        keys.append({"key": k['Key'], "etag": k['ETag'].replace('"', '')})

        if len(parts) == 2:
            pkg_name, file_name = parts
            if normalize(pkg_name) != pkg_name:
                return web.HTTPFound(f'/simple/{normalize(parts[0])}/{file_name}')

            if PIPSY_SIMPLE_ROOT:
                key = '/'.join([PIPSY_SIMPLE_ROOT, pkg_name, file_name])
            else:
                key = '/'.join([pkg_name, file_name])

            session = aiobotocore.get_session()
            async with session.create_client('s3') as client:
                release = await client.get_object(Bucket=PIPSY_BUCKET, Key=key)
                data = {
                    'ContentType': release['ContentType'],
                    'ETag': release['ETag'].replace('"', ''),
                }

        if len(parts) > 2:
            return web.HTTPNotFound()

        return web.Response(
                status=200,
                body=json.dumps({
                    'path': path,
                    'parts': parts,
                    'keys': keys,
                    'key': data,
                }),
            )

app = web.Application()
app.router.add_route('GET', '/simple', IndexHandler)
app.router.add_route('GET', '/simple/{path:.*}', IndexHandler)
web.run_app(app, host='127.0.0.1', port=8080)

#@APP.route('/', methods=['GET'], defaults={'path': ''})
#@APP.route('/<path:path>')
#def root_route(path):
#    keys = []
#    path_with_seperator = "{0}/".format(path)
#    pipsy_simple_root = "{0}/".format(PIPSY_SIMPLE_ROOT)
#    possible_pkg_name = os.path.basename(path[:-1])
#    possible_pkg_path = "{0}/{1}/".format(PIPSY_SIMPLE_ROOT, possible_pkg_name)
#
#    for key in s3_bucket.list(prefix=path, delimiter='/'):
#        keys.append(key.name)
#
#    if not keys:
#        return _404('Not found')
#
#    if len(keys) == 1 and keys[0] == path_with_seperator:
#        return redirect(path_with_seperator)
#
#    if path == pipsy_simple_root:
#        return _simple_root(keys)
#    elif path == possible_pkg_path:
#        return _package_root(keys, path, possible_pkg_name)
#    else:
#        return _404('Not found')
#
#
#def _package_root(keys, path, package_name):
#    body = []
#    for key in keys:
#        if key != path:
#            package_key = s3_bucket.get_key(key)
#            package_hash = package_key.etag.strip('"')
#            body.append("<a href='{0}#md5={1}' rel='internal'>{0}</a><br/>".format(os.path.basename(key), package_hash))
#
#    return PKG_TEMPLATE.format(body="\n".join(body), package_name=package_name)
#
#
#def _simple_root(keys):
#    body = []
#    for key in keys:
#        body.append("<a href='{0}/'>{0}</a><br/>".format(os.path.basename(key[:-1])))
#
#    return SIMPLE_TEMPLATE.format(body="\n".join(body))
#
#
#def _404(message):
#    return message, 404
#
#
#def main():
#    APP.run()
#
#if __name__ == "__main__":
#    main()
