#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/czds/__init__.py

# Metadata is defined before the import so client.py can read __version__ for its User-Agent
__version__ = '1.4.0'
__author__  = 'acidvegas'
__email__   = 'acid.vegas@acid.vegas'
__github__  = 'https://github.com/acidvegas/czds'
__all__     = ['CZDS']

from .client import CZDS
