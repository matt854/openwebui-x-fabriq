# Custom Changes to Open WebUI

This document details all custom modifications made to the Open WebUI codebase for Agentic Fabriq integration and Okta SSO configuration.

## Overview

The following changes implement:
1. **Okta SSO/OIDC Authentication** - Login with Okta credentials
2. **Agentic Fabriq Token Exchange** - Exchange Okta tokens for AF tokens
3. **Token Caching** - Cache AF tokens with 1-hour TTL
4. **Frontend UI** - Add AF authentication option in tool server configuration

---

## New Files Created

### 1. `backend/.oidc` - Okta SSO Configuration

```bash
# --- OIDC Core Settings ---

# Enable OAuth signup if you want users to be able to create accounts via Okta

ENABLE_OAUTH_SIGNUP="true"

# Your Okta application's Client ID
OAUTH_CLIENT_ID="0oaxgjd6smKViHWdb697"

# Your Okta application's Client Secret
OAUTH_CLIENT_SECRET="CxyWvTimEd9KG-WTHGy2GwzQgwfDI4a8M7qvO4IxZbBf727q0nS1HZglb6EHUxm-"

# Your Okta organization's OIDC discovery URL

# Format: https://<your-okta-domain>/.well-known/openid-configuration

# Or for a specific authorization server: https://<your-okta-domain>/oauth2/<auth-server-id>/.well-known/openid-configuration
OPENID_PROVIDER_URL="https://integrator-3617642.okta.com/oauth2/default/.well-known/openid-configuration"

# Name displayed on the login button (e.g., "Login with Okta")
OAUTH_PROVIDER_NAME="Okta"

OPENID_REDIRECT_URI="http://localhost:8080/oauth/oidc/login/callback"

# Scopes to request (default is usually sufficient)

# OAUTH_SCOPES="openid email profile groups" # Ensure 'groups' is included if not default

# --- OAuth Group Management (Optional) ---

# Set to "true" only if you configured the Groups Claim in Okta (Step 2)

# and want Open WebUI groups to be managed based on Okta groups upon login.

# This syncs existing groups. Users will be added/removed from Open WebUI groups

# to match their Okta group claims.

# ENABLE_OAUTH_GROUP_MANAGEMENT="true"

# Required only if ENABLE_OAUTH_GROUP_MANAGEMENT is true.

# The claim name in the ID token containing group information (must match Okta config)

# OAUTH_GROUP_CLAIM="groups"

# Optional: Enable Just-in-Time (JIT) creation of groups if they exist in Okta claims but not in Open WebUI.

# Requires ENABLE_OAUTH_GROUP_MANAGEMENT="true".

# If set to false (default), only existing groups will be synced.

# ENABLE_OAUTH_GROUP_CREATION="false"
```

### 2. `backend/open_webui/utils/af_token_cache.py` - Token Cache Utility

```python
"""
Agentic Fabriq token cache utility.
Caches AF tokens with 1-hour expiration per user.
"""

import logging
import time
from typing import Optional, Dict
from threading import Lock

log = logging.getLogger(__name__)

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
```

---

## Modified Files

### 1. `backend/dev.sh` - Load OAuth Environment Variables

**Changes:**
- Added proper bash error handling
- Load `.oidc` file to set OAuth environment variables
- Added `WEBUI_URL` export
- Better quote handling for PORT variable

```diff
+#!/usr/bin/env bash
+
+set -euo pipefail
+
+SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
+
+# Load env files so local OAuth config propagates into the dev server env
+set -a
+for env_file in "$SCRIPT_DIR/.oidc"; do
+    if [ -f "$env_file" ]; then
+        # shellcheck disable=SC1091
+        source "$env_file"
+    fi
+done
+set +a
+
 export CORS_ALLOW_ORIGIN="http://localhost:5173;http://localhost:8080"
+export WEBUI_URL="http://localhost:5173"
 PORT="${PORT:-8080}"
-uvicorn open_webui.main:app --port $PORT --host 0.0.0.0 --forwarded-allow-ips '*' --reload
+uvicorn open_webui.main:app --port "$PORT" --host 0.0.0.0 --forwarded-allow-ips '*' --reload
```

### 2. `backend/requirements.txt` - Add Agentic Fabriq SDK

**Changes:**
- Added `agentic-fabriq-sdk==0.1.27` dependency

```diff
 # AI libraries
 tiktoken
 mcp==1.14.1
+agentic-fabriq-sdk==0.1.27
 
 openai
 anthropic
```

### 3. `backend/open_webui/routers/configs.py` - Tool Server Configuration

**Changes:**
- Added imports for AF token cache and SDK
- Added `agentic_fabriq` authentication type handler
- Implements Okta-to-AF token exchange for tool server verification

