# ICANN Centralized Zone Data Service API

The [ICANN Centralized Zone Data Service](https://czds.icann.org) *(CZDS)* allows *approved* users to request and download DNS zone files in bulk, provided they represent a legitimate company or academic institution and their intended use is legal and ethical. Once ICANN approves the request, this tool streamlines the retrieval of extensive domain name system data, facilitating research and security analysis in the realm of internet infrastructure.

## Features
* Asynchronous downloads with configurable concurrency
* Support for both CSV and JSON report formats
* Automatic gzip decompression of zone files *(optional)*
* Skips zones that have not changed since the last download
* Automatic re-authentication when the access token expires
* Zone access requests, extensions & cancellations
* Environment variable support for credentials
* Comprehensive error handling and logging

## Zone Information
Zone files are updated once every 24 hours, specifically from 00:00 UTC to 06:00 UTC. Access to these zones is granted in increments, and the total time for approval across all zones may extend to a month or longer. It is typical for more than 90% of requested zones to receive approval. Access to certain zone files may require additional application forms with the TLD organization. Please be aware that access to certain zones is time-bound, expiring at the beginning of the following year, or up to a decade after the initial approval has been confirmed.

At the time of writing this repository, the CZDS offers access to 1,150 zones in total.

1,066 have been approved, 51 are still pending, 12 have been revoked because the TLDs are no longer active, and 6 have been denied. Zones that have expired automatically had the expiration extended for me without doing anything, aside from 15 zones that remained expired. I have included a recent [stats file](./extras/stats.csv) directly from my ICANN account.

## Installation
```bash
pip install czds-api
```

## Usage
### Command Line Interface
```bash
czds [-h] [-u USERNAME] [-p PASSWORD] [-o OUTPUT] [--zones] [-z TLD [TLD ...]] [-c CONCURRENCY] [--no-decompress] [--force] [-r] [-s] [-f {csv,json}] [--request TLD [TLD ...]] [--reason REASON] [--extend TLD [TLD ...]] [--cancel TLD [TLD ...]]
```

#### Arguments
###### Basic Options
| Argument           | Description                | Default           |
|--------------------|----------------------------|-------------------|
| `-h`, `--help`     | Show help message and exit |                   |
| `-u`, `--username` | ICANN Username             | `$CZDS_USER`      |
| `-p`, `--password` | ICANN Password             | `$CZDS_PASS`      |
| `-o`, `--output`   | Output directory           | Current directory |

###### Zone Options
| Argument              | Description                                           | Default |
|-----------------------|-------------------------------------------------------|---------|
| `--zones`             | Download all zone files                               |         |
| `-z`, `--zone`        | Download specific zone files by TLD                   |         |
| `-c`, `--concurrency` | Number of concurrent downloads                        | `3`     |
| `--no-decompress`     | Keep the zone files gzip compressed                   |         |
| `--force`             | Download zone files even if the local copy is current |         |

Zone files are saved to `<output>/zones/`. Each file is stamped with the zone's `Last-Modified` time, and zones that have not changed since the last run are skipped.

###### Report Options
| Argument         | Description                     | Default |
|------------------|---------------------------------|---------|
| `-r`, `--report` | Download the zone stats report  |         |
| `-s`, `--scrub`  | Scrub username from the report  |         |
| `-f`, `--format` | Report output format (csv/json) | `csv`   |

The report is saved to `<output>/report.<format>`.

###### Zone Request Options
| Argument    | Description                                                                               |
|-------------|-------------------------------------------------------------------------------------------|
| `--request` | Request access to zones *(`all` for every requestable zone)*                              |
| `--reason`  | Reason for the zone request *(required with `--request`)*                                 |
| `--extend`  | Request an extension for approved zones *(`all` for every zone expiring within 120 days)* |
| `--cancel`  | Cancel pending zone requests                                                              |

Extensions and cancellations only go through when CZDS marks the request as extensible or cancellable *(a freshly submitted request cannot be cancelled until it is pending)*.

### Environment Variables
```bash
export CZDS_USER='your_username'
export CZDS_PASS='your_password'
```

### Python Module
```python
import asyncio
import os

from czds import CZDS


async def main():
	async with CZDS(os.environ['CZDS_USER'], os.environ['CZDS_PASS']) as client:
		# Download zone stats report
		await client.get_report('report.json', scrub=True, format='json')

		# Download zone files (returns the TLDs that failed)
		failed = await client.download_zones('zones', concurrency=3)

		# Request extensions for every zone expiring soon
		await client.extend_all()


asyncio.run(main())
```

## Respects & extras
While ICANN does have an official [czds-api-client-python](https://github.com/icann/czds-api-client-python) repository, I rewrote it from scratch to be more streamline & included a [POSIX version](./extras/czds) for portability. There is some [official documentation](https://raw.githubusercontent.com/icann/czds-api-client-java/master/docs/ICANN_CZDS_api.pdf) that was referenced in the creation of the POSIX version. Either way, big props to ICANN for allowing me to use the CZDS for research purposes!

___

###### Mirrors for this repository: [acid.vegas](https://git.acid.vegas/czds) • [SuperNETs](https://git.supernets.org/acidvegas/czds) • [GitHub](https://github.com/acidvegas/czds) • [GitLab](https://gitlab.com/acidvegas/czds) • [Codeberg](https://codeberg.org/acidvegas/czds)
---

###### Mirrors: [SuperNETs](https://git.supernets.org/acidvegas/) • [GitHub](https://github.com/acidvegas/) • [GitLab](https://gitlab.com/acidvegas/) • [Codeberg](https://codeberg.org/acidvegas/)
