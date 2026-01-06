# Atomic Actions

Rapyer provides powerful atomic operations that ensure data consistency and prevent race conditions in concurrent environments. The most user-friendly approach is using the **pipeline context manager**, which allows you to perform multiple operations atomically while working with your models in a natural, Pythonic way.

## Pipeline Context Manager

The pipeline is a context manager that batches all Redis operations performed on a model into a single atomic transaction. When you enter the pipeline context, the model is automatically loaded to its current state, and all changes are applied atomically when the context exits.

### Basic Usage

```python
from rapyer import AtomicRedisModel
from typing import List, Dict


class User(AtomicRedisModel):
    name: str
    score: int = 0
    achievements: List[str] = []
    metadata: Dict[str, str] = {}


async def update_user_progress(user: User, points: int, achievement: str):
    # All operations inside this context are atomic
    async with user.apipeline() as pipeline_user:
        # Model is automatically loaded to current state
        user.score += points
        user.achievements.append(achievement)
        user.metadata["last_update"] = "2024-01-15"

        # All changes are saved atomically when context exits
```

### Key Benefits

1. **Simplicity**: No need to call async methods - just modify attributes directly
2. **Atomicity**: All operations succeed or fail together
3. **Auto-loading**: Model state is refreshed when entering the context
4. **Performance**: Multiple operations batched into single Redis transaction

### Supported Operations

The pipeline context manager supports atomic operations for all Redis types:

- **List operations**: `append()`, `extend()`, `insert()`, `pop()`, `remove()`, `clear()`
- **Dictionary operations**: `update()`, item assignment (`dict[key] = value`), `pop()`, `clear()`
- **String operations**: Direct assignment and modification
- **Integer operations**: Direct assignment, arithmetic operations
- **Bytes operations**: Direct assignment and modification

!!! warning "Inplace Operators and Concurrency"
    When using inplace operators like `+=`, `-=`, `*=`, etc. inside a pipeline, the data sent to Redis is computed as the current value in the Python process plus the new value. This means that if another process modifies the same field between when you entered the pipeline and when it executes, your operation will override those changes. For truly atomic increments/decrements that respect concurrent modifications, consider using the lock context manager instead.

### Real-World Examples

#### User Score and Achievement System

```python
class GameUser(AtomicRedisModel):
    username: str
    total_score: int = 0
    level: int = 1
    achievements: List[str] = []
    stats: Dict[str, int] = {}

async def complete_level(user: GameUser, level_score: int, level_name: str):
    async with user.apipeline():
        # Update score and level
        user.total_score += level_score
        if user.total_score > user.level * 1000:
            user.level += 1
            user.achievements.append(f"Reached Level {user.level}")
        
        # Add level-specific achievement
        user.achievements.append(f"Completed {level_name}")
        
        # Update stats
        user.stats["levels_completed"] = user.stats.get("levels_completed", 0) + 1
        user.stats["last_level_score"] = level_score
```

#### Shopping Cart Operations

```python
class ShoppingCart(AtomicRedisModel):
    user_id: str
    items: List[str] = []
    quantities: Dict[str, int] = {}
    total_price: int = 0

async def add_items_to_cart(cart: ShoppingCart, items_with_prices: List[tuple]):
    async with cart.apipeline():
        for item_id, quantity, price_per_item in items_with_prices:
            # Add item to cart
            cart.items.append(item_id)
            
            # Set quantity
            cart.quantities[item_id] = cart.quantities.get(item_id, 0) + quantity
            
            # Update total price
            cart.total_price += price_per_item * quantity
```

#### User Profile Updates

```python
class UserProfile(AtomicRedisModel):
    username: str
    email: str
    preferences: Dict[str, str] = {}
    activity_log: List[str] = []
    last_login: str = ""

async def update_user_settings(profile: UserProfile, new_email: str, theme: str):
    async with profile.apipeline():
        # Update email
        old_email = profile.email
        profile.email = new_email
        
        # Update preferences
        profile.preferences["theme"] = theme
        profile.preferences["email_notifications"] = "enabled"
        
        # Log the activity
        profile.activity_log.append(f"Email changed from {old_email} to {new_email}")
        profile.activity_log.append(f"Theme changed to {theme}")
        
        # Update last login
        from datetime import datetime
        profile.last_login = datetime.now().isoformat()
```

### Error Handling

Pipeline operations are atomic - if any operation fails, all changes are rolled back:

```python
async def safe_user_update(user: User):
    try:
        async with user.apipeline():
            user.score += 100
            user.achievements.append("New Achievement")
            user.metadata["invalid_key"] = "some_value"  # This might fail

    except Exception as e:
        print(f"Update failed: {e}")
        # All changes are automatically rolled back
        # User state remains unchanged in Redis
```

### Advanced Usage with Error Recovery

