import pynetbox
import structlog
from typing import List, Dict, Any

logger = structlog.get_logger()

class NetBoxCollector:
    """Collects and manages VM, disk, interface, IP, and cluster group data in NetBox using pynetbox."""
    def __init__(self, url: str, token: str, site_name: str):
        self.url = url.rstrip("/")
        self.token = token
        self.site_name = site_name
        self.nb = pynetbox.api(self.url, token=self.token)

    def ensure_site(self) -> int:
        """Ensure site exists and return its ID."""
        site = self.nb.dcim.sites.get(name=self.site_name)
        if not site:
            site = self.nb.dcim.sites.create({
                "name": self.site_name,
                "status": "active"
            })
        return site.id

    def ensure_cluster_group(self, name: str) -> int:
        """Ensure cluster group exists and return its ID."""
        group = self.nb.virtualization.cluster_groups.get(name=name)
        if not group:
            group = self.nb.virtualization.cluster_groups.create({
                "name": name,
                "slug": name.lower().replace(" ", "-")
            })
        return group.id

    def ensure_cluster_type(self, name: str = "Yandex Cloud") -> int:
        """Ensure cluster type exists and return its ID."""
        cluster_type = self.nb.virtualization.cluster_types.get(name=name)
        if not cluster_type:
            cluster_type = self.nb.virtualization.cluster_types.create({
                "name": name,
                "slug": name.lower().replace(" ", "-")
            })
        return cluster_type.id

    def ensure_cluster(self, name: str, group_id: int, site_id: int) -> int:
        """Ensure cluster exists and return its ID."""
        cluster = self.nb.virtualization.clusters.get(name=name)
        if not cluster:
            cluster_type_id = self.ensure_cluster_type()
            cluster = self.nb.virtualization.clusters.create({
                "name": name,
                "slug": name.lower().replace(" ", "-"),
                "group": group_id,
                "site": site_id,
                "type": cluster_type_id
            })
        return cluster.id

    def ensure_prefix(self, prefix: str, vpc_name: str, site_id: int) -> int:
        """Ensure prefix exists and return its ID."""
        prefix_obj = self.nb.ipam.prefixes.get(prefix=prefix)
        if not prefix_obj:
            prefix_obj = self.nb.ipam.prefixes.create({
                "prefix": prefix,
                "site": site_id,
                "description": f"VPC: {vpc_name}"
            })
        return prefix_obj.id

    def fetch_vms(self) -> List[Dict[str, Any]]:
        """Fetch all VMs from NetBox."""
        return list(self.nb.virtualization.virtual_machines.all())

    def create_vm(self, vm_data: Dict[str, Any]) -> Any:
        """Create a new VM in NetBox."""
        try:
            vm = self.nb.virtualization.virtual_machines.create(vm_data)
            logger.info("created_vm",
                        name=vm.name,
                        cluster_id=vm_data["cluster"])
            return vm
        except Exception as e:
            logger.error("failed_to_create_vm",
                        name=vm_data.get("name"),
                        error=str(e))
            raise

    def create_disk(self, disk_data: dict) -> Any:
        return self.nb.extras.custom_fields.create(disk_data)  # Placeholder, adjust to your NetBox disk model

    def create_interface(self, iface_data: Dict[str, Any]) -> Any:
        """Create a new interface in NetBox."""
        try:
            interface = self.nb.virtualization.interfaces.create(iface_data)
            logger.info("created_interface",
                        name=interface.name,
                        vm_id=iface_data["virtual_machine"])
            return interface
        except Exception as e:
            logger.error("failed_to_create_interface",
                        name=iface_data.get("name"),
                        error=str(e))
            raise

    def create_ip(self, ip_data: Dict[str, Any]) -> Any:
        """Create a new IP address in NetBox and assign it to VM interface."""
        try:
            # Ensure IP address has CIDR notation
            address = ip_data["address"]
            if "/" not in address:
                address = f"{address}/32"

            # Create IP with proper assignment to interface
            ip_create_data = {
                "address": address,
                "status": ip_data.get("status", "active"),
                "assigned_object_type": "virtualization.vminterface",
                "assigned_object_id": ip_data["interface"],
                "description": ip_data.get("description", "")
            }

            # Add custom fields if needed
            if ip_data.get("is_primary"):
                ip_create_data["role"] = "anycast"  # or appropriate role

            ip = self.nb.ipam.ip_addresses.create(ip_create_data)

            # If this is primary IP, set it on the VM
            if ip_data.get("is_primary") and ip_data.get("virtual_machine"):
                vm = self.nb.virtualization.virtual_machines.get(id=ip_data["virtual_machine"])
                if vm:
                    vm.primary_ip4 = ip.id
                    vm.save()

            logger.info("created_ip_address",
                        address=ip.address,
                        interface_id=ip_data["interface"],
                        vm_id=ip_data.get("virtual_machine"),
                        is_primary=ip_data.get("is_primary", False))
            return ip
        except Exception as e:
            logger.error("failed_to_create_ip",
                        address=ip_data["address"],
                        error=str(e))
            raise

    def update_vm(self, vm_id: int, updates: Dict[str, Any]) -> Any:
        """Update VM in NetBox."""
        vm = self.nb.virtualization.virtual_machines.get(id=vm_id)
        if vm:
            vm.update(updates)
        return vm
