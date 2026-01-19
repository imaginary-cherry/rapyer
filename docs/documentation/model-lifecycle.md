# Model Lifecycle

Rapyer provides TTL (Time To Live) management for your models, allowing automatic expiration and lifecycle control of your Redis-stored data.

## TTL (Time To Live)

Set automatic expiration for your models:

```python
class Session(AtomicRedisModel):
    user_id: str
    data: dict = {}

# Sessions expire after 30 minutes
Session.Meta.redis = redis_client
Session.Meta.ttl = 1800  # 30 minutes in seconds
```

When a TTL is set, the model will automatically be deleted from Redis after the specified time period.

## TTL Refresh

By default, Rapyer automatically refreshes the TTL of a model whenever it is accessed or modified. This prevents models from expiring while they are still in active use.

### How It Works

When `refresh_ttl` is enabled (the default), the following operations will reset the TTL timer:

- Reading a model with `afind` or `aget`
- Saving changes with `asave`
- Any atomic field operations (e.g., `aappend`, `aupdate`, `aincrease`)

This means a model with a 1-hour TTL will only expire if it remains untouched for a full hour.

### Configuration

TTL refresh can be configured globally or per-model:

#### Global Configuration

```python
from rapyer import init_rapyer

# Enable TTL refresh (default behavior)
await init_rapyer(redis="redis://localhost:6379/0", ttl=3600, refresh_ttl=True)

# Disable TTL refresh globally
await init_rapyer(redis="redis://localhost:6379/0", ttl=3600, refresh_ttl=False)
```

#### Per-Model Configuration

```python
class Session(AtomicRedisModel):
    user_id: str
    data: dict = {}

# Enable TTL refresh for this model
Session.Meta.ttl = 1800
Session.Meta.refresh_ttl = True  # Default

# Disable TTL refresh for this model
Session.Meta.refresh_ttl = False
```

### Use Cases

#### Active Session Management

Keep user sessions alive while they are actively using the application:

```python
class UserSession(AtomicRedisModel):
    user_id: str
    last_page: str
    cart_items: list = []

UserSession.Meta.ttl = 1800  # 30 minutes
UserSession.Meta.refresh_ttl = True

# Session TTL resets every time user navigates
session = await UserSession.afind(session_id)
session.last_page = "/checkout"
await session.asave()  # TTL reset to 30 minutes
```

#### Fixed Expiration

For models that should expire at a fixed time regardless of access:

```python
class PasswordResetToken(AtomicRedisModel):
    user_id: str
    token: str

PasswordResetToken.Meta.ttl = 3600  # 1 hour
PasswordResetToken.Meta.refresh_ttl = False  # Token expires in exactly 1 hour
```

## Setting TTL Dynamically

Use `aset_ttl()` to set or update the TTL of a specific model instance at runtime:

```python
session = await Session.aget("Session:abc123")
await session.aset_ttl(7200)  # Expire in 2 hours
```

This is useful when you need different expiration times for individual instances, or when the TTL should be determined by business logic rather than a fixed configuration.

!!! note
    `aset_ttl()` can only be called on top-level models, not on nested models.

### Best Practices

1. **Enable for sessions**: User sessions, shopping carts, and other user-activity-related models benefit from TTL refresh
2. **Disable for time-sensitive tokens**: Password reset tokens, verification codes, and similar security-related models should have fixed expiration
3. **Consider your use case**: If a model should "live" as long as it's being used, enable TTL refresh. If it should expire at a specific time, disable it
4. **Use `aset_ttl()` for dynamic expiration**: When different instances need different TTLs based on runtime conditions