```python
async def robust_cart_update(cart: ShoppingCart, items: List[dict]):
    max_retries = 3
    for attempt in range(max_retries):
        try:
            async with cart.apipeline():
                for item in items:
                    cart.items.append(item["id"])
                    cart.quantities[item["id"]] = item["quantity"]
                    cart.total_price += item["price"] * item["quantity"]

            print("Cart updated successfully")
            break

        except Exception as e:
            if attempt < max_retries - 1:
                print(f"Attempt {attempt + 1} failed, retrying...")
                await asyncio.sleep(0.1)  # Brief delay before retry
            else:
                print(f"All attempts failed: {e}")
                raise
```

## When to Use Pipeline Context Manager

**Perfect for:**
- Multiple related changes that should succeed or fail together
- Batch updates for performance
- Natural Python-like operations on lists and dictionaries
- User-facing operations where atomicity prevents data corruption

**Consider alternatives for:**
- Single field updates (use `field.asave()`)
- Complex conditional logic requiring current values (use lock context manager)
- Operations requiring complex Python logic or conditional branching

The pipeline context manager provides the most intuitive way to ensure your Redis operations are atomic while keeping your code clean and readable.

## Lock Context Manager

When you need atomic operations but require more complex Python logic or conditional operations, the lock context manager provides exclusive access to a model. The lock ensures that only one process can modify the model at a time, and it automatically updates the local model state to reflect the current values in Redis.

### How Lock Works

The lock context manager:

1. **Acquires an exclusive lock** on the model in Redis
2. **Refreshes the local model** with the latest data from Redis  
3. **Allows any Python operations** on the model
4. **Automatically saves changes** when the context exits
5. **Releases the lock** after saving

### Basic Lock Usage

```python
from rapyer import AtomicRedisModel


class BankAccount(AtomicRedisModel):
    balance: int = 0
    transaction_count: int = 0
    account_holder: str = ""


async def transfer_money(from_account_key: str, to_account_key: str, amount: int):
    # Lock both accounts to prevent race conditions
    async with BankAccount.alock_from_key(from_account_key, "transfer") as from_account:
        async with BankAccount.alock_from_key(to_account_key, "transfer") as to_account:
            # Models are automatically refreshed with latest Redis state
            if from_account.balance >= amount:
                # Pure Python operations - no async needed
                from_account.balance -= amount
                from_account.transaction_count += 1

                to_account.balance += amount
                to_account.transaction_count += 1

                return f"Transferred ${amount} successfully"
            else:
                return "Insufficient funds"
    # All changes are automatically saved when contexts exit
```

### Lock with Operation Names

You can specify operation names to allow multiple types of operations on the same model instance to run concurrently. The lock is specific to both the model instance and the operation name - different operation names can execute simultaneously, while the same operation name will be serialized.

**Important**: The lock is scoped to the specific model instance (by its key). Different model instances have completely separate locks and won't wait for each other, even if using the same operation name.

```python
class User(AtomicRedisModel):
    name: str
    email: str
    profile_views: int = 0
    last_login: str = ""
    settings: Dict[str, str] = {}

# These can run concurrently (different lock actions)
async def update_profile(user_key: str, new_name: str, new_email: str):
    async with User.alock_from_key(user_key, "profile_update") as user:
        # Model state refreshed from Redis
        user.name = new_name
        user.email = new_email

async def track_page_view(user_key: str):
    async with User.alock_from_key(user_key, "view_tracking") as user:
        # Independent operation with separate lock
        user.profile_views += 1
        
async def update_login_time(user_key: str):
    async with User.alock_from_key(user_key, "login_update") as user:
        from datetime import datetime
        user.last_login = datetime.now().isoformat()

# This would be serialized with other "profile_update" locks on the SAME user
async def another_profile_update(user_key: str):
    async with User.alock_from_key(user_key, "profile_update") as user:
        # Must wait for other "profile_update" operations on this specific user to complete
        user.settings["theme"] = "dark"
```

### Model Instance Lock Isolation

Each model instance has its own independent locks. Operations on different instances never interfere with each other:

```python
# These operations can ALL run concurrently, even with the same operation name
async def concurrent_example():
    import asyncio

    # All of these will run simultaneously - different model instances
    await asyncio.gather(
        User.alock_from_key("user:123", "profile_update"),  # User 123
        User.alock_from_key("user:456", "profile_update"),  # User 456  
        User.alock_from_key("user:789", "profile_update"),  # User 789
    )

    # But these would be serialized - same instance, same operation
    # Only one can run at a time for user:123 with "profile_update"
    async with User.alock_from_key("user:123", "profile_update") as user:
        user.name = "First Update"

    async with User.alock_from_key("user:123", "profile_update") as user:
        user.name = "Second Update"  # Waits for first to complete


# Different operation names on same instance - these CAN run concurrently
async def concurrent_operations_same_user():
    import asyncio

    user_key = "user:123"

    # These run simultaneously - same instance, different operations
    await asyncio.gather(
        update_profile(user_key, "New Name", "new@email.com"),  # "profile_update"
        track_page_view(user_key),  # "view_tracking"  
        update_login_time(user_key)  # "login_update"
    )
```

### Locking Existing Model Instances

You can also lock an existing model instance:

