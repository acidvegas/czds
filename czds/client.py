#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/client.py

import asyncio
import gzip
import logging
import os
import io

try:
    import aiohttp
except ImportError:
    raise ImportError('missing aiohttp library (pip install aiohttp)')

try:
    import aiofiles
except ImportError:
    raise ImportError('missing aiofiles library (pip install aiofiles)')


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
        
        self.username = username
        self.password = password

        # Configure longer timeouts and proper SSL settings
        timeout = aiohttp.ClientTimeout(total=None, connect=60, sock_connect=60, sock_read=60)
        self.session = aiohttp.ClientSession(timeout=timeout)
        self.headers = None

        logging.info('Initialized CZDS client')

    async def __aenter__(self):
        '''Async context manager entry'''
        await self.authenticate()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        '''Async context manager exit'''
        await self.close()

    async def close(self):
        '''Close the client session'''

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
                self.headers = {'Authorization': f'Bearer {result["accessToken"]}'}
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
            logging.info(f'Successfully fetched {len(links):,} zone links')
            return links


    async def get_report(self, filepath: str = None, scrub: bool = True, format: str = 'csv') -> str | dict:
        '''
        Downloads the zone report stats from the API and scrubs the report for privacy
        
        :param filepath: Filepath to save the scrubbed report
        :param scrub: Whether to scrub the username from the report
        :param format: Output format ('csv' or 'json')
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
        :param cleanup: Whether to remove the original gzip file after decompressions
        '''

        logging.debug(f'Decompressing {filepath}')
        output_path = filepath[:-3]  # Remove .gz extension
        chunk_size = 1024 * 1024  # 1MB chunks
        
        try:
            with gzip.open(filepath, 'rb') as gz:
                async with aiofiles.open(output_path, 'wb') as f_out:
                    while True:
                        chunk = gz.read(chunk_size)
                        if not chunk:
                            break
                        await f_out.write(chunk)
        
            if cleanup:
                os.remove(filepath)
                logging.debug(f'Removed original gzip file: {filepath}')
            
        except Exception as e:
            error_msg = f'Failed to decompress {filepath}: {str(e)}'
            logging.error(error_msg)
            # Clean up any partial files
            if os.path.exists(output_path):
                os.remove(output_path)
            raise Exception(error_msg)


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
            tld = url.split('/')[-1].split('.')[0]  # Extract TLD from URL
            max_retries = 3
            retry_delay = 5  # seconds
            
            for attempt in range(max_retries):
                try:
                    logging.info(f'Starting download of {tld} zone file{" (attempt " + str(attempt + 1) + ")" if attempt > 0 else ""}')
                    
                    async with self.session.get(url, headers=self.headers, timeout=aiohttp.ClientTimeout(total=3600)) as response:
                        if response.status != 200:
                            error_msg = f'Failed to download {tld}: {response.status} {await response.text()}'
                            logging.error(error_msg)
                            if attempt + 1 < max_retries:
                                logging.info(f'Retrying {tld} in {retry_delay} seconds...')
                                await asyncio.sleep(retry_delay)
                                continue
                            raise Exception(error_msg)

                        # Get expected file size from headers
                        expected_size = int(response.headers.get('Content-Length', 0))
                        if not expected_size:
                            logging.warning(f'No Content-Length header for {tld}')

                        if not (content_disposition := response.headers.get('Content-Disposition')):
                            error_msg = f'Missing Content-Disposition header for {tld}'
                            logging.error(error_msg)
                            raise ValueError(error_msg)

                        filename = content_disposition.split('filename=')[-1].strip('"')
                        filepath = os.path.join(output_directory, filename)

                        async with aiofiles.open(filepath, 'wb') as file:
                            total_size = 0
                            last_progress = 0
                            try:
                                async for chunk in response.content.iter_chunked(8192):
                                    await file.write(chunk)
                                    total_size += len(chunk)
                                    if expected_size:
                                        progress = int((total_size / expected_size) * 100)
                                        if progress >= last_progress + 5:
                                            logging.info(f'Downloading {tld}: {progress}% ({total_size:,}/{expected_size:,} bytes)')
                                            last_progress = progress
                            except (asyncio.TimeoutError, aiohttp.ClientError) as e:
                                logging.error(f'Connection error while downloading {tld}: {str(e)}')
                                if attempt + 1 < max_retries:
                                    logging.info(f'Retrying {tld} in {retry_delay} seconds...')
                                    await asyncio.sleep(retry_delay)
                                    continue
                                raise

                        # Verify file size
                        if expected_size and total_size != expected_size:
                            error_msg = f'Incomplete download for {tld}: Got {total_size} bytes, expected {expected_size} bytes'
                            logging.error(error_msg)
                            os.remove(filepath)
                            if attempt + 1 < max_retries:
                                logging.info(f'Retrying {tld} in {retry_delay} seconds...')
                                await asyncio.sleep(retry_delay)
                                continue
                            raise Exception(error_msg)
                        
                        size_mb = total_size / (1024 * 1024)
                        logging.info(f'Successfully downloaded {tld} zone file ({size_mb:.2f} MB)')

                        if decompress:
                            try:
                                with gzip.open(filepath, 'rb') as test_gzip:
                                    test_gzip.read(1)
                                
                                await self.gzip_decompress(filepath, cleanup)
                                filepath = filepath[:-3]
                                logging.info(f'Decompressed {tld} zone file')
                            except (gzip.BadGzipFile, OSError) as e:
                                error_msg = f'Failed to decompress {tld}: {str(e)}'
                                logging.error(error_msg)
                                os.remove(filepath)
                                raise Exception(error_msg)

                        return filepath

                except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                    if attempt + 1 >= max_retries:
                        logging.error(f'Failed to download {tld} after {max_retries} attempts: {str(e)}')
                        if 'filepath' in locals() and os.path.exists(filepath):
                            os.remove(filepath)
                        raise
                    logging.warning(f'Download attempt {attempt + 1} failed for {tld}: {str(e)}')
                    await asyncio.sleep(retry_delay)

                except Exception as e:
                    logging.error(f'Error downloading {tld}: {str(e)}')
                    if 'filepath' in locals() and os.path.exists(filepath):
                        os.remove(filepath)
                    raise

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
        
        # Create the output directory if it doesn't exist
        os.makedirs(output_directory, exist_ok=True)
        
        logging.info(f'Starting concurrent download of zones with concurrency={concurrency}')

        # Get the zone links
        zone_links = await self.fetch_zone_links()

        # Create a semaphore to limit the number of concurrent downloads
        semaphore = asyncio.Semaphore(concurrency)

        # Create a list of tasks to download the zone files
        tasks = [self.download_zone(url, output_directory, decompress, cleanup, semaphore) for url in zone_links]

        # Run the tasks concurrently
        await asyncio.gather(*tasks)

        logging.info('Completed downloading all zone files')
