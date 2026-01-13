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
@classmethod
async def afind(cls) -> list[AtomicRedisModel]
```

Retrieves all instances of a specific model class from Redis.

### Parameters

None

### Returns

- **list[AtomicRedisModel]**: A list containing all instances of the model class stored in Redis

### Raises

- **CantSerializeRedisValueError**: If a value in Redis cannot be deserialized (Corruption or missing resources)

### Description

The `afind()` method is a class method that retrieves all instances of a particular model class from Redis. It works by:

1. Finding all Redis keys that match the model's key pattern using `afind_keys()`
2. Performing a batch retrieval of all matching records using Redis JSON's `mget` operation
3. Deserializing each record back into the appropriate model instance

This method is efficient for retrieving multiple instances as it uses Redis's bulk operations rather than individual get operations.

### Example

```python
import asyncio
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
    # Create and save multiple users
    users = [
        User(name="Alice", age=30, email="alice@example.com"),
        User(name="Bob", age=25, email="bob@example.com"),
        User(name="Charlie", age=35, email="charlie@example.com")
    ]

    products = [
        Product(name="Laptop", price=999.99, in_stock=True),
        Product(name="Mouse", price=29.99, in_stock=False)
    ]

    # Save all instances
    for user in users:
        await user.asave()
    for product in products:
        await product.asave()

    # Find all users and products
    all_users = await User.afind()
    all_products = await Product.afind()

    print(f"Found {len(all_users)} users:")
    for user in all_users:
        print(f"  - {user.name} ({user.age})")

    print(f"Found {len(all_products)} products:")
    for product in all_products:
        print(f"  - {product.name}: ${product.price}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Note

The `afind()` method only returns instances of the specific model class it's called on. To find all instances across different model types, you would need to call `afind()` on each model class separately.
