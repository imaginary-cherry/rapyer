from rapyer import AtomicRedisModel

# Rapyer Functions

This page documents the global functions available in the rapyer package for working with Redis models.

## ainsert()

```python
async def ainsert(*models: AtomicRedisModel) -> list[AtomicRedisModel]
```

Performs bulk insertion of multiple Redis models in a single transaction, supporting models of different types.

### Description

The `ainsert()` function provides a global way to insert multiple Redis models in a single atomic transaction. Unlike the class-specific `ainsert()` method, this global function can handle models of different types in a single operation.

### Example

```python
import asyncio
import rapyer
from rapyer import AtomicRedisModel


class User(AtomicRedisModel):
    name: str
    age: int
    email: str


class Product(AtomicRedisModel):
    name: str
    price: float
    in_stock: bool


class Order(AtomicRedisModel):
    user_id: str
    product_id: str
    quantity: int


async def main():
    # Create instances of different model types
    user = User(name="Alice", age=30, email="alice@example.com")
    product1 = Product(name="Laptop", price=999.99, in_stock=True)
    product2 = Product(name="Mouse", price=29.99, in_stock=True)
    order = Order(user_id=user.key, product_id=product1.key, quantity=1)
    
    # Insert all models in a single transaction
    await rapyer.ainsert(user, product1, product2, order)
    print("All models inserted atomically")
    
    # Verify all models were saved
    saved_user = await User.aget(user.key)
    saved_product1 = await Product.aget(product1.key)
    saved_order = await Order.aget(order.key)
    
    print(f"User: {saved_user.name}")
    print(f"Product: {saved_product1.name}")
    print(f"Order quantity: {saved_order.quantity}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Performance Benefits

The global `ainsert()` function is particularly useful when:
- You need to insert multiple models of different types
- You want atomic guarantees across different model types
- You're initializing related data that spans multiple model classes
- You need optimal performance for bulk insertions

### Comparison with Class-Specific ainsert()

```python
async def comparison_example():
    users = [User(name=f"User{i}", age=20+i, email=f"user{i}@example.com") for i in range(3)]
    products = [Product(name=f"Product{i}", price=10.0*i, in_stock=True) for i in range(3)]
    
    # ❌ Less efficient: Multiple transactions
    await User.ainsert(*users)
    await Product.ainsert(*products)
    
    # ✅ More efficient: Single transaction for all models
    await rapyer.ainsert(*users, *products)
```

## adelete_many()

```python
async def adelete_many(*args: str | AtomicRedisModel) -> ModuleDeleteResult
```

Deletes multiple models of different types in a single pipeline. Unlike the class method `Model.adelete_many()`, this global function works across model types and tracks deletions per model class.

### Parameters

- **args** (`str | AtomicRedisModel`): Redis keys (must include the class prefix, e.g. `"User:123"`) or model instances

### Returns

- **ModuleDeleteResult**: Contains:
    - `count` (`int`): Total number of deleted models
    - `by_model` (`dict`): Deletion count per model class

### Raises

- **TypeError**: If no arguments are provided
- **RapyerModelDoesntExistError**: If a key refers to an unregistered model class

### Example

```python
import rapyer
from rapyer import AtomicRedisModel


class User(AtomicRedisModel):
    name: str

class Order(AtomicRedisModel):
    total: float


async def main():
    user = User(name="Alice")
    order = Order(total=99.99)
    await rapyer.ainsert(user, order)

    # Delete models of different types in one call
    result = await rapyer.adelete_many(user, order)
    print(result.count)     # 2
    print(result.by_model)  # {"User": 1, "Order": 1}

    # Delete by keys
    result = await rapyer.adelete_many("User:abc123", "Order:def456")
```

## aget()

```python
async def aget(redis_key: str) -> AtomicRedisModel
```

Retrieves a model instance from Redis by its key, automatically determining the correct model class.

### Parameters

- **redis_key** (`str`): The Redis key of the model instance to retrieve

### Returns

- **AtomicRedisModel**: The model instance corresponding to the Redis key

### Raises

- **KeyError**: If the model class cannot be determined from the key
- **ValueError**: If the key format is invalid
- **CantSerializeRedisValueError**: If the value in Redis cannot be deserialized (Corruption or missing resources)

### Description

The `aget()` function provides a global way to retrieve any model instance from Redis without knowing its specific class beforehand. It works by:

1. Extracting the class name from the Redis key format (`ClassName:instance_id`)
2. Looking up the appropriate model class from the registered Redis models
3. Calling the class-specific `aget()` method to retrieve and deserialize the instance

This is particularly useful when you have multiple model types and want a unified retrieval mechanism, or when working with keys of unknown model types.

### Example

```python
import asyncio
import rapyer
from rapyer import AtomicRedisModel


class User(AtomicRedisModel):
    name: str
    age: int
    email: str


class Product(AtomicRedisModel):
    name: str
    price: float
    in_stock: bool


