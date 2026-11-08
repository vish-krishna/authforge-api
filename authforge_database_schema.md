# AuthForge: Database Schema Architecture & DDL (PostgreSQL)

## 1. Schema Diagram

```
                        +----------------------------+
                        |           users            |
                        +--------------+-------------+
                                       |
          +----------------------------+----------------------------+
          | 1                          | 1                          | 1
          |                            |                            |
          | N                          | N                          | N
+---------v----------+       +---------v----------+       +---------v----------+
|   user_passwords   |       |   user_sessions    |       |   account_locks    |
+--------------------+       +--------------------+       +--------------------+
          |
          | 1
          |
          | N
+---------v------------------+       +------------------------------------+
|  password_reset_requests   |       |          auth_audit_logs           |
+----------------------------+       |        (Append-Only Ledger)        |
                                     +------------------------------------+
```

---

## 2. Table Specifications

### 2.1 `users`
Central identity record.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Immutable unique identifier |
| `email` | `VARCHAR(255)` | `NOT NULL` | Lowercase normalized email |
| `email_verified` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Email confirmation state |
| `status` | `VARCHAR(30)` | `NOT NULL DEFAULT 'ACTIVE'` | `ACTIVE`, `SUSPENDED`, `LOCKED`, `DEACTIVATED` |
| `failed_login_count` | `INTEGER` | `NOT NULL DEFAULT 0` | Consecutive login failure counter |
| `last_login_at` | `TIMESTAMPTZ`| `NULL` | Timestamp of latest successful auth |
| `last_login_ip` | `VARCHAR(45)` | `NULL` | IPv4 or IPv6 address |
| `password_changed_at`| `TIMESTAMPTZ`| `NULL` | Timestamp of latest password modification |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Update timestamp |
| `deleted_at` | `TIMESTAMPTZ`| `NULL` | Soft delete timestamp |

---

### 2.2 `user_passwords`
Maintains current active password and previous hashes for non-reuse enforcement.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Credential record identifier |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| Owner user |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | Argon2id / bcrypt hash string |
| `algorithm_version` | `INTEGER` | `NOT NULL DEFAULT 1` | Hash upgrade version tracking |
| `is_active` | `BOOLEAN` | `NOT NULL DEFAULT TRUE` | Active status (only one true per user) |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Password set timestamp |

---

### 2.3 `user_sessions`
Database-backed refresh token store for session tracking and rotation.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Session identifier |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| User identity |
| `refresh_token_hash`| `VARCHAR(64)` | `NOT NULL UNIQUE` | SHA-256 hash of refresh token |
| `ip_address` | `VARCHAR(45)` | `NOT NULL` | Client IP address |
| `user_agent` | `VARCHAR(255)` | `NULL` | Browser / device string |
| `is_revoked` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Explicit revocation status |
| `expires_at` | `TIMESTAMPTZ`| `NOT NULL` | Absolute token expiry |
| `last_used_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Idle activity timestamp |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Session creation time |

---

### 2.4 `account_locks`
Lock history and active lockout records.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Lock record ID |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| Locked user |
| `reason` | `VARCHAR(50)` | `NOT NULL` | e.g. `MAX_FAILED_LOGINS`, `MANUAL_ADMIN` |
| `locked_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Start of lock |
| `unlock_at` | `TIMESTAMPTZ`| `NULL` | Scheduled auto-unlock time (`NULL` = indefinite) |
| `unlocked_at` | `TIMESTAMPTZ`| `NULL` | Actual unlock time |
| `unlocked_by` | `UUID` | `NULL REFERENCES users(id) ON DELETE SET NULL` | Admin user who unlocked |

---

### 2.5 `password_reset_requests`
OTP tokens, attempt counts, and lifecycle statuses.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Reset flow ID |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| Target user |
| `otp_hash` | `VARCHAR(64)` | `NOT NULL` | SHA-256 hash of the 6-digit OTP |
| `attempt_count` | `INTEGER` | `NOT NULL DEFAULT 0` | Failed attempts counter |
| `max_attempts` | `INTEGER` | `NOT NULL DEFAULT 3` | Maximum allowed tries before lock |
| `status` | `VARCHAR(20)` | `NOT NULL DEFAULT 'PENDING'` | `PENDING`, `USED`, `EXPIRED`, `LOCKED` |
| `expires_at` | `TIMESTAMPTZ`| `NOT NULL` | Expiration (e.g. 15 minutes) |
| `used_at` | `TIMESTAMPTZ`| `NULL` | Completion timestamp |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Issuance timestamp |

