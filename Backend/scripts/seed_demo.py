"""Deterministic demo-data seeder for the intelligence layer (Phase 2A.6).

Populates the Phase-2A entities — users (reps), customers, items, leads (with
full stage history), sales activities, customer targets, and invoices +
payments — with distributions tuned so the scoring engines (Phase 2B) have
something to work with across every band.

**Deterministic:** a fixed RNG seed (42) and a single ``today`` snapshot mean
two runs against a fresh DB produce identical data (UUIDs included — they are
drawn from the seeded RNG, not ``uuid4``).

**Guarded:** refuses to run if any ``leads`` row already exists, unless
``--force`` is passed (which only *adds*, never deletes). Reads the same
``.env`` as the app, so point it only at a dev database.

Run from ``Backend/``::

    python scripts/seed_demo.py            # or: uv run python scripts/seed_demo.py
    python scripts/seed_demo.py --force    # add another batch on top

Note (scope): SHIPPED sales orders / dispatch history are **not** seeded here.
That data is produced through the Phase-1 PO-receive-into-lots → SO-ship flow
and is added alongside the customer-health engine in Phase 2B, where it is
actually consumed. Everything Phase 2A owns is seeded.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
import uuid
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

# Make ``app`` importable when run as a standalone script (src layout).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings
from app.core.security import hash_password
from app.models.customer import CompetitiveRiskLevel, Customer, CustomerType
from app.models.customer_target import CustomerTarget
from app.models.invoice import Invoice, Payment
from app.models.item import Item, ItemType
from app.models.lead import (
    DealerPotential,
    Lead,
    LeadSource,
    LeadStage,
    LeadStageHistory,
)
from app.models.sales_activity import ActivityType, SalesActivity
from app.models.user import User

RNG = random.Random(42)
TODAY = date.today()

STATES = {"Odisha": ["Jajpur", "Cuttack", "Khordha"], "Jharkhand": ["Ranchi", "Dhanbad", "Bokaro"]}
# Lead-stage mix → counts sum to 200.
STAGE_MIX = (
    [LeadStage.NEW] * 50
    + [LeadStage.QUALIFICATION] * 40
    + [LeadStage.NEGOTIATION] * 30
    + [LeadStage.WON] * 50
    + [LeadStage.LOST] * 30
)


def new_id() -> uuid.UUID:
    """A deterministic UUID drawn from the seeded RNG."""
    return uuid.UUID(int=RNG.getrandbits(128))


def dt_days_ago(days: int) -> datetime:
    """A timezone-aware datetime ``days`` before now (noon, for stability)."""
    return datetime.combine(TODAY - timedelta(days=days), time(12, 0), tzinfo=UTC)


def build_users() -> list[User]:
    admin = User(
        id=new_id(),
        email="admin@demo.local",
        full_name="Demo Admin",
        hashed_password=hash_password("demo-pass-admin"),
        is_active=True,
        is_admin=True,
    )
    reps = [
        User(
            id=new_id(),
            email=f"rep{i}@demo.local",
            full_name=f"Sales Rep {i}",
            hashed_password=hash_password(f"demo-pass-{i}"),
            is_active=True,
            is_admin=False,
        )
        for i in range(8)
    ]
    return [admin, *reps]


def build_items(actor: uuid.UUID) -> list[Item]:
    items: list[Item] = []
    for i in range(25):
        unit_price = Decimal(RNG.randrange(100, 2000))
        # 80% carry a cost spread across the margin bands; 20% leave it NULL.
        if i % 5 == 0:
            standard_cost = None
        else:
            margin_pct = RNG.choice([5, 8, 15, 20, 30, 40])  # <10 / 10-24 / >=25
            standard_cost = (unit_price * (Decimal(100 - margin_pct) / Decimal(100))).quantize(
                Decimal("0.01")
            )
        is_raw = i % 2 == 0
        items.append(
            Item(
                id=new_id(),
                sku=f"DEMO-{i:03d}",
                name=f"Demo {'Material' if is_raw else 'Product'} {i}",
                type=ItemType.RAW if is_raw else ItemType.FINISHED,
                category="Cement" if is_raw else "Finished Goods",
                unit_of_measure=RNG.choice(["kg", "ton", "bag", "pcs"]),
                unit_price=unit_price,
                standard_cost=standard_cost,
                created_by_user_id=actor,
                updated_by_user_id=actor,
            )
        )
    return items


def build_customers(actor: uuid.UUID) -> list[Customer]:
    types = (
        [CustomerType.DEALER] * 18 + [CustomerType.SUB_DEALER] * 18 + [CustomerType.RETAILER] * 24
    )
    risks = (
        [CompetitiveRiskLevel.NONE] * 42
        + [CompetitiveRiskLevel.LOW] * 9
        + [CompetitiveRiskLevel.MEDIUM] * 6
        + [CompetitiveRiskLevel.HIGH] * 3
    )
    RNG.shuffle(types)
    RNG.shuffle(risks)
    customers: list[Customer] = []
    for i in range(60):
        # Concentrate the first 14 customers in one district (dense cluster).
        if i < 14:
            state, district = "Odisha", "Jajpur"
        else:
            state = RNG.choice(list(STATES))
            district = RNG.choice(STATES[state])
        customers.append(
            Customer(
                id=new_id(),
                company_name=f"Demo Customer {i:02d}",
                contact_person=f"Contact {i:02d}",
                phone=f"+91 90000 {i:05d}",
                customer_type=types[i],
                competitive_risk_level=risks[i],
                state=state,
                district=district,
                city=district,
                pincode=f"7{i:05d}"[:6],
                created_by_user_id=actor,
                updated_by_user_id=actor,
            )
        )
    return customers


def build_targets(actor: uuid.UUID, customers: list[Customer]) -> list[CustomerTarget]:
    """One target per customer for each of the two most recent quarters."""
    targets: list[CustomerTarget] = []
    quarters = [(date(2026, 1, 1), date(2026, 4, 1)), (date(2026, 4, 1), date(2026, 7, 1))]
    for cust in customers:
        for start, end in quarters:
            targets.append(
                CustomerTarget(
                    id=new_id(),
                    customer_id=cust.id,
                    period_start=start,
                    period_end=end,
                    target_quantity=Decimal(RNG.randrange(500, 5000)),
                    target_revenue=Decimal(RNG.randrange(1_000_000, 9_000_000)),
                    created_by_user_id=actor,
                    updated_by_user_id=actor,
                )
            )
    return targets


def build_leads(
    actor: uuid.UUID, reps: list[User], customers: list[Customer], items: list[Item]
) -> tuple[list[Lead], list[LeadStageHistory]]:
    leads: list[Lead] = []
    history: list[LeadStageHistory] = []
    stages = STAGE_MIX[:]
    RNG.shuffle(stages)
    for i, stage in enumerate(stages):
        rep = reps[i % len(reps)]
        created = dt_days_ago(RNG.randrange(1, 180))
        sparse = i % 7 == 0  # ~15% sparse leads → exercise scoring defaults
        item = None if sparse else RNG.choice(items)
        cust = RNG.choice(customers) if i % 3 == 0 else None
        lead = Lead(
            id=new_id(),
            lead_number=f"LD-SEED-{i:06d}",
            stage=stage,
            contact_name=f"Lead Contact {i:03d}",
            source=RNG.choice(list(LeadSource)),
            assigned_to_user_id=rep.id,
            customer_id=cust.id if cust else None,
            item_id=item.id if item else None,
            quantity=None if sparse else Decimal(RNG.randrange(5, 200)),
            estimated_budget=None if sparse else Decimal(RNG.randrange(50_000, 3_000_000)),
            dealer_potential=None if sparse else RNG.choice(list(DealerPotential)),
            required_by_date=None if sparse else TODAY + timedelta(days=RNG.randrange(-5, 90)),
            state=None if sparse else (cust.state if cust else "Odisha"),
            district=None if sparse else (cust.district if cust else "Jajpur"),
            created_by_user_id=actor,
            updated_by_user_id=actor,
            created_at=created,
        )
        # Build a stage-history chain consistent with the final stage.
        path: list[LeadStage] = [LeadStage.NEW]
        if stage == LeadStage.QUALIFICATION:
            path += [LeadStage.QUALIFICATION]
        elif stage == LeadStage.NEGOTIATION:
            path += [LeadStage.QUALIFICATION, LeadStage.NEGOTIATION]
        elif stage == LeadStage.WON:
            path += [LeadStage.QUALIFICATION, LeadStage.NEGOTIATION, LeadStage.WON]
        elif stage == LeadStage.LOST:
            path += [LeadStage.LOST]
        if stage == LeadStage.WON:
            lead.won_at = created + timedelta(days=len(path))
            lead.won_value = Decimal(RNG.randrange(100_000, 4_000_000))
        elif stage == LeadStage.LOST:
            lead.lost_at = created + timedelta(days=len(path))
            lead.lost_reason = RNG.choice(["Budget cut", "Lost to competitor", "No response"])

        prev: LeadStage | None = None
        for step, to_stage in enumerate(path):
            history.append(
                LeadStageHistory(
                    id=new_id(),
                    lead_id=lead.id,
                    from_stage=prev,
                    to_stage=to_stage,
                    changed_at=created + timedelta(days=step),
                    changed_by_user_id=actor,
                )
            )
            prev = to_stage
        leads.append(lead)
    return leads, history


def build_activities(
    actor: uuid.UUID, reps: list[User], customers: list[Customer]
) -> list[SalesActivity]:
    activities: list[SalesActivity] = []
    # Spread "most recent visit" across the visit-gap bands.
    recency_bands = [5, 20, 35, 60]
    for idx, cust in enumerate(customers):
        # rep[7] is the deliberate near-zero performer.
        rep = reps[7] if idx % 30 == 0 else reps[idx % 7]
        count = 1 if rep is reps[7] else RNG.randrange(8, 36)
        most_recent = recency_bands[idx % len(recency_bands)]
        for n in range(count):
            days_ago = most_recent if n == 0 else most_recent + RNG.randrange(1, 110)
            atype = RNG.choices(
                [ActivityType.VISIT, ActivityType.CALL, ActivityType.MEETING,
                 ActivityType.FOLLOW_UP, ActivityType.COMPLAINT],
                weights=[40, 25, 15, 15, 5],
            )[0]
            activities.append(
                SalesActivity(
                    id=new_id(),
                    type=atype,
                    rep_user_id=rep.id,
                    customer_id=cust.id,
                    occurred_at=dt_days_ago(days_ago),
                    duration_minutes=RNG.randrange(15, 120),
                    created_by_user_id=actor,
                    updated_by_user_id=actor,
                )
            )
    return activities


def build_invoices(
    actor: uuid.UUID, customers: list[Customer]
) -> tuple[list[Invoice], list[Payment]]:
    invoices: list[Invoice] = []
    payments: list[Payment] = []
    for idx, cust in enumerate(customers):
        if idx % 10 >= 7:  # ~70% of customers get invoices
            continue
        for n in range(RNG.randrange(1, 4)):
            inv_days_ago = RNG.randrange(10, 150)
            invoice_date = TODAY - timedelta(days=inv_days_ago)
            amount = Decimal(RNG.randrange(50_000, 800_000))
            inv = Invoice(
                id=new_id(),
                invoice_number=f"INV-SEED-{idx:03d}-{n}",
                customer_id=cust.id,
                invoice_date=invoice_date,
                due_date=invoice_date + timedelta(days=30),
                amount=amount,
                created_by_user_id=actor,
                updated_by_user_id=actor,
            )
            invoices.append(inv)
            bucket = idx % 5
            if bucket == 0:
                # Unpaid + overdue (invoice well in the past).
                pass
            elif bucket == 1:
                # Partially paid.
                payments.append(
                    Payment(
                        id=new_id(),
                        invoice_id=inv.id,
                        paid_date=invoice_date + timedelta(days=RNG.randrange(10, 40)),
                        amount=(amount / 2).quantize(Decimal("0.01")),
                        created_by_user_id=actor,
                        updated_by_user_id=actor,
                    )
                )
            else:
                # Fully paid, DSO spread across the bands.
                dso = RNG.choice([20, 38, 55, 80])
                payments.append(
                    Payment(
                        id=new_id(),
                        invoice_id=inv.id,
                        paid_date=invoice_date + timedelta(days=dso),
                        amount=amount,
                        created_by_user_id=actor,
                        updated_by_user_id=actor,
                    )
                )
    return invoices, payments


async def _assert_coverage(session: AsyncSession) -> None:
    """Structural acceptance — every Phase-2A entity is populated with variety.

    (Score-bucket coverage — HOT/MEDIUM/COLD, health classes, etc. — is
    asserted in Phase 2B once the engines + recompute endpoint exist.)
    """
    lead_count = await session.scalar(select(func.count()).select_from(Lead))
    stages = set((await session.execute(select(Lead.stage).distinct())).scalars().all())
    types = set((await session.execute(select(SalesActivity.type).distinct())).scalars().all())
    cust_type_rows = await session.execute(select(Customer.customer_type).distinct())
    cust_types = set(cust_type_rows.scalars().all())
    null_cost = await session.scalar(
        select(func.count()).select_from(Item).where(Item.standard_cost.is_(None))
    )
    inv_count = await session.scalar(select(func.count()).select_from(Invoice))
    pay_count = await session.scalar(select(func.count()).select_from(Payment))

    problems: list[str] = []
    if lead_count == 0:
        problems.append("no leads")
    if len(stages) < 5:
        problems.append(f"only {len(stages)}/5 lead stages present")
    if len(types) < 5:
        problems.append(f"only {len(types)}/5 activity types present")
    if len(cust_types) < 3:
        problems.append(f"only {len(cust_types)}/3 customer types present")
    if not null_cost:
        problems.append("no items with NULL standard_cost (default path uncovered)")
    if not inv_count or not pay_count:
        problems.append("invoices/payments not populated")
    if problems:
        raise SystemExit("Seed acceptance FAILED: " + "; ".join(problems))

    print(
        f"  leads={lead_count} (stages={len(stages)}/5)  "
        f"activity_types={len(types)}/5  customer_types={len(cust_types)}/3  "
        f"items_null_cost={null_cost}  invoices={inv_count}  payments={pay_count}"
    )


async def seed(*, force: bool) -> None:
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=False)
    try:
        async with AsyncSession(engine) as session:
            existing = await session.scalar(select(func.count()).select_from(Lead))
            if existing and not force:
                print(
                    f"Refusing to seed: {existing} lead(s) already exist. "
                    "Pass --force to add another batch."
                )
                return

            users = build_users()
            admin = users[0]
            reps = users[1:]
            session.add_all(users)
            await session.flush()

            items = build_items(admin.id)
            customers = build_customers(admin.id)
            session.add_all(items)
            session.add_all(customers)
            await session.flush()

            targets = build_targets(admin.id, customers)
            leads, history = build_leads(admin.id, reps, customers, items)
            activities = build_activities(admin.id, reps, customers)
            invoices, payments = build_invoices(admin.id, customers)

            session.add_all(targets)
            session.add_all(leads)
            await session.flush()
            session.add_all(history)
            session.add_all(activities)
            session.add_all(invoices)
            await session.flush()
            session.add_all(payments)

            await session.commit()

            print("Seed complete:")
            print(
                f"  users={len(users)} items={len(items)} customers={len(customers)} "
                f"targets={len(targets)} leads={len(leads)} history={len(history)} "
                f"activities={len(activities)} invoices={len(invoices)} payments={len(payments)}"
            )
            await _assert_coverage(session)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic demo data.")
    parser.add_argument(
        "--force", action="store_true", help="Add a batch even if leads already exist."
    )
    args = parser.parse_args()
    asyncio.run(seed(force=args.force))


if __name__ == "__main__":
    main()