async def main():
    # Create and save different model types
    user = User(name="Alice", age=30, email="alice@example.com")
    product = Product(name="Laptop", price=999.99, in_stock=True)

    await user.asave()
    await product.asave()

    # Retrieve using global aget function
    retrieved_user = await rapyer.aget(user.key)
    retrieved_product = await rapyer.aget(product.key)

    print(f"User: {retrieved_user.name}, Age: {retrieved_user.age}")
    print(f"Product: {retrieved_product.name}, Price: {retrieved_product.price}")

    # The function automatically returns the correct model type
    print(f"User type: {type(retrieved_user).__name__}")
    print(f"Product type: {type(retrieved_product).__name__}")


if __name__ == "__main__":
    asyncio.run(main())
```

## apipeline()

```python
async def apipeline(ignore_redis_error: bool = False)
```

Creates a pipeline context manager for batching Redis operations across multiple models.

### Parameters

- **ignore_redis_error** (`bool`, optional): If True, suppresses `ResponseError` exceptions during pipeline execution. Default is False.

### Description

The global `rapyer.apipeline()` function creates a Redis pipeline that batches all operations performed within its context into a single atomic transaction. Unlike the model-specific `model.apipeline()`, this global function:

- Works without a specific model instance
- Allows saving multiple models of different types in a single transaction
- Supports nested pipelines (each pipeline commits independently when exiting)

All `asave()` calls and field modifications within the pipeline are queued and executed together when the context exits.

### Example

```python
import rapyer
from rapyer import AtomicRedisModel


class User(AtomicRedisModel):
    name: str
    balance: int = 0


class Order(AtomicRedisModel):
    user_id: str
    total: float


async def create_order_with_user(name: str, order_total: float):
    user = User(name=name, balance=100)
    order = Order(user_id=user.key, total=order_total)

    # Both models saved in a single atomic transaction
    async with rapyer.apipeline():
        await user.asave()
        await order.asave()
```

### Nested Pipelines

Pipelines can be nested. Each pipeline commits its changes when its context exits:

```python
async def nested_example():
    user = User(name="Alice", balance=100)
    order = Order(user_id=user.key, total=50.0)
    await user.asave()
    await order.asave()

    async with user.apipeline() as u:
        u.balance -= 50

        async with order.apipeline() as o:
            o.total = 75.0
        # Order changes committed here

    # User changes committed here
```

## alock_from_key()

```python
async def alock_from_key(
    key: str, action: str = "default", save_at_end: bool = False
) -> AbstractAsyncContextManager[AtomicRedisModel | None]
```

Creates a lock context manager for any Redis model by its key, without needing to know the specific model class.

### Parameters

- **key** (`str`): The Redis key of the model to lock
- **action** (`str`, optional): The operation name for the lock. Default is "default". Different operation names allow concurrent execution on the same model instance
- **save_at_end** (`bool`, optional): If True, automatically saves the model when the context exits. Default is False

### Description

The global `alock_from_key()` function provides a way to create locks on Redis models without knowing their specific class. This is particularly useful when:

1. Working with keys from different or unknown model types
2. Building generic utilities that operate on any model
3. The model class is not imported in the current module
4. You need graceful handling of non-existent keys

Unlike the class-specific `Model.alock_from_key()` method, this global function:
- Automatically discovers the correct model type from the key
- Returns `None` if the key doesn't exist (instead of raising KeyNotFound)
- Works with any AtomicRedisModel subclass

### Example

```python
import asyncio
import rapyer
from rapyer import AtomicRedisModel, alock_from_key


class User(AtomicRedisModel):
    name: str
    balance: int = 0


class Product(AtomicRedisModel):
    name: str
    stock: int = 0


async def generic_update(key: str, operation: str):
    # Works with any model type
    async with alock_from_key(key, operation, save_at_end=True) as model:
        if model is None:
            print(f"Key not found: {key}")
            return
        
        # Check what type of model we're working with
        if hasattr(model, 'balance'):
            model.balance += 100
            print(f"Updated balance for {model.name}")
        elif hasattr(model, 'stock'):
            model.stock -= 1
            print(f"Reduced stock for {model.name}")
        # Model is automatically saved when context exits due to save_at_end=True


async def cross_model_transaction(user_key: str, product_key: str):
    # Lock multiple models of different types
    async with alock_from_key(user_key, "purchase") as user:
        async with alock_from_key(product_key, "purchase") as product:
            if not user or not product:
                raise ValueError("User or product not found")
            
            # Both models are locked and can be modified atomically
            if user.balance >= 50 and product.stock > 0:
                user.balance -= 50
                product.stock -= 1
                print(f"{user.name} purchased {product.name}")
            else:
                print("Insufficient balance or out of stock")
            # Changes are saved when contexts exit


