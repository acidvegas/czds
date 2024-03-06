#!/usr/bin/env python
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# Reference: https://czds.icann.org

import argparse
import concurrent.futures
import getpass
import json
import logging
import os
import time
import urllib.request


# Setting up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def authenticate(username: str, password: str) -> str:
	'''
	Authenticate with the ICANN API and return the access token.

	:param username: ICANN Username
	:param password: ICANN Password
	'''

	data	= json.dumps({'username': username, 'password': password}).encode('utf-8')
	headers = {'Content-Type': 'application/json'}
	request = urllib.request.Request('https://account-api.icann.org/api/authenticate', data=data, headers=headers)

	with urllib.request.urlopen(request) as response:
		response = response.read().decode('utf-8')
		return json.loads(response)['accessToken']


def fetch_zone_links(token: str) -> list:
	'''
	Fetch the list of zone files available for download.

	:param token: ICANN access token
	'''

	headers = {'Authorization': f'Bearer {token}'}
	request = urllib.request.Request('https://czds-api.icann.org/czds/downloads/links', headers=headers)

	with urllib.request.urlopen(request) as response:
		if response.status == 200:
			return json.loads(response.read().decode('utf-8'))
		else:
			raise Exception(f'Failed to fetch zone links: {response.status} {response.reason}')


def download_report(token: str, output_directory: str, username: str):
	'''
	Downloads the zone report stats from the API and scrubs the report for privacy.

	:param token: ICANN access token
	:param output_directory: Directory to save the scrubbed report
	:param username: Username to be redacted
	'''

	filepath = os.path.join(output_directory, '.stats.csv')
	headers  = {'Authorization': f'Bearer {token}'}
	request  = urllib.request.Request('https://czds-api.icann.org/czds/requests/report', headers=headers)

	with urllib.request.urlopen(request) as response:
		if response.status == 200:
			report_data = response.read().decode('utf-8').replace(username, 'nobody@no.name')
			with open(filepath, 'w') as file:
				file.write(report_data)
		else:
			raise Exception(f'Failed to download the zone stats report: {response.status} {response.reason}')



def download_zone(url: str, token: str, output_directory: str):
	'''
	Download a single zone file using urllib.request.

	:param url: URL to download
	:param token: ICANN access token
	:param output_directory: Directory to save the zone file
	'''

	headers = {'Authorization': f'Bearer {token}'}
	request = urllib.request.Request(url, headers=headers)

	with urllib.request.urlopen(request) as response:
		if response.status == 200:
			content_disposition = response.getheader('Content-Disposition')
			if content_disposition:
				filename = content_disposition.split('filename=')[-1].strip('"')
			else:
				raise ValueError(f'Failed to get filename from Content-Disposition header: {content_disposition}')

			filepath = os.path.join(output_directory, filename)

			with open(filepath, 'wb') as file:
				while True:
					chunk = response.read(1024)
					if not chunk:
						break
					file.write(chunk)

			return filepath
		else:
			raise Exception(f'Failed to download {url}: {response.status} {response.reason}')


def main(username: str, password: str, concurrency: int):
	'''
	Main function to download all zone files.

	:param username: ICANN Username
	:param password: ICANN Password
	:param concurrency: Number of concurrent downloads
	'''

	now = time.strftime('%Y-%m-%d')

	logging.info(f'Authenticating with ICANN API...')
	try:
		token = authenticate(username, password)
	except Exception as e:
		raise Exception(f'Failed to authenticate with ICANN API: {e}')
	#logging.info(f'Authenticated with token: {token}')
	# The above line is commented out to avoid printing the token to the logs, you can uncomment it for debugging purposes

	output_directory = os.path.join(os.getcwd(), 'zones', now)
	os.makedirs(output_directory, exist_ok=True)

	logging.info('Fetching zone stats report...')
	try:
		download_report(token, output_directory, username)
	except Exception as e:
		raise Exception(f'Failed to download zone stats report: {e}')

	logging.info('Fetching zone links...')
	try:
		zone_links = fetch_zone_links(token)
	except Exception as e:
		raise Exception(f'Failed to fetch zone links: {e}')
	logging.info(f'Fetched {len(zone_links)} zone links')

	with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
		future_to_url = {executor.submit(download_zone, url, token, output_directory): url for url in zone_links}
		for future in concurrent.futures.as_completed(future_to_url):
			url = future_to_url[future]
			try:
				filepath = future.result()
				logging.info(f'Completed downloading {url} to file {filepath}')
			except Exception as e:
				logging.error(f'{url} generated an exception: {e}')



if __name__ == '__main__':
	parser = argparse.ArgumentParser(description='ICANN API for the Centralized Zones Data Service')
	parser.add_argument('-u', '--username', help='ICANN Username')
	parser.add_argument('-p', '--password', help='ICANN Password')
	parser.add_argument('-c', '--concurrency', type=int, default=3, help='Number of concurrent downloads')
	args = parser.parse_args()

	username = args.username or os.getenv('CZDS_USER') or input('ICANN Username: ')
	password = args.password or os.getenv('CZDS_PASS') or getpass.getpass('ICANN Password: ')

	main(username, password, args.concurrency)
