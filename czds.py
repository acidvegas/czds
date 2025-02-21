#!/usr/bin/env python3
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


class CZDS:
	'''Class for the ICANN Centralized Zones Data Service'''

	def __init__(self, username: str, password: str):
		self.headers = {'Authorization': f'Bearer {self.authenticate(username, password)}'}


	def authenticate(self, username: str, password: str) -> dict:
		'''
		Authenticate with the ICANN API and return the access token.

		:param username: ICANN Username
		:param password: ICANN Password
		'''

		try:
			# Prepare the request
			data	= json.dumps({'username': username, 'password': password}).encode('utf-8')
			headers = {'Content-Type': 'application/json'}
			request = urllib.request.Request('https://account-api.icann.org/api/authenticate', data=data, headers=headers)

			# Make the request
			with urllib.request.urlopen(request) as response:
				response = response.read().decode('utf-8')
			
			return json.loads(response)['accessToken']

		except Exception as e:
			raise Exception(f'Failed to authenticate with ICANN API: {e}')


	def fetch_zone_links(self) -> list:
		'''
		Fetch the list of zone files available for download.

		:param token: ICANN access token
		'''

		request = urllib.request.Request('https://czds-api.icann.org/czds/downloads/links', headers=self.headers)

		with urllib.request.urlopen(request) as response:
			if response.status == 200:
				return json.loads(response.read().decode('utf-8'))
			else:
				raise Exception(f'Failed to fetch zone links: {response.status} {response.reason}')


	def download_report(self, output_directory):
		'''
		Downloads the zone report stats from the API and scrubs the report for privacy.

		:param token: ICANN access token
		:param output_directory: Directory to save the scrubbed report
		:param username: Username to be redacted
		'''

		filepath = os.path.join(output_directory, '.stats.csv')
		request  = urllib.request.Request('https://czds-api.icann.org/czds/requests/report', headers=self.headers)

		with urllib.request.urlopen(request) as response:
			if not (response.status == 200):
				raise Exception(f'Failed to download the zone stats report: {response.status} {response.reason}')

			report_data = response.read().decode('utf-8').replace(username, 'nobody@no.name')
			with open(filepath, 'w') as file:
				file.write(report_data)


	def download_zone(self, url: str, output_directory: str):
		'''
		Download a single zone file using urllib.request.

		:param url: URL to download
		:param output_directory: Directory to save the zone file
		'''

		request = urllib.request.Request(url, headers=self.headers)

		with urllib.request.urlopen(request) as response:
			if response.status != 200:
				raise Exception(f'Failed to download {url}: {response.status} {response.reason}')

			if not (content_disposition := response.getheader('Content-Disposition')):
				raise ValueError('Missing Content-Disposition header')

			filename = content_disposition.split('filename=')[-1].strip('"')
			filepath = os.path.join(output_directory, filename)

			with open(filepath, 'wb') as file:
				while True:
					chunk = response.read(1024)
					if not chunk:
						break
					file.write(chunk)

			return filepath


def main(username: str, password: str, concurrency: int):
	'''
	Main function to download all zone files.

	:param username: ICANN Username
	:param password: ICANN Password
	:param concurrency: Number of concurrent downloads
	'''

	now = time.strftime('%Y-%m-%d')

	logging.info(f'Authenticating with ICANN API...')
	
	CZDS_client = CZDS(username, password)

	logging.debug('Created CZDS client')
	
	output_directory = os.path.join(os.getcwd(), 'zones', now)
	os.makedirs(output_directory, exist_ok=True)

	logging.info('Fetching zone stats report...')	
	
	try:
		CZDS_client.download_report(output_directory)
	except Exception as e:
		raise Exception(f'Failed to download zone stats report: {e}')

	logging.info('Fetching zone links...')

	try:
		zone_links = CZDS_client.fetch_zone_links()
	except Exception as e:
		raise Exception(f'Failed to fetch zone links: {e}')
	
	logging.info(f'Fetched {len(zone_links):,} zone links')

	with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
		future_to_url = {executor.submit(CZDS_client.download_zone, url, output_directory): url for url in sorted(zone_links)}
		for future in concurrent.futures.as_completed(future_to_url):
			url = future_to_url[future]
			try:
				filepath = future.result()
				logging.info(f'Completed downloading {url} to file {filepath}')
			except Exception as e:
				logging.error(f'{url} generated an exception: {e}')



if __name__ == '__main__':
	# Create argument parser
	parser = argparse.ArgumentParser(description='ICANN API for the Centralized Zones Data Service')

	# Add arguments
	parser.add_argument('-u', '--username', default=os.getenv('CZDS_USER'), help='ICANN Username')
	parser.add_argument('-p', '--password', default=os.getenv('CZDS_PASS'), help='ICANN Password')
	parser.add_argument('-c', '--concurrency', type=int, default=3, help='Number of concurrent downloads')

	# Parse arguments
	args = parser.parse_args()

	# Setting up logging
	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

	# Get username and password
	username = args.username or input('ICANN Username: ')
	password = args.password or getpass.getpass('ICANN Password: ')

	# Execute main function
	main(username, password, args.concurrency)
