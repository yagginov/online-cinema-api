from enum import StrEnum


class PaymentSortByEnum(StrEnum):
    CREATED_AT = "created_at"
    AMOUNT = "amount"


class PaymentStatus(StrEnum):
    SUCCESSFUL = "successful"
    PENDING = "pending"
    CANCELED = "canceled"
    REFUNDED = "refunded"
