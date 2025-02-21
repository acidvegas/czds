#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/__main__.py

import argparse
import concurrent.futures
import getpass
import logging
import os
import time

from .client import CZDS


def main(username: str, password: str, concurrency: int) -> None:
    '''
    Main function to download all zone files
    
    :param username: ICANN Username
    :param password: ICANN Password
    :param concurrency: Number of concurrent downloads
    '''

    now = time.strftime('%Y-%m-%d')
    
    logging.info('Authenticating with ICANN API...')

    CZDS_client = CZDS(username, password)

    logging.debug('Created CZDS client')
    
    output_directory = os.path.join(os.getcwd(), 'zones', now)
    os.makedirs(output_directory, exist_ok=True)
    
    logging.info('Fetching zone stats report...')

    try:
        CZDS_client.download_report(os.path.join(output_directory, '.report.csv'))
    except Exception as e:
        raise Exception(f'Failed to download zone stats report: {e}')
    
    logging.info('Fetching zone links...')

    try:
        zone_links = CZDS_client.fetch_zone_links()
    except Exception as e:
        raise Exception(f'Failed to fetch zone links: {e}')
    
    logging.info(f'Fetched {len(zone_links):,} zone links')

    logging.info('Downloading zone files...')
    
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
    parser = argparse.ArgumentParser(description='ICANN API for the Centralized Zones Data Service')
    parser.add_argument('-u', '--username', default=os.getenv('CZDS_USER'), help='ICANN Username')
    parser.add_argument('-p', '--password', default=os.getenv('CZDS_PASS'), help='ICANN Password')
    parser.add_argument('-c', '--concurrency', type=int, default=3, help='Number of concurrent downloads')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    username = args.username or input('ICANN Username: ')
    password = args.password or getpass.getpass('ICANN Password: ')
    
    main(username, password, args.concurrency) 