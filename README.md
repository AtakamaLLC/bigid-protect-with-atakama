# Protect with Atakama - BigID Marketplace App

Applies advanced multi-factor file-level encryption to protect files classified by BigID. Requires
an Atakama client installation to encrypt and decrypt files.

Data source types currently supported:
- SMB network shares

## Defined Routes
See `app.py` and `resources.py`:
- `/logs`: GET request. Returns the logs. 
- `/manifest`: GET request. Return the Manifest JSON.
- `/execute`: POST request. Given the required parameters, executes a command.

## Components
- `bigid_api.py`: Wrapper for BigID API, used to fetch Data Source and Data Catalog info
- `smb_api.py`: Wrapper for PySMB library, used to write metadata to SMB network shares

## Dependencies
- falcon: API routing
- requests: HTTP requests
- PySMB: SMB protocol client

## Usage
- `waitress-serve --port=54321 protect_with_atakama.app:app`
