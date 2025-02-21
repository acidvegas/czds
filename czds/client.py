#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/client.py

import asyncio
import os
import gzip

try:
    import aiohttp
except ImportError:
    raise ImportError('missing aiohttp library (pip install aiohttp)')

try:
    import aiofiles
except ImportError:
    raise ImportError('missing aiofiles library (pip install aiofiles)')


class CZDS:
    '''Class for the ICANN Centralized Zones Data Service'''

    def __init__(self, username: str, password: str):
        '''
        Initialize CZDS client
        
        :param username: ICANN Username
        :param password: ICANN Password
        '''

        self.username = username
        self.password = password
        self.headers  = None # Store the authorization header for reuse
        self.session  = None # Store the client session for reuse


    async def __aenter__(self):
        '''Async context manager entry'''

        self.session = aiohttp.ClientSession()
        self.headers = {'Authorization': f'Bearer {await self.authenticate()}'}

        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        '''Async context manager exit'''

        if self.session:
            await self.session.close()


    async def authenticate(self) -> str:
        '''Authenticate with the ICANN API and return the access token'''

        try:
            data = {'username': self.username, 'password': self.password}

            async with self.session.post('https://account-api.icann.org/api/authenticate', json=data) as response:
                if response.status != 200:
                    raise Exception(f'Authentication failed: {response.status} {await response.text()}')

                result = await response.json()

                return result['accessToken']

        except Exception as e:
            raise Exception(f'Failed to authenticate with ICANN API: {e}')


    async def fetch_zone_links(self) -> list:
        '''Fetch the list of zone files available for download'''

        async with self.session.get('https://czds-api.icann.org/czds/downloads/links', headers=self.headers) as response:
            if response.status != 200:
                raise Exception(f'Failed to fetch zone links: {response.status} {await response.text()}')

            return await response.json()


    async def get_report(self, filepath: str = None, scrub: bool = True, format: str = 'csv') -> str | dict:
        '''
        Downloads the zone report stats from the API and scrubs the report for privacy
        
        :param filepath: Filepath to save the scrubbed report
        :param scrub: Whether to scrub the username from the report
        :param format: Output format ('csv' or 'json')
        :return: Report content as CSV string or JSON dict
        '''

        async with self.session.get('https://czds-api.icann.org/czds/requests/report', headers=self.headers) as response:
            if response.status != 200:
                raise Exception(f'Failed to download the zone stats report: {response.status} {await response.text()}')

            content = await response.text()

            if scrub:
                content = content.replace(self.username, 'nobody@no.name')

            if format.lower() == 'json':
                rows    = [row.split(',') for row in content.strip().split('\n')]
                header  = rows[0]
                content = [dict(zip(header, row)) for row in rows[1:]]

            if filepath:
                async with aiofiles.open(filepath, 'w') as file:
                    if format.lower() == 'json':
                        import json
                        await file.write(json.dumps(content, indent=4))
                    else:
                        await file.write(content)

            return content
        

    async def gzip_decompress(self, filepath: str, cleanup: bool = True):
        '''
        Decompress a gzip file in place
        
        :param filepath: Path to the gzip file
        :param cleanup: Whether to remove the original gzip file after decompression
        '''

        output_path = filepath[:-3] # Remove .gz extension
        
        async with aiofiles.open(filepath, 'rb') as f_in:
            content = await f_in.read()
            with gzip.open(content, 'rb') as gz:
                async with aiofiles.open(output_path, 'wb') as f_out:
                    await f_out.write(gz.read())
        
        if cleanup:
            os.remove(filepath)


    async def download_zone(self, url: str, output_directory: str, decompress: bool = False, cleanup: bool = True, semaphore: asyncio.Semaphore = None):
        '''
        Download a single zone file
        
        :param url: URL to download
        :param output_directory: Directory to save the zone file
        :param decompress: Whether to decompress the gzip file after download
        :param cleanup: Whether to remove the original gzip file after decompression
        :param semaphore: Optional semaphore for controlling concurrency
        '''

        async def _download():
            async with self.session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    raise Exception(f'Failed to download {url}: {response.status} {await response.text()}')

                if not (content_disposition := response.headers.get('Content-Disposition')):
                    raise ValueError('Missing Content-Disposition header')

                filename = content_disposition.split('filename=')[-1].strip('"')
                filepath = os.path.join(output_directory, filename)

                async with aiofiles.open(filepath, 'wb') as file:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        await file.write(chunk)

                if decompress:
                    await self.gzip_decompress(filepath, cleanup)
                    filepath = filepath[:-3] # Remove .gz extension

                return filepath

        if semaphore:
            async with semaphore:
                return await _download()
        else:
            return await _download()


    async def download_zones(self, zone_links: list, output_directory: str, concurrency: int, decompress: bool = False, cleanup: bool = True):
        '''
        Download multiple zone files concurrently
        
        :param zone_links: List of zone URLs to download
        :param output_directory: Directory to save the zone files
        :param concurrency: Number of concurrent downloads
        :param decompress: Whether to decompress the gzip files after download
        :param cleanup: Whether to remove the original gzip files after decompression
        '''

        os.makedirs(output_directory, exist_ok=True)

        semaphore = asyncio.Semaphore(concurrency)
        tasks     = [self.download_zone(url, output_directory, decompress, cleanup, semaphore) for url in zone_links]

        await asyncio.gather(*tasks)
