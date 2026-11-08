# AuthForge: REST API Specification

## 1. Overview & Security Architecture

### Base URL
`https://auth.authforge.io/api/v1`

### Authentication Schemes
* **Public / Guest:** No credentials required. Subject to aggressive rate-limiting (e.g., 5 requests/min per IP on login/reset).
* **Bearer Access Token:** Standard short-lived JWT passed in the HTTP Authorization header:
  `Authorization: Bearer <jwt_access_token>`
* **Refresh Token Rotation:** Sent as an opaque string either in the JSON payload or via an `HttpOnly`, `Secure`, `SameSite=Strict` cookie.

### Common Error Payload Structure
```json
{
  "error": {
    "code": "STRING_ERROR_CODE",
    "message": "Human-readable explanation of error.",
    "details": {}
  }
}
```

---

## 2. Public Authentication Endpoints

### 2.1 User Registration
* **Endpoint:** `POST /auth/register`
* **Description:** Provisions a new user account, stores initial password, and initializes status.

#### Request Body
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

#### Response (`201 Created`)
```json
{
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "email": "user@example.com",
  "email_verified": false,
  "status": "ACTIVE",
  "created_at": "2026-11-08T10:30:00Z"
}
```

#### Error Responses
* `400 Bad Request` (`WEAK_PASSWORD`): Password does not meet minimum complexity standards.
* `409 Conflict` (`EMAIL_ALREADY_EXISTS`): Active account with email already exists.

---

### 2.2 User Login
* **Endpoint:** `POST /auth/login`
* **Description:** Authenticates credentials, evaluates lock status, increments failure counter, and generates tokens.

#### Request Body
```json
{
  "email": "user@example.com",
  "password": "SecurePassword123!"
}
```

#### Response (`200 OK`)
```json
{
  "token_type": "Bearer",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900,
  "refresh_token": "rt_8f14e45fceea4c6db2c2193b2de9a175",
  "user": {
    "id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
    "email": "user@example.com",
    "email_verified": true
  }
}
```

#### Error Responses
* `401 Unauthorized` (`INVALID_CREDENTIALS`): Email or password incorrect.
* `403 Forbidden` (`ACCOUNT_SUSPENDED`): Account is deactivated or banned.
* `423 Locked` (`ACCOUNT_LOCKED`): Account is locked due to 5 consecutive failures. Includes remaining lock duration.
  ```json
  {
    "error": {
      "code": "ACCOUNT_LOCKED",
      "message": "Account is locked due to too many failed attempts. Try again in 28 minutes.",
      "details": {
        "unlock_at": "2026-11-08T11:00:00Z"
      }
    }
  }
  ```

---

### 2.3 Refresh Token Rotation
* **Endpoint:** `POST /auth/refresh`
* **Description:** Validates incoming refresh token hash, invalidates it, and issues a fresh token pair.

#### Request Body
```json
{
  "refresh_token": "rt_8f14e45fceea4c6db2c2193b2de9a175"
}
```

#### Response (`200 OK`)
```json
{
  "token_type": "Bearer",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900,
  "refresh_token": "rt_e9b311265ac44a14bf98a28f731a57ce"
}
```

#### Error Responses
* `401 Unauthorized` (`INVALID_REFRESH_TOKEN`): Token expired, missing, or malformed.
* `401 Unauthorized` (`TOKEN_REUSE_DETECTED`): Presented token was already revoked. All user sessions have been terminated.

---

### 2.4 Forgot Password (Initiate Request)
* **Endpoint:** `POST /auth/forgot-password`
* **Description:** Generates a 6-digit numeric OTP, saves hash to `password_reset_requests`, and sends it via email.

#### Request Body
```json
{
  "email": "user@example.com"
}
```

#### Response (`200 OK`)
*Always returns `200 OK` to prevent email enumeration.*
```json
{
  "message": "If an active account exists for this email, a verification code has been dispatched."
}
```

---

### 2.5 Reset Password (OTP Verification & New Password)
* **Endpoint:** `POST /auth/reset-password`
* **Description:** Verifies the 6-digit OTP, validates the new password against the last 5 passwords, updates credentials, and revokes all active sessions.

#### Request Body
```json
{
  "email": "user@example.com",
  "otp": "491823",
  "new_password": "NewSecurePassword456!"
}
```

#### Response (`200 OK`)
```json
{
  "message": "Password successfully reset. All active sessions have been terminated. Please log in."
}
```

