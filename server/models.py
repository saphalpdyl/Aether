"""Pydantic models for request/response validation."""
from typing import Literal
from pydantic import BaseModel


class RouterCreate(BaseModel):
    router_name: str
    giaddr: str
    bng_id: str | None = None


class RouterUpdate(BaseModel):
    giaddr: str | None = None
    bng_id: str | None = None


class PlanCreate(BaseModel):
    name: str
    download_speed: int
    upload_speed: int
    price: float
    is_active: bool = True


class PlanUpdate(BaseModel):
    name: str | None = None
    download_speed: int | None = None
    upload_speed: int | None = None
    price: float | None = None
    is_active: bool | None = None


class CustomerCreate(BaseModel):
    name: str
    email: str | None = None
    phone: str | None = None
    street: str | None = None
    city: str | None = None
    zip_code: str | None = None
    state: str | None = None


class CustomerUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    street: str | None = None
    city: str | None = None
    zip_code: str | None = None
    state: str | None = None


class ServiceCreate(BaseModel):
    customer_id: int
    plan_id: int
    circuit_id: str
    remote_id: str
    relay_id: str | None = None
    status: Literal["ACTIVE", "SUSPENDED", "TERMINATED"] = "ACTIVE"


class ServiceUpdate(BaseModel):
    customer_id: int | None = None
    plan_id: int | None = None
    circuit_id: str | None = None
    remote_id: str | None = None
    relay_id: str | None = None
    status: Literal["ACTIVE", "SUSPENDED", "TERMINATED"] | None = None
