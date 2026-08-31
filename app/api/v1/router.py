"""Aggregate all v1 routers under a single APIRouter."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, business, customers, ml, statements, transactions, verification

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(customers.router)
api_router.include_router(statements.router)
api_router.include_router(transactions.router)
api_router.include_router(verification.router)
api_router.include_router(business.router)
api_router.include_router(ml.router)
