from enum import StrEnum


class PaymentStatus(StrEnum):
    SUCCESSFUL = "successful"
    CANCELED = "canceled"
    REFUNDED = "refunded"
