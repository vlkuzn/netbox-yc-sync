#!/usr/bin/env python3
"""
Quick configuration and connectivity check for NetBox-YC sync.
Run this before using the main sync to verify everything is configured correctly.
"""

import os
import sys
import logging
from dotenv import load_dotenv

def check_environment():
    """Check if all required environment variables are set."""
    print("🔍 Checking environment variables...")
    
    required_vars = ["YC_TOKEN", "NETBOX_URL", "NETBOX_TOKEN"]
    optional_vars = ["NETBOX_SITE", "LOG_LEVEL"]
    
    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if not value:
            missing.append(var)
            print(f"  ❌ {var}: Missing")
        else:
            # Mask sensitive values
            if "TOKEN" in var:
                masked = value[:10] + "..." + value[-10:] if len(value) > 20 else "***"
                print(f"  ✅ {var}: {masked}")
            else:
                print(f"  ✅ {var}: {value}")
    
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚪ {var}: Not set (using default)")
    
    if missing:
        print(f"\n❌ Missing required variables: {', '.join(missing)}")
        return False
    
    print("✅ All required environment variables are set")
    return True

def test_yandex_cloud():
    """Test connection to Yandex Cloud API."""
    print("\n🔍 Testing Yandex Cloud connection...")
    
    try:
        from clients.yandex_cloud_client import YandexCloudClient
        
        yc_token = os.getenv("YC_TOKEN")
        client = YandexCloudClient(yc_token)
        
        # Try to fetch clouds
        clouds = client.fetch_clouds()
        print(f"  ✅ Connected successfully")
        print(f"  📊 Found {len(clouds)} cloud(s):")
        for cloud in clouds:
            print(f"    - {cloud['name']} ({cloud['id']})")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Connection failed: {str(e)}")
        return False

def test_netbox():
    """Test connection to NetBox API."""
    print("\n🔍 Testing NetBox connection...")
    
    try:
        from clients.netbox_client import NetBoxClient
        
        netbox_url = os.getenv("NETBOX_URL")
        netbox_token = os.getenv("NETBOX_TOKEN")
        netbox_site = os.getenv("NETBOX_SITE", "Yandex Cloud RU")
        
        client = NetBoxClient(netbox_url, netbox_token, netbox_site, dry_run=True)
        
        # Try to fetch VMs
        vms = client.fetch_vms()
        print(f"  ✅ Connected successfully")
        print(f"  📊 Found {len(vms)} VM(s) in NetBox")
        
        # Check for virtual disks support
        if hasattr(client.nb.virtualization, 'virtual_disks'):
            print(f"  ✅ Virtual disks supported (NetBox 3.4+)")
        else:
            print(f"  ⚠️  Virtual disks not supported (NetBox < 3.4)")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Connection failed: {str(e)}")
        return False

def check_matching():
    """Quick check of VM matching logic."""
    print("\n🔍 Testing VM matching logic...")
    
    try:
        from clients.yandex_cloud_client import YandexCloudClient
        from clients.netbox_client import NetBoxClient
        from sync.synchronizer import compare_and_plan
        
        yc_token = os.getenv("YC_TOKEN")
        netbox_url = os.getenv("NETBOX_URL")
        netbox_token = os.getenv("NETBOX_TOKEN")
        netbox_site = os.getenv("NETBOX_SITE", "Yandex Cloud RU")
        
        yc_client = YandexCloudClient(yc_token)
        nb_client = NetBoxClient(netbox_url, netbox_token, netbox_site, dry_run=True)
        
        # Fetch data
        print("  📥 Fetching Yandex Cloud data...")
        yc_data = yc_client.fetch_all_data()
        
        print("  📥 Fetching NetBox data...")
        netbox_vms = nb_client.fetch_vms()
        
        # Run comparison
        print("  🔄 Running comparison logic...")
        actions = compare_and_plan(yc_data["vms"], netbox_vms)
        
        create_count = len([a for a in actions if a["action"] == "create"])
        update_count = len([a for a in actions if a["action"] == "update"])
        
        print(f"  📊 Results:")
        print(f"    - Yandex Cloud VMs: {len(yc_data['vms'])}")
        print(f"    - NetBox VMs: {len(netbox_vms)}")
        print(f"    - Would create: {create_count}")
        print(f"    - Would update: {update_count}")
        
        if create_count == len(yc_data['vms']) and len(netbox_vms) > 0:
            print(f"  ⚠️  WARNING: All YC VMs would be created (possible matching issue)")
            print(f"  💡 Check cluster/group assignments in NetBox")
        elif create_count > len(yc_data['vms']) * 0.8:
            print(f"  ⚠️  WARNING: High creation ratio ({create_count}/{len(yc_data['vms'])})")
            print(f"  💡 Consider checking cluster/group names in NetBox")
        else:
            print(f"  ✅ Matching looks reasonable")
        
        return True
        
    except Exception as e:
        print(f"  ❌ Matching test failed: {str(e)}")
        return False

def main():
    """Main check function."""
    print("🚀 NetBox-YC Sync Quick Check")
    print("=" * 50)
    
    # Load environment
    load_dotenv()
    
    # Suppress info logs for cleaner output
    logging.getLogger().setLevel(logging.WARNING)
    
    all_good = True
    
    # Run checks
    all_good &= check_environment()
    all_good &= test_yandex_cloud()
    all_good &= test_netbox()
    all_good &= check_matching()
    
    print("\n" + "=" * 50)
    
    if all_good:
        print("✅ ALL CHECKS PASSED!")
        print("\n🚀 Ready to run:")
        print("  python main.py --dry-run  # Preview changes")
        print("  python main.py            # Apply changes")
    else:
        print("❌ SOME CHECKS FAILED!")
        print("\n🔧 Please fix the issues above before running sync")
    
    return all_good

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)