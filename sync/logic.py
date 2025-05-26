import structlog
from typing import List, Dict, Any

logger = structlog.get_logger()

def compare_and_plan(yc_vms: List[Dict[str, Any]], netbox_vms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compare Yandex Cloud VMs with NetBox VMs and plan actions.
    Returns a list of actions to perform.
    """
    actions = []
    
    # Create lookup dictionaries for faster comparison
    yc_vm_map = {}
    for yc_vm in yc_vms:
        # Use folder_name as cluster name and cloud_name as cluster group
        key = (yc_vm["name"], yc_vm["folder_name"], yc_vm["cloud_name"])
        yc_vm_map[key] = yc_vm

    netbox_vm_map = {}
    for nb_vm in netbox_vms:
        # Get cluster and cluster group names from NetBox VM
        cluster = nb_vm.cluster
        if cluster:
            cluster_name = cluster.name
            cluster_group_name = cluster.group.name if cluster.group else None
            key = (nb_vm.name, cluster_name, cluster_group_name)
            netbox_vm_map[key] = nb_vm

    # Find VMs to create (in YC but not in NetBox)
    for key, yc_vm in yc_vm_map.items():
        if key not in netbox_vm_map:
            actions.append({
                "action": "create",
                "vm": yc_vm
            })

    # Find VMs to update (in both YC and NetBox)
    for key, yc_vm in yc_vm_map.items():
        if key in netbox_vm_map:
            nb_vm = netbox_vm_map[key]
            updates = {}

            # Check VM parameters
            if yc_vm["status"] == "RUNNING" and nb_vm.status.value != "active":
                updates["status"] = "active"
            elif yc_vm["status"] != "RUNNING" and nb_vm.status.value != "offline":
                updates["status"] = "offline"

            # Check vCPUs
            yc_vcpus = int(yc_vm["resources"].get("cores", 0))
            if yc_vcpus != nb_vm.vcpus:
                updates["vcpus"] = yc_vcpus

            # Check memory (convert to MB)
            yc_memory = int(int(yc_vm["resources"].get("memory", 0)) // (1024 * 1024))
            if yc_memory != nb_vm.memory:
                updates["memory"] = yc_memory

            # Check disk size (sum of all disks in MB)
            disk_sizes_mb = [int(d["size"]) // (1024 * 1024) for d in yc_vm["disks"]]
            yc_disk = sum(disk_sizes_mb)
            if yc_disk != nb_vm.disk:
                updates["disk"] = yc_disk

            if updates:
                actions.append({
                    "action": "update",
                    "netbox_vm": nb_vm,
                    "updates": updates
                })

    logger.info("planned_actions", count=len(actions))
    return actions