```python
async def update_user_safely(user: User):
    async with user.alock("settings_update") as locked_user:
        # locked_user has refreshed state from Redis
        locked_user.settings["last_updated"] = "2024-01-15"
        locked_user.settings["updated_by"] = "admin"
        # Changes saved automatically when context exits
```

### Complex Business Logic Example

The lock context manager is perfect for operations requiring conditional logic:

```python
class GameCharacter(AtomicRedisModel):
    name: str
    level: int = 1
    experience: int = 0
    health: int = 100
    inventory: List[str] = []
    skills: Dict[str, int] = {}

async def level_up_character(character_key: str, exp_gained: int):
    async with GameCharacter.alock_from_key(character_key, "level_up") as character:
        # Character state is refreshed from Redis
        character.experience += exp_gained
        
        # Complex conditional logic
        if character.experience >= character.level * 1000:
            old_level = character.level
            character.level += 1
            character.health = 100  # Full heal on level up
            
            # Give level-based rewards
            if character.level % 5 == 0:  # Every 5 levels
                character.inventory.append(f"legendary_item_level_{character.level}")
                
            # Update skills based on new level
            for skill in character.skills:
                if character.level > 10:
                    character.skills[skill] += 2
                else:
                    character.skills[skill] += 1
            
            return f"Leveled up from {old_level} to {character.level}!"
        else:
            needed_exp = (character.level * 1000) - character.experience
            return f"Need {needed_exp} more experience to level up"
```

### Error Handling with Locks

If an error occurs within the lock context, changes are not saved:

```python
async def safe_account_operation(account_key: str, amount: int):
    try:
        async with BankAccount.alock_from_key(account_key, "withdraw") as account:
            if account.balance < amount:
                raise ValueError("Insufficient funds")

            if amount > 10000:
                raise ValueError("Daily limit exceeded")

            account.balance -= amount
            account.transaction_count += 1

    except ValueError as e:
        print(f"Operation failed: {e}")
        # No changes saved to Redis - account state unchanged
        return False

    return True
```

## When to Use Pipeline vs Lock

| Feature | Pipeline | Lock |
|---------|----------|------|
| **Best for** | Batch operations, list/dict changes | Complex logic, conditional operations |
| **Python operations** | Limited to supported types | Any Python code |
| **Concurrency** | High performance batching | Exclusive access with action-based concurrency |
| **State refresh** | Automatic on entry | Automatic on entry |
| **Use when** | Multiple related changes | Need current values for decisions |

### Pipeline Example (Good for batch operations)

```python
async with user.apipeline():
    user.score += 100
    user.achievements.append("New Achievement")
    user.stats["games_played"] = user.stats.aget("games_played", 0) + 1
```

### Lock Example (Good for complex logic)

```python
async with user.alock("score_update") as locked_user:
    if locked_user.score >= 1000:
        locked_user.level += 1
        locked_user.achievements.append(f"Reached Level {locked_user.level}")
        if locked_user.level % 10 == 0:
            locked_user.inventory.append("special_reward")
    locked_user.score += 100
```

The lock context manager provides the flexibility to perform any Python operations while ensuring data consistency and preventing race conditions through exclusive access control.

## Global alock_from_key Function

In addition to the class method `Model.alock_from_key()`, Rapyer provides a global `rapyer.alock_from_key()` function that allows you to create locks without needing to know the specific model class. This is particularly useful when working with keys from different model types or when the model class is not available in the current context.

### Global Function Usage

```python
from rapyer import alock_from_key

async def generic_lock_operation(redis_key: str):
    # Lock any Redis key without knowing its model class
    async with alock_from_key(redis_key, "operation") as model:
        if model is not None:
            # Model exists - work with it
            # The model will be the correct type based on the key
            model.some_field = "updated value"
            # Changes saved automatically when context exits
        else:
            # Key doesn't exist in Redis
            print(f"No model found for key: {redis_key}")
```

### Key Differences from Class Method

The global `alock_from_key` function differs from the class method in a few important ways:

1. **Model Discovery**: Automatically determines the correct model type from the key
2. **Handles Missing Keys**: Returns `None` if the key doesn't exist (doesn't raise KeyNotFound)
3. **Type Flexibility**: Works with any AtomicRedisModel subclass

### Example: Cross-Model Operations

```python
from rapyer import alock_from_key

async def transfer_ownership(old_owner_key: str, new_owner_key: str, asset_key: str):
    # Lock multiple models of potentially different types
    async with alock_from_key(old_owner_key, "transfer") as old_owner:
        async with alock_from_key(new_owner_key, "transfer") as new_owner:
            async with alock_from_key(asset_key, "transfer") as asset:
                # Check all models exist
                if not all([old_owner, new_owner, asset]):
                    raise ValueError("One or more keys not found")
                
                # Perform transfer (models can be different types)
                if hasattr(asset, 'owner_id'):
                    asset.owner_id = new_owner.id
                
                if hasattr(old_owner, 'assets'):
                    old_owner.assets.remove(asset_key)
                
                if hasattr(new_owner, 'assets'):
                    new_owner.assets.append(asset_key)
```