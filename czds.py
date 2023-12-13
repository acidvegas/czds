#!/usr/bin/env python
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)

'''
References:
    - https://czds.icann.org
    - https://czds.icann.org/sites/default/files/czds-api-documentation.pdf
'''

import argparse
import concurrent.futures
import getpass
import logging
import os


try:
    import requests
except ImportError:
    raise ImportError('Missing dependency: requests (pip install requests)')


def authenticate(username: str, password: str) -> str:
    '''
    Authenticate with ICANN's API and return the access token.
    
    :param username: ICANN Username
    :param password: ICANN Password
    '''
    response = requests.post('https://account-api.icann.org/api/authenticate', json={'username': username, 'password': password})
    response.raise_for_status()
    return response.json()['accessToken']


def download_zone(url: str, token: str, output_directory: str):
    '''
    Download a single zone file.
    
    :param url: URL to download
    :param token: ICANN access token
    :param output_directory: Directory to save the zone file
    '''
    headers = {'Authorization': f'Bearer {token}'}
    response = requests.get(url, headers=headers)
    response.raise_for_status()
    filename = response.headers.get('Content-Disposition').split('filename=')[-1].strip('"')
    filepath = os.path.join(output_directory, filename)
    with open(filepath, 'wb') as file:
        for chunk in response.iter_content(chunk_size=1024):
            file.write(chunk)
    return filepath


def main(username: str, password: str, concurrency: int):
    '''
    Main function to download all zone files.

    :param username: ICANN Username
    :param password: ICANN Password
    :param concurrency: Number of concurrent downloads
    '''
    token = authenticate(username, password)
    headers = {'Authorization': f'Bearer {token}'}
    
    response = requests.get('https://czds-api.icann.org/czds/downloads/links', headers=headers)
    response.raise_for_status()
    zone_links = response.json()
    
    output_directory = 'zonefiles'
    os.makedirs(output_directory, exist_ok=True)
    
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
    parser = argparse.ArgumentParser(description="ICANN Zone Files Downloader")
    parser.add_argument('-u', '--username', help='ICANN Username')
    parser.add_argument('-p', '--password', help='ICANN Password')
    parser.add_argument('-c', '--concurrency', type=int, default=5, help='Number of concurrent downloads')
    args = parser.parse_args()

    username = args.username or os.getenv('CZDS_USER')
    password = args.password or os.getenv('CZDS_PASS')

    if not username:
        username = input('ICANN Username: ')
    if not password:
        password = getpass.getpass('ICANN Password: ')
    
    try:
        main(username, password, args.concurrency)
    except requests.HTTPError as e:
        logging.error(f'HTTP error occurred: {e.response.status_code} - {e.response.reason}')
    except Exception as e:
        logging.error(f'An error occurred: {e}')