async def main():
    # Create and save models
    user = User(name="Alice", balance=100)
    product = Product(name="Book", stock=10)
    await user.asave()
    await product.asave()
    
    # Use generic update function with different model types
    await generic_update(user.key, "credit")
    await generic_update(product.key, "restock")
    
    # Perform cross-model transaction
    await cross_model_transaction(user.key, product.key)
    
    # Try with non-existent key
    await generic_update("NonExistentModel:12345", "test")


if __name__ == "__main__":
    asyncio.run(main())
```

### Comparison with Class Method

| Feature | `rapyer.alock_from_key()` (Global) | `Model.alock_from_key()` (Class Method) |
|---------|-------------------------------------|------------------------------------------|
| Model type knowledge | Not required | Required |
| Non-existent keys | Returns None | Raises KeyNotFound |
| Type hints | Generic AtomicRedisModel | Specific model type |
| Use case | Generic utilities, unknown types | Type-safe operations |

## find_redis_models()

```python
def find_redis_models() -> list[type[AtomicRedisModel]]
```

Returns a list of all registered Redis model classes.

### Parameters

None

### Returns

- **list[type[AtomicRedisModel]]**: A list containing all model classes that inherit from `AtomicRedisModel`

### Description

The `find_redis_models()` function provides access to all Redis model classes that have been defined and registered in the application.

## afind()

```python
async def afind(*redis_keys: str) -> list[AtomicRedisModel]
```

Retrieves multiple models of different types by their keys in a single bulk operation.

### Parameters

- **redis_keys** (`str`): Variable number of Redis keys to retrieve (e.g., `"UserModel:123"`, `"OrderModel:456"`)

### Returns

- **list[AtomicRedisModel]**: A list of model instances in the same order as the input keys

### Raises

- **KeyNotFound**: If any of the specified keys is missing in Redis
- **RapyerModelDoesntExist**: If a key refers to an unregistered model class (the class name prefix doesn't match any known model)

### Description

The global `rapyer.afind()` function provides a way to retrieve multiple models of heterogeneous types in a single bulk operation. Unlike the class-specific `Model.afind()` method (which retrieves all instances of one model type), this function:

1. Accepts explicit Redis keys as arguments
2. Supports fetching different model types in one call
3. Automatically refreshes TTL for models with `refresh_ttl` enabled
4. Raises errors for missing keys or unknown model types

This is particularly useful when you need to fetch related models of different types in a single efficient operation.

### Example

```python
import asyncio
import rapyer
from rapyer import AtomicRedisModel


class User(AtomicRedisModel):
    name: str
    email: str


class Order(AtomicRedisModel):
    user_id: str
    total: float


class Product(AtomicRedisModel):
    name: str
    price: float


async def main():
    # Create and save models of different types
    user = User(name="Alice", email="alice@example.com")
    order = Order(user_id=user.key, total=150.00)
    product = Product(name="Laptop", price=999.99)

    await rapyer.ainsert(user, order, product)

    # Retrieve multiple models of different types in one call
    models = await rapyer.afind(user.key, order.key, product.key)

    print(f"Retrieved {len(models)} models:")
    for model in models:
        print(f"  - {type(model).__name__}: {model.key}")

    # Models are returned in the same order as keys
    retrieved_user, retrieved_order, retrieved_product = models
    print(f"User: {retrieved_user.name}")
    print(f"Order total: ${retrieved_order.total}")
    print(f"Product: {retrieved_product.name}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Error Handling

```python
from rapyer.errors import KeyNotFound, RapyerModelDoesntExistError


async def safe_fetch():
  try:
    models = await rapyer.afind("User:123", "Order:456")
  except KeyNotFound as e:
    print(f"Key not found: {e}")
  except RapyerModelDoesntExistError as e:
    print(f"Unknown model type: {e}")
```

## Model.afind() (Class Method)

```python
@classmethod
async def afind(cls, *args) -> list[AtomicRedisModel]
```

Retrieves all instances of a specific model class from Redis.

### Parameters

- **args**: Optional. Can be:
    - **Empty**: Returns all instances of the model
    - **Keys** (`str`): One or more Redis keys to retrieve specific models
    - **Expressions** (`Expression`): Filter conditions for indexed fields

### Returns

- **list[AtomicRedisModel]**: A list of model instances in the order corresponding to the input keys (when keys are provided)

### Raises

- **KeyNotFound**: If any specified key is missing in Redis (only when keys are provided)
- **CantSerializeRedisValueError**: If a value cannot be deserialized

### Description

The `afind()` class method retrieves instances of a model class from Redis with three modes:

1. **No arguments**: Retrieves all instances matching the model's key pattern
2. **With keys**: Retrieves specific instances by their Redis keys (full key or just primary key)
3. **With expressions**: Filters instances using indexed field conditions

When passing keys, the method raises `KeyNotFound` if any key is missing.

### Note

The `Model.afind()` method only returns instances of the specific model class it's called on. To retrieve models of different types by their keys, use the global `rapyer.afind()` function instead.
