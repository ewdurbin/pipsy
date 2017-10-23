import asyncio
import json
import os
import re
from urllib.parse import urlsplit, urlunparse

import aiobotocore
from aiohttp import ClientSession
from aiohttp import web

PIPSY_BUCKET = os.getenv('PIPSY_BUCKET', default="zapier-pipsy-test")
PIPSY_SIMPLE_ROOT = os.getenv('PIPSY_SIMPLE_ROOT', default="")
PIPSY_PROXY_INDEX = os.getenv('PIPSY_PROXY_INDEX', default='https://pypi.org/simple')
PIPSY_PROXY_PYPI = os.getenv('PIPSY_PROXY_PYPI', default=True)
PIPSY_PROXY_CACHE = os.getenv('PIPSY_PROXY_CACHE', default=True)

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


def normalize_project_name(name):
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

        projects = sorted(list({normalize_project_name(k.rstrip('/')) for k in keys}))
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

    async def fetch_releases_for_project_from_s3(self, project_name):
        if PIPSY_SIMPLE_ROOT:
            prefix = '/'.join([PIPSY_SIMPLE_ROOT, project_name])
        else:
            prefix = project_name

        release_files = {}
        session = aiobotocore.get_session()
        async with session.create_client('s3') as client:
            paginator = client.get_paginator('list_objects_v2')
            async for result in paginator.paginate(Bucket=PIPSY_BUCKET, Prefix=prefix):
                for k in result.get('Contents', []):
                    release_files[os.path.basename(k['Key'])] = {
                        "filename": os.path.basename(k['Key']),
                        "url": os.path.basename(k['Key']),
                        "md5_digest": k['ETag'].strip('"'),
                    }

        return release_files

    async def fetch_releases_for_project_from_pypi(self, project_name):
        url = f'https://pypi.org/pypi/{project_name}/json'
        async with ClientSession() as session:
            async with session.get(url) as index_response:
                if index_response.status != 200:
                    return {}
                project_data = await index_response.json()
        release_files = {}
        for _, releases in project_data['releases'].items():
            for release in releases:
                release_files[release['filename']] = release

        if PIPSY_PROXY_CACHE:
            for release_file, data in release_files.items():
                url = urlsplit(data['url'])
                data['url'] = f'/proxy/{project_name}{url.path}{url.query}{url.fragment}'
                release_files[release_file] = data

        return release_files

    async def get(self):

        if not self.request.path.endswith('/'):
            return web.HTTPFound(self.request.path + '/')

        project_name = self.request.match_info.get('project_name', '')

        if normalize_project_name(project_name) != project_name:
            return web.HTTPFound(f'/simple/{normalize_project_name(project_name)}/')
        project_name = normalize_project_name(project_name)

        s3_keys = await self.fetch_releases_for_project_from_s3(project_name)

        if PIPSY_PROXY_PYPI:
            pypi_keys = await self.fetch_releases_for_project_from_pypi(project_name)
            s3_keys = {**pypi_keys, **s3_keys}

        body = [f"  <a href='{l['url']}#md5={l['md5_digest']}' rel='internal'>{l['filename']}</a><br/>" for _, l in s3_keys.items()]
        body = PKG_TEMPLATE.format(body="\n".join(body), project_name=project_name)

        return web.Response(
                status=200,
                body=body,
                headers={
                    'Content-Type': 'text/html; charset=utf-8',
                }
            )


class ReleaseFileHandler(web.View):

    async def stream_key_from_s3(self, key):
        session = aiobotocore.get_session()
        async with session.create_client('s3') as client:
            try:
                release = await client.get_object(Bucket=PIPSY_BUCKET, Key=key)
            except client.exceptions.NoSuchKey:
                raise KeyError

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

    async def get(self):

        data = {}
        project_name = self.request.match_info.get('project_name', '')
        release_file = self.request.match_info.get('release_file', '')

        if normalize_project_name(project_name) != project_name:
            return web.HTTPFound(f'/simple/{normalize_project_name(project_name)}/{release_file}')

        if PIPSY_SIMPLE_ROOT:
            key = '/'.join([PIPSY_SIMPLE_ROOT, project_name, release_file])
        else:
            key = '/'.join([project_name, release_file])

        try:
            return await self.stream_key_from_s3(key)
        except KeyError:
            raise web.HTTPNotFoundError()


async def cache_package(project_name, url, package_path):
    key = '/'.join((PIPSY_SIMPLE_ROOT, project_name, os.path.basename(package_path))).lstrip('/')
    boto_session = aiobotocore.get_session()
    async with boto_session.create_client('s3') as s3_client:
        try:
            release = await s3_client.get_object(Bucket=PIPSY_BUCKET, Key=key)
        except s3_client.exceptions.NoSuchKey:
            async with ClientSession() as session:
                async with session.get(url) as index_response:
                    data = await index_response.content.read()
                    await s3_client.put_object(
                        Body=data,
                        Bucket=PIPSY_BUCKET,
                        Key=key,
                    )

class ProxyReleaseFileHandler(web.View):

    async def stream_file_from_url(self, url):
        async with ClientSession() as session:
            async with session.get(url) as index_response:
                if index_response.status == 200:
                    response = web.StreamResponse(
                        status=200,
                        headers={
                            "Content-Type": index_response.content_type,
                            "ETag": index_response.headers.get('etag', ''),
                        }
                    )
                    response.content_length = index_response.headers.get('content-length', 0)
                    await response.prepare(self.request)
                    while True:
                        data = await index_response.content.read(8192)
                        if not data:
                            await response.drain()
                            break
                        response.write(data)
                    return response
                elif index_response.status == 404:
                    raise web.HTTPNotFound()
                else:
                    raise web.HTTPInternalServerError()

    async def get(self):

        scheme = 'https'
        netloc = 'files.pythonhosted.org'
        project_name = self.request.match_info.get('project_name', '')
        package_path = self.request.match_info.get('package_path', '')

        url = urlunparse((scheme, netloc, package_path, None, None, None))

        asyncio.ensure_future(cache_package(normalize_project_name(project_name), url, package_path))

        return await self.stream_file_from_url(url)


app = web.Application()
app.router.add_route('GET', '/simple', IndexHandler)
app.router.add_route('GET', '/simple/', IndexHandler)
app.router.add_route('GET', '/simple/{project_name}', ProjectHandler)
app.router.add_route('GET', '/simple/{project_name}/', ProjectHandler)
app.router.add_route('GET', '/simple/{project_name}/{release_file}', ReleaseFileHandler)
app.router.add_route('GET', '/proxy/{project_name}/{package_path:.*}', ProxyReleaseFileHandler)
web.run_app(app, host='127.0.0.1', port=8080)
