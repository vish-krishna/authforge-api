# AuthForge: Software Requirements Specification (SRS)

## 1. System Overview & Scope

### 1.1 Purpose
AuthForge is an enterprise-grade identity and authentication microservice. It manages user credentials, provides brute-force mitigation, handles stateful session tracking with database-backed refresh tokens, implements OTP-based password recovery, enforces a password non-reuse policy, and produces tamper-resistant audit logs.

### 1.2 User Roles & Actors
* **Anonymous Guest / Client:** Unauthenticated user accessing registration, login, and password-reset initiation.
* **Authenticated User:** Identified user holding active tokens, entitled to rotate tokens, inspect sessions, change passwords, and revoke access.
* **Security Administrator (SecOps):** Privileged operator authorized to review audit logs, manually lock/unlock accounts, and inspect security telemetry.
* **System Daemon / Cron Worker:** Background service handling lock expiry sweeps, session pruning, and notification dispatch.

---

## 2. Functional Requirements

### FR-1: User Registration & Verification
* **FR-1.1 Registration:** The system shall accept `email` and `password`. The email must be normalized to lowercase and must be unique among active accounts.
* **FR-1.2 Verification Flag:** New users shall have `email_verified` initialized to `false` until confirmed via email link or verification code.
* **FR-1.3 Initial Credential Storage:** Passwords must be hashed using Argon2id or bcrypt before storage. The first password entry is created in `user_passwords` with `is_active = true`.

### FR-2: User Authentication & Login Pipeline
* **FR-2.1 Input Data:** The login endpoint accepts `email`, `password`, and request context (client IP address, User-Agent).
* **FR-2.2 Account Standing Verification:**
  * If the user does not exist: log `LOGIN_FAIL_UNKNOWN_USER` in audit logs and return `401 Unauthorized` (generic error).
  * If the user is marked `deleted_at IS NOT NULL`: return `401 Unauthorized`.
  * If `status` is not `ACTIVE` (e.g., `SUSPENDED`, `DEACTIVATED`): return `403 Forbidden`.
* **FR-2.3 Active Lock Check:**
  * Check `account_locks` for an active lock: `unlocked_at IS NULL AND (unlock_at IS NULL OR unlock_at > NOW())`.
  * If active: log `LOGIN_BLOCKED_LOCKED` and return `423 Locked`.
  * If expired (`unlock_at <= NOW()`): mark lock resolved, reset `failed_login_count` to 0, restore `status = ACTIVE`, and continue auth.
* **FR-2.4 Credential Verification:**
  * Validate password against active `user_passwords` entry.
  * **On Failure:**
    * Increment `users.failed_login_count` by 1.
    * Record entry in `auth_audit_logs` with `event_type = 'LOGIN_FAIL_CREDENTIALS'`.
    * If `failed_login_count >= 5`: trigger **FR-3 (Account Lockout)** immediately.
    * Return `401 Unauthorized`.
  * **On Success:**
    * Set `users.failed_login_count = 0`.
    * Update `users.last_login_at = NOW()` and `users.last_login_ip = client_ip`.
    * Issue a short-lived Access Token (JWT, 15m expiration).
    * Issue a long-lived Refresh Token (cryptographic random string, 30d expiration).
    * Save `SHA256(refresh_token)` in `user_sessions`.
    * Record `LOGIN_SUCCESS` in `auth_audit_logs`.
    * Return token pair to client.

### FR-3: Brute-Force Attack Mitigation & Account Lockout
* **FR-3.1 Lock Threshold:** An account shall be locked when `failed_login_count` reaches 5 consecutive failures without a successful login.
* **FR-3.2 Lock Record:**
  * Insert a row into `account_locks` with `reason = 'MAX_FAILED_LOGINS'`, `locked_at = NOW()`, and `unlock_at = NOW() + INTERVAL '30 MINUTES'`.
  * Update `users.status = 'LOCKED'`.
  * Record `ACCOUNT_LOCKED` in `auth_audit_logs`.
* **FR-3.3 Lock Clearance:**
  * Automatic: When `NOW() > unlock_at`, subsequent login attempt clears the lock.
  * Manual: Admin endpoint sets `unlocked_at = NOW()`, `unlocked_by = admin_id`, resets user `status = 'ACTIVE'`, and sets `failed_login_count = 0`.