#### Error Responses
* `400 Bad Request` (`INVALID_OR_EXPIRED_OTP`): OTP is incorrect or expired.
* `400 Bad Request` (`OTP_MAX_ATTEMPTS_EXCEEDED`): Max 3 attempts reached; OTP invalidated.
* `400 Bad Request` (`CANNOT_REUSE_RECENT_PASSWORD`): Candidate password matches one of the user's last 5 passwords.

---

## 3. Authenticated User Endpoints

### 3.1 Session Logout (Current Device)
* **Endpoint:** `POST /auth/logout`
* **Headers:** `Authorization: Bearer <jwt_access_token>`
* **Description:** Marks the current device session as revoked.

#### Request Body
```json
{
  "refresh_token": "rt_e9b311265ac44a14bf98a28f731a57ce"
}
```

#### Response (`200 OK`)
```json
{
  "message": "Successfully logged out of current session."
}
```

---

### 3.2 Global Logout (All Devices)
* **Endpoint:** `POST /auth/logout-all`
* **Headers:** `Authorization: Bearer <jwt_access_token>`
* **Description:** Marks all active sessions for the authenticated user as revoked.

#### Response (`200 OK`)
```json
{
  "message": "All active sessions have been revoked."
}
```

---

### 3.3 List Active Sessions
* **Endpoint:** `GET /auth/sessions`
* **Headers:** `Authorization: Bearer <jwt_access_token>`
* **Description:** Retrieves all active sessions registered to the calling user.

#### Response (`200 OK`)
```json
{
  "sessions": [
    {
      "id": "e3b0c442-98fc-1c14-9afb-4c7b8c2d1b5a",
      "ip_address": "192.168.1.10",
      "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)...",
      "last_used_at": "2026-11-08T10:15:00Z",
      "created_at": "2026-11-08T08:00:00Z",
      "is_current": true
    }
  ]
}
```

---

### 3.4 Invalidate Specific Remote Session
* **Endpoint:** `DELETE /auth/sessions/{session_id}`
* **Headers:** `Authorization: Bearer <jwt_access_token>`
* **Description:** Allows user to terminate a specific remote device session.

#### Response (`200 OK`)
```json
{
  "message": "Session terminated successfully."
}
```

---

### 3.5 Change Password (In-App)
* **Endpoint:** `POST /auth/change-password`
* **Headers:** `Authorization: Bearer <jwt_access_token>`
* **Description:** Updates password after validating current password and ensuring the new password is not among the last 5.

#### Request Body
```json
{
  "current_password": "CurrentPassword123!",
  "new_password": "NewDifferentPassword789!"
}
```

#### Response (`200 OK`)
```json
{
  "message": "Password updated successfully. Other sessions have been revoked."
}
```

#### Error Responses
* `400 Bad Request` (`CANNOT_REUSE_RECENT_PASSWORD`): Matches one of the last 5 passwords.
* `401 Unauthorized` (`CURRENT_PASSWORD_INCORRECT`): Current password check failed.

---

## 4. Administrative & Security Endpoints (SecOps)

### 4.1 Unlock Account
* **Endpoint:** `POST /admin/users/{user_id}/unlock`
* **Headers:** `Authorization: Bearer <admin_jwt>` (Requires `secops:admin` role)
* **Description:** Resolves active lock records, resets `failed_login_count` to 0, and restores user status to `ACTIVE`.

#### Response (`200 OK`)
```json
{
  "message": "User account unlocked successfully.",
  "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
  "status": "ACTIVE"
}
```

---

### 4.2 Query Audit Logs
* **Endpoint:** `GET /admin/audit-logs`
* **Headers:** `Authorization: Bearer <admin_jwt>` (Requires `secops:read` role)
* **Query Parameters:**
  * `user_id` (optional UUID)
  * `email` (optional string)
  * `event_type` (optional string, e.g. `LOGIN_FAIL_CREDENTIALS`)
  * `limit` (default: 50)
  * `offset` (default: 0)

#### Response (`200 OK`)
```json
{
  "total": 128,
  "items": [
    {
      "id": "76495df4-f8d2-45e3-96b3-6c7db9e15967",
      "user_id": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d",
      "email_attempted": "user@example.com",
      "event_type": "ACCOUNT_LOCKED",
      "ip_address": "203.0.113.195",
      "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)...",
      "metadata": {
        "reason": "MAX_FAILED_LOGINS",
        "lock_duration_minutes": 30
      },
      "created_at": "2026-11-08T10:14:22Z"
    }
  ]
}
```