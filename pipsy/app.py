import json
import os
import re

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
  <title>Links for {project_name}</title>
  <meta name="api-version" value="2" />
</head>
<body>
  <h1>Links for {project_name}</h1>
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

        projects = sorted(list({normalize(k.rstrip('/')) for k in keys}))
        body = [f"  <a href='{project}/'>{project}</a><br/>" for project in projects]
        body = SIMPLE_TEMPLATE.format(body="\n".join(body))

        return web.Response(
                status=200,
                body=body,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                }
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
                    keys.append({
                        "key": k['Key'],
                        "release_file": os.path.basename(k['Key']),
                        "etag": k['ETag'].strip('"'),
                    })

        body = [f"  <a href='{l['release_file']}#md5={l['etag']}' rel='internal'>{l['release_file']}</a><br/>" for l in keys]
        body = PKG_TEMPLATE.format(body="\n".join(body), project_name=project_name)

        return web.Response(
                status=200,
                body=body,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                }
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
            try:
                release = await client.get_object(Bucket=PIPSY_BUCKET, Key=key)
            except client.exceptions.NoSuchKey:
                raise web.HTTPNotFound()

            response = web.StreamResponse(
                status=200,
                headers={
                    "Content-Type": release['ContentType'],
                    "ETag": release['ETag'].strip('"'),
                }
            )
            response.content_length = release['ContentLength']
            await response.prepare(self.request)
            while True:
                data = await release['Body'].read(8192)
                if not data:
                    await response.drain()
                    break
                response.write(data)
            return response


app = web.Application()
app.router.add_route('GET', '/simple', IndexHandler)
app.router.add_route('GET', '/simple/', IndexHandler)
app.router.add_route('GET', '/simple/{project_name}', ProjectHandler)
app.router.add_route('GET', '/simple/{project_name}/', ProjectHandler)
app.router.add_route('GET', '/simple/{project_name}/{release_file}', ReleaseFileHandler)
web.run_app(app, host='127.0.0.1', port=8080)
