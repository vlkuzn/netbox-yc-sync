import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

def compare_and_plan(yc_vms: List[Dict[str, Any]], netbox_vms: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Compare Yandex Cloud VMs with NetBox VMs and plan actions.
    Uses full matching (name + cluster + group) with fallback to name-only matching.
    Returns a list of actions to perform.
    """
    actions = []
    
    # Create lookup dictionaries for faster comparison
    yc_vm_map = {}
    yc_vm_names = {}  # For name-only fallback matching
    
    for yc_vm in yc_vms:
        # Use folder_name as cluster name and cloud_name as cluster group
        full_key = (yc_vm["name"], yc_vm["folder_name"], yc_vm["cloud_name"])
        name_key = yc_vm["name"]
        yc_vm_map[full_key] = yc_vm
        yc_vm_names[name_key] = yc_vm

    netbox_vm_map = {}
    netbox_vm_names = {}  # For name-only fallback matching
    
    for nb_vm in netbox_vms:
        # Get cluster and cluster group names from NetBox VM
        cluster = getattr(nb_vm, 'cluster', None)
        vm_name = getattr(nb_vm, 'name', None)
        
        if vm_name:
            netbox_vm_names[vm_name] = nb_vm
            
            if cluster:
                cluster_name = getattr(cluster, 'name', None)
                cluster_group = getattr(cluster, 'group', None)
                cluster_group_name = getattr(cluster_group, 'name', None) if cluster_group else None
                
                if cluster_name:
                    full_key = (vm_name, cluster_name, cluster_group_name)
                    netbox_vm_map[full_key] = nb_vm

    # Track which VMs have been matched to avoid duplicates
    matched_yc_vms = set()
    matched_nb_vms = set()

    logger.info(f"Starting VM comparison: {len(yc_vms)} YC VMs vs {len(netbox_vms)} NetBox VMs")
    
    # First pass: exact matching (name + cluster + group)
    exact_matches = 0
    for full_key, yc_vm in yc_vm_map.items():
        if full_key in netbox_vm_map:
            nb_vm = netbox_vm_map[full_key]
            matched_yc_vms.add(yc_vm["name"])
            matched_nb_vms.add(getattr(nb_vm, 'name'))
            exact_matches += 1
            
            # Check for updates needed
            updates = _check_vm_updates(yc_vm, nb_vm)
            if updates:
                actions.append({
                    "action": "update",
                    "netbox_vm": nb_vm,
                    "updates": updates,
                    "match_type": "exact"
                })

    logger.info(f"Exact matches found: {exact_matches}")

    # Second pass: name-only matching for unmatched VMs
    name_matches = 0
    for name, yc_vm in yc_vm_names.items():
        if name not in matched_yc_vms and name in netbox_vm_names:
            nb_vm = netbox_vm_names[name]
            nb_vm_name = getattr(nb_vm, 'name')
            
            if nb_vm_name not in matched_nb_vms:
                matched_yc_vms.add(name)
                matched_nb_vms.add(nb_vm_name)
                name_matches += 1
                
                logger.warning(f"Name-only match: {name} (YC: {yc_vm['folder_name']}/{yc_vm['cloud_name']} vs NB: cluster mismatch)")
                
                # Check for updates needed
                updates = _check_vm_updates(yc_vm, nb_vm)
                if updates:
                    actions.append({
                        "action": "update",
                        "netbox_vm": nb_vm,
                        "updates": updates,
                        "match_type": "name_only"
                    })

    logger.info(f"Name-only matches found: {name_matches}")

    # Third pass: VMs to create (unmatched YC VMs)
    create_count = 0
    for yc_vm in yc_vms:
        if yc_vm["name"] not in matched_yc_vms:
            actions.append({
                "action": "create",
                "vm": yc_vm
            })
            create_count += 1

    logger.info(f"VMs to create: {create_count}")
    logger.info(f"Total planned actions: {len(actions)} (exact: {exact_matches}, name-only: {name_matches}, create: {create_count})")
    
    return actions


def _check_vm_updates(yc_vm: Dict[str, Any], nb_vm: Any) -> Dict[str, Any]:
    """Check what updates are needed for a VM."""
    updates = {}

    # Check VM parameters
    nb_status = getattr(getattr(nb_vm, 'status', None), 'value', None)
    if yc_vm["status"] == "RUNNING" and nb_status != "active":
        updates["status"] = "active"
    elif yc_vm["status"] != "RUNNING" and nb_status != "offline":
        updates["status"] = "offline"

    # Check vCPUs
    yc_vcpus = int(yc_vm["resources"].get("cores", 0))
    nb_vcpus = getattr(nb_vm, 'vcpus', 0)
    if yc_vcpus != nb_vcpus:
        updates["vcpus"] = yc_vcpus

    # Check memory (convert to MB)
    yc_memory = int(int(yc_vm["resources"].get("memory", 0)) // (1024 * 1024))
    nb_memory = getattr(nb_vm, 'memory', 0)
    if yc_memory != nb_memory:
        updates["memory"] = yc_memory

    # Check disk size (sum of all disks in MB)
    disk_sizes_mb = [int(d["size"]) // (1024 * 1024) for d in yc_vm["disks"]]
    yc_disk = sum(disk_sizes_mb)
    nb_disk = getattr(nb_vm, 'disk', 0)
    if yc_disk != nb_disk:
        updates["disk"] = yc_disk

    return updates