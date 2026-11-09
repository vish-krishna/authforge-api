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
     | password_histories |       |   user_sessions    |       |   account_locks    |
     +--------------------+       +--------------------+       +--------------------+
                                            |
                                            | 1
                                            +----------------------------+
                                            | 1                          | 1
                                            |                            |
                                            | N                          | N
                                  +---------v------------------+       +-v------------------+
                                  |  password_reset_requests   |       |    sent_emails     |
                                  +----------------------------+       +--------------------+
                                                |
                                                +------------------------+
                                                                         |
                                                              +----------v---------+
                                                              |  auth_audit_logs   |
                                                              | (Append-Only)      |
                                                              +--------------------+
```

---

## 2. Status Master & Reference Data Specifications

### 2.1 User Account Statuses (`users.status`)
Master enumeration controlling authorization gates across all application entry points.

| Status Code | Description | Allows Login | Can Trigger Reset | State Transitions Allowed |
| :--- | :--- | :--- | :--- | :--- |
| `PENDING_VERIFICATION` | User registered, awaiting initial email confirmation. | No | No | `ACTIVE`, `DEACTIVATED` |
| `ACTIVE` | Account in good standing; full access granted. | Yes | Yes | `LOCKED`, `SUSPENDED`, `DEACTIVATED` |
| `LOCKED` | Automated freeze due to threshold infractions (e.g., 5 failed attempts). | No | Yes (via OTP flow) | `ACTIVE`, `SUSPENDED` |
| `SUSPENDED` | Administrative security hold or policy violation penalty. | No | No | `ACTIVE`, `DEACTIVATED` |
| `DEACTIVATED` | Soft-deleted account initiated by user or retention policy. | No | No | `ACTIVE` (admin reactivation) |

### 2.2 Account Lock Reasons (`account_locks.reason`)
Standardized audit reasons for temporary or indefinite access suspension.

| Reason Code | Category | Default Auto-Unlock Window | Description |
| :--- | :--- | :--- | :--- |
| `MAX_FAILED_LOGINS` | Automated | 30 Minutes | 5 consecutive invalid password submissions. |
| `EXCESSIVE_OTP_FAILURES` | Automated | 60 Minutes | Brute-force guessing detected on reset requests. |
| `SECURITY_INCIDENT` | Admin / SOC | Indefinite (`NULL`) | Compromised credentials or token reuse anomaly. |
| `MANUAL_ADMIN_HOLD` | Admin | Indefinite (`NULL`) | Customer support or compliance inspection hold. |

### 2.3 Password Reset Request Statuses (`password_reset_requests.status`)
Lifecycle tracking for OTP challenges.

| Status Code | Description | Terminal State |
| :--- | :--- | :--- |
| `PENDING` | Active OTP issued; awaiting user submission within expiry window. | No |
| `USED` | OTP successfully validated and new password established. | Yes |
| `EXPIRED` | Wall-clock expiry elapsed without verification. | Yes |
| `LOCKED` | Max attempt limit exceeded (3 attempts); challenge invalidated. | Yes |

### 2.4 Email Notification Types & Delivery Statuses (`sent_emails`)
Catalog of outbound security transmissions and delivery states.

| Category / Field | Code | Description |
| :--- | :--- | :--- |
| **Email Types** (`email_type`) | `EMAIL_VERIFICATION` | New account onboarding verification link/code. |
| | `PASSWORD_RESET_OTP` | One-time password for credential recovery. |
| | `ACCOUNT_LOCKED_NOTICE` | Alert notification when account enters locked status. |
| | `PASSWORD_CHANGED_NOTICE`| Confirmation dispatch on successful password change. |
| | `NEW_LOGIN_LOCATION` | Anomaly alert on login from new IP or user-agent. |
| **Delivery Statuses** (`status`) | `QUEUED` | Stored in outbox; awaiting worker dispatch. |
| | `SENT` | Successfully handed off to SMTP/SES provider. |
| | `DELIVERED` | Delivery receipt received from recipient MTA. |
| | `BOUNCED` | Permanent or transient delivery failure. |
| | `FAILED` | Internal worker/SMTP exception. |

---

## 3. Table Specifications

### 3.1 `users`
Central identity record maintaining active credentials and authentication metrics.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Immutable identity UUID |
| `email` | `VARCHAR(255)` | `NOT NULL` | Lowercase normalized email |
| `email_verified` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Email confirmation gate |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | Current active Argon2id / bcrypt hash |
| `algorithm_version` | `INTEGER` | `NOT NULL DEFAULT 1` | Active hash algorithm version |
| `status` | `VARCHAR(30)` | `NOT NULL DEFAULT 'PENDING_VERIFICATION'` | Reference to User Status Master |
| `failed_login_count` | `INTEGER` | `NOT NULL DEFAULT 0` | Consecutive login failures counter |
| `last_login_at` | `TIMESTAMPTZ`| `NULL` | Timestamp of latest successful auth |
| `last_login_ip` | `VARCHAR(45)` | `NULL` | IPv4 or IPv6 client address |
| `password_changed_at`| `TIMESTAMPTZ`| `NULL` | Timestamp of latest password modification |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Creation timestamp |
| `updated_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Modification timestamp |
| `deleted_at` | `TIMESTAMPTZ`| `NULL` | Soft delete timestamp |

