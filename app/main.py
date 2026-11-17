from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func

from app.db import SessionLocal, init_db
from app.models import Expense

app = FastAPI(title="Expenses Dashboard")
templates = Jinja2Templates(directory="app/templates")

init_db()


@app.get("/api/expenses")
def list_expenses(days: int = 7):
    """JSON: траты за последние N дней."""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(Expense)
            .filter(Expense.created_at >= since)
            .order_by(Expense.created_at.desc())
            .all()
        )
        return [
            {
                "id": r.id,
                "amount": r.amount,
                "description": r.description,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]
    finally:
        db.close()


@app.get("/api/stats")
def stats(days: int = 7):
    """JSON: сумма по дням за последние N дней (для графика)."""
    db = SessionLocal()
    try:
        since = datetime.utcnow() - timedelta(days=days)
        rows = (
            db.query(
                func.date(Expense.created_at).label("day"),
                func.sum(Expense.amount).label("total"),
            )
            .filter(Expense.created_at >= since)
            .group_by("day")
            .order_by("day")
            .all()
        )
        return [{"day": str(r.day), "total": float(r.total)} for r in rows]
    finally:
        db.close()


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")