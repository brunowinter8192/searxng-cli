# INFRASTRUCTURE

# Legacy coarse statuses — unchanged, still emitted on clean paths
OK        = "OK"
EMPTY     = "EMPTY"
TIMEOUT   = "TIMEOUT"
ERROR     = "ERROR"
RATE_SKIP = "RATE_SKIP"

# EMPTY sub-statuses (Stage 2: per-engine _diagnose_empty fills these in)
EMPTY_NO_RESULTS      = "EMPTY_NO_RESULTS"       # Page loaded, container found, 0 hits — legit empty
EMPTY_NO_CONTAINER    = "EMPTY_NO_CONTAINER"     # Result-container selector found 0 elements — DOM-drift suspect
EMPTY_CONSENT         = "EMPTY_CONSENT"          # Consent-detection fired, redirect not handled
EMPTY_BLOCK           = "EMPTY_BLOCK"            # CAPTCHA / block-page marker detected
EMPTY_CONCURRENT_RACE = "EMPTY_CONCURRENT_RACE"  # Page-state unexpected, possible concurrent-tab collision

# TIMEOUT sub-statuses
TIMEOUT_WATCHDOG = "TIMEOUT_WATCHDOG"  # asyncio.wait_for fired AND search_ms < timeout*1.2 — clean cancel
TIMEOUT_NONCOOP  = "TIMEOUT_NONCOOP"   # asyncio.wait_for fired BUT search_ms >> timeout — non-cooperative
TIMEOUT_HTTPX    = "TIMEOUT_HTTPX"     # httpx.TimeoutException — engine-internal, not watchdog

# ERROR sub-statuses
ERROR_BROWSER = "ERROR_BROWSER"  # pydoll/Chrome connection failure
ERROR_HTTP    = "ERROR_HTTP"     # httpx.HTTPError (non-timeout): 4xx/5xx or transport
ERROR_PARSE   = "ERROR_PARSE"    # JSONDecodeError / KeyError / ValueError / AttributeError from parser
ERROR_OTHER   = "ERROR_OTHER"    # Uncategorized exception
