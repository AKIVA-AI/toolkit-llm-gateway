"""
Toolkit LLM Gateway - Security Module

Provides security features including:
- Input validation
- Rate limiting
- API key management
- Request sanitization
"""

import re
import hashlib
import secrets
import time
from typing import Dict, Optional, Any, List
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class RateLimitConfig:
    """Rate limit configuration"""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    requests_per_day: int = 10000
    burst_size: int = 10


@dataclass
class RateLimitState:
    """Rate limit state for a client"""
    minute_requests: List[float] = field(default_factory=list)
    hour_requests: List[float] = field(default_factory=list)
    day_requests: List[float] = field(default_factory=list)


class InputValidator:
    """Validates and sanitizes user input"""
    
    # Patterns for validation
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    API_KEY_PATTERN = re.compile(r'^[a-zA-Z0-9_-]{32,}$')
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(--)",
        r"(;.*--)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
    ]
    
    @classmethod
    def validate_email(cls, email: str) -> bool:
        """Validate email format"""
        if not email or len(email) > 255:
            return False
        return bool(cls.EMAIL_PATTERN.match(email))
    
    @classmethod
    def validate_api_key(cls, api_key: str) -> bool:
        """Validate API key format"""
        if not api_key:
            return False
        return bool(cls.API_KEY_PATTERN.match(api_key))
    
    @classmethod
    def validate_uuid(cls, uuid_str: str) -> bool:
        """Validate UUID format"""
        if not uuid_str:
            return False
        return bool(cls.UUID_PATTERN.match(uuid_str))
    
    @classmethod
    def sanitize_string(cls, value: str, max_length: int = 1000) -> str:
        """Sanitize string input"""
        if not isinstance(value, str):
            return ""
        
        # Truncate to max length
        value = value[:max_length]
        
        # Remove null bytes
        value = value.replace('\x00', '')
        
        # Strip whitespace
        value = value.strip()
        
        return value
    
    @classmethod
    def check_sql_injection(cls, value: str) -> bool:
        """Check for SQL injection patterns"""
        if not isinstance(value, str):
            return False
        
        value_upper = value.upper()
        for pattern in cls.SQL_INJECTION_PATTERNS:
            if re.search(pattern, value_upper, re.IGNORECASE):
                return True
        
        return False
    
    @classmethod
    def validate_model_name(cls, model: str) -> bool:
        """Validate model name"""
        if not model or len(model) > 100:
            return False
        
        # Allow alphanumeric, hyphens, underscores, dots, slashes
        pattern = re.compile(r'^[a-zA-Z0-9._/-]+$')
        return bool(pattern.match(model))
    
    @classmethod
    def validate_numeric_range(cls, value: float, min_val: float = 0, max_val: float = float('inf')) -> bool:
        """Validate numeric value is in range"""
        try:
            return min_val <= float(value) <= max_val
        except (ValueError, TypeError):
            return False


class RateLimiter:
    """Rate limiter with sliding window"""
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter"""
        self.config = config or RateLimitConfig()
        self.clients: Dict[str, RateLimitState] = defaultdict(RateLimitState)
    
    def check_rate_limit(self, client_id: str) -> Dict[str, Any]:
        """
        Check if client is within rate limits
        
        Returns:
            Dict with 'allowed' (bool) and 'retry_after' (int seconds)
        """
        now = time.time()
        state = self.clients[client_id]
        
        # Clean old requests
        self._clean_old_requests(state, now)
        
        # Check limits
        if len(state.minute_requests) >= self.config.requests_per_minute:
            retry_after = int(60 - (now - state.minute_requests[0]))
            return {"allowed": False, "retry_after": retry_after, "reason": "minute_limit"}
        
        if len(state.hour_requests) >= self.config.requests_per_hour:
            retry_after = int(3600 - (now - state.hour_requests[0]))
            return {"allowed": False, "retry_after": retry_after, "reason": "hour_limit"}
        
        if len(state.day_requests) >= self.config.requests_per_day:
            retry_after = int(86400 - (now - state.day_requests[0]))
            return {"allowed": False, "retry_after": retry_after, "reason": "day_limit"}
        
        # Record request
        state.minute_requests.append(now)
        state.hour_requests.append(now)
        state.day_requests.append(now)
        
        return {"allowed": True, "retry_after": 0}
    
    def _clean_old_requests(self, state: RateLimitState, now: float):
        """Remove requests outside the time windows"""
        # Keep only last minute
        state.minute_requests = [t for t in state.minute_requests if now - t < 60]
        
        # Keep only last hour
        state.hour_requests = [t for t in state.hour_requests if now - t < 3600]
        
        # Keep only last day
        state.day_requests = [t for t in state.day_requests if now - t < 86400]


class APIKeyManager:
    """Manages API key generation and validation"""
    
    @staticmethod
    def generate_api_key(prefix: str = "ak") -> str:
        """Generate a secure API key"""
        random_part = secrets.token_urlsafe(32)
        return f"{prefix}_{random_part}"
    
    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for storage"""
        return hashlib.sha256(api_key.encode()).hexdigest()
    
    @staticmethod
    def verify_api_key(api_key: str, key_hash: str) -> bool:
        """Verify API key against hash"""
        return APIKeyManager.hash_api_key(api_key) == key_hash


