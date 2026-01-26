# Story 1.1: Token Management System for Dual-Market Trading

**Story Key**: 1-1-token-management-system
**Epic**: Auto-Trading System Core Infrastructure
**Priority**: P0 (Critical)
**Status**: done
**Assignee**: Dev Agent
**Created**: 2026-01-26
**Updated**: 2026-01-26

---

## Story

**As a** trading system administrator
**I want** separate token management for US and KR markets with automatic renewal
**So that** the system can operate 24/7 without manual intervention for authentication

**Context:**
The Korean Investment Securities (KIS) API requires OAuth2 tokens that expire after a certain period. The system needs to manage tokens separately for US and KR markets, handle automatic renewal, and respect the 24-hour token issuance limits imposed by the API.

**Business Value:**
- Enables unattended 24/7 automated trading
- Prevents authentication failures during trading hours
- Supports dual-market operations (US + KR)
- Reduces operational overhead

---

## Acceptance Criteria

### AC1: US/KR Token Separation
**Given** the system initializes
**When** tokens are requested for US and KR markets
**Then** separate token files are created and managed:
- US tokens: `us_api_token.json`, `us_token_issued_at.dat`
- KR tokens: `kr_api_token.json`, `kr_token_issued_at.dat`
- Token files do not conflict or overwrite each other

**Validation:**
- [ ] US and KR token files use different prefixes
- [ ] Token managers can operate simultaneously without conflicts
- [ ] Mojito2 library token files are also separated (`us_krs_token.dat`, `kr_krs_token.dat`)

### AC2: Automatic Token Renewal
**Given** a token is about to expire or has expired
**When** the system requests a valid token
**Then** the token manager automatically requests a new token from the API

**Validation:**
- [ ] Expired tokens trigger automatic renewal
- [ ] Token expiration is calculated correctly (expires_at timestamp)
- [ ] New tokens are saved to the correct token file
- [ ] Token renewal does not disrupt ongoing operations

### AC3: 24-Hour Issuance Limit Handling
**Given** the API enforces 24-hour token issuance limits
**When** a token renewal fails due to rate limiting
**Then** the system logs the error and uses the existing valid token if available

**Validation:**
- [ ] System detects 24-hour limit errors
- [ ] Error messages are logged clearly
- [ ] Existing valid tokens continue to work
- [ ] System does not enter infinite retry loops

### AC4: Token Status Management
**Given** the token management system is running
**When** administrators need to check token status
**Then** CLI commands are available to check, delete, and refresh tokens

**Validation:**
- [ ] `python -m us.token_manager check` - displays US token status
- [ ] `python -m kr.token_manager check` - displays KR token status
- [ ] `python -m us.token_manager delete` - removes US token
- [ ] `python -m kr.token_manager refresh` - forces US token renewal
- [ ] `python -m us.token_manager get` - retrieves valid US token

### AC5: Base Token Manager Inheritance
**Given** US and KR markets share common token management logic
**When** implementing market-specific token managers
**Then** both inherit from a common `BaseTokenManager` class

**Validation:**
- [ ] `BaseTokenManager` implements core token logic
- [ ] `USTokenManager` extends base with US-specific config
- [ ] `KRTokenManager` extends base with KR-specific config
- [ ] Code duplication is minimized through inheritance

---

## Tasks/Subtasks

### Design & Architecture
- [x] Design token separation strategy (file prefixes: us_, kr_)
- [x] Define BaseTokenManager abstract class interface
- [x] Plan 24-hour limit error handling approach

### Implementation
- [x] Implement `BaseTokenManager` class
  - [x] `load_token()` - load token from file
  - [x] `save_token()` - save token to file
  - [x] `delete_token()` - remove token file
  - [x] `get_valid_token()` - get or renew token
  - [x] `get_token_info()` - display token status
  - [x] `is_token_expired()` - check expiration
- [x] Implement `USTokenManager` (inherits BaseTokenManager)
  - [x] Override `get_api_url()` for US endpoint
  - [x] Override `get_app_credentials()` for US credentials
  - [x] Override `get_token_file_prefix()` return "us_"
- [x] Implement `KRTokenManager` (inherits BaseTokenManager)
  - [x] Override `get_api_url()` for KR endpoint
  - [x] Override `get_app_credentials()` for KR credentials
  - [x] Override `get_token_file_prefix()` return "kr_"
- [x] Add CLI command handlers in `__main__` blocks

### Testing
- [x] Create `tests/test_dual_token.py` for token separation tests
  - [x] Test token file paths are different
  - [x] Test US token generation
  - [x] Test KR token generation
  - [x] Test token independence
  - [x] Test mojito2 token file separation
  - [x] Test token file contents
- [x] Create `test_token_refresh.py` for renewal tests
  - [x] Test token expiration detection
  - [x] Test automatic token renewal
  - [x] Test broker reinitialization after renewal

### Configuration
- [x] Update `us/config.py` with TOKEN_FILE_PREFIX = "us_"
- [x] Update `kr/config.py` with TOKEN_FILE_PREFIX = "kr_"
- [x] Set MOJITO_TOKEN_FILE paths with prefixes

---

## Dev Agent Record

### Implementation Summary
Implemented a robust dual-market token management system using inheritance to minimize code duplication. The `BaseTokenManager` class provides core token lifecycle management (load, save, delete, renew, check expiration), while `USTokenManager` and `KRTokenManager` customize behavior for their respective markets through configuration overrides.

Token files are strictly separated using prefixes:
- US: `us_api_token.json`, `us_token_issued_at.dat`, `us_krs_token.dat`
- KR: `kr_api_token.json`, `kr_token_issued_at.dat`, `kr_krs_token.dat`

