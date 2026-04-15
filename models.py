"""
models.py — Pydantic v2 request/response schemas.
"""

from typing import Optional

from pydantic import BaseModel, Field, model_validator


# ── Types ─────────────────────────────────────────────────────────────────────


class TypeOut(BaseModel):
    id: int
    name: str


# ── Subtypes ──────────────────────────────────────────────────────────────────


class SubtypeIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    type_id: int


class SubtypeUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    type_id: Optional[int] = None


class SubtypeOut(BaseModel):
    id: int
    name: str
    type_id: int
    type_name: str


# ── Accounts ──────────────────────────────────────────────────────────────────


class AccountIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type_id: int
    subtype_id: Optional[int] = None
    description: str = ""
    initial_balance: float = 0.0
    properties: str = "{}"


class AccountUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    subtype_id: Optional[int] = None
    description: Optional[str] = None
    initial_balance: Optional[float] = None
    properties: Optional[str] = None


class MovementOut(BaseModel):
    id: int
    date: str
    description: str
    amount: float
    role: str  # "debit" | "credit"
    counterpart: str  # name of the other account


class MonthlyBar(BaseModel):
    month: str  # "YYYY-MM"
    net: float  # net change for that month


class AccountOut(BaseModel):
    id: int
    name: str
    type_id: int
    type_name: str
    subtype_id: Optional[int]
    subtype_name: Optional[str]
    description: str
    initial_balance: float
    balance: float
    properties: dict = Field(default_factory=dict)
    last_movements: list[MovementOut] = []
    monthly_history: list[MonthlyBar] = []


class UserOut(BaseModel):
    id: int
    username: str
    is_admin: bool
    is_active: bool
    created_at: str


class LoginIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=255)
    remember_me: bool = False


class SessionOut(BaseModel):
    authenticated: bool
    user: Optional[UserOut] = None
    expires_at: Optional[str] = None
    remember_me: bool = False
    requires_setup: bool = False
    message: Optional[str] = None


class UserCreateIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=255)
    is_admin: bool = False


class UserUpdateIn(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    is_admin: bool = False


class UserPasswordUpdateIn(BaseModel):
    password: str = Field(..., min_length=8, max_length=255)


class UserStatusUpdateIn(BaseModel):
    is_active: bool


# ── Tags ─────────────────────────────────────────────────────────────────────


class TagSummary(BaseModel):
    id: int
    name: str
    color: str


class TagIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    color: str = Field("#3B82F6", pattern=r"^#[0-9A-Fa-f]{6}$")
    user_id: Optional[str] = Field(None, max_length=100)


class TagUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=60)
    color: Optional[str] = Field(None, pattern=r"^#[0-9A-Fa-f]{6}$")
    user_id: Optional[str] = Field(None, max_length=100)


class TagOut(TagSummary):
    user_id: Optional[str] = None
    created_at: str
    updated_at: str
    transaction_count: int = 0


# ── Transactions ──────────────────────────────────────────────────────────────


class TransactionIn(BaseModel):
    debit_account: int
    credit_account: int
    tag_ids: list[int] = Field(default_factory=list)
    amount: Optional[float] = Field(None, gt=0)
    original_amount: Optional[float] = Field(None, gt=0)
    original_currency: Optional[str] = None
    fx_rate: Optional[float] = Field(None, gt=0)
    fx_source: Optional[str] = None
    description: str = ""
    date: Optional[str] = None  # ISO datetime; default = now()

    @model_validator(mode="after")
    def validate_amounts(self):
        if self.amount is None and self.original_amount is None:
            raise ValueError("Either amount or original_amount is required")
        return self


class TransactionUpdate(BaseModel):
    debit_account: Optional[int] = Field(None, gt=0)
    credit_account: Optional[int] = Field(None, gt=0)
    tag_ids: Optional[list[int]] = None
    amount: Optional[float] = Field(None, gt=0)
    original_amount: Optional[float] = Field(None, gt=0)
    original_currency: Optional[str] = None
    fx_rate: Optional[float] = Field(None, gt=0)
    fx_source: Optional[str] = None
    description: Optional[str] = None
    date: Optional[str] = None


class TransactionOut(BaseModel):
    id: int
    debit_account: int
    debit_name: str
    debit_type_id: int
    credit_account: int
    credit_name: str
    credit_type_id: int
    amount: float
    original_amount: float
    original_currency: str
    fx_rate: float
    fx_source: Optional[str]
    description: str
    date: str
    created_at: str
    tags: list[TagSummary] = Field(default_factory=list)


# ── Reports ───────────────────────────────────────────────────────────────────


class BalanceLineItem(BaseModel):
    account_id: int
    account_name: str
    balance: float


class BalanceSubgroup(BaseModel):
    subtype_name: str
    items: list[BalanceLineItem]
    subtotal: float


class BalanceGroup(BaseModel):
    type_name: str
    type_id: int
    subgroups: list[BalanceSubgroup]
    total: float


class BalanceSheet(BaseModel):
    period_from: str
    period_to: str
    groups: list[BalanceGroup]
    total_activo: float
    total_pasivo: float
    total_patrimonio: float
    total_ingreso: float
    total_gasto: float
    resultado: float  # Ingresos - Gastos
    equation_check: float  # Activo - (Pasivo + Patrimonio + Resultado) ≈ 0


class StatsData(BaseModel):
    summary: dict  # {total_income, total_expense, net_result, savings_rate, ...}
    monthly_cashflow: list[dict]  # {month, ingresos, gastos, neto}
    expenses_by_subtype: list[dict]  # {subtype, amount}
    income_by_subtype: list[dict]  # {subtype, amount}
    asset_composition: list[dict]  # {account, balance}
    top_accounts: list[dict]  # {account, volume, tx_count}
    balance_evolution: list[dict]  # {month, account_id, account_name, subtype_name, balance}
    net_worth_evolution: list[dict]  # {month, assets, liabilities, net_worth}


# ── Projections ────────────────────────────────────────────────────────────────


class ProjectionSeriesIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern=r"^(income|expense)$")
    start_date: str  # "YYYY-MM-DD"
    months: int = Field(..., ge=1)
    monthly_amount: float = Field(..., gt=0)


class ProjectionSeriesUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    type: Optional[str] = Field(None, pattern=r"^(income|expense)$")
    start_date: Optional[str] = None
    months: Optional[int] = Field(None, ge=1)
    monthly_amount: Optional[float] = Field(None, gt=0)


class ProjectionSeriesOut(BaseModel):
    id: int
    name: str
    type: str
    start_date: str
    months: int
    monthly_amount: float
    created_at: str
