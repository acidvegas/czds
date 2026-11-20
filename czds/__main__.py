#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/czds/__main__.py

import argparse
import asyncio
import getpass
import logging
import os

from .client import CZDS


async def main() -> int:
	'''Entry point for the command line interface'''

	# Create argument parser
	parser = argparse.ArgumentParser(description='ICANN API for the Centralized Zones Data Service')

	# Authentication
	parser.add_argument('-u', '--username', default=os.getenv('CZDS_USER'), help='ICANN Username')
	parser.add_argument('-p', '--password', default=os.getenv('CZDS_PASS'), help='ICANN Password')
	parser.add_argument('-o', '--output', default=os.getcwd(), help='Output directory')

	# Zone download options
	zone_group = parser.add_argument_group('Zone download options')
	zone_group.add_argument('--zones', action='store_true', help='Download all zone files')
	zone_group.add_argument('-z', '--zone', nargs='+', metavar='TLD', help='Download specific zone files by TLD (e.g., com org)')
	zone_group.add_argument('-c', '--concurrency', type=int, default=3, help='Number of concurrent downloads')
	zone_group.add_argument('--no-decompress', action='store_true', help='Keep the zone files gzip compressed')
	zone_group.add_argument('--force', action='store_true', help='Download zone files even if the local copy is up to date')

	# Report options
	report_group = parser.add_argument_group('Report options')
	report_group.add_argument('-r', '--report', action='store_true', help='Download the zone stats report')
	report_group.add_argument('-s', '--scrub', action='store_true', help='Scrub the username from the report')
	report_group.add_argument('-f', '--format', choices=['csv', 'json'], default='csv', help='Report output format')

	# Zone request options
	request_group = parser.add_argument_group('Zone request options')
	request_group.add_argument('--request', nargs='+', metavar='TLD', help='Request access to zones (use "all" for every requestable zone)')
	request_group.add_argument('--reason', help='Reason for the zone request (required with --request)')
	request_group.add_argument('--extend', nargs='+', metavar='TLD', help='Request an extension for approved zones (use "all" for every zone expiring within 120 days)')
	request_group.add_argument('--cancel', nargs='+', metavar='TLD', help='Cancel pending zone requests')

	# Parse arguments
	args = parser.parse_args()

	# Require at least one action
	if not any((args.zones, args.zone, args.report, args.request, args.extend, args.cancel)):
		parser.error('no action specified (use --zones, -z, -r, --request, --extend or --cancel)')

	if args.request and not args.reason:
		parser.error('--reason is required with --request')

	# Configure logging
	logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

	# Get username and password
	username = args.username or input('ICANN Username: ')
	password = args.password or getpass.getpass('ICANN Password: ')

	# Create the CZDS client
	async with CZDS(username, password) as client:
		# Cancel zone requests if requested
		if args.cancel:
			for tld in args.cancel:
				await client.cancel_request(tld)
				logging.info(f'Cancelled request for {tld}')

		# Extend zone requests if requested
		if args.extend:
			if args.extend == ['all']:
				extended = await client.extend_all()
				logging.info(f'Requested extensions for {len(extended):,} zones')
			else:
				for tld in args.extend:
					await client.extend_request(tld)
					logging.info(f'Requested extension for {tld}')

		# Request access to zones if requested
		if args.request:
			await client.request_zones(args.reason, None if args.request == ['all'] else args.request)

		# Download zone stats report if requested
		if args.report:
			logging.info('Fetching zone stats report...')
			try:
				# Create the report filepath
				output = os.path.join(args.output, f'report.{args.format}')

				# Download the report
				await client.get_report(output, scrub=args.scrub, format=args.format)

				logging.info(f'Zone stats report saved to {output}')
			except Exception as e:
				raise Exception(f'Failed to download zone stats report: {e}') from e

		# Download zone files if requested (all zones, or only the TLDs given with -z)
		if args.zones or args.zone:
			logging.info('Downloading zone files...')
			try:
				# Download the zone files
				failed = await client.download_zones(os.path.join(args.output, 'zones'), args.concurrency, args.zone, not args.no_decompress, args.force)
			except Exception as e:
				raise Exception(f'Failed to download zone files: {e}') from e

			# Exit with an error if any zone failed
			if failed:
				return 1

	return 0


def cli_entry() -> int:
	'''Synchronous entry point for console script'''

	return asyncio.run(main())



if __name__ == '__main__':
	raise SystemExit(cli_entry())
