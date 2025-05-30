import argparse
import logging
from dotenv import load_dotenv

from config import Config
from clients.yandex_cloud_client import YandexCloudClient
from clients.netbox_client import NetBoxClient
from sync.synchronizer import compare_and_plan
from sync.flexible_synchronizer import compare_and_plan_flexible


def parse_args():
    parser = argparse.ArgumentParser(description="Sync Yandex Cloud VMs to NetBox.")
    parser.add_argument("--dry-run", action="store_true", help="Show actions without applying changes.")
    parser.add_argument("--log-level", choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], 
                       default='INFO', help="Set logging level")
    parser.add_argument("--ignore-clusters", action="store_true", 
                       help="Match VMs by name only, ignoring cluster assignments")
    return parser.parse_args()


def main():
    """Main application entry point."""
    load_dotenv()
    args = parse_args()
    
    try:
        config = Config.from_env(dry_run=args.dry_run)
        config.log_level = args.log_level
        config.ignore_clusters = args.ignore_clusters
        config.setup_logging()
        
        logger = logging.getLogger(__name__)
        logger.info(f"Starting NetBox-YC sync (dry_run={config.dry_run})")
        
        # Initialize clients
        yc_client = YandexCloudClient(config.yc_token)
        nb_client = NetBoxClient(
            config.netbox_url, 
            config.netbox_token, 
            config.netbox_site, 
            dry_run=config.dry_run
        )
        
        # Perform synchronization
        sync_result = perform_sync(yc_client, nb_client, logger, config.dry_run, 
                                 getattr(config, 'ignore_clusters', False))
        
        if sync_result:
            logger.info("Synchronization completed successfully")
        else:
            logger.error("Synchronization failed")
            exit(1)
            
    except ValueError as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Configuration error: {e}")
        exit(1)
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error: {e}")
        exit(1)


def perform_sync(yc_client: YandexCloudClient, nb_client: NetBoxClient, 
                logger: logging.Logger, dry_run: bool, ignore_clusters: bool = False) -> bool:
    """Perform the actual synchronization process."""
    try:
        # Ensure site exists
        site_id = nb_client.ensure_site()

        # Fetch all data from Yandex Cloud
        logger.info("Fetching data from Yandex Cloud...")
        yc_data = yc_client.fetch_all_data()
        
        # Fetch all VMs from NetBox
        logger.info("Fetching VMs from NetBox...")
        netbox_vms = nb_client.fetch_vms()

        # Create infrastructure components
        logger.info("Ensuring NetBox infrastructure...")
        _ensure_infrastructure(yc_data, nb_client, site_id)

        # Fix any IP issues before synchronization
        logger.info("Checking and fixing IP address issues...")
        duplicate_fixed = nb_client.fix_duplicate_ips(dry_run)
        if duplicate_fixed > 0:
            logger.info(f"Fixed {duplicate_fixed} duplicate IP addresses")

        # Plan synchronization actions
        logger.info("Planning synchronization actions...")
        if ignore_clusters:
            logger.info("Using flexible matching (ignoring cluster assignments)")
            actions = compare_and_plan_flexible(yc_data["vms"], netbox_vms, ignore_clusters=True)
        else:
            actions = compare_and_plan(yc_data["vms"], netbox_vms)

        if dry_run:
            _log_dry_run_actions(actions, logger)
        else:
            _execute_actions(actions, yc_data, nb_client, logger)
            
            # After synchronization, assign missing primary IPs
            logger.info("Assigning missing primary IP addresses...")
            primary_fixed = nb_client.assign_missing_primary_ips(yc_data, dry_run=False)
            if primary_fixed > 0:
                logger.info(f"Assigned primary IPs to {primary_fixed} VMs")
            
        return True
        
    except Exception as e:
        logger.error(f"Synchronization failed: {e}")
        return False


def _ensure_infrastructure(yc_data: dict, nb_client: NetBoxClient, site_id: int):
    """Ensure all necessary infrastructure exists in NetBox."""
    # Create prefixes for all subnets
    for subnet in yc_data["subnets"]:
        if subnet["cidr"]:
            nb_client.ensure_prefix(subnet["cidr"], subnet["vpc_name"], site_id)

    # Create cluster groups for clouds and clusters for folders
    for cloud in yc_data["clouds"]:
        cluster_group_id = nb_client.ensure_cluster_group(cloud["name"])
        # Find folders for this cloud
        cloud_folders = [f for f in yc_data["folders"] if f["cloud_id"] == cloud["id"]]
        for folder in cloud_folders:
            nb_client.ensure_cluster(folder["name"], cluster_group_id, site_id)


