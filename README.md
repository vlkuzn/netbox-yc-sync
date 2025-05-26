# NetBox-Yandex Cloud Sync Utility

Synchronizes virtual machine data between Yandex Cloud and a corporate NetBox instance.

## Features
- Collects VM data from Yandex Cloud and NetBox
- Compares and syncs (creates missing VMs in NetBox)
- Dry-run mode for safe testing
- Structured logging (JSON/key-value)
- Containerized for production use

## Usage

### Environment Variables
Set these variables (e.g., in a `.env` file):

```
# Yandex Cloud
YC_TOKEN=your_yandex_cloud_token

# NetBox
NETBOX_URL=https://netbox.example.com
NETBOX_TOKEN=your_netbox_api_token
NETBOX_SITE=Yandex Cloud RU  # Name of the NetBox site to use (configurable)

# Yandex Cloud Organizations/Folders
YC_ORG_IDS=org1,org2  # Comma-separated list of Yandex Cloud organization IDs to sync
YC_FOLDER_IDS=folder1,folder2  # Comma-separated list of Yandex Cloud folder IDs to sync (optional, if not auto-discovering)
```

### Running Locally
```
pip install -r requirements.txt
python main.py --dry-run
```

### Running with Docker
```
docker build -t netbox-yc-sync .
docker run --env-file .env netbox-yc-sync --dry-run
```

## Project Structure
- `collectors/` — Data collectors for Yandex Cloud and NetBox
- `sync/` — Business logic for comparison and sync
- `main.py` — Entrypoint and CLI

---
For more details, see code comments and docstrings. 