from dataclasses import dataclass, field

REQUIRED_COLUMNS = ("transaction_id", "transaction_date", "amount", "currency")
CURRENCIES = ("GBP", "EUR", "USD")
MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_ROWS = 100_000
STATUSES = ("matched", "amount_mismatch", "missing_platform", "missing_internal", "blocked")
STATUS_LABELS = {
    "matched": "Matched", "amount_mismatch": "Amount mismatch",
    "missing_platform": "Missing from platform", "missing_internal": "Missing from internal",
    "blocked": "Blocked by data issues",
}
SOURCE_LABELS = {"internal": "Internal system", "platform": "Payment platform"}


class InputError(ValueError):
    """A whole file cannot be safely interpreted."""


@dataclass
class Record:
    source: str
    filename: str
    row_number: int
    raw: dict[str, str]
    transaction_id: str
    currency: str
    transaction_date: str
    amount_minor: int | None
    issues: list[tuple[str, str]] = field(default_factory=list)

    @property
    def key(self):
        return (self.transaction_id, self.currency) if self.transaction_id and self.currency else None

    @property
    def valid(self):
        return not self.issues


@dataclass
class Result:
    transaction_id: str
    currency: str
    status: str
    internal_rows: list[int]
    platform_rows: list[int]
    internal_amount_minor: int | None
    platform_amount_minor: int | None
    difference_minor: int | None
    reason: str