CLI commands enable manual token management during development and troubleshooting.

### File List
```
common/base_token_manager.py      # Core token management logic
us/token_manager.py                # US market token manager
us/config.py                       # US configuration with TOKEN_FILE_PREFIX
kr/token_manager.py                # KR market token manager
kr/config.py                       # KR configuration with TOKEN_FILE_PREFIX
tests/test_dual_token.py           # Token separation tests (262 lines)
test_token_refresh.py              # Token renewal tests (141 lines)
```

### Technical Decisions

**1. Inheritance Pattern**
- **Decision**: Use abstract base class `BaseTokenManager`
- **Rationale**: US and KR markets share 90% of token logic
- **Alternative Considered**: Duplicate code in each manager
- **Trade-off**: Slight complexity increase for major code reduction

**2. File Prefix Strategy**
- **Decision**: Use prefixes (`us_`, `kr_`) instead of subdirectories
- **Rationale**: Simpler file paths, easier to locate in project root
- **Alternative Considered**: Separate `/us-tokens/` and `/kr-tokens/` directories
- **Trade-off**: All token files in one directory (acceptable for 2 markets)

**3. Token Expiration Calculation**
- **Decision**: Calculate expiration as `issue_time + 86400` (24 hours)
- **Rationale**: API tokens valid for 24 hours from issuance
- **Alternative Considered**: Use API-provided expiration timestamp
- **Trade-off**: Assumes 24-hour validity (matches API documentation)

**4. 24-Hour Limit Error Handling**
- **Decision**: Log error, continue with existing valid token
- **Rationale**: Prevents service disruption when renewal blocked
- **Alternative Considered**: Crash and alert administrator
- **Trade-off**: Silent degradation vs. aggressive failure

**5. CLI Command Structure**
- **Decision**: Python module execution (`python -m us.token_manager check`)
- **Rationale**: Standard Python pattern, no additional scripts needed
- **Alternative Considered**: Separate shell scripts
- **Trade-off**: Slightly verbose commands (acceptable for admin tools)

### Known Limitations

1. **No Token Caching in Memory**
   - Current: Reads token file on every request
   - Impact: Minor performance overhead (~1ms per read)
   - Future: Add in-memory cache with expiration

2. **No Concurrent Token Renewal Protection**
   - Current: Multiple processes could trigger simultaneous renewals
   - Impact: Possible race condition if >1 process starts simultaneously
   - Future: Add file locking or atomic operations

3. **Hard-Coded 24-Hour Expiration**
   - Current: Assumes all tokens valid for 24 hours
   - Impact: May break if API changes expiration policy
   - Future: Parse expiration from API response if provided

4. **No Token Renewal Retry Logic**
   - Current: Single renewal attempt on expiration
   - Impact: Network errors cause immediate failure
   - Future: Add exponential backoff retry (3 attempts)

### Test Coverage

**tests/test_dual_token.py** (262 lines, 6 tests):
- Token file path separation
- US token generation
- KR token generation
- Token independence verification
- Mojito2 token file separation
- Token file contents validation

**test_token_refresh.py** (141 lines, 8 steps):
- Token status check
- Forced expiration for testing
- Token renewal trigger
- Broker reinitialization
- API call validation after renewal

**Integration Tests** (`tests/test_integration.py`):
- Module import verification
- Token separation end-to-end
- API client initialization with tokens

### Change Log

**2026-01-26** - Initial Implementation
- Created `BaseTokenManager` with core token lifecycle
- Implemented `USTokenManager` and `KRTokenManager` subclasses
- Added token separation via file prefixes
- Created comprehensive test suite (6 tests in test_dual_token.py)
- Added token refresh validation (8-step test in test_token_refresh.py)
- Integrated CLI commands for manual token management

---

## Dependencies

**Upstream Dependencies:**
- None (foundational infrastructure)

**Downstream Dependencies:**
- Story 1.2: API Client Implementation (requires token managers)
- Story 1.3: Trading Strategy Engine (requires authenticated API access)
- Story 1.4: Dual Market Scheduler (requires independent US/KR tokens)

**External Dependencies:**
- KIS API OAuth2 endpoints
- `mojito2` library for API communication
- Python `requests` library for HTTP calls

---

## Notes

**Security Considerations:**
- Token files contain sensitive credentials
- Should be added to `.gitignore` to prevent accidental commits
- File permissions should restrict read access to application user only

**Operational Notes:**
- Monitor token renewal logs for 24-hour limit errors
- Pre-generate tokens before market open if concerned about limits
- Keep backup tokens for emergency manual intervention

**Future Enhancements:**
- Add Prometheus metrics for token expiration monitoring
- Implement token health check endpoint for monitoring systems
- Add Slack/email notifications for token renewal failures
- Consider token rotation strategy for improved security

---

## Review Checklist

**Code Quality:**
- [ ] All tasks marked complete are actually implemented
- [ ] Acceptance Criteria are fully satisfied
- [ ] Code follows project standards (PEP 8 for Python)
- [ ] No hardcoded credentials in source code

**Testing:**
- [ ] Unit tests pass for token lifecycle
- [ ] Integration tests verify US/KR separation
- [ ] Token renewal tested with forced expiration
- [ ] Error cases handled (network errors, API limits)

**Documentation:**
- [ ] Docstrings present for all classes/methods
- [ ] CLI command usage documented
- [ ] Token file formats documented
- [ ] Troubleshooting guide for common issues

**Security:**
- [ ] Token files excluded from version control
- [ ] No tokens logged in plaintext
- [ ] Secure file permissions recommended
- [ ] API credentials sourced from environment variables

---

*This story is now ready for adversarial code review.*