def _log_dry_run_actions(actions: list, logger: logging.Logger):
    """Log all actions that would be performed in dry-run mode."""
    create_actions = [a for a in actions if a["action"] == "create"]
    update_actions = [a for a in actions if a["action"] == "update"]
    exact_updates = [a for a in update_actions if a.get("match_type") == "exact"]
    name_only_updates = [a for a in update_actions if a.get("match_type") == "name_only"]
    
    logger.info(f"[DRY-RUN] SYNCHRONIZATION SUMMARY:")
    logger.info(f"  Total actions: {len(actions)}")
    logger.info(f"  - Create new VMs: {len(create_actions)}")
    logger.info(f"  - Update VMs (exact match): {len(exact_updates)}")
    logger.info(f"  - Update VMs (name-only match): {len(name_only_updates)}")
    
    if create_actions:
        logger.info(f"\n[DRY-RUN] WOULD CREATE {len(create_actions)} VMs:")
        for i, action in enumerate(create_actions[:10], 1):  # Show first 10
            vm = action["vm"]
            logger.info(f"  {i:2d}. {vm['name']} → {vm['folder_name']}/{vm['cloud_name']}")
        if len(create_actions) > 10:
            logger.info(f"  ... and {len(create_actions) - 10} more VMs")
    
    if exact_updates:
        logger.info(f"\n[DRY-RUN] WOULD UPDATE {len(exact_updates)} VMs (EXACT MATCH):")
        for i, action in enumerate(exact_updates[:5], 1):  # Show first 5
            nb_vm = action["netbox_vm"]
            updates = action["updates"]
            logger.info(f"  {i}. {nb_vm.name} → {list(updates.keys())}")
    
    if name_only_updates:
        logger.info(f"\n[DRY-RUN] WOULD UPDATE {len(name_only_updates)} VMs (NAME-ONLY MATCH):")
        logger.info(f"  ⚠️  These VMs have matching names but different cluster assignments!")
        for i, action in enumerate(name_only_updates[:5], 1):  # Show first 5
            nb_vm = action["netbox_vm"]
            updates = action["updates"]
            logger.info(f"  {i}. {nb_vm.name} → {list(updates.keys())}")
        if len(name_only_updates) > 0:
            logger.info(f"  💡 Consider reviewing cluster assignments in NetBox")


def _execute_actions(actions: list, yc_data: dict, nb_client: NetBoxClient, 
                    logger: logging.Logger):
    """Execute synchronization actions."""
    created_count = 0
    updated_count = 0
    failed_count = 0
    
    for action in actions:
        try:
            if action["action"] == "create":
                success = _create_vm(action, yc_data, nb_client, logger)
                if success:
                    created_count += 1
                else:
                    failed_count += 1
                    
            elif action["action"] == "update":
                success = _update_vm(action, nb_client, logger)
                if success:
                    updated_count += 1
                else:
                    failed_count += 1
                    
        except Exception as e:
            logger.error(f"Failed to execute action {action['action']}: {e}")
            failed_count += 1
    
    logger.info(f"Sync completed: {created_count} created, {updated_count} updated, {failed_count} failed")


def _create_vm(action: dict, yc_data: dict, nb_client: NetBoxClient, 
              logger: logging.Logger) -> bool:
    """Create a new VM in NetBox with all associated resources."""
    vm = action["vm"]
    
    # Find folder and cloud info
    folder = next((f for f in yc_data["folders"] if f["id"] == vm["folder_id"]), None)
    if not folder:
        logger.error(f"Folder not found for VM {vm['name']}, folder_id: {vm['folder_id']}")
        return False

    try:
        # Get cluster ID (folder name is cluster name)
        site_id = nb_client.ensure_site()
        cluster_id = nb_client.ensure_cluster(
            folder["name"],
            nb_client.ensure_cluster_group(folder["cloud_name"]),
            site_id
        )

        # Prepare VM data for NetBox
        disk_sizes_mb = [int(d["size"]) // (1024 * 1024) for d in vm["disks"]]
        disk_mb = sum(disk_sizes_mb)
        vm_data = {
            "name": vm["name"],
            "status": "active" if vm["status"] == "RUNNING" else "offline",
            "cluster": cluster_id,
            "vcpus": int(vm["resources"].get("cores", 0)),
            "memory": int(int(vm["resources"].get("memory", 0)) // (1024 * 1024)),
            "disk": disk_mb,
        }
        netbox_vm = nb_client.create_vm(vm_data)
        if not netbox_vm:
            return False

        # Create virtual disks
        for disk in vm["disks"]:
            disk_data = {
                "virtual_machine": netbox_vm.id,
                "name": disk["name"],
                "size": int(disk["size"]) // (1024 * 1024),  # Convert to MB
                "description": f"Disk type: {disk['type']}"
            }
            nb_client.create_disk(disk_data)

        # Create interfaces and IPs
        for idx, iface in enumerate(vm["network_interfaces"]):
            iface_data = {
                "virtual_machine": netbox_vm.id,
                "name": f"eth{idx}",
                "type": "virtual",
            }
            netbox_iface = nb_client.create_interface(iface_data)
            if not netbox_iface:
                continue

            # Primary IPv4
            if iface.get("primary_v4_address"):
                ip_data = {
                    "address": iface["primary_v4_address"],
                    "status": "active",
                    "interface": netbox_iface.id,
                    "virtual_machine": netbox_vm.id,
                    "is_primary": idx == 0,  # First interface as primary
                    "description": f"Primary IP for {vm['name']}"
                }
                nb_client.create_ip(ip_data, yc_data["subnets"])

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
                nb_client.create_ip(ip_data, yc_data["subnets"])

        logger.info(f"Created NetBox VM: {vm['name']} in cluster: {folder['name']}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create VM {vm['name']}: {e}")
        return False


def _update_vm(action: dict, nb_client: NetBoxClient, logger: logging.Logger) -> bool:
    """Update an existing VM in NetBox."""
    try:
        nb_vm = action["netbox_vm"]
        updates = action["updates"]
        result = nb_client.update_vm(nb_vm.id, updates)
        if result:
            logger.info(f"Updated NetBox VM: {nb_vm.name} with: {updates}")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to update VM: {e}")
        return False


if __name__ == "__main__":
    main()
