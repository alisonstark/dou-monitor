"""Security utilities for DOU Monitor"""
from urllib.parse import urlparse
import ipaddress
import socket
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

# Networks blocked to prevent SSRF attacks
BLOCKED_NETWORKS = [
    ipaddress.ip_network('10.0.0.0/8'),      # Private
    ipaddress.ip_network('172.16.0.0/12'),   # Private
    ipaddress.ip_network('192.168.0.0/16'),  # Private
    ipaddress.ip_network('127.0.0.0/8'),     # Localhost
    ipaddress.ip_network('169.254.0.0/16'),  # AWS metadata
    ipaddress.ip_network('::1/128'),         # IPv6 localhost
    ipaddress.ip_network('fc00::/7'),        # IPv6 private
]

def is_safe_url(url: str, require_https: bool = True) -> Tuple[bool, str]:
    """
    Validate URL to prevent SSRF attacks.
    
    Args:
        url: URL to validate
        require_https: If True, only allow HTTPS URLs
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        parsed = urlparse(url)
        
        # Check scheme
        if require_https and parsed.scheme != 'https':
            return False, "Only HTTPS URLs are allowed"
        
        if parsed.scheme not in ('http', 'https'):
            return False, f"Invalid scheme: {parsed.scheme}"
        
        # Get hostname
        hostname = parsed.hostname
        if not hostname:
            return False, "Missing hostname"
        
        # Resolve hostname to IP
        try:
            ip_str = socket.gethostbyname(hostname)
            ip_obj = ipaddress.ip_address(ip_str)
        except (socket.gaierror, ValueError) as e:
            return False, f"Cannot resolve hostname: {e}"
        
        # Check if IP is in blocked networks
        for blocked_net in BLOCKED_NETWORKS:
            if ip_obj in blocked_net:
                return False, f"Private/internal IP blocked: {ip_str}"
        
        return True, "OK"
    
    except Exception as e:
        return False, f"Invalid URL: {e}"

def validate_filename(filename: str) -> Tuple[bool, str]:
    """
    Validate filename to prevent path traversal attacks.
    
    Args:
        filename: Filename to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # Check for path traversal attempts
    if '..' in filename:
        return False, "Path traversal detected: .."
    
    if filename.startswith('/') or filename.startswith('\\'):
        return False, "Absolute paths not allowed"
    
    # Check for null bytes
    if '\x00' in filename:
        return False, "Null byte detected"
    
    # Check for allowed characters (alphanumeric, dash, underscore, dot)
    import re
    if not re.match(r'^[\w\-. ()]+$', filename):
        return False, "Invalid characters in filename"
    
    return True, "OK"

def validate_email(email: str) -> Tuple[bool, str]:
    """
    Validate email address format.
    
    Args:
        email: Email address to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    import re
    
    # Basic email regex (RFC 5322 simplified)
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    if not re.match(email_regex, email):
        return False, "Invalid email format"
    
    # Additional checks
    if len(email) > 254:  # RFC 5321
        return False, "Email too long"
    
    local, domain = email.rsplit('@', 1)
    if len(local) > 64:  # RFC 5321
        return False, "Local part too long"
    
    return True, "OK"

def sanitize_days_parameter(days: int) -> Tuple[bool, str]:
    """
    Validate days parameter to prevent abuse.
    
    Args:
        days: Number of days to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not isinstance(days, int):
        return False, "Days must be an integer"
    
    if days < 1:
        return False, "Days must be at least 1"
    
    if days > 365:
        return False, "Days cannot exceed 365"
    
    return True, "OK"
