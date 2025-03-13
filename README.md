# ICANN Centralized Zone Data Service API

The [ICANN Centralized Zone Data Service](https://czds.icann.org) *(CZDS)* allows *approved* users to request and download DNS zone files in bulk, provided they represent a legitimate company or academic institution and their intended use is legal and ethical. Once ICANN approves the request, this tool streamlines the retrieval of extensive domain name system data, facilitating research and security analysis in the realm of internet infrastructure.

## Features
* Asynchronous downloads with configurable concurrency
* Support for both CSV and JSON report formats
* Optional gzip decompression of zone files
* Environment variable support for credentials
* Comprehensive error handling and logging

## Zone Information
Zone files are updated once every 24 hours, specifically from 00:00 UTC to 06:00 UTC. Access to these zones is granted in increments, and the total time for approval across all zones may extend to a month or longer. It is typical for more than 90% of requested zones to receive approval. Access to certain zone files may require additional application forms with the TLD organization. Please be aware that access to certain zones is time-bound, expiring at the beginning of the following year, or up to a decade after the initial approval has been confirmed.

At the time of writing this repository, the CZDS offers access to 1,151 zones in total.

1,079 have been approved, 55 are still pending *(after 3 months)*, 10 have been revoked because the TLDs are longer active, and 6 have been denied. Zones that have expired automatically had the expiration extended for me without doing anything, aside from 13 zones that remained expired. I have included a recent [stats file](./extras/stats.csv) directly from my ICANN account.

## Installation
```bash
pip install czds-api
```

## Usage
### Command Line Interface
```bash
czds [-h] [-u USERNAME] [-p PASSWORD] [-z] [-c CONCURRENCY] [-d] [-k] [-r] [-s] [-f {csv,json}] [-o OUTPUT]
```

#### Arguments
###### Basic Options
| Argument              | Description                                  | Default           |
|-----------------------|----------------------------------------------|-------------------|
| `-h`, `--help`        | Show help message and exit                   |                   |
| `-u`, `--username`    | ICANN Username                               | `$CZDS_USER`      |
| `-p`, `--password`    | ICANN Password                               | `$CZDS_PASS`      |
| `-o`, `--output`      | Output directory                             | Current directory |

###### Zone Options
| `-z`, `--zones`       | Download zone files                          |                   |
| `-c`, `--concurrency` | Number of concurrent downloads               | `3`               |
| `-d`, `--decompress`  | Decompress zone files after download         |                   |
| `-k`, `--keep`        | Keep original gzip files after decompression |                   |

###### Report Options
| `-r`, `--report`      | Download the zone stats report               |                   |
| `-s`, `--scrub`       | Scrub username from the report               |                   |
| `-f`, `--format`      | Report output format (csv/json)              | `csv`             |

### Environment Variables
```bash
export CZDS_USER='your_username'
export CZDS_PASS='your_password'
```

### Python Module
```python
import os
from czds import CZDS

async with CZDS(username, password) as client:
    # Download zone stats report
    await client.get_report('report.csv', scrub=True, format='json')
    
    # Download zone files
    zone_links = await client.fetch_zone_links()
    await client.download_zones(zone_links, 'zones', concurrency=3, decompress=True)
```

## Zone Information
Zone files are updated once every 24 hours, specifically from 00:00 UTC to 06:00 UTC. Access to these zones is granted in increments, and the total time for approval across all zones may extend to a month or longer. It is typical for more than 90% of requested zones to receive approval. Access to certain zone files may require additional application forms with the TLD organization. Please be aware that access to certain zones is time-bound, expiring at the beginning of the following year, or up to a decade after the initial approval has been confirmed.

At the time of writing this repository, the CZDS offers access to 1,151 zones in total.

1,079 have been approved, 55 are still pending *(after 3 months)*, 10 have been revoked because the TLDs are longer active, and 6 have been denied. Zones that have expired automatically had the expiration extended for me without doing anything, aside from 13 zones that remained expired. I have included a recent [stats file](./extras/stats.csv) directly from my ICANN account.

## Respects & extras
While ICANN does have an official [czds-api-client-python](https://github.com/icann/czds-api-client-python) repository, I rewrote it from scratch to be more streamline & included a [POSIX version](./extras/czds) for portability. There is some [official documentation](https://raw.githubusercontent.com/icann/czds-api-client-java/master/docs/ICANN_CZDS_api.pdf) that was referenced in the creation of the POSIX version. Either way, big props to ICANN for allowing me to use the CZDS for research purposes!

___

###### Mirrors for this repository: [acid.vegas](https://git.acid.vegas/czds) • [SuperNETs](https://git.supernets.org/acidvegas/czds) • [GitHub](https://github.com/acidvegas/czds) • [GitLab](https://gitlab.com/acidvegas/czds) • [Codeberg](https://codeberg.org/acidvegas/czds)