"""
Lirox v2.0 — Input Validation [FIX #5]

Validates all user input for safety and sanity.
Blocks XSS, SQL injection, path traversal, etc.
"""

import re
from typing import Tuple, Optional


class InputValidator:
    """Validates user input for safety."""
    
    MAX_QUERY_LENGTH = 10000
    
    BLOCKED_PATTERNS = [
        r"<script.*?>",      # XSS
        r"SELECT.*FROM",     # SQL injection
        r"exec\(",           # Code injection
        r"__import__",       # Python injection
        r"DROP\s+TABLE",     # SQL drop
        r"DELETE\s+FROM",    # SQL delete
    ]
    
    @staticmethod
    def validate_query(query: str) -> None:
        """
        Validate a search/research query.
        Raises: Exception if invalid
        """
        if not query or len(query) > InputValidator.MAX_QUERY_LENGTH:
            raise ValueError(f"Query must be 1-{InputValidator.MAX_QUERY_LENGTH} chars")
        
        query_lower = query.lower()
        for pattern in InputValidator.BLOCKED_PATTERNS:
            if re.search(pattern, query_lower, re.IGNORECASE):
                if "<script" in pattern:
                    raise ValueError("XSS pattern detected")
                if "SELECT" in pattern:
                    raise ValueError("SQL injection pattern detected")
                raise ValueError(f"Query contains blocked pattern: {pattern}")
    
    @staticmethod
    def validate_url(url: str) -> Tuple[bool, Optional[str]]:
        """Validate a URL."""
        url_pattern = r"^https?://[^\s/$.?#].[^\s]*$"
        if not re.match(url_pattern, url):
            return False, "Invalid URL format"
        
        blocked_hosts = ["localhost", "127.0.0.1", "192.168", "10.0"]
        for blocked in blocked_hosts:
            if blocked in url:
                return False, f"Access to {blocked} blocked for security"
        
        return True, None
    
    @staticmethod
    def validate_file_path(path: str) -> Tuple[bool, Optional[str]]:
        """Validate file path for safety."""
        if ".." in path:
            return False, "Path traversal (..) not allowed"
        if path.startswith("/"):
            return False, "Absolute paths not allowed"
        return True, None
