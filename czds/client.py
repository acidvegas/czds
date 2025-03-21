#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/client.py

import asyncio
import gzip
import logging
import os


try:
    import aiohttp
except ImportError:
    raise ImportError('missing aiohttp library (pip install aiohttp)')

try:
    import aiofiles
except ImportError:
    raise ImportError('missing aiofiles library (pip install aiofiles)')


# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


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
        logging.info('Initialized CZDS client')


    async def __aenter__(self):
        '''Async context manager entry'''

        self.session = aiohttp.ClientSession()
        self.headers = {'Authorization': f'Bearer {await self.authenticate()}'}
        logging.debug('Entered async context')
        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        '''Async context manager exit'''

        if self.session:
            await self.session.close()
            logging.debug('Closed aiohttp session')


    async def authenticate(self) -> str:
        '''Authenticate with the ICANN API and return the access token'''

        try:
            data = {'username': self.username, 'password': self.password}
            logging.info('Authenticating with ICANN API')

            async with self.session.post('https://account-api.icann.org/api/authenticate', json=data) as response:
                if response.status != 200:
                    error_msg = f'Authentication failed: {response.status} {await response.text()}'
                    logging.error(error_msg)
                    raise Exception(error_msg)

                result = await response.json()
                logging.info('Successfully authenticated with ICANN API')
                return result['accessToken']

        except Exception as e:
            error_msg = f'Failed to authenticate with ICANN API: {e}'
            logging.error(error_msg)
            raise Exception(error_msg)


    async def fetch_zone_links(self) -> list:
        '''Fetch the list of zone files available for download'''
        logging.info('Fetching zone links')
        async with self.session.get('https://czds-api.icann.org/czds/downloads/links', headers=self.headers) as response:
            if response.status != 200:
                error_msg = f'Failed to fetch zone links: {response.status} {await response.text()}'
                logging.error(error_msg)
                raise Exception(error_msg)

            links = await response.json()
            logging.info(f'Successfully fetched {len(links)} zone links')
            return links


    async def get_report(self, filepath: str = None, scrub: bool = True, format: str = 'csv') -> str | dict:
        '''
        Downloads the zone report stats from the API and scrubs the report for privacy
        
        :param filepath: Filepath to save the scrubbed report
        :param scrub: Whether to scrub the username from the report
        :param format: Output format ('csv' or 'json')
        :return: Report content as CSV string or JSON dict
        '''
        logging.info('Downloading zone stats report')
        async with self.session.get('https://czds-api.icann.org/czds/requests/report', headers=self.headers) as response:
            if response.status != 200:
                error_msg = f'Failed to download the zone stats report: {response.status} {await response.text()}'
                logging.error(error_msg)
                raise Exception(error_msg)

            content = await response.text()

            if scrub:
                content = content.replace(self.username, 'nobody@no.name')
                logging.debug('Scrubbed username from report')

            if format.lower() == 'json':
                rows    = [row.split(',') for row in content.strip().split('\n')]
                header  = rows[0]
                content = [dict(zip(header, row)) for row in rows[1:]]
                logging.debug('Converted report to JSON format')

            if filepath:
                async with aiofiles.open(filepath, 'w') as file:
                    if format.lower() == 'json':
                        import json
                        await file.write(json.dumps(content, indent=4))
                    else:
                        await file.write(content)
                    logging.info(f'Saved report to {filepath}')

            return content


    async def gzip_decompress(self, filepath: str, cleanup: bool = True):
        '''
        Decompress a gzip file in place
        
        :param filepath: Path to the gzip file
        :param cleanup: Whether to remove the original gzip file after decompression
        '''
        logging.debug(f'Decompressing {filepath}')
        output_path = filepath[:-3] # Remove .gz extension
        
        async with aiofiles.open(filepath, 'rb') as f_in:
            content = await f_in.read()
            with gzip.open(content, 'rb') as gz:
                async with aiofiles.open(output_path, 'wb') as f_out:
                    await f_out.write(gz.read())
        
        if cleanup:
            os.remove(filepath)
            logging.debug(f'Removed original gzip file: {filepath}')


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
            logging.debug(f'Downloading zone file from {url}')
            async with self.session.get(url, headers=self.headers) as response:
                if response.status != 200:
                    error_msg = f'Failed to download {url}: {response.status} {await response.text()}'
                    logging.error(error_msg)
                    raise Exception(error_msg)

                if not (content_disposition := response.headers.get('Content-Disposition')):
                    error_msg = 'Missing Content-Disposition header'
                    logging.error(error_msg)
                    raise ValueError(error_msg)

                filename = content_disposition.split('filename=')[-1].strip('"')
                filepath = os.path.join(output_directory, filename)

                async with aiofiles.open(filepath, 'wb') as file:
                    while True:
                        chunk = await response.content.read(8192)
                        if not chunk:
                            break
                        await file.write(chunk)
                    logging.info(f'Successfully downloaded {filename}')

                if decompress:
                    await self.gzip_decompress(filepath, cleanup)
                    filepath = filepath[:-3] # Remove .gz extension

                return filepath

        if semaphore:
            async with semaphore:
                return await _download()
        else:
            return await _download()


    async def download_zones(self, output_directory: str, concurrency: int, decompress: bool = False, cleanup: bool = True):
        '''
        Download multiple zone files concurrently
        
        :param output_directory: Directory to save the zone files
        :param concurrency: Number of concurrent downloads
        :param decompress: Whether to decompress the gzip files after download
        :param cleanup: Whether to remove the original gzip files after decompression
        '''
        os.makedirs(output_directory, exist_ok=True)
        logging.info(f'Starting concurrent download of zones with concurrency={concurrency}')

        semaphore  = asyncio.Semaphore(concurrency)
        zone_links = await self.fetch_zone_links()
        tasks      = [self.download_zone(url, output_directory, decompress, cleanup, semaphore) for url in zone_links]

        await asyncio.gather(*tasks)
        logging.info('Completed downloading all zone files')