---

### 3.2 `password_histories`
Stores archived password hashes to enforce the "last 5 cannot be reused" rule.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Unique record identifier |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| Owner user |
| `password_hash` | `VARCHAR(255)` | `NOT NULL` | password hash |
| `algorithm_version` | `INTEGER` | `NOT NULL DEFAULT 1` | Hash upgrade version tracking |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Archival timestamp |

---

### 3.3 `user_sessions`
Database-backed refresh token storage for session tracking, device context, and token rotation.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Session identifier |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| Session owner |
| `refresh_token_hash`| `VARCHAR(255)` | `NOT NULL UNIQUE` | Cryptographic hash/fingerprint of token |
| `ip_address` | `VARCHAR(45)` | `NOT NULL` | Origin client IP address |
| `user_agent` | `VARCHAR(255)` | `NULL` | Client browser or application string |
| `is_revoked` | `BOOLEAN` | `NOT NULL DEFAULT FALSE` | Explicit session revocation status |
| `expires_at` | `TIMESTAMPTZ`| `NOT NULL` | Absolute session expiry timestamp |
| `last_refreshed_at`| `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Timestamp of last token exchange |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Session establishment timestamp |

---

### 3.4 `account_locks`
Historical and active account lockout ledger.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Lock record ID |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| Locked user |
| `reason` | `VARCHAR(50)` | `NOT NULL` | Reference to Lock Reason Master |
| `locked_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Beginning of lockout |
| `unlock_at` | `TIMESTAMPTZ`| `NULL` | Scheduled auto-unlock time (`NULL` = indefinite) |
| `unlocked_at` | `TIMESTAMPTZ`| `NULL` | Actual unlock timestamp |
| `unlocked_by` | `UUID` | `NULL REFERENCES users(id) ON DELETE SET NULL` | Admin who lifted lock (`NULL` if auto) |

---

### 3.5 `password_reset_requests`
OTP verification tokens and brute-force guard rails.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Reset token/flow identifier |
| `user_id` | `UUID` | `NOT NULL REFERENCES users(id) ON DELETE CASCADE`| Target user identity |
| `otp_hash` | `VARCHAR(255)` | `NOT NULL` | Cryptographic hash of 6-digit OTP |
| `attempt_count` | `INTEGER` | `NOT NULL DEFAULT 0` | Verification failure counter |
| `max_attempts` | `INTEGER` | `NOT NULL DEFAULT 3` | Allowed attempts before invalidation |
| `status` | `VARCHAR(20)` | `NOT NULL DEFAULT 'PENDING'` | Reference to Reset Request Statuses |
| `expires_at` | `TIMESTAMPTZ`| `NOT NULL` | Expiration (e.g., 15 minutes) |
| `used_at` | `TIMESTAMPTZ`| `NULL` | Consumed timestamp |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Creation timestamp |

