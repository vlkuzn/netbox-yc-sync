import os
import argparse
from dotenv import load_dotenv
import structlog

from logging_config import setup_logging
from collectors.yandex_cloud import YandexCloudCollector
from collectors.netbox import NetBoxCollector
from sync.logic import compare_and_plan


def parse_args():
    parser = argparse.ArgumentParser(description="Sync Yandex Cloud VMs to NetBox.")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without applying changes.")
    return parser.parse_args()


def main():
    setup_logging()
    load_dotenv()
    args = parse_args()
    logger = structlog.get_logger()

    yc_token = os.getenv("YC_TOKEN")
    netbox_url = os.getenv("NETBOX_URL")
    netbox_token = os.getenv("NETBOX_TOKEN")
    netbox_site = os.getenv("NETBOX_SITE", "Yandex Cloud RU")

    if not all([yc_token, netbox_url, netbox_token, netbox_site]):
        logger.error("missing_env_vars")
        exit(1)

    yc = YandexCloudCollector(yc_token)
    nb = NetBoxCollector(netbox_url, netbox_token, netbox_site)

    # Ensure site exists
    site_id = nb.ensure_site()
    # Ensure cluster type exists
    cluster_type_id = nb.ensure_cluster_type()

    # Fetch all data from Yandex Cloud
    yc_data = yc.fetch_all_data()
    # Fetch all VMs from NetBox
    netbox_vms = nb.fetch_vms()

    # Create prefixes for all subnets
    for subnet in yc_data["subnets"]:
        if subnet["cidr"]:
            nb.ensure_prefix(subnet["cidr"], subnet["vpc_name"], site_id)

    # Create cluster groups for clouds and clusters for folders
    for cloud in yc_data["clouds"]:
        cluster_group_id = nb.ensure_cluster_group(cloud["name"])
        # Find folders for this cloud
        cloud_folders = [f for f in yc_data["folders"] if f["cloud_id"] == cloud["id"]]
        for folder in cloud_folders:
            nb.ensure_cluster(folder["name"], cluster_group_id, site_id)

    actions = compare_and_plan(yc_data["vms"], netbox_vms)

    if args.dry_run:
        logger.info("dry_run_actions", actions=actions)
    else:
        for action in actions:
            if action["action"] == "create":
                vm = action["vm"]
                # Find folder and cloud info
                folder = next((f for f in yc_data["folders"] if f["id"] == vm["folder_id"]), None)
                if not folder:
                    logger.error("folder_not_found", vm=vm["name"], folder_id=vm["folder_id"])
                    continue

                # Get cluster ID (folder name is cluster name)
                cluster_id = nb.ensure_cluster(folder["name"],
                                             nb.ensure_cluster_group(folder["cloud_name"]),
                                             site_id)

                # Prepare VM data for NetBox
                disk_sizes_mb = [int(d["size"]) // (1024 * 1024) for d in vm["disks"]]
                if len(disk_sizes_mb) == 1:
                    disk_mb = disk_sizes_mb[0]
                else:
                    disk_mb = sum(disk_sizes_mb)
                vm_data = {
                    "name": vm["name"],
                    "status": "active" if vm["status"] == "RUNNING" else "offline",
                    "cluster": cluster_id,
                    "vcpus": int(vm["resources"].get("cores", 0)),
                    "memory": int(int(vm["resources"].get("memory", 0)) // (1024 * 1024)),
                    "disk": disk_mb,
                }
                netbox_vm = nb.create_vm(vm_data)

                # Create interfaces and IPs
                for idx, iface in enumerate(vm["network_interfaces"]):
                    iface_data = {
                        "virtual_machine": netbox_vm.id,
                        "name": f"eth{idx}",
                        "type": "virtual",  # Добавляем тип интерфейса
                    }
                    netbox_iface = nb.create_interface(iface_data)

                    # Primary IPv4
                    if iface.get("primary_v4_address"):
                        ip_data = {
                            "address": iface["primary_v4_address"],
                            "status": "active",
                            "interface": netbox_iface.id,
                            "virtual_machine": netbox_vm.id,
                            "is_primary": idx == 0,  # Первый интерфейс как primary
                            "description": f"Primary IP for {vm['name']}"
                        }
                        nb.create_ip(ip_data)

                    # One-to-one NAT IPv4 if exists
                    if iface.get("primary_v4_address_one_to_one_nat"):
                        ip_data = {
                            "address": iface["primary_v4_address_one_to_one_nat"],
                            "status": "active",
                            "interface": netbox_iface.id,
                            "virtual_machine": netbox_vm.id,
                            "is_primary": False,
                            "description": f"NAT IP for {vm['name']}"
                        }
                        nb.create_ip(ip_data)

                logger.info("created_netbox_vm", vm=vm["name"], cluster=folder["name"])


            elif action["action"] == "update":
                nb_vm = action["netbox_vm"]
                updates = action["updates"]
                nb.update_vm(nb_vm.id, updates)
                logger.info("updated_netbox_vm", vm=nb_vm.name, updates=updates)


if __name__ == "__main__":
    main()
