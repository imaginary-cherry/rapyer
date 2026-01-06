from typing import Any

from pydantic import TypeAdapter

from rapyer.errors import BadFilterError
from rapyer.types.base import REDIS_DUMP_FLAG_NAME
from rapyer.typing_support import Unpack


class Expression:
    def create_filter(self) -> str:
        raise NotImplementedError(  # pragma: no cover
            "Subclasses must implement create_filter"  # pragma: no cover
        )  # pragma: no cover

    def __and__(self, other: "Expression") -> "AndExpression":
        return AndExpression(self, other)

    def __or__(self, other: "Expression") -> "OrExpression":
        return OrExpression(self, other)

    def __invert__(self) -> "NotExpression":
        return NotExpression(self)


class AtomicField(Expression):
    def __init__(self, field_name: str, **sub_fields: Unpack[Expression]):
        self.field_name = field_name
        for sub_field_name, sub_field in sub_fields.items():
            setattr(self, sub_field_name, sub_field)


class ExpressionField(Expression):
    def __init__(self, field_name: str, field_type: Any = None):
        self.field_name = field_name
        self._adapter = TypeAdapter(field_type)

    def create_filter(self) -> str:
        raise BadFilterError(
            "You must use an operator to filter an expression in redis"
        )

    def serialize_value(self, value: Any) -> Any:
        return self._adapter.dump_python(
            value, mode="json", context={REDIS_DUMP_FLAG_NAME: True}
        )

    def __eq__(self, value: Any) -> "EqExpression":
        return EqExpression(self, value)

    def __ne__(self, value: Any) -> "NeExpression":
        return NeExpression(self, value)

    def __gt__(self, value: Any) -> "GtExpression":
        return GtExpression(self, value)

    def __lt__(self, value: Any) -> "LtExpression":
        return LtExpression(self, value)

    def __ge__(self, value: Any) -> "GteExpression":
        return GteExpression(self, value)

    def __le__(self, value: Any) -> "LteExpression":
        return LteExpression(self, value)


class EqExpression(Expression):
    def __init__(self, left: ExpressionField, right: Any):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # Serialize the value using the field's TypeAdapter
        serialized_value = self.left.serialize_value(self.right)

        # For string fields, wrap in quotes if needed
        if isinstance(self.right, str):
            # Escape special characters in the string
            escaped_value = (
                self.right.replace('"', '\\"').replace("\\", "\\\\").replace("/", "\\/")
            )
            return f'@{self.left.field_name}:"{escaped_value}"'
        # For numeric fields, use range syntax for exact match
        return f"@{self.left.field_name}:[{serialized_value} {serialized_value}]"


class NeExpression(Expression):
    def __init__(self, left: ExpressionField, right: Any):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # Serialize the value using the field's TypeAdapter
        serialized_value = self.left.serialize_value(self.right)

        # For not equal, we need to use different syntax
        if isinstance(self.right, str):
            escaped_value = (
                self.right.replace('"', '\\"').replace("\\", "\\\\").replace("/", "\\/")
            )
            return f'-@{self.left.field_name}:"{escaped_value}"'
        # For numeric fields, use range syntax for exact match
        return f"-@{self.left.field_name}:[{serialized_value} {serialized_value}]"


class GtExpression(Expression):
    def __init__(self, left: ExpressionField, right: Any):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # Serialize the value using the field's TypeAdapter
        serialized_value = self.left.serialize_value(self.right)
        return f"@{self.left.field_name}:[({serialized_value} +inf]"


class LtExpression(Expression):
    def __init__(self, left: ExpressionField, right: Any):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # Serialize the value using the field's TypeAdapter
        serialized_value = self.left.serialize_value(self.right)
        return f"@{self.left.field_name}:[-inf ({serialized_value}]"


class GteExpression(Expression):
    def __init__(self, left: ExpressionField, right: Any):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # Serialize the value using the field's TypeAdapter
        serialized_value = self.left.serialize_value(self.right)
        return f"@{self.left.field_name}:[{serialized_value} +inf]"


class LteExpression(Expression):
    def __init__(self, left: ExpressionField, right: Any):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # Serialize the value using the field's TypeAdapter
        serialized_value = self.left.serialize_value(self.right)
        return f"@{self.left.field_name}:[-inf {serialized_value}]"


class AndExpression(Expression):
    def __init__(self, left: Expression, right: Expression):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # In Redis Search, AND is implicit with space
        left_filter = self.left.create_filter()
        right_filter = self.right.create_filter()
        return f"({left_filter}) ({right_filter})"


class OrExpression(Expression):
    def __init__(self, left: Expression, right: Expression):
        self.left = left
        self.right = right

    def create_filter(self) -> str:
        # In Redis Search, OR needs pipe operator
        left_filter = self.left.create_filter()
        right_filter = self.right.create_filter()
        return f"({left_filter})|({right_filter})"


class NotExpression(Expression):
    def __init__(self, expression: Expression):
        self.expression = expression

    def create_filter(self) -> str:
        # NOT operator in Redis Search
        inner_filter = self.expression.create_filter()
        return f"-{inner_filter}"
