#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# setup.py

from setuptools import setup, find_packages


with open('README.md', 'r', encoding='utf-8') as fh:
	long_description = fh.read()


setup(
	name='czds-api',
	version='1.2.3',
	author='acidvegas',
	author_email='acid.vegas@acid.vegas',
	description='ICANN API for the Centralized Zones Data Service',
	long_description=long_description,
	long_description_content_type='text/markdown',
	url='https://github.com/acidvegas/czds',
	project_urls={
		'Bug Tracker': 'https://github.com/acidvegas/czds/issues',
		'Documentation': 'https://github.com/acidvegas/czds#readme',
		'Source Code': 'https://github.com/acidvegas/czds',
	},
	classifiers=[
		'Development Status :: 5 - Production/Stable',
		'Intended Audience :: Developers',
		'License :: OSI Approved :: ISC License (ISCL)',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.6',
		'Programming Language :: Python :: 3.7',
		'Programming Language :: Python :: 3.8',
		'Programming Language :: Python :: 3.9',
		'Programming Language :: Python :: 3.10',
		'Programming Language :: Python :: 3.11',
		'Topic :: Internet',
		'Topic :: Security',
		'Topic :: Software Development :: Libraries :: Python Modules',
	],
	packages=find_packages(),
	python_requires='>=3.6',
	entry_points={
		'console_scripts': [
			'czds=czds.__main__:cli_entry',
		],
	},
	install_requires=[
		'aiohttp>=3.8.0',
		'aiofiles>=23.2.1',
	],
)