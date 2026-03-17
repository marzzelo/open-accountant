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
    last_movements: list[MovementOut] = []
    monthly_history: list[MonthlyBar] = []


# ── Transactions ──────────────────────────────────────────────────────────────


class TransactionIn(BaseModel):
    debit_account: int
    credit_account: int
    amount: Optional[float] = Field(None, gt=0)
    original_amount: Optional[float] = Field(None, gt=0)
    original_currency: Optional[str] = None
    fx_source: Optional[str] = None
    description: str = ""
    date: Optional[str] = None  # ISO datetime; default = now()

    @model_validator(mode="after")
    def validate_amounts(self):
        if self.amount is None and self.original_amount is None:
            raise ValueError("Either amount or original_amount is required")
        return self


class TransactionUpdate(BaseModel):
    amount: Optional[float] = Field(None, gt=0)
    original_amount: Optional[float] = Field(None, gt=0)
    original_currency: Optional[str] = None
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
    monthly_cashflow: list[dict]  # {month, ingresos, gastos, neto}
    expenses_by_subtype: list[dict]  # {subtype, amount}
    income_by_subtype: list[dict]  # {subtype, amount}
    asset_composition: list[dict]  # {account, balance}
    top_accounts: list[dict]  # {account, volume, tx_count}
    balance_evolution: list[dict]  # {month, account_id, account_name, balance}
