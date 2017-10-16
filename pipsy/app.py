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

        if not self.request.path.endswith('/'):
            return web.HTTPFound(self.request.path + '/')

        keys = []
        session = aiobotocore.get_session()
        async with session.create_client('s3') as client:
            paginator = client.get_paginator('list_objects_v2')
            async for result in paginator.paginate(Bucket=PIPSY_BUCKET, Prefix=PIPSY_SIMPLE_ROOT, Delimiter="/"):
                for k in result.get('CommonPrefixes', []):
                    keys.append(k['Prefix'])

        return web.Response(
                status=200,
                body=json.dumps({
                    'keys': keys,
                }),
            )


class ProjectHandler(web.View):

    async def get(self):

        if not self.request.path.endswith('/'):
            return web.HTTPFound(self.request.path + '/')

        keys = []
        project_name = self.request.match_info.get('project_name', '')

        if normalize(project_name) != project_name:
            return web.HTTPFound(f'/simple/{normalize(project_name)}/')
        project_name = normalize(project_name)

        if PIPSY_SIMPLE_ROOT:
            prefix = '/'.join([PIPSY_SIMPLE_ROOT, project_name])
        else:
            prefix = project_name

        session = aiobotocore.get_session()
        async with session.create_client('s3') as client:
            paginator = client.get_paginator('list_objects_v2')
            async for result in paginator.paginate(Bucket=PIPSY_BUCKET, Prefix=prefix):
                for k in result.get('Contents', []):
                    keys.append({"key": k['Key'], "etag": k['ETag'].replace('"', '')})

        return web.Response(
                status=200,
                body=json.dumps({
                    'keys': keys,
                }),
            )


class ReleaseFileHandler(web.View):

    async def get(self):

        data = {}
        project_name = self.request.match_info.get('project_name', '')
        release_file = self.request.match_info.get('release_file', '')

        if normalize(project_name) != project_name:
            return web.HTTPFound(f'/simple/{normalize(project_name)}/{release_file}')

        if PIPSY_SIMPLE_ROOT:
            key = '/'.join([PIPSY_SIMPLE_ROOT, project_name, release_file])
        else:
            key = '/'.join([project_name, release_file])

        session = aiobotocore.get_session()
        async with session.create_client('s3') as client:
            release = await client.get_object(Bucket=PIPSY_BUCKET, Key=key)
            data = {
                'ContentType': release['ContentType'],
                'ETag': release['ETag'].replace('"', ''),
            }

        return web.Response(
                status=200,
                body=json.dumps({
                    'data': data,
                }),
            )

app = web.Application()
app.router.add_route('GET', '/simple', IndexHandler)
app.router.add_route('GET', '/simple/', IndexHandler)
app.router.add_route('GET', '/simple/{project_name}', ProjectHandler)
app.router.add_route('GET', '/simple/{project_name}/', ProjectHandler)
app.router.add_route('GET', '/simple/{project_name}/{release_file}', ReleaseFileHandler)
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
