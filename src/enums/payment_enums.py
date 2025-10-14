from enum import StrEnum


class PaymentStatus(StrEnum):
    SUCCESSFUL = "successful"
    PENDING = "pending"
    CANCELED = "canceled"
    REFUNDED = "refunded"
