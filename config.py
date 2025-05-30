import os
import logging
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Application configuration."""
    
    # Yandex Cloud settings
    yc_token: str
    
    # NetBox settings
    netbox_url: str
    netbox_token: str
    netbox_site: str = "Yandex Cloud RU"
    
    # Application settings
    dry_run: bool = False
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls, dry_run: bool = False) -> 'Config':
        """Create configuration from environment variables."""
        yc_token = os.getenv("YC_TOKEN")
        netbox_url = os.getenv("NETBOX_URL")
        netbox_token = os.getenv("NETBOX_TOKEN")
        netbox_site = os.getenv("NETBOX_SITE", "Yandex Cloud RU")
        log_level = os.getenv("LOG_LEVEL", "INFO")
        
        missing_vars = []
        if not yc_token:
            missing_vars.append("YC_TOKEN")
        if not netbox_url:
            missing_vars.append("NETBOX_URL")
        if not netbox_token:
            missing_vars.append("NETBOX_TOKEN")
            
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
            
        return cls(
            yc_token=yc_token,
            netbox_url=netbox_url,
            netbox_token=netbox_token,
            netbox_site=netbox_site,
            dry_run=dry_run,
            log_level=log_level
        )
    
    def setup_logging(self) -> None:
        """Setup logging configuration."""
        numeric_level = getattr(logging, self.log_level.upper(), logging.INFO)
        logging.basicConfig(
            level=numeric_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        # Set specific log levels for external libraries
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)