```diff
 from open_webui.utils.mcp.client import MCPClient
 from open_webui.models.oauth_sessions import OAuthSessions
+from open_webui.utils.af_token_cache import af_token_cache
+from af_sdk import exchange_okta_for_af_token
 
 from open_webui.env import SRC_LOG_LEVELS
```

```diff
                         except Exception as e:
                             pass
+                    elif form_data.auth_type == "agentic_fabriq":
+                        try:
+                            # Check cache first
+                            cached_token = af_token_cache.get(user.id)
+                            if cached_token:
+                                token = cached_token
+                                log.debug(f"Using cached AF token for user {user.id}")
+                            else:
+                                # Get Okta token from OAuth session
+                                # Try both "okta" and "oidc" provider names
+                                okta_session = OAuthSessions.get_session_by_provider_and_user_id(
+                                    "okta", user.id
+                                )
+                                if not okta_session:
+                                    okta_session = OAuthSessions.get_session_by_provider_and_user_id(
+                                        "oidc", user.id
+                                    )
+                                
+                                if not okta_session or not okta_session.token.get("access_token"):
+                                    raise HTTPException(
+                                        status_code=400,
+                                        detail="No Okta/OIDC session found. Please log in with Okta first.",
+                                    )
+                                
+                                okta_access_token = okta_session.token.get("access_token")
+                                
+                                # Exchange Okta token for AF token
+                                # Hardcoded credentials for Agentic Fabriq
+                                AF_APP_ID = "org-dab47e96-cd27-417b-90f3-59585f39b9a7_openwebui"
+                                AF_APP_SECRET = "kB4ONkd8on0hxJUgbk6ryInt5XdeZ2VM"
+                                
+                                af_token = await exchange_okta_for_af_token(
+                                    okta_access_token,
+                                    AF_APP_ID,
+                                    AF_APP_SECRET
+                                )
+                                
+                                if not af_token:
+                                    raise HTTPException(
+                                        status_code=400,
+                                        detail="Failed to exchange Okta token for Agentic Fabriq token",
+                                    )
+                                
+                                # Cache the token for 1 hour
+                                af_token_cache.set(user.id, af_token)
+                                token = af_token
+                                log.info(f"Successfully exchanged Okta token for AF token for user {user.id}")
+                        except HTTPException:
+                            raise
+                        except Exception as e:
+                            log.error(f"Error getting Agentic Fabriq token: {e}")
+                            raise HTTPException(
+                                status_code=400,
+                                detail=f"Failed to authenticate with Agentic Fabriq: {str(e)}",
+                            )
 
                     if token:
                         headers = {"Authorization": f"Bearer {token}"}
```

### 4. `backend/open_webui/utils/middleware.py` - Chat Payload Processing

**Changes:**
- Added imports for AF token cache and SDK
- Added `agentic_fabriq` authentication type handler for chat requests
- Extensive debug logging for token exchange
- Same token exchange logic as configs.py

```diff
 from open_webui.models.chats import Chats
 from open_webui.models.folders import Folders
 from open_webui.models.users import Users
+from open_webui.utils.af_token_cache import af_token_cache
+from af_sdk import exchange_okta_for_af_token
 from open_webui.socket.main import (
     get_event_call,
     get_event_emitter,
```

```diff
                         except Exception as e:
                             log.error(f"Error getting OAuth token: {e}")
                             oauth_token = None
+                    elif auth_type == "agentic_fabriq":
+                        try:
+                            # Check cache first
+                            cached_token = af_token_cache.get(user.id)
+                            if cached_token:
+                                headers["Authorization"] = f"Bearer {cached_token}"
+                                log.debug(f"Using cached AF token for user {user.id}")
+                            else:
+                                # Get Okta token from OAuth session
+                                # Try both "okta" and "oidc" provider names
+                                okta_session = OAuthSessions.get_session_by_provider_and_user_id(
+                                    "okta", user.id
+                                )
+                                if not okta_session:
+                                    okta_session = OAuthSessions.get_session_by_provider_and_user_id(
+                                        "oidc", user.id
+                                    )
+                                
+                                if okta_session and okta_session.token.get("access_token"):
+                                    okta_access_token = okta_session.token.get("access_token")
+                                    
+                                    # Log the Okta access token for debugging
+                                    log.info(f"=== OKTA ACCESS TOKEN ===")
+                                    log.info(f"Full Token: {okta_access_token}")
+                                    log.info(f"Token Length: {len(okta_access_token)}")
+                                    log.info(f"========================")
+                                    
+                                    # Exchange Okta token for AF token
+                                    # Hardcoded credentials for Agentic Fabriq
+                                    AF_APP_ID = "org-dab47e96-cd27-417b-90f3-59585f39b9a7_openwebui"
+                                    AF_APP_SECRET = "kB4ONkd8on0hxJUgbk6ryInt5XdeZ2VM"
+                                    
+                                    af_token = await exchange_okta_for_af_token(
+                                        okta_access_token,
+                                        AF_APP_ID,
+                                        AF_APP_SECRET
+                                    )
+                                    
+                                    # Log the token details for debugging
+                                    log.info(f"=== AF TOKEN RESULT ===")
+                                    log.info(f"Type: {type(af_token)}, Value: {af_token}")
+                                    log.info(f"======================")
+
+                                    
+                                    if af_token:
+                                        # Cache the token for 1 hour
+                                        af_token_cache.set(user.id, af_token)
+                                        headers["Authorization"] = f"Bearer {af_token}"
+                                        log.info(f"Successfully exchanged Okta token for AF token for user {user.id}")
+                                    else:
+                                        log.error(f"Failed to exchange Okta token for AF token for user {user.id}")
+                                else:
+                                    log.error(f"No Okta/OIDC session found for user {user.id}")
+                        except Exception as e:
+                            log.error(f"Error getting Agentic Fabriq token: {e}")
 
                     mcp_clients[server_id] = MCPClient()
                     await mcp_clients[server_id].connect(
```

