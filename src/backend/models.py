import datetime
from enum import Enum
from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship
import sqlalchemy as sa
import uuid

class AccountType(str, Enum):
    CHECKING = "checking"
    SAVINGS = "savings"
    CREDIT = "credit"
    INVESTMENT = "investment"

class MatchField(str, Enum):
    RAW_PAYEE = "raw_payee"
    AMOUNT = "amount"
    NOTES = "notes"

class MatchType(str, Enum):
    CONTAINS = "contains"
    EXACT = "exact"
    STARTS_WITH = "starts_with"

class AmountCondition(str, Enum):
    ANY = "any"
    INCOME = "income"   # amount_cents > 0
    EXPENSE = "expense" # amount_cents < 0

# ----------------------------------------------------------------------
# Account Entity
# ----------------------------------------------------------------------
class Account(SQLModel, table=True):
    __tablename__ = "accounts"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    type: AccountType
    currency: str = Field(default="USD", max_length=3)
    opening_balance_cents: int = Field(default=0)
    opening_date: datetime.date
    is_closed: bool = Field(default=False, index=True)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    transactions: List["Transaction"] = Relationship(back_populates="account")

# ----------------------------------------------------------------------
# Category Group & Category Entities
# ----------------------------------------------------------------------
class CategoryGroup(SQLModel, table=True):
    __tablename__ = "category_groups"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    display_order: int = Field(default=0)

    categories: List["Category"] = Relationship(back_populates="group")

class Category(SQLModel, table=True):
    __tablename__ = "categories"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    group_id: uuid.UUID = Field(foreign_key="category_groups.id", index=True)
    name: str = Field(index=True)
    is_income: bool = Field(default=False)
    is_fixed: bool = Field(default=False)
    is_archived: bool = Field(default=False, index=True)

    group: Optional[CategoryGroup] = Relationship(back_populates="categories")
    splits: List["TransactionSplit"] = Relationship(back_populates="category")

# ----------------------------------------------------------------------
# Transaction & Transaction Split Entities
# ----------------------------------------------------------------------
class Transaction(SQLModel, table=True):
    __tablename__ = "transactions"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    account_id: uuid.UUID = Field(foreign_key="accounts.id", index=True)
    date: datetime.date = Field(index=True)
    raw_payee: str = Field(index=True)
    normalized_payee: Optional[str] = Field(default=None, index=True)
    amount_cents: int = Field(index=True)  # Negative for expenses, positive for income
    notes: Optional[str] = Field(default=None)
    cleared: bool = Field(default=True)
    import_hash: Optional[str] = Field(default=None, unique=True, index=True)
    is_ml_suggested: bool = Field(default=False)
    ml_confidence: Optional[float] = Field(default=None)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

    account: Optional[Account] = Relationship(back_populates="transactions")
    splits: List["TransactionSplit"] = Relationship(back_populates="transaction", sa_relationship_kwargs={"cascade": "all, delete-orphan"})

class TransactionSplit(SQLModel, table=True):
    __tablename__ = "transaction_splits"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    transaction_id: uuid.UUID = Field(foreign_key="transactions.id", index=True)
    category_id: Optional[uuid.UUID] = Field(default=None, foreign_key="categories.id", index=True)
    amount_cents: int  # Must sum up to parent transaction.amount_cents
    notes: Optional[str] = Field(default=None)

    transaction: Optional[Transaction] = Relationship(back_populates="splits")
    category: Optional[Category] = Relationship(back_populates="splits")

# ----------------------------------------------------------------------
# Monthly Budget Entity
# ----------------------------------------------------------------------
class MonthlyBudget(SQLModel, table=True):
    __tablename__ = "monthly_budgets"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    month: str = Field(index=True, max_length=7)  # Format: YYYY-MM
    category_id: uuid.UUID = Field(foreign_key="categories.id", index=True)
    budgeted_cents: int = Field(default=0)
    carryover_enabled: bool = Field(default=False)

# ----------------------------------------------------------------------
# Automation & Rule Entity
# ----------------------------------------------------------------------
class Rule(SQLModel, table=True):
    __tablename__ = "rules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    priority: int = Field(default=0, index=True)
    match_field: MatchField = Field(default=MatchField.RAW_PAYEE, sa_column=sa.Column(sa.String, default="raw_payee"))
    match_type: MatchType = Field(default=MatchType.CONTAINS, sa_column=sa.Column(sa.String, default="contains"))
    match_value: str
    amount_condition: AmountCondition = Field(default=AmountCondition.ANY, sa_column=sa.Column(sa.String, default="any"))
    secondary_match_field: Optional[MatchField] = Field(default=None, sa_column=sa.Column(sa.String, nullable=True))
    secondary_match_type: Optional[MatchType] = Field(default=None, sa_column=sa.Column(sa.String, nullable=True))
    secondary_match_value: Optional[str] = Field(default=None)
    target_payee: Optional[str] = Field(default=None)
    target_category_id: Optional[uuid.UUID] = Field(default=None, foreign_key="categories.id")
    is_active: bool = Field(default=True, index=True)

# ----------------------------------------------------------------------
# Saved Query Entity
# ----------------------------------------------------------------------
class SavedQuery(SQLModel, table=True):
    __tablename__ = "saved_queries"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(unique=True, index=True)
    description: Optional[str] = Field(default=None)
    query_ast: str  # JSON string of AST structure
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    updated_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)

