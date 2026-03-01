from datetime import datetime
from typing import Optional

from rapyer import AtomicRedisModel
from rapyer.config import RedisConfig
from rapyer.fields import Index, Key


# Basic Index Models
class IndexTestModel(AtomicRedisModel):
    name: Index[str]
    age: Index[int]
    description: str


# Inheritance Models with Index
class BaseIndexModel(AtomicRedisModel):
    id: Index[str]
    created_at: Index[datetime]


class UserIndexModel(BaseIndexModel):
    username: Index[str]
    email: str


class ProductIndexModel(BaseIndexModel):
    name: Index[str]
    price: Index[float]


# Nested Models with Keys and Index
class AddressModel(AtomicRedisModel):
    street: Index[str]
    city: Index[str]


class PersonModel(AtomicRedisModel):
    name: Index[str]
    email: Key[str]
    address: AddressModel


# Nested Model with indexed parent field for testing
class ParentWithIndexModel(AtomicRedisModel):
    age: Index[int]
    occupation: Index[str]
    retirement_date: Index[datetime]


class ChildWithParentModel(AtomicRedisModel):
    name: Index[str]
    dad: ParentWithIndexModel
    birth_date: Index[datetime]


class UnsupportedIndexModel(AtomicRedisModel):
    name: str
    data: Index[set]

    Meta = RedisConfig(init_with_rapyer=False)


class UnsupportedGenericIndexModel(AtomicRedisModel):
    name: str
    tags: Index[list[str]]

    Meta = RedisConfig(init_with_rapyer=False)


class UnsupportedOptionalIndexModel(AtomicRedisModel):
    name: str
    count: Index[Optional[int]]

    Meta = RedisConfig(init_with_rapyer=False)