### 5. `src/lib/components/AddToolServerModal.svelte` - Frontend UI

**Changes:**
- Added "Agentic Fabriq" option to authentication type dropdown
- Added help text for AF authentication
- Added debug console.log for type toggling

```diff
-							<div class="flex gap-2 mb-1.5">
-								<div class="flex w-full justify-between items-center">
-									<div class=" text-xs text-gray-500">{$i18n.t('Type')}</div>
+					<div class="flex gap-2 mb-1.5">
+						<div class="flex w-full justify-between items-center">
+							<div class=" text-xs text-gray-500">{$i18n.t('Type')}</div>

-									<div class="">
-										<button
-											on:click={() => {
-												type = ['', 'openapi'].includes(type) ? 'mcp' : 'openapi';
-											}}
-											type="button"
-											class=" text-xs text-gray-700 dark:text-gray-300"
-										>
-											{#if ['', 'openapi'].includes(type)}
-												{$i18n.t('OpenAPI')}
-											{:else if type === 'mcp'}
-												{$i18n.t('MCP')}
-												<span class="text-gray-500">{$i18n.t('Streamable HTTP')}</span>
-											{/if}
-										</button>
-									</div>
-								</div>
+							<div class="">
+								<button
+									on:click={() => {
+										type = ['', 'openapi'].includes(type) ? 'mcp' : 'openapi';
+										console.log('Type toggled to:', type, 'Direct mode:', direct);
+									}}
+									type="button"
+									class=" text-xs text-gray-700 dark:text-gray-300"
+								>
+									{#if ['', 'openapi'].includes(type)}
+										{$i18n.t('OpenAPI')}
+									{:else if type === 'mcp'}
+										{$i18n.t('MCP')}
+										<span class="text-gray-500">{$i18n.t('Streamable HTTP')}</span>
+									{/if}
+								</button>
 							</div>
+						</div>
+					</div>
```

```diff
-											<option value="none">{$i18n.t('None')}</option>
+					<option value="none">{$i18n.t('None')}</option>

-											<option value="bearer">{$i18n.t('Bearer')}</option>
-											<option value="session">{$i18n.t('Session')}</option>
+					<option value="bearer">{$i18n.t('Bearer')}</option>
+					<option value="session">{$i18n.t('Session')}</option>

-											{#if !direct}
-												<option value="system_oauth">{$i18n.t('OAuth')}</option>
-												{#if type === 'mcp'}
-													<option value="oauth_2.1">{$i18n.t('OAuth 2.1')}</option>
-												{/if}
-											{/if}
+					{#if !direct}
+						<option value="system_oauth">{$i18n.t('OAuth')}</option>
+						{#if type === 'mcp'}
+							<option value="oauth_2.1">{$i18n.t('OAuth 2.1')}</option>
+							<option value="agentic_fabriq">Agentic Fabriq</option>
+						{/if}
+					{/if}
```

```diff
+										{:else if auth_type === 'agentic_fabriq'}
+											<div
+												class={`flex items-center text-xs self-center translate-y-[1px] ${($settings?.highContrastMode ?? false) ? 'text-gray-800 dark:text-gray-100' : 'text-gray-500'}`}
+											>
+												{$i18n.t('Exchanges Okta token for Agentic Fabriq access')}
+											</div>
 										{/if}
```

---

## Deleted Files

The following static files were deleted (likely moved to a different location):