---

### 3.6 `sent_emails`
Outbox and delivery log for all system-generated security emails (OTPs, lock warnings, notices).

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Notification event ID |
| `user_id` | `UUID` | `NULL REFERENCES users(id) ON DELETE SET NULL` | Recipient user ID (nullable) |
| `recipient_email` | `VARCHAR(255)` | `NOT NULL` | Delivery destination email address |
| `email_type` | `VARCHAR(50)` | `NOT NULL` | Classification from Email Type Master |
| `subject` | `VARCHAR(255)` | `NOT NULL` | Rendered email subject header |
| `template_name` | `VARCHAR(100)` | `NOT NULL` | HTML/text template identifier |
| `template_variables`| `JSONB` | `NULL` | Contextual parameters (excluding cleartext OTPs) |
| `status` | `VARCHAR(20)` | `NOT NULL DEFAULT 'QUEUED'` | Delivery Status Master |
| `provider_message_id`| `VARCHAR(255)`| `NULL` | External tracking ID (SES/SendGrid) |
| `error_message` | `TEXT` | `NULL` | Error details if dispatch failed |
| `sent_at` | `TIMESTAMPTZ`| `NULL` | Actual transmission timestamp |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Record creation timestamp |

---

### 3.7 `auth_audit_logs`
Unified immutable ledger for security telemetry, attempts, and forensics.

| Column | Data Type | Constraints | Description |
| :--- | :--- | :--- | :--- |
| `id` | `UUID` | `PRIMARY KEY DEFAULT gen_random_uuid()` | Event ID |
| `user_id` | `UUID` | `NULL REFERENCES users(id) ON DELETE SET NULL` | Resolved user ID (nullable) |
| `email_attempted` | `VARCHAR(255)` | `NOT NULL` | Email supplied in request payload |
| `event_type` | `VARCHAR(50)` | `NOT NULL` | Event classifier (e.g., `LOGIN_SUCCESS`) |
| `ip_address` | `VARCHAR(45)` | `NOT NULL` | Client IP address |
| `user_agent` | `VARCHAR(255)` | `NULL` | Client user-agent string |
| `metadata` | `JSONB` | `NULL` | Structured contextual metadata |
| `created_at` | `TIMESTAMPTZ`| `NOT NULL DEFAULT clock_timestamp()` | Event creation timestamp |

---

## 4. Production PostgreSQL DDL Script

