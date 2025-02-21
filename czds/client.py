#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/client.py

import json
import os
import urllib.request


class CZDS:
    '''Class for the ICANN Centralized Zones Data Service'''

    def __init__(self, username: str, password: str):
        '''
        Initialize CZDS client
        
        :param username: ICANN Username
        :param password: ICANN Password
        '''

        self.username = username
        self.headers  = {'Authorization': f'Bearer {self.authenticate(username, password)}'}


    def authenticate(self, username: str, password: str) -> str:
        '''
        Authenticate with the ICANN API and return the access token
        
        :param username: ICANN Username
        :param password: ICANN Password
        '''

        try:
            data    = json.dumps({'username': username, 'password': password}).encode('utf-8')
            headers = {'Content-Type': 'application/json'}
            request = urllib.request.Request('https://account-api.icann.org/api/authenticate', data=data, headers=headers)
            
            with urllib.request.urlopen(request) as response:
                response = response.read().decode('utf-8')
            
            return json.loads(response)['accessToken']
        except Exception as e:
            raise Exception(f'Failed to authenticate with ICANN API: {e}')


    def fetch_zone_links(self) -> list:
        '''Fetch the list of zone files available for download'''
        
        request = urllib.request.Request('https://czds-api.icann.org/czds/downloads/links', headers=self.headers)
        
        with urllib.request.urlopen(request) as response:
            if response.status != 200:
                raise Exception(f'Failed to fetch zone links: {response.status} {response.reason}')
            
            return json.loads(response.read().decode('utf-8'))


    def download_report(self, filepath: str):
        '''
        Downloads the zone report stats from the API and scrubs the report for privacy
        
        :param filepath: Filepath to save the scrubbed report
        '''
        
        request = urllib.request.Request('https://czds-api.icann.org/czds/requests/report', headers=self.headers)
        
        with urllib.request.urlopen(request) as response:
            if response.status != 200:
                raise Exception(f'Failed to download the zone stats report: {response.status} {response.reason}')
            
            content = response.read().decode('utf-8')

        with open(filepath, 'w') as file:
            file.write(content.replace(self.username, 'nobody@no.name'))


    def download_zone(self, url: str, output_directory: str) -> str:
        '''
        Download a single zone file
        
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