#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/czds/client.py

import asyncio
import contextlib
import csv
import io
import json
import logging
import os
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

try:
	import aiohttp
except ImportError:
	raise ImportError('missing aiohttp library (pip install aiohttp)') from None

try:
	import aiofiles
except ImportError:
	raise ImportError('missing aiofiles library (pip install aiofiles)') from None

try:
	from tqdm import tqdm
except ImportError:
	raise ImportError('missing tqdm library (pip install tqdm)') from None

from . import __version__
from .utils import gzip_decompress, humanize_bytes


API_URL  = 'https://czds-api.icann.org'
AUTH_URL = 'https://account-api.icann.org/api/authenticate'

# Statuses from /czds/tlds that can be requested
REQUESTABLE = ('available', 'canceled', 'denied', 'expired', 'revoked')


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
		connector = aiohttp.TCPConnector(keepalive_timeout=300, force_close=False, enable_cleanup_closed=True, ttl_dns_cache=300)

		# Set the session with longer timeouts and keepalive
		self.session = aiohttp.ClientSession(
			connector=connector,
			timeout=aiohttp.ClientTimeout(total=None, connect=60, sock_connect=60, sock_read=None),
			headers={'User-Agent': f'czds-api/{__version__}'},
			raise_for_status=True
		)

		# Placeholder for the headers after authentication
		self.headers = None

		# Lock so concurrent tasks only re-authenticate once when the token expires
		self.auth_lock = asyncio.Lock()

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


	async def _api(self, method: str, url: str, data: dict | None = None, read: str = 'json') -> dict | list | str:
		'''
		Send an authenticated request to the CZDS API, re-authenticating once if the access token expired

		:param method: HTTP method
		:param url: URL to request
		:param data: Optional JSON body
		:param read: What to return from the response ('json', 'text' or 'headers')
		'''

		for attempt in range(2):
			headers = self.headers

			try:
				async with self.session.request(method, url, headers=headers, json=data) as response:
					if read == 'headers':
						return response.headers
					elif read == 'text':
						return await response.text()
					return await response.json(content_type=None)
			except aiohttp.ClientResponseError as e:
				if e.status != 401 or attempt:
					raise
				await self._reauthenticate(headers)


	async def _download(self, url: str, tld_name: str, filepath: str) -> float:
		'''
		Download a zone file with retries and return its Last-Modified timestamp

		:param url: URL to download
		:param tld_name: Name of the TLD
		:param filepath: Path to save the gzip zone file
		'''

		max_retries = 20 # Maximum number of retries for failed downloads
		retry_delay = 5  # Delay between retries in seconds

		for attempt in range(1, max_retries + 1):
			headers = self.headers

			try:
				logging.info(f'Starting download of {tld_name} zone file{f" (attempt {attempt})" if attempt > 1 else ""} [{url}]')

				# Send the request to the API
				async with self.session.get(url, headers=headers) as response:
					# Get expected file size from headers
					if not (expected_size := int(response.headers.get('Content-Length', 0))):
						raise ValueError(f'Missing Content-Length header for {tld_name}')

					# Create a progress bar to track the download
					with tqdm(total=expected_size, unit='B', unit_scale=True, desc=f'Downloading {tld_name}', leave=False) as pbar:
						# Open the file for writing
						async with aiofiles.open(filepath, 'wb') as file:
							# Initialize the total size for tracking
							total_size = 0

							# Write the chunk to the file
							async for chunk in response.content.iter_chunked(8192):
								await file.write(chunk)
								total_size += len(chunk)
								pbar.update(len(chunk))

					# Verify file size
					if total_size != expected_size:
						raise ValueError(f'Incomplete download for {tld_name}: Got {humanize_bytes(total_size)}, expected {humanize_bytes(expected_size)}')

					logging.info(f'Successfully downloaded {tld_name} zone file ({humanize_bytes(total_size)})')

					return parsedate_to_datetime(response.headers['Last-Modified']).timestamp()

			except aiohttp.ClientResponseError as e:
				# Re-authenticate on an expired token, never retry other client errors (403 no access, 409 terms not accepted)
				if e.status == 401:
					await self._reauthenticate(headers)
				elif e.status < 500:
					raise
				error = e
			except (aiohttp.ClientError, TimeoutError, ValueError) as e:
				error = e

			# Remove the partial download
			if os.path.exists(filepath):
				os.remove(filepath)

			if attempt == max_retries:
				raise Exception(f'Failed to download {tld_name} after {max_retries} attempts: {error}') from error

			logging.warning(f'Download attempt {attempt} failed for {tld_name}: {error!s}, retrying in {retry_delay} seconds...')
			await asyncio.sleep(retry_delay)


	async def _reauthenticate(self, stale_headers: dict):
		'''
		Re-authenticate unless another task already replaced the expired token

		:param stale_headers: The headers that were rejected with a 401
		'''

		async with self.auth_lock:
			if self.headers is stale_headers:
				logging.warning('Access token expired, re-authenticating...')
				await self.authenticate()


	async def authenticate(self):
		'''Authenticate with the ICANN API and set the authorization headers'''

		# Set the data to be sent to the API
		data = {'username': self.username, 'password': self.password}

		logging.info('Authenticating with ICANN API...')

		# Send the request to the API
		async with self.session.post(AUTH_URL, json=data) as response:
			# Get the result from the API
			result = await response.json()

			logging.info('Successfully authenticated with ICANN API')

			# Set the headers for the API requests
			self.headers = {'Authorization': f'Bearer {result["accessToken"]}'}


	async def cancel_request(self, tld: str) -> dict:
		'''
		Cancel a pending zone access request

		:param tld: TLD of the request to cancel
		'''

		request_id = await self.get_request_id(tld)

		# The API refuses (405) to cancel a request it does not mark as cancellable
		if not (info := await self.get_request_info(request_id))['cancellable']:
			raise Exception(f'Request for {tld} is not cancellable while {info["status"]}')

		return await self._api('POST', f'{API_URL}/czds/requests/cancel', {'integrationId': request_id, 'tldName': info['tld']['tld']})


	async def close(self):
		'''Close the client session'''

		# Close the client session
		await self.session.close()
		logging.debug('Closed aiohttp session')


	async def download_zone(self, url: str, output_directory: str, semaphore: asyncio.Semaphore | None = None, decompress: bool = True, force: bool = False) -> str:
		'''
		Download a single zone file, skipping it if the local copy is already up to date

		:param url: URL to download
		:param output_directory: Directory to save the zone file
		:param semaphore: Optional semaphore for controlling concurrency
		:param decompress: Whether to decompress the gzip zone file
		:param force: Download even if the local copy is up to date
		'''

		tld_name = url.rsplit('/', 1)[-1].removesuffix('.zone') # Extract TLD from URL

		async with semaphore or contextlib.nullcontext():
			# Check the zone file status without downloading it
			info = await self._api('HEAD', url, read='headers')

			# Extract the filename from the Content-Disposition header
			if not (content_disposition := info.get('Content-Disposition')):
				raise ValueError(f'Missing Content-Disposition header for {tld_name}')

			filename   = content_disposition.split('filename=')[-1].strip('"')
			filepath   = os.path.join(output_directory, filename)
			final_path = filepath.removesuffix('.gz') if decompress else filepath

			# Skip the zone if the local copy matches the remote Last-Modified time
			if not force and os.path.exists(final_path) and os.path.getmtime(final_path) == parsedate_to_datetime(info['Last-Modified']).timestamp():
				logging.info(f'Skipping {tld_name} zone file, already up to date')
				return final_path

			last_modified = await self._download(url, tld_name, filepath)

		# Decompress outside the semaphore so it does not hold a download slot
		if decompress:
			await gzip_decompress(filepath)
			logging.info(f'Decompressed {tld_name} zone file')

		# Stamp the file with the remote Last-Modified time for the next up to date check
		os.utime(final_path, (last_modified, last_modified))

		return final_path


	async def download_zones(self, output_directory: str, concurrency: int = 3, tlds: list | None = None, decompress: bool = True, force: bool = False) -> list:
		'''
		Download multiple zone files concurrently and return the TLDs that failed

		:param output_directory: Directory to save the zone files
		:param concurrency: Number of concurrent downloads
		:param tlds: Optional list of TLDs to download (default: all approved zones)
		:param decompress: Whether to decompress the gzip zone files
		:param force: Download even if the local copy is up to date
		'''

		# Create the output directory if it doesn't exist
		os.makedirs(output_directory, exist_ok=True)

		# Get the zone links sorted alphabetically for better tracking
		zone_links = sorted(await self.fetch_zone_links(tlds))

		# Create a semaphore to limit the number of concurrent downloads
		semaphore = asyncio.Semaphore(concurrency)

		logging.info(f'Downloading {len(zone_links):,} zone files...')

		# Run the downloads concurrently, one failed zone does not stop the others
		results = await asyncio.gather(*[self.download_zone(url, output_directory, semaphore, decompress, force) for url in zone_links], return_exceptions=True)

		# Collect the failed zones
		failed = []
		for url, result in zip(zone_links, results, strict=True):
			if isinstance(result, BaseException):
				tld_name = url.rsplit('/', 1)[-1].removesuffix('.zone')
				logging.error(f'Failed to download {tld_name} zone file: {result}')
				failed.append(tld_name)

		logging.info(f'Completed downloading {len(zone_links) - len(failed):,}/{len(zone_links):,} zone files')

		if failed:
			logging.error(f'Failed zones: {", ".join(failed)}')

		return failed


	async def extend_all(self, days: int = 120) -> list:
		'''
		Request extensions for every approved zone expiring soon that is extensible and return the extended TLDs

		:param days: Only check zones expiring within this many days
		'''

		cutoff   = time.time() + days * 86400
		extended = []

		for request in await self.get_requests('Approved'):
			# Skip zones that do not expire soon
			if datetime.fromisoformat(request['expired']).timestamp() > cutoff:
				continue

			# Only extend requests the API marks as extensible
			if (await self.get_request_info(request['requestId']))['extensible']:
				await self._api('POST', f'{API_URL}/czds/requests/extension/{request["requestId"]}', {})
				logging.info(f'Requested extension for {request["tld"]}')
				extended.append(request['tld'])

		return extended


	async def extend_request(self, tld: str) -> dict:
		'''
		Request an extension for an approved zone

		:param tld: TLD to extend
		'''

		request_id = await self.get_request_id(tld)

		# Only requests the API marks as extensible can be extended
		if not (await self.get_request_info(request_id))['extensible']:
			raise Exception(f'Request for {tld} is not extensible yet')

		info = await self._api('POST', f'{API_URL}/czds/requests/extension/{request_id}', {})

		if not info['extensionInProcess']:
			raise Exception(f'Failed to initiate extension for {tld}, it may not be extensible yet')

		return info


	async def fetch_zone_links(self, tlds: list | None = None) -> list:
		'''
		Fetch the list of zone files available for download

		:param tlds: Optional list of TLDs to filter the zone links
		'''

		logging.info('Fetching zone file links...')

		# Send the request to the API
		links = await self._api('GET', f'{API_URL}/czds/downloads/links')

		logging.info(f'Successfully fetched {len(links):,} zone links')

		# Filter the zone links if TLDs are provided
		if tlds:
			wanted = {tld.lower().lstrip('.') for tld in tlds}
			links  = [link for link in links if link.rsplit('/', 1)[-1].removesuffix('.zone') in wanted]

			# Check every TLD is available for download
			if missing := wanted - {link.rsplit('/', 1)[-1].removesuffix('.zone') for link in links}:
				raise Exception(f'Zone(s) not found in available zones: {", ".join(sorted(missing))}')

		return links


	async def get_report(self, filepath: str | None = None, scrub: bool = False, format: str = 'csv') -> str:
		'''
		Downloads the zone report stats from the API and optionally scrubs the report for privacy

		:param filepath: Filepath to save the report
		:param scrub: Whether to scrub the username from the report
		:param format: Output format ('csv' or 'json')
		'''

		logging.info('Downloading zone stats report')

		# Get the content of the report
		content = await self._api('GET', f'{API_URL}/czds/requests/report', read='text')

		# Scrub the username from the report if requested
		if scrub:
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


	async def get_request_id(self, tld: str) -> str:
		'''
		Get the ID of the most recent request for a TLD

		:param tld: TLD to look up
		'''

		tld = tld.lower().lstrip('.')

		for request in await self.get_requests(search=tld):
			if request['tld'] == tld:
				return request['requestId']

		raise Exception(f'No request found for {tld}')


	async def get_request_info(self, request_id: str) -> dict:
		'''
		Get the details and history of a zone request

		:param request_id: ID of the request
		'''

		return await self._api('GET', f'{API_URL}/czds/requests/{request_id}')


	async def get_requests(self, status: str = '', search: str = '') -> list:
		'''
		Get all zone requests, newest first

		:param status: Optional status filter ('Submitted', 'Pending', 'Approved', 'Denied', 'Revoked', 'Expired', 'Canceled')
		:param search: Optional zone name search
		'''

		requests = []
		page     = 0

		# Fetch every page of results
		while True:
			data   = {'status': status, 'filter': search, 'pagination': {'size': 100, 'page': page}, 'sort': {'field': 'created', 'direction': 'desc'}}
			result = await self._api('POST', f'{API_URL}/czds/requests/all', data)

			if not result['requests']:
				return requests

			requests.extend(result['requests'])
			page += 1


	async def get_terms(self) -> dict:
		'''Get the current CZDS terms and conditions'''

		return await self._api('GET', f'{API_URL}/czds/terms/condition')


	async def get_tld_status(self) -> list:
		'''Get the current request status of every TLD'''

		return await self._api('GET', f'{API_URL}/czds/tlds')


	async def request_zones(self, reason: str, tlds: list | None = None) -> list:
		'''
		Request access to zones and return the requested TLDs

		:param reason: Reason for the request
		:param tlds: TLDs to request (default: every requestable zone)
		'''

		# Default to every zone that can be requested
		if not (requested := [tld.lower().lstrip('.') for tld in tlds or []]):
			requested = [tld['tld'] for tld in await self.get_tld_status() if tld['currentStatus'] in REQUESTABLE]

			if not requested:
				logging.info('No zones available to request')
				return requested

		# The request must reference the current terms and conditions version
		terms = await self.get_terms()

		await self._api('POST', f'{API_URL}/czds/requests/create', {'allTlds': not tlds, 'tldNames': requested, 'reason': reason, 'tcVersion': terms['version']})

		logging.info(f'Requested access to {len(requested):,} zones')

		return requested
