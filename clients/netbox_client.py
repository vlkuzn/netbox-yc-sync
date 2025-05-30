import logging
import pynetbox
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class NetBoxClient:
    """NetBox API client with dry-run support for VM, disk, interface, and IP management."""

    def __init__(self, url: str, token: str, site_name: str, dry_run: bool = False):
        self.url = url.rstrip("/")
        self.token = token
        self.site_name = site_name
        self.dry_run = dry_run
        self.nb = pynetbox.api(self.url, token=self.token)

    def ensure_site(self) -> int:
        """Ensure site exists and return its ID."""
        site = self.nb.dcim.sites.get(name=self.site_name)
        if not site:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would create site: {self.site_name}")
                return 1  # Return dummy ID for dry-run
            else:
                site = self.nb.dcim.sites.create({
                    "name": self.site_name,
                    "status": "active"
                })
                logger.info(f"Created site: {self.site_name}")
        return site.id

    def ensure_cluster_group(self, name: str) -> int:
        """Ensure cluster group exists and return its ID."""
        group = self.nb.virtualization.cluster_groups.get(name=name)
        if not group:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would create cluster group: {name}")
                return 1  # Return dummy ID for dry-run
            else:
                group = self.nb.virtualization.cluster_groups.create({
                    "name": name,
                    "slug": name.lower().replace(" ", "-")
                })
                logger.info(f"Created cluster group: {name}")
        return group.id

    def ensure_cluster_type(self, name: str = "Yandex Cloud") -> int:
        """Ensure cluster type exists and return its ID."""
        cluster_type = self.nb.virtualization.cluster_types.get(name=name)
        if not cluster_type:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would create cluster type: {name}")
                return 1  # Return dummy ID for dry-run
            else:
                cluster_type = self.nb.virtualization.cluster_types.create({
                    "name": name,
                    "slug": name.lower().replace(" ", "-")
                })
                logger.info(f"Created cluster type: {name}")
        return cluster_type.id

    def ensure_cluster(self, name: str, group_id: int, site_id: int) -> int:
        """Ensure cluster exists and return its ID."""
        cluster = self.nb.virtualization.clusters.get(name=name)
        if not cluster:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would create cluster: {name}")
                return 1  # Return dummy ID for dry-run
            else:
                cluster_type_id = self.ensure_cluster_type()
                cluster = self.nb.virtualization.clusters.create({
                    "name": name,
                    "slug": name.lower().replace(" ", "-"),
                    "group": group_id,
                    "site": site_id,
                    "type": cluster_type_id
                })
                logger.info(f"Created cluster: {name}")
        return cluster.id

    def ensure_prefix(self, prefix: str, vpc_name: str, site_id: int) -> int:
        """Ensure prefix exists and return its ID."""
        prefix_obj = self.nb.ipam.prefixes.get(prefix=prefix)
        if not prefix_obj:
            if self.dry_run:
                logger.info(f"[DRY-RUN] Would create prefix: {prefix} for VPC: {vpc_name}")
                return 1  # Return dummy ID for dry-run
            else:
                prefix_obj = self.nb.ipam.prefixes.create({
                    "prefix": prefix,
                    "site": site_id,
                    "description": f"VPC: {vpc_name}"
                })
                logger.info(f"Created prefix: {prefix} for VPC: {vpc_name}")
        return prefix_obj.id

    def fetch_vms(self) -> List[Dict[str, Any]]:
        """Fetch all VMs from NetBox."""
        # Always fetch VMs even in dry-run mode for comparison
        return list(self.nb.virtualization.virtual_machines.all())

    def create_vm(self, vm_data: Dict[str, Any]) -> Any:
        """Create a new VM in NetBox."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would create VM: {vm_data.get('name')} in cluster {vm_data.get('cluster')}")
            # Return mock VM object for dry-run
            class MockVM:
                def __init__(self, data):
                    self.id = 999
                    self.name = data.get('name')
            return MockVM(vm_data)
        else:
            try:
                vm = self.nb.virtualization.virtual_machines.create(vm_data)
                logger.info(f"Created VM: {vm.name} in cluster {vm_data['cluster']}")
                return vm
            except Exception as e:
                logger.error(f"Failed to create VM {vm_data.get('name')}: {str(e)}")
                raise

    def create_disk(self, disk_data: Dict[str, Any]) -> Any:
        """Create a new virtual disk in NetBox."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would create disk: {disk_data.get('name')} for VM {disk_data.get('virtual_machine')}")
            # Return mock disk object for dry-run
            class MockDisk:
                def __init__(self, data):
                    self.id = 999
                    self.name = data.get('name')
            return MockDisk(disk_data)
        else:
            try:
                # Check if virtual_disks endpoint exists (NetBox 3.4+)
                if hasattr(self.nb.virtualization, 'virtual_disks'):
                    disk = self.nb.virtualization.virtual_disks.create(disk_data)
                    logger.info(f"Created disk: {disk.name} for VM {disk_data['virtual_machine']}")
                    return disk
                else:
                    logger.warning(f"Virtual disks not supported in this NetBox version, skipping disk creation for VM {disk_data.get('virtual_machine')}")
                    return None
            except Exception as e:
                logger.error(f"Failed to create disk {disk_data.get('name')}: {str(e)}")
                # Don't raise, just log and continue
                return None

    def create_interface(self, iface_data: Dict[str, Any]) -> Any:
        """Create a new interface in NetBox."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would create interface: {iface_data.get('name')} for VM {iface_data.get('virtual_machine')}")
            # Return mock interface object for dry-run
            class MockInterface:
                def __init__(self, data):
                    self.id = 999
                    self.name = data.get('name')
            return MockInterface(iface_data)
        else:
            try:
                interface = self.nb.virtualization.interfaces.create(iface_data)
                logger.info(f"Created interface: {interface.name} for VM {iface_data['virtual_machine']}")
                return interface
            except Exception as e:
                logger.error(f"Failed to create interface {iface_data.get('name')}: {str(e)}")
                raise

    def find_subnet_cidr(self, ip_address: str, subnets: List[Dict[str, Any]]) -> Optional[str]:
        """Find the CIDR of the subnet that contains the given IP address."""
        import ipaddress

        try:
            ip = ipaddress.ip_address(ip_address)
            for subnet in subnets:
                if subnet.get('cidr'):
                    try:
                        network = ipaddress.ip_network(subnet['cidr'])
                        if ip in network:
                            return subnet['cidr']
                    except ValueError:
                        continue
        except ValueError:
            pass

        # Fallback to /32 if no matching subnet found
        return f"{ip_address}/32"

    def create_ip(self, ip_data: Dict[str, Any], subnets: Optional[List[Dict[str, Any]]] = None) -> Any:
        """Create a new IP address in NetBox with proper CIDR from subnet data."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would create IP: {ip_data.get('address')} for interface {ip_data.get('interface')}")
            # Return mock IP object for dry-run
            class MockIP:
                def __init__(self, data):
                    self.id = 999
                    self.address = data.get('address')
            return MockIP(ip_data)
        else:
            try:
                original_address = ip_data["address"]
                address = original_address

                # If subnets data is provided, find the correct CIDR
                if subnets and "/" not in address:
                    cidr = self.find_subnet_cidr(address, subnets)
                    if cidr and cidr != f"{address}/32":
                        cidr_parts = cidr.split('/')
                        if len(cidr_parts) == 2:
                            address = f"{address}/{cidr_parts[1]}"
                        else:
                            address = f"{address}/32"
                    else:
                        address = f"{address}/32"
                elif "/" not in address:
                    address = f"{address}/32"

                # Check for existing IP with exact address match
                existing_ip = self.nb.ipam.ip_addresses.get(address=address)
                if existing_ip:
                    return self._handle_existing_ip(existing_ip, ip_data, address)

                # Check for existing IP with different CIDR but same host
                host_ip = original_address.split('/')[0]
                all_ips_for_host = list(self.nb.ipam.ip_addresses.filter(q=host_ip))

                for existing_ip in all_ips_for_host:
                    existing_host = str(existing_ip.address).split('/')[0]
                    if existing_host == host_ip:
                        logger.warning(f"IP {host_ip} exists with different CIDR: {existing_ip.address}, expected: {address}")
                        return self._handle_existing_ip(existing_ip, ip_data, str(existing_ip.address))

                # Create new IP with proper assignment to interface
                ip_create_data = {
                    "address": address,
                    "status": ip_data.get("status", "active"),
                    "assigned_object_type": "virtualization.vminterface",
                    "assigned_object_id": ip_data["interface"],
                    "description": ip_data.get("description", "")
                }

                ip = self.nb.ipam.ip_addresses.create(ip_create_data)

                # If this is primary IP, set it on the VM
                if ip_data.get("is_primary") and ip_data.get("virtual_machine"):
                    self._set_primary_ip(ip, ip_data["virtual_machine"])

                logger.info(f"Created IP: {ip.address} for interface {ip_data['interface']}")
                return ip
            except Exception as e:
                logger.error(f"Failed to create IP {ip_data['address']}: {str(e)}")
                # Don't raise for IP creation failures to avoid stopping sync
                return None

    def _handle_existing_ip(self, existing_ip: Any, ip_data: Dict[str, Any], address: str) -> Any:
        """Handle existing IP address assignment and primary IP logic."""
        try:
            current_interface_id = getattr(existing_ip, 'assigned_object_id', None)
            target_interface_id = ip_data["interface"]

            # If IP is already assigned to the correct interface, just handle primary IP
            if current_interface_id == target_interface_id:
                logger.info(f"IP {address} already correctly assigned to interface {target_interface_id}")
                if ip_data.get("is_primary") and ip_data.get("virtual_machine"):
                    self._set_primary_ip(existing_ip, ip_data["virtual_machine"])
                return existing_ip

            # Check if this IP is a primary IP for another VM
            is_primary_elsewhere = self._is_primary_ip_elsewhere(existing_ip, ip_data.get("virtual_machine"))

            if is_primary_elsewhere:
                logger.warning(f"IP {address} is primary IP for another VM, skipping reassignment")
                return existing_ip

            # Try to reassign the IP
            if not self.dry_run:
                logger.info(f"Updating IP assignment for {address} from interface {current_interface_id} to {target_interface_id}")
                existing_ip.assigned_object_type = "virtualization.vminterface"
                existing_ip.assigned_object_id = target_interface_id
                existing_ip.save()

                # Set as primary IP if needed
                if ip_data.get("is_primary") and ip_data.get("virtual_machine"):
                    self._set_primary_ip(existing_ip, ip_data["virtual_machine"])

                logger.info(f"Successfully updated IP assignment for {address}")
            else:
                logger.info(f"[DRY-RUN] Would update IP assignment for {address} from interface {current_interface_id} to {target_interface_id}")

            return existing_ip

        except Exception as e:
            logger.error(f"Failed to handle existing IP {address}: {str(e)}")
            return existing_ip

    def _is_primary_ip_elsewhere(self, ip: Any, current_vm_id: int) -> bool:
        """Check if IP is set as primary for a different VM."""
        try:
            # Get all VMs where this IP might be primary
            vms_with_primary = list(self.nb.virtualization.virtual_machines.filter(primary_ip4_id=ip.id))

            for vm in vms_with_primary:
                if vm.id != current_vm_id:
                    logger.debug(f"IP {ip.address} is primary for VM {vm.name} (ID: {vm.id})")
                    return True
            return False
        except Exception:
            return False

    def _set_primary_ip(self, ip: Any, vm_id: int) -> None:
        """Safely set IP as primary for VM."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would set IP {ip.address} as primary for VM ID {vm_id}")
            return

        try:
            vm = self.nb.virtualization.virtual_machines.get(id=vm_id)
            if vm:
                # Check if VM already has this IP as primary
                current_primary_id = getattr(vm.primary_ip4, 'id', None) if vm.primary_ip4 else None
                if current_primary_id == ip.id:
                    logger.debug(f"IP {ip.address} is already primary for VM {vm.name}")
                    return

                vm.primary_ip4 = ip.id
                vm.save()
                logger.info(f"Set IP {ip.address} as primary for VM {vm.name}")
        except Exception as e:
            logger.error(f"Failed to set primary IP {ip.address} for VM {vm_id}: {str(e)}")

    def fix_duplicate_ips(self, dry_run=True) -> int:
        """Find and fix duplicate IP addresses."""
        logger.info("Checking for duplicate IP addresses...")

        # Get all IPs and group by host
        all_ips = list(self.nb.ipam.ip_addresses.all())
        ip_groups = {}

        for ip in all_ips:
            host = str(ip.address).split('/')[0]
            if host not in ip_groups:
                ip_groups[host] = []
            ip_groups[host].append(ip)

        # Find duplicates
        duplicates = []
        for host, ips in ip_groups.items():
            if len(ips) > 1:
                duplicates.append({
                    'host': host,
                    'ips': ips
                })

        if not duplicates:
            logger.info("No duplicate IPs found")
            return 0

        logger.info(f"Found {len(duplicates)} hosts with duplicate IPs")
        fixed_count = 0

        for dup in duplicates:
            host = dup['host']
            ips = dup['ips']

            # Sort by CIDR specificity and interface assignment
            def sort_key(ip):
                prefix_len = int(str(ip.address).split('/')[1])
                has_assignment = 1 if ip.assigned_object_id else 0
                return (prefix_len, has_assignment)

            ips_sorted = sorted(ips, key=sort_key, reverse=True)
            keep_ip = ips_sorted[0]
            remove_ips = ips_sorted[1:]

            logger.info(f"Host {host}: keeping {keep_ip.address}, removing {[str(ip.address) for ip in remove_ips]}")

            for ip_to_remove in remove_ips:
                if dry_run:
                    logger.info(f"[DRY-RUN] Would remove duplicate IP {ip_to_remove.address}")
                else:
                    try:
                        # Transfer any primary IP assignments
                        vms_using_as_primary = list(self.nb.virtualization.virtual_machines.filter(primary_ip4_id=ip_to_remove.id))
                        for vm in vms_using_as_primary:
                            vm.primary_ip4 = keep_ip.id
                            vm.save()
                            logger.info(f"Transferred primary IP assignment from {ip_to_remove.address} to {keep_ip.address} for VM {vm.name}")

                        # If the IP to remove has interface assignment, transfer it
                        if (ip_to_remove.assigned_object_type == 'virtualization.vminterface' and
                            ip_to_remove.assigned_object_id and
                            not keep_ip.assigned_object_id):
                            keep_ip.assigned_object_type = ip_to_remove.assigned_object_type
                            keep_ip.assigned_object_id = ip_to_remove.assigned_object_id
                            keep_ip.save()
                            logger.info(f"Transferred interface assignment from {ip_to_remove.address} to {keep_ip.address}")

                        # Delete duplicate
                        ip_to_remove.delete()
                        logger.info(f"Deleted duplicate IP: {ip_to_remove.address}")
                        fixed_count += 1

                    except Exception as e:
                        logger.error(f"Failed to remove duplicate IP {ip_to_remove.address}: {e}")

        return fixed_count

    def assign_missing_primary_ips(self, yc_data: Dict[str, Any] = None, dry_run=True) -> int:
        """Assign primary IPs to VMs that don't have them."""
        logger.info("Checking for VMs without primary IP...")

        all_vms = list(self.nb.virtualization.virtual_machines.all())
        vms_without_primary = [vm for vm in all_vms if not vm.primary_ip4]

        if not vms_without_primary:
            logger.info("All VMs have primary IPs")
            return 0

        logger.info(f"Found {len(vms_without_primary)} VMs without primary IP")
        fixed_count = 0

        for vm in vms_without_primary:
            # Get VM interfaces and their IPs
            interfaces = list(self.nb.virtualization.interfaces.filter(virtual_machine_id=vm.id))

            if not interfaces:
                logger.warning(f"VM {vm.name} has no interfaces")
                continue

            # Find any IP assigned to VM interfaces
            best_ip = None
            for iface in interfaces:
                iface_ips = list(self.nb.ipam.ip_addresses.filter(assigned_object_id=iface.id))
                if iface_ips:
                    best_ip = iface_ips[0]
                    break

            if best_ip:
                if dry_run:
                    logger.info(f"[DRY-RUN] Would set IP {best_ip.address} as primary for VM {vm.name}")
                else:
                    try:
                        vm.primary_ip4 = best_ip.id
                        vm.save()
                        logger.info(f"Set IP {best_ip.address} as primary for VM {vm.name}")
                        fixed_count += 1
                    except Exception as e:
                        logger.error(f"Failed to set primary IP for VM {vm.name}: {e}")
            else:
                logger.warning(f"No IP addresses found for VM {vm.name}")

        return fixed_count

    def update_vm(self, vm_id: int, updates: Dict[str, Any]) -> Any:
        """Update VM in NetBox."""
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would update VM {vm_id} with: {updates}")
            return None
        else:
            vm = self.nb.virtualization.virtual_machines.get(id=vm_id)
            if vm:
                vm.update(updates)
                logger.info(f"Updated VM {vm.name} with: {updates}")
            return vm