```sql
-- Enable cryptographic extensions for UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- 1. USERS TABLE (Current Identity & Active Password)
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    email_verified BOOLEAN NOT NULL DEFAULT FALSE,
    password_hash VARCHAR(255) NOT NULL,
    algorithm_version INTEGER NOT NULL DEFAULT 1,
    status VARCHAR(30) NOT NULL DEFAULT 'PENDING_VERIFICATION',
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    last_login_at TIMESTAMPTZ NULL,
    last_login_ip VARCHAR(45) NULL,
    password_changed_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    deleted_at TIMESTAMPTZ NULL,
    CONSTRAINT chk_users_status CHECK (
        status IN ('PENDING_VERIFICATION', 'ACTIVE', 'LOCKED', 'SUSPENDED', 'DEACTIVATED')
    )
);

-- Active email partial index ensuring uniqueness across non-deleted rows
CREATE UNIQUE INDEX uq_users_active_email ON users (LOWER(email)) WHERE deleted_at IS NULL;
CREATE INDEX ix_users_status ON users (status);

-- ============================================================================
-- 2. PASSWORD HISTORIES TABLE (Archived Past Passwords for Non-Reuse Check)
-- ============================================================================
CREATE TABLE password_histories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    algorithm_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

-- Fast lookup for checking candidate passwords against user's last 5 history items
CREATE INDEX ix_password_histories_lookup ON password_histories (user_id, created_at DESC);

-- ============================================================================
-- 3. USER SESSIONS TABLE (Refresh Token Storage & Token Rotation)
-- ============================================================================
CREATE TABLE user_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    refresh_token_hash VARCHAR(255) NOT NULL UNIQUE,
    ip_address VARCHAR(45) NOT NULL,
    user_agent VARCHAR(255) NULL,
    is_revoked BOOLEAN NOT NULL DEFAULT FALSE,
    expires_at TIMESTAMPTZ NOT NULL,
    last_refreshed_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp()
);

CREATE INDEX ix_user_sessions_lookup ON user_sessions (refresh_token_hash) WHERE is_revoked = FALSE;
CREATE INDEX ix_user_sessions_active ON user_sessions (user_id) WHERE is_revoked = FALSE;

-- ============================================================================
-- 4. ACCOUNT LOCKS TABLE (Historical & Active Lockouts)
-- ============================================================================
CREATE TABLE account_locks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reason VARCHAR(50) NOT NULL,
    locked_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    unlock_at TIMESTAMPTZ NULL,
    unlocked_at TIMESTAMPTZ NULL,
    unlocked_by UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    CONSTRAINT chk_account_locks_reason CHECK (
        reason IN ('MAX_FAILED_LOGINS', 'EXCESSIVE_OTP_FAILURES', 'SECURITY_INCIDENT', 'MANUAL_ADMIN_HOLD')
    )
);

CREATE INDEX ix_account_locks_active ON account_locks (user_id) WHERE unlocked_at IS NULL;

-- ============================================================================
-- 5. PASSWORD RESET REQUESTS TABLE (OTP Storage & Rate Limiting)
-- ============================================================================
CREATE TABLE password_reset_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    otp_hash VARCHAR(255) NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_reset_status CHECK (status IN ('PENDING', 'USED', 'EXPIRED', 'LOCKED'))
);

CREATE INDEX ix_password_reset_pending ON password_reset_requests (user_id, status) WHERE status = 'PENDING';

-- ============================================================================
-- 6. SENT EMAILS TABLE (Outbox & Delivery Tracking)
-- ============================================================================
CREATE TABLE sent_emails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NULL REFERENCES users(id) ON DELETE SET NULL,
    recipient_email VARCHAR(255) NOT NULL,
    email_type VARCHAR(50) NOT NULL,
    subject VARCHAR(255) NOT NULL,
    template_name VARCHAR(100) NOT NULL,
    template_variables JSONB NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'QUEUED',
    provider_message_id VARCHAR(255) NULL,
    error_message TEXT NULL,
    sent_at TIMESTAMPTZ NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    CONSTRAINT chk_email_status CHECK (
        status IN ('QUEUED', 'SENT', 'DELIVERED', 'BOUNCED', 'FAILED')
    ),
    CONSTRAINT chk_email_type CHECK (
        email_type IN (
            'EMAIL_VERIFICATION',
            'PASSWORD_RESET_OTP',
            'ACCOUNT_LOCKED_NOTICE',
            'PASSWORD_CHANGED_NOTICE',
            'NEW_LOGIN_LOCATION'
        )
    )
);

CREATE INDEX ix_sent_emails_recipient ON sent_emails (LOWER(recipient_email), created_at DESC);
CREATE INDEX ix_sent_emails_status ON sent_emails (status) WHERE status = 'QUEUED';
CREATE INDEX ix_sent_emails_user ON sent_emails (user_id, created_at DESC);

-- ============================================================================
-- 7. AUTH AUDIT LOGS TABLE (Append-Only Forensic Ledger)
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