- `backend/open_webui/static/apple-touch-icon.png`
- `backend/open_webui/static/custom.css`
- `backend/open_webui/static/favicon-96x96.png`
- `backend/open_webui/static/favicon-dark.png`
- `backend/open_webui/static/favicon.ico`
- `backend/open_webui/static/favicon.png`
- `backend/open_webui/static/favicon.svg`
- `backend/open_webui/static/loader.js`
- `backend/open_webui/static/logo.png`
- `backend/open_webui/static/site.webmanifest`
- `backend/open_webui/static/splash-dark.png`
- `backend/open_webui/static/splash.png`
- `backend/open_webui/static/user-import.csv`
- `backend/open_webui/static/user.png`
- `backend/open_webui/static/web-app-manifest-192x192.png`
- `backend/open_webui/static/web-app-manifest-512x512.png`

---

## How It Works

### Authentication Flow

1. **User Login**: User logs in with Okta SSO via Open WebUI
2. **OAuth Session**: Okta access token is stored in `OAuthSessions` model
3. **Tool Server Connection**: When user connects to an MCP tool server with "Agentic Fabriq" auth:
   - System checks AF token cache
   - If no cached token, retrieves Okta access token from session
   - Exchanges Okta token for AF token using `exchange_okta_for_af_token()`
   - Caches AF token for 1 hour
   - Uses AF token for tool server authentication

### Token Exchange Details

**Agentic Fabriq Credentials:**
- App ID: `org-dab47e96-cd27-417b-90f3-59585f39b9a7_openwebui`
- App Secret: `kB4ONkd8on0hxJUgbk6ryInt5XdeZ2VM`

**Cache Configuration:**
- TTL: 1 hour (3600 seconds)
- Storage: In-memory (non-persistent)
- Thread-safe with locking mechanism

---

## Running the Application

### Development Mode

**Backend:**
```bash
cd backend
./dev.sh
```
This loads the `.oidc` file and starts the backend on `http://localhost:8080`

**Frontend:**
```bash
npm run dev
```
This starts the frontend on `http://localhost:5173`

### Environment Variables

The `.oidc` file is automatically loaded by `dev.sh` and sets:
- `ENABLE_OAUTH_SIGNUP`
- `OAUTH_CLIENT_ID`
- `OAUTH_CLIENT_SECRET`
- `OPENID_PROVIDER_URL`
- `OAUTH_PROVIDER_NAME`
- `OPENID_REDIRECT_URI`

---

## Security Notes

⚠️ **Important Security Considerations:**

1. **Credentials in Code**: The Agentic Fabriq credentials are currently hardcoded. Consider moving to environment variables or secure configuration.

2. **Token Logging**: The middleware includes extensive token logging for debugging. **Remove or disable in production** to avoid exposing sensitive tokens in logs.

3. **Cache Security**: The token cache is in-memory only. Tokens will be lost on server restart.

4. **OAuth Secrets**: The `.oidc` file contains sensitive credentials. Ensure it's:
   - Added to `.gitignore`
   - Not committed to version control
   - Properly secured on the server

---

## Testing

To test the Agentic Fabriq integration:

1. Start the backend with `./dev.sh` (loads OAuth config)
2. Start the frontend with `npm run dev`
3. Log in with Okta credentials
4. Add a new MCP tool server
5. Select "Agentic Fabriq" as authentication type
6. Verify the tool server connects successfully
7. Check logs for token exchange confirmation

---

## Dependencies Added

```
agentic-fabriq-sdk==0.1.27
```

This SDK provides the `exchange_okta_for_af_token()` function used for token exchange.

---

## Git Status

Current branch: `main`

**Modified files:**
- `backend/dev.sh`
- `backend/open_webui/routers/configs.py`
- `backend/open_webui/utils/middleware.py`
- `backend/requirements.txt`
- `src/lib/components/AddToolServerModal.svelte`

**New files (untracked):**
- `backend/.oidc`
- `backend/open_webui/utils/af_token_cache.py`

**To commit these changes:**
```bash
git add backend/.oidc
git add backend/open_webui/utils/af_token_cache.py
git add backend/dev.sh
git add backend/open_webui/routers/configs.py
git add backend/open_webui/utils/middleware.py
git add backend/requirements.txt
git add src/lib/components/AddToolServerModal.svelte
git commit -m "Add Agentic Fabriq integration and Okta SSO configuration"
```

---

## Troubleshooting

### Token Exchange Fails

Check logs for:
- Okta session exists and has valid access token
- AF SDK is installed (`pip install agentic-fabriq-sdk==0.1.27`)
- Okta access token format is correct

### OAuth Login Not Working

Verify:
- `.oidc` file is loaded (check `dev.sh` is sourcing it)
- Okta redirect URI matches: `http://localhost:8080/oauth/oidc/login/callback`
- Okta app is configured correctly with proper scopes

### Cache Issues

Clear the cache programmatically:
```python
from open_webui.utils.af_token_cache import af_token_cache
af_token_cache.clear()
```

---

*Last Updated: December 18, 2024*