### FR-4: Database-Backed Session & Refresh Token Handling
* **FR-4.1 Persistence:** Each issued refresh token must be hashed via SHA-256 and stored in `user_sessions` with `ip_address`, `user_agent`, `expires_at`, and `is_revoked = false`.
* **FR-4.2 Refresh Token Rotation (RTR):**
  * When exchanging a refresh token for a new token pair, verify the incoming token hash against `user_sessions`.
  * If the session is found and `is_revoked = true`: **Token Reuse Detected**. Immediately revoke all active sessions for that `user_id` and log `SECURITY_ALERT_TOKEN_REUSE`.
  * If valid and active: mark current session `is_revoked = true`, create a new session row for the newly issued refresh token, and return new access/refresh tokens.
* **FR-4.3 Session Revocation:**
  * **Single Logout:** Sets `is_revoked = true` for the active session.
  * **Global Logout:** Sets `is_revoked = true` across all sessions for `user_id`.

### FR-5: Forgot Password via Email OTP
* **FR-5.1 Request OTP:**
  * User provides `email`.
  * If user exists and is active, generate a 6-digit numeric code.
  * Mark any existing `PENDING` reset requests for this user as `EXPIRED`.
  * Save `SHA256(otp)` in `password_reset_requests` with `expires_at = NOW() + INTERVAL '15 MINUTES'`, `max_attempts = 3`, and `status = 'PENDING'`.
  * Dispatch the OTP via transactional email.
  * Log `PASSWORD_RESET_REQUESTED` in `auth_audit_logs`.
  * Return generic `200 OK` regardless of whether the email exists.
* **FR-5.2 OTP Verification & Reset:**
  * User provides `email`, `otp`, and `new_password`.
  * Locate latest `PENDING` request where `expires_at > NOW()`.
  * If hash check fails:
    * Increment `attempt_count` by 1.
    * If `attempt_count >= max_attempts`: set `status = 'LOCKED'`.
    * Log `OTP_VERIFY_FAIL` in `auth_audit_logs`.
    * Return `400 Bad Request`.
  * If hash matches: proceed to password policy validation (FR-6).

### FR-6: Password Non-Reuse Policy (Last 5 Passwords)
* **FR-6.1 Policy Enforcement:**
  * When a user submits a new password (via reset or profile change), retrieve the user's last 5 records from `user_passwords` ordered by `created_at DESC`.
  * Compare the new password against each hash using constant-time verification.
  * If a match is found: reject the request with `400 Bad Request` (`CANNOT_REUSE_RECENT_PASSWORD`).
* **FR-6.2 Credential Application:**
  * Set current active credential `is_active = false`.
  * Insert new record in `user_passwords` with `is_active = true` and `created_at = NOW()`.
  * Set `users.password_changed_at = NOW()`.
  * Mark `password_reset_requests.status = 'USED'` and `used_at = NOW()`.
  * Invalidate all existing `user_sessions` for that user (`is_revoked = true`).
  * Record `PASSWORD_RESET_SUCCESS` in `auth_audit_logs`.

### FR-7: Forensic Logging & Audit Telemetry
* **FR-7.1 Immutable Ledger:** Write append-only records to `auth_audit_logs` for all critical security events:
  * `LOGIN_ATTEMPT`, `LOGIN_SUCCESS`, `LOGIN_FAIL_CREDENTIALS`, `LOGIN_FAIL_UNKNOWN_USER`
  * `ACCOUNT_LOCKED`, `ACCOUNT_UNLOCKED`
  * `PASSWORD_RESET_REQUESTED`, `OTP_VERIFY_FAIL`, `PASSWORD_RESET_SUCCESS`
  * `SESSION_REVOKED`, `ALL_SESSIONS_REVOKED`, `TOKEN_REUSE_DETECTED`
* **FR-7.2 Context Capture:** Every audit entry must store client IP, User-Agent, user ID (if identified), email attempted, event type, metadata JSON, and database server timestamp.

---

## 3. Non-Functional Requirements

* **Security:** Cryptographic storage for all credentials (Argon2id or bcrypt) and one-way SHA-256 hashing for all stored tokens and OTPs. No raw tokens or plain text passwords may appear in logs or DB.
* **Performance:** Authentication and token verification queries must resolve in $< 20\text{ ms}$ via covered indexes on `email`, `refresh_token_hash`, and composite user lookup keys.
* **Auditability & Integrity:** The `auth_audit_logs` table must be write-only (`INSERT` only; no `UPDATE` or `DELETE` permitted at the database role level).
* **Clock Accuracy:** All timestamps must use standard UTC (`TIMESTAMPTZ`) backed by system database clock (`func.now()`).