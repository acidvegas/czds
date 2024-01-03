# ICANN CZDS

The [ICANN Centralized Zone Data Service](https://czds.icann.org) *(CZDS)* allows *approved* users to request and download DNS zone files in bulk, provided they represent a legitimate company or academic institution and their intended use is legal and ethical. Once ICANN approves the request, this tool streamlines the retrieval of extensive domain name system data, facilitating research and security analysis in the realm of internet infrastructure.

## Zone Information
Zone files are updated once every 24 hours, specifically from 00:00 UTC to 06:00 UTC. Access to these zones is granted in increments, and the total time for approval across all zones may extend to a month or longer. It is typical for more than 90% of requested zones to receive approval. Access to certain zone files may require additional application forms with the TLD organization. Please be aware that access to certain zones is time-bound, expiring at the beginning of the following year, or up to a decade after the initial approval has been confirmed.

At the time of writing this repository, the CZDS offers access to 1,150 zones in total.

1,079 have been approved, 55 are still pending *(after 3 months)*, 10 have been revoked because the TLDs are longer active, and 6 have been denied.

## Usage
### Authentication
Credentials may be provided interactively upon execution or via the `CZDS_USER` & `CZDS_PASS` environment variables:

```bash
export CZDS_USER='your_username'
export CZDS_PASS='your_password'
```

### Python version
```bash
python czds.py [--username <username> --password <password>] [--concurrency <int>]
```

### POSIX version
```bash
./czds
```

## Respects
While ICANN does have an official [czds-api-client-python](https://github.com/icann/czds-api-client-python) repository, I rewrote it from scratch to be more streamline & included a POSIX version for portability. Either way, big props to ICANN for allowing me to use the CZDS for research purposes!

___

###### Mirrors
[acid.vegas](https://git.acid.vegas/czds) • [GitHub](https://github.com/acidvegas/czds) • [GitLab](https://gitlab.com/acidvegas/czds) • [SuperNETs](https://git.supernets.org/acidvegas/czds)