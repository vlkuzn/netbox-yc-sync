import os
import requests
import structlog
from typing import List, Dict, Any

logger = structlog.get_logger()

class YandexCloudCollector:
    """Collects VM, disk, network data from Yandex Cloud for all clouds/folders."""
    def __init__(self, token: str):
        self.token = token
        self.headers = {"Authorization": f"Bearer {self.token}"}

    def fetch_clouds(self) -> List[Dict[str, Any]]:
        url = "https://resource-manager.api.cloud.yandex.net/resource-manager/v1/clouds"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("clouds", [])

    def fetch_folders(self, cloud_id: str) -> List[Dict[str, Any]]:
        url = "https://resource-manager.api.cloud.yandex.net/resource-manager/v1/folders"
        params = {"cloudId": cloud_id}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json().get("folders", [])

    def fetch_vpcs(self, folder_id: str) -> List[Dict[str, Any]]:
        url = "https://vpc.api.cloud.yandex.net/vpc/v1/networks"
        params = {"folderId": folder_id}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json().get("networks", [])

    def fetch_subnets(self, folder_id: str) -> List[Dict[str, Any]]:
        """Fetch all subnets in a folder with pagination support."""
        url = "https://vpc.api.cloud.yandex.net/vpc/v1/subnets"
        params = {"folderId": folder_id}
        all_subnets = []
        
        while True:
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            subnets = data.get("subnets", [])
            all_subnets.extend(subnets)
            
            # Check if there are more pages
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                break
                
            params["pageToken"] = next_page_token
            
        return all_subnets

    def fetch_vms_in_folder(self, folder_id: str) -> List[Dict[str, Any]]:
        url = "https://compute.api.cloud.yandex.net/compute/v1/instances"
        params = {"folderId": folder_id}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json().get("instances", [])

    def fetch_disk(self, disk_id: str) -> Dict[str, Any]:
        url = f"https://compute.api.cloud.yandex.net/compute/v1/disks/{disk_id}"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()

    def fetch_all_data(self) -> Dict[str, Any]:
        """
        Fetches all data from Yandex Cloud including VMs, VPCs, and subnets.
        Returns a structured dictionary with all the data.
        """
        result = {
            "clouds": [],
            "folders": [],
            "vpcs": [],
            "subnets": [],
            "vms": []
        }

        clouds = self.fetch_clouds()
        for cloud in clouds:
            cloud_id = cloud["id"]
            cloud_name = cloud["name"]
            result["clouds"].append({
                "id": cloud_id,
                "name": cloud_name
            })

            folders = self.fetch_folders(cloud_id)
            for folder in folders:
                folder_id = folder["id"]
                folder_name = folder["name"]
                result["folders"].append({
                    "id": folder_id,
                    "name": folder_name,
                    "cloud_id": cloud_id,
                    "cloud_name": cloud_name
                })

                # Fetch VPCs and subnets
                vpcs = self.fetch_vpcs(folder_id)
                for vpc in vpcs:
                    vpc_id = vpc["id"]
                    vpc_name = vpc["name"]
                    result["vpcs"].append({
                        "id": vpc_id,
                        "name": vpc_name,
                        "folder_id": folder_id,
                        "folder_name": folder_name,
                        "cloud_id": cloud_id,
                        "cloud_name": cloud_name
                    })

                # Fetch all subnets in the folder
                subnets = self.fetch_subnets(folder_id)
                for subnet in subnets:
                    vpc_id = subnet["networkId"]
                    vpc_info = next((v for v in result["vpcs"] if v["id"] == vpc_id), None)
                    result["subnets"].append({
                        "id": subnet["id"],
                        "name": subnet["name"],
                        "cidr": subnet["v4CidrBlocks"][0] if subnet.get("v4CidrBlocks") else None,
                        "vpc_id": vpc_id,
                        "vpc_name": vpc_info["name"] if vpc_info else None,
                        "folder_id": folder_id,
                        "folder_name": folder_name,
                        "cloud_id": cloud_id,
                        "cloud_name": cloud_name,
                        "zone_id": subnet.get("zoneId"),
                        "description": subnet.get("description")
                    })

                # Fetch VMs
                folder_vms = self.fetch_vms_in_folder(folder_id)
                for vm in folder_vms:
                    # Fetch all disks (boot, secondary, local)
                    disk_ids = []
                    if "bootDisk" in vm and vm["bootDisk"].get("diskId"):
                        disk_ids.append(vm["bootDisk"]["diskId"])
                    for d in vm.get("secondaryDisks", []):
                        if d.get("diskId"): disk_ids.append(d["diskId"])
                    # Local disks (size only, no diskId)
                    local_disks = vm.get("localDisks", [])
                    disks = []
                    for disk_id in disk_ids:
                        disk = self.fetch_disk(disk_id)
                        disks.append({
                            "id": disk["id"],
                            "size": int(disk["size"]),
                            "name": disk.get("name", disk["id"]),
                            "type": "cloud"
                        })
                    for ld in local_disks:
                        disks.append({
                            "id": None,
                            "size": int(ld["size"]),
                            "name": ld.get("deviceName", "local"),
                            "type": "local"
                        })

                    # Find VPC and subnet for each network interface
                    network_interfaces = []
                    for idx, iface in enumerate(vm.get("networkInterfaces", [])):
                        vpc_id = iface.get("networkId")
                        subnet_id = iface.get("subnetId")
                        vpc_info = next((v for v in result["vpcs"] if v["id"] == vpc_id), None)
                        subnet_info = next((s for s in result["subnets"] if s["id"] == subnet_id), None)
                        
                        network_interfaces.append({
                            "index": idx,  # Using index instead of id
                            "vpc_id": vpc_id,
                            "vpc_name": vpc_info["name"] if vpc_info else None,
                            "subnet_id": subnet_id,
                            "subnet_name": subnet_info["name"] if subnet_info else None,
                            "primary_v4_address": iface.get("primaryV4Address", {}).get("address"),
                            "primary_v4_address_one_to_one_nat": iface.get("primaryV4Address", {}).get("oneToOneNat", {}).get("address")
                        })

                    # Normalize VM structure
                    result["vms"].append({
                        "id": vm["id"],
                        "name": vm["name"],
                        "status": vm["status"],
                        "folder_id": folder_id,
                        "folder_name": folder_name,
                        "cloud_id": cloud_id,
                        "cloud_name": cloud_name,
                        "resources": vm.get("resources", {}),
                        "disks": disks,
                        "network_interfaces": network_interfaces
                    })

        logger.info("fetched_all_yc_data", 
                   clouds_count=len(result["clouds"]),
                   folders_count=len(result["folders"]),
                   vpcs_count=len(result["vpcs"]),
                   subnets_count=len(result["subnets"]),
                   vms_count=len(result["vms"]))
        return result 