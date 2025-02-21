#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/__main__.py

import argparse
import asyncio
import getpass
import logging
import os
import time

from .client import CZDS


async def main():
    '''Entry point for the command line interface'''

    # Create argument parser
    parser = argparse.ArgumentParser(description='ICANN API for the Centralized Zones Data Service')

    # Authentication
    parser.add_argument('-u', '--username', default=os.getenv('CZDS_USER'), help='ICANN Username')
    parser.add_argument('-p', '--password', default=os.getenv('CZDS_PASS'), help='ICANN Password')
    
    # Zone download options
    parser.add_argument('-z', '--zones', action='store_true', help='Download zone files')
    parser.add_argument('-c', '--concurrency', type=int, default=3, help='Number of concurrent downloads')
    parser.add_argument('-d', '--decompress', action='store_true', help='Decompress zone files after download')
    parser.add_argument('-k', '--keep', action='store_true', help='Keep the original gzip files after decompression')

    # Report options
    parser.add_argument('-r', '--report', action='store_true', help='Download the zone stats report')
    parser.add_argument('-s', '--scrub', action='store_true', help='Scrub the username from the report')
    parser.add_argument('-f', '--format', choices=['csv', 'json'], default='csv', help='Report output format')

    # Output options
    parser.add_argument('-o', '--output', default=os.getcwd(), help='Output directory')

    # Parse arguments
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Get username and password
    username = args.username or input('ICANN Username: ')
    password = args.password or getpass.getpass('ICANN Password: ')

    # Create output directory
    now = time.strftime('%Y-%m-%d')
    output_directory = os.path.join(args.output, 'zones', now)
    os.makedirs(output_directory, exist_ok=True)

    logging.info('Authenticating with ICANN API...')

    async with CZDS(username, password) as client:
        # Download zone stats report if requested
        if args.report:
            logging.info('Fetching zone stats report...')
            try:
                output = os.path.join(output_directory, '.report.csv')
                await client.get_report(output, scrub=args.scrub, format=args.format)
                logging.info(f'Zone stats report saved to {output}')
                return
            except Exception as e:
                raise Exception(f'Failed to download zone stats report: {e}')
        
        # Download zone files if requested
        if args.zones:
            logging.info('Fetching zone links...')
            try:
                zone_links = await client.fetch_zone_links()
            except Exception as e:
                raise Exception(f'Failed to fetch zone links: {e}')

            logging.info(f'Downloading {len(zone_links):,} zone files...')
            await client.download_zones(zone_links, output_directory, args.concurrency, decompress=args.decompress, cleanup=not args.keep)



if __name__ == '__main__':
    asyncio.run(main()) 