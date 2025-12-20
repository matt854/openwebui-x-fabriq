"""
Agentic Fabriq token cache utility.
Caches AF tokens with 1-hour expiration per user.
"""

import logging
import time
from typing import Optional, Dict
from threading import Lock

log = logging.getLogger(__name__)

# ===========================================
# Agentic Fabriq credentials - EDIT HERE
# ===========================================
AF_APP_ID = "org-f4c7eab7-4439-494a-8ddd-06abb3974541_openwebui-test"
AF_APP_SECRET = "kI6ZIJGK3zZmHvL5KCUxwgJGQnuYcVhq"
# ===========================================

async def exchange_okta_token_for_af_token(okta_access_token: str) -> Optional[str]:
    """
    Exchange an Okta access token for an Agentic Fabriq token.
    
    Args:
        okta_access_token: The Okta access token to exchange
        
    Returns:
        The AF token if successful, None otherwise
    """
    from af_sdk import exchange_okta_for_af_token
    
    return await exchange_okta_for_af_token(
        okta_access_token,
        AF_APP_ID,
        AF_APP_SECRET
    )

class AFTokenCache:
    """Simple in-memory cache for AF tokens with TTL."""
    
    def __init__(self):
        self._cache: Dict[str, tuple[str, float]] = {}  # user_id -> (token, expires_at)
        self._lock = Lock()
        self.TTL = 3600  # 1 hour in seconds
    
    def get(self, user_id: str) -> Optional[str]:
        """
        Get cached AF token for a user if it exists and is not expired.
        
        Args:
            user_id: The user ID
            
        Returns:
            str: The AF token if valid, None otherwise
        """
        with self._lock:
            if user_id in self._cache:
                token, expires_at = self._cache[user_id]
                
                # Check if token is still valid
                if time.time() < expires_at:
                    log.debug(f"AF token cache hit for user {user_id}")
                    return token
                else:
                    # Token expired, remove from cache
                    log.debug(f"AF token expired for user {user_id}, removing from cache")
                    del self._cache[user_id]
            
            log.debug(f"AF token cache miss for user {user_id}")
            return None
    
    def set(self, user_id: str, token: str) -> None:
        """
        Store an AF token for a user with 1-hour TTL.
        
        Args:
            user_id: The user ID
            token: The AF token to cache
        """
        with self._lock:
            expires_at = time.time() + self.TTL
            self._cache[user_id] = (token, expires_at)
            log.debug(f"AF token cached for user {user_id}, expires at {expires_at}")
    
    def invalidate(self, user_id: str) -> None:
        """
        Invalidate/remove the cached token for a user.
        
        Args:
            user_id: The user ID
        """
        with self._lock:
            if user_id in self._cache:
                del self._cache[user_id]
                log.debug(f"AF token invalidated for user {user_id}")
    
    def clear(self) -> None:
        """Clear all cached tokens."""
        with self._lock:
            self._cache.clear()
            log.debug("AF token cache cleared")
    
    def cleanup_expired(self) -> None:
        """Remove all expired tokens from cache."""
        with self._lock:
            current_time = time.time()
            expired_users = [
                user_id for user_id, (_, expires_at) in self._cache.items()
                if current_time >= expires_at
            ]
            
            for user_id in expired_users:
                del self._cache[user_id]
            
            if expired_users:
                log.debug(f"Cleaned up {len(expired_users)} expired AF tokens")


# Global cache instance
af_token_cache = AFTokenCache()


