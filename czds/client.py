#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/client.py

import asyncio
import json
import logging
import os
import csv
import io

try:
    import aiohttp
except ImportError:
    raise ImportError('missing aiohttp library (pip install aiohttp)')

try:
    import aiofiles
except ImportError:
    raise ImportError('missing aiofiles library (pip install aiofiles)')

try:
    from tqdm import tqdm
except ImportError:
    raise ImportError('missing tqdm library (pip install tqdm)')

from .utils import gzip_decompress, humanize_bytes


# Configure logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)


class CZDS:
    '''Class for the ICANN Centralized Zones Data Service'''

    def __init__(self, username: str, password: str):
        '''
        Initialize CZDS client
        
        :param username: ICANN Username
        :param password: ICANN Password
        '''

        # Set the username and password
        self.username = username
        self.password = password

        # Configure TCP keepalive
        connector = aiohttp.TCPConnector(
            keepalive_timeout=300,     # Keep connections alive for 5 minutes
            force_close=False,         # Don't force close connections
            enable_cleanup_closed=True, # Cleanup closed connections
            ttl_dns_cache=300,         # Cache DNS results for 5 minutes
        )

        # Set the session with longer timeouts and keepalive
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=None, connect=60, sock_connect=60, sock_read=None),
            headers={'Connection': 'keep-alive'},
            raise_for_status=True
        )

        # Placeholder for the headers after authentication
        self.headers = None

        logging.info('Initialized CZDS client')


    async def __aenter__(self):
        '''Async context manager entry'''

        # Authenticate with the ICANN API
        await self.authenticate()

        return self


    async def __aexit__(self, exc_type, exc_val, exc_tb):
        '''Async context manager exit'''

        # Close the client session
        await self.close()


    async def close(self):
        '''Close the client session'''

        # Close the client session if it exists
        if self.session:
            await self.session.close()
            logging.debug('Closed aiohttp session')


    async def authenticate(self) -> str:
        '''Authenticate with the ICANN API and return the access token'''

        # Set the data to be sent to the API
        data = {'username': self.username, 'password': self.password}

        logging.info('Authenticating with ICANN API...')

        # Send the request to the API
        async with self.session.post('https://account-api.icann.org/api/authenticate', json=data) as response:
            if response.status != 200:
                raise Exception(f'Authentication failed: {response.status} {await response.text()}')

            # Get the result from the API
            result = await response.json()

            logging.info('Successfully authenticated with ICANN API')

            # Set the headers for the API requests
            self.headers = {'Authorization': f'Bearer {result["accessToken"]}'}

            return result['accessToken']


    async def fetch_zone_links(self) -> list:
        '''Fetch the list of zone files available for download'''

        logging.info('Fetching zone file links...')

        # Send the request to the API
        async with self.session.get('https://czds-api.icann.org/czds/downloads/links', headers=self.headers) as response:
            if response.status != 200:
                raise Exception(f'Failed to fetch zone links: {response.status} {await response.text()}')

            # Get the result from the API
            links = await response.json()

            logging.info(f'Successfully fetched {len(links):,} zone links')

            return links


    async def get_report(self, filepath: str = None, format: str = 'csv') -> str | dict:
        '''
        Downloads the zone report stats from the API and scrubs the report for privacy
        
        :param filepath: Filepath to save the scrubbed report
        :param format: Output format ('csv' or 'json')
        '''
        logging.info('Downloading zone stats report')

        # Send the request to the API
        async with self.session.get('https://czds-api.icann.org/czds/requests/report', headers=self.headers) as response:
            if response.status != 200:
                raise Exception(f'Failed to download the zone stats report: {response.status} {await response.text()}')

            # Get the content of the report
            content = await response.text()

            # Scrub the username from the report
            content = content.replace(self.username, 'nobody@no.name')
            logging.debug('Scrubbed username from report')

            # Convert the report to JSON format if requested
            if format.lower() == 'json':
                # Parse CSV content
                csv_reader = csv.DictReader(io.StringIO(content))
                
                # Convert to list of dicts with formatted keys
                json_data = []
                for row in csv_reader:
                    formatted_row = {
                        key.lower().replace(' ', '_'): value 
                        for key, value in row.items()
                    }
                    json_data.append(formatted_row)
                
                content = json.dumps(json_data, indent=4)
                logging.debug('Converted report to JSON format')

            # Save the report to a file if a filepath is provided
            if filepath:
                async with aiofiles.open(filepath, 'w') as file:
                    await file.write(content)
                logging.info(f'Saved report to {filepath}')

            return content


    async def download_zone(self, url: str, output_directory: str, semaphore: asyncio.Semaphore):
        '''
        Download a single zone file
        
        :param url: URL to download
        :param output_directory: Directory to save the zone file
        :param semaphore: Optional semaphore for controlling concurrency
        '''
        
        async def _download():
            tld_name    = url.split('/')[-1].split('.')[0] # Extract TLD from URL
            max_retries = 20                               # Maximum number of retries for failed downloads
            retry_delay = 5                                # Delay between retries in seconds
            
            # Headers for better connection stability
            download_headers = {
                **self.headers,
                'Connection': 'keep-alive',
                'Keep-Alive': 'timeout=600', # 10 minutes
                'Accept-Encoding': 'gzip'
            }

            # Start the attempt loop
            for attempt in range(max_retries):
                try:
                    logging.info(f'Starting download of {tld_name} zone file{" (attempt " + str(attempt + 1) + ")" if attempt > 0 else ""}')

                    # Send the request to the API
                    async with self.session.get(url, headers=download_headers) as response:
                        # Check if the request was successful
                        if response.status != 200:
                            logging.error(f'Failed to download {tld_name}: {response.status} {await response.text()}')

                            # Retry the download if there are more attempts
                            if attempt + 1 < max_retries:
                                logging.info(f'Retrying {tld_name} in {retry_delay:,} seconds...')
                                await asyncio.sleep(retry_delay)
                                continue

                            raise Exception(f'Failed to download {tld_name}: {response.status} {await response.text()}')

                        # Get expected file size from headers
                        if not (expected_size := int(response.headers.get('Content-Length', 0))):
                            raise ValueError(f'Missing Content-Length header for {tld_name}')

                        # Check if the Content-Disposition header is present
                        if not (content_disposition := response.headers.get('Content-Disposition')):
                            raise ValueError(f'Missing Content-Disposition header for {tld_name}')

                        # Extract the filename from the Content-Disposition header
                        filename = content_disposition.split('filename=')[-1].strip('"')

                        # Create the filepath
                        filepath = os.path.join(output_directory, filename)

                        # Create a progress bar to track the download
                        with tqdm(total=expected_size, unit='B', unit_scale=True, desc=f'Downloading {tld_name}', leave=False) as pbar:
                            # Open the file for writing
                            async with aiofiles.open(filepath, 'wb') as file:
                                # Initialize the total size for tracking
                                total_size = 0

                                # Write the chunk to the file
                                try:
                                    async for chunk in response.content.iter_chunked(8192):
                                        await file.write(chunk)
                                        total_size += len(chunk)
                                        pbar.update(len(chunk))
                                except Exception as e:
                                    logging.error(f'Connection error while downloading {tld_name}: {str(e)}')
                                    if attempt + 1 < max_retries:
                                        logging.info(f'Retrying {tld_name} in {retry_delay} seconds...')
                                        await asyncio.sleep(retry_delay)
                                        continue
                                    raise

                        # Verify file size
                        if expected_size and total_size != expected_size:
                            error_msg = f'Incomplete download for {tld_name}: Got {humanize_bytes(total_size)}, expected {humanize_bytes(expected_size)}'
                            logging.error(error_msg)
                            os.remove(filepath)
                            if attempt + 1 < max_retries:
                                logging.info(f'Retrying {tld_name} in {retry_delay} seconds...')
                                await asyncio.sleep(retry_delay)
                                continue
                            raise Exception(error_msg)
                        
                        logging.info(f'Successfully downloaded {tld_name} zone file ({humanize_bytes(total_size)})')

                        await gzip_decompress(filepath)
                        filepath = filepath[:-3]
                        logging.info(f'Decompressed {tld_name} zone file')

                        return filepath

                except Exception as e:
                    if attempt + 1 >= max_retries:
                        logging.error(f'Failed to download {tld_name} after {max_retries} attempts: {str(e)}')
                        if 'filepath' in locals() and os.path.exists(filepath):
                            os.remove(filepath)
                        raise
                    logging.warning(f'Download attempt {attempt + 1} failed for {tld_name}: {str(e)}')
                    await asyncio.sleep(retry_delay)

        async with semaphore:
            return await _download()


    async def download_zones(self, output_directory: str, concurrency: int):
        '''
        Download multiple zone files concurrently
        
        :param output_directory: Directory to save the zone files
        :param concurrency: Number of concurrent downloads
        '''
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)
        
        # Get the zone links
        zone_links = await self.fetch_zone_links()
        zone_links.sort() # Sort the zone alphabetically for better tracking

        # Create a semaphore to limit the number of concurrent downloads
        semaphore = asyncio.Semaphore(concurrency)

        logging.info(f'Downloading {len(zone_links):,} zone files...')

        # Create a list of tasks to download the zone files
        tasks = [self.download_zone(url, output_directory, semaphore) for url in zone_links]

        # Run the tasks concurrently
        await asyncio.gather(*tasks)

        logging.info(f'Completed downloading {len(zone_links):,} zone files')