---

### 2.6 `auth_audit_logs`
Unified immutable audit ledger.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Event ID |
| `user_id` | `UUID` | `NULL REFERENCES users(id) ON DELETE SET NULL` | Target user ID (nullable) |
| `email_attempted` | `VARCHAR(255)` | `NOT NULL` | Email supplied in request |
| `event_type` | `VARCHAR(50)` | `NOT NULL` | Event classifier (e.g., `LOGIN_SUCCESS`) |
| `ip_address` | `VARCHAR(45)` | `NOT NULL` | Request IP |
| `user_agent` | `VARCHAR(255)` | `NULL` | Request user-agent |
| `metadata` | `JSONB` | `NULL` | Structured contextual metadata |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Event timestamp |

---

## 3. Production PostgreSQL DDL Script

```sql
-- Enable cryptographic extensions for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. USERS TABLE
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    status VARCHAR(30) NOT NULL DEFAULT 'ACTIVE',
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    last_login_at TIMESTAMPTZ NULL,
    last_login_ip VARCHAR(45) NULL,
    password_changed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT chk_users_status CHECK (status IN ('ACTIVE', 'SUSPENDED', 'LOCKED', 'DEACTIVATED'))
);

-- Partial index for active users ensuring email uniqueness across non-deleted rows
CREATE UNIQUE INDEX uq_users_active_email ON users (LOWER(email)) WHERE deleted_at IS NULL;
CREATE INDEX ix_users_status ON users (status);

-- ============================================================================
-- 2. USER PASSWORDS TABLE (Active Credential + Last 5 History)
-- ============================================================================
CREATE TABLE user_passwords (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    algorithm_version INTEGER NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX ix_user_passwords_history ON user_passwords (user_id, created_at DESC);
CREATE UNIQUE INDEX uq_user_passwords_active ON user_passwords (user_id) WHERE is_active = TRUE;

-- ============================================================================
-- 3. USER SESSIONS TABLE (Refresh Token Storage)
-- ============================================================================
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(64) NOT NULL UNIQUE,
    ip_address VARCHAR(45) NOT NULL,
    user_agent VARCHAR(255) NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    last_used_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX ix_user_sessions_lookup ON user_sessions (refresh_token_hash) WHERE is_revoked = FALSE;
CREATE INDEX ix_user_sessions_user_active ON user_sessions (user_id) WHERE is_revoked = FALSE;

-- ============================================================================
-- 4. ACCOUNT LOCKS TABLE
-- ============================================================================
CREATE TABLE account_locks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(50) NOT NULL,
    locked_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    unlock_at TIMESTAMPTZ NULL,
    unlocked_at TIMESTAMPTZ NULL,
    unlocked_by UUID NULL REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX ix_account_locks_active ON account_locks (user_id) WHERE unlocked_at IS NULL;

-- ============================================================================
-- 5. PASSWORD RESET REQUESTS TABLE (OTP Storage)
-- ============================================================================
CREATE TABLE password_reset_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash VARCHAR(64) NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_reset_status CHECK (status IN ('PENDING', 'USED', 'EXPIRED', 'LOCKED'))
);

CREATE INDEX ix_reset_requests_pending ON password_reset_requests (user_id, status) WHERE status = 'PENDING';

-- ============================================================================
-- 6. AUTH AUDIT LOGS TABLE (Forensic Ledger)
-- ============================================================================
CREATE TABLE auth_audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    email_attempted VARCHAR(255) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    ip_address VARCHAR(45) NOT NULL,
    user_agent VARCHAR(255) NULL,
    metadata JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX ix_audit_user_created ON auth_audit_logs (user_id, created_at DESC);
CREATE INDEX ix_audit_event_created ON auth_audit_logs (event_type, created_at DESC);
CREATE INDEX ix_audit_email_attempted ON auth_audit_logs (LOWER(email_attempted), created_at DESC);
```