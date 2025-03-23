#!/usr/bin/env python3
# ICANN API for the Centralized Zones Data Service - developed by acidvegas (https://git.acid.vegas/czds)
# czds/utils.py

import gzip
import logging
import os

try:
    import aiofiles
except ImportError:
    raise ImportError('missing aiofiles library (pip install aiofiles)')

try:
    from tqdm import tqdm
except ImportError:
    raise ImportError('missing tqdm library (pip install tqdm)')


async def gzip_decompress(filepath: str, cleanup: bool = True):
    '''
    Decompress a gzip file in place
    
    :param filepath: Path to the gzip file
    :param cleanup: Whether to remove the original gzip file after decompressions
    '''

    # Get the original size of the file
    original_size = os.path.getsize(filepath)

    logging.debug(f'Decompressing {filepath} ({humanize_bytes(original_size)})...')

    # Remove the .gz extension
    output_path = filepath[:-3]

    # Set the chunk size to 25MB
    chunk_size = 25 * 1024 * 1024

    # Create progress bar for decompression
    with tqdm(total=original_size, unit='B', unit_scale=True, desc=f'Decompressing {os.path.basename(filepath)}', leave=False) as pbar:
        # Decompress the file
        with gzip.open(filepath, 'rb') as gz:
            async with aiofiles.open(output_path, 'wb') as f_out:
                while True:
                    # Read the next chunk
                    chunk = gz.read(chunk_size)

                    # If the chunk is empty, break
                    if not chunk:
                        break

                    # Write the chunk to the output file
                    await f_out.write(chunk)

                    # Update the progress bar
                    pbar.update(len(chunk))

    # Get the decompressed size of the file
    decompressed_size = os.path.getsize(output_path)

    logging.debug(f'Decompressed {filepath} ({humanize_bytes(decompressed_size)})')

    # If the cleanup flag is set, remove the original gzip file
    if cleanup:
        os.remove(filepath)
        logging.debug(f'Removed original gzip file: {filepath}')


def humanize_bytes(bytes: int) -> str:
	'''
	Humanize a number of bytes

	:param bytes: The number of bytes to humanize
	'''

	# List of units
	units = ('B','KB','MB','GB','TB','PB','EB','ZB','YB')

	# Iterate over the units
	for unit in units:
		# If the bytes are less than 1024, return the bytes with the unit
		if bytes < 1024:
			return f'{bytes:.2f} {unit}' if unit != 'B' else f'{bytes} {unit}'

		# Divide the bytes by 1024
		bytes /= 1024

	return f'{bytes:.2f} {units[-1]}'