import stripe
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import crud, models

stripe.api_key = settings.stripe_secret_key


PLAN_LIMITS = {
    models.PlanType.free: {"emails_per_month": 200, "smart_replies": 50, "autopilot": False, "calendar_sync": False},
    models.PlanType.pro: {"emails_per_month": 5000, "smart_replies": -1, "autopilot": True, "calendar_sync": True},
    models.PlanType.team: {"emails_per_month": 5000, "smart_replies": -1, "autopilot": True, "calendar_sync": True},
}


def get_plan_limits(plan: models.PlanType) -> dict:
    return PLAN_LIMITS.get(plan, PLAN_LIMITS[models.PlanType.free])


async def create_checkout_session(db: AsyncSession, user_id: str, price_id: str, mode: str = "subscription") -> str:
    user = await crud.get_user(db, user_id)
    if not user:
        raise ValueError("User not found")

    customer_id = None
    sub = await crud.get_active_subscription(db, user_id)
    if sub and sub.stripe_customer_id:
        customer_id = sub.stripe_customer_id
    else:
        customer = stripe.Customer.create(email=user.email, metadata={"user_id": str(user.id)})
        customer_id = customer.id

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": price_id, "quantity": 1}],
        mode=mode,
        success_url=f"{settings.frontend_url}/billing?success=1",
        cancel_url=f"{settings.frontend_url}/billing?canceled=1",
        metadata={"user_id": str(user.id)},
        allow_promotion_codes=True,
    )
    return session.url


async def create_portal_session(db: AsyncSession, user_id: str) -> str:
    sub = await crud.get_active_subscription(db, user_id)
    if not sub or not sub.stripe_customer_id:
        raise ValueError("No Stripe customer found")
    session = stripe.billing_portal.Session.create(
        customer=sub.stripe_customer_id,
        return_url=f"{settings.frontend_url}/billing",
    )
    return session.url


async def handle_webhook(payload: bytes, sig_header: str, db: AsyncSession) -> dict:
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as e:
        raise ValueError(f"Webhook signature verification failed: {e}")

    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        await _handle_checkout_completed(db, session)
    elif event["type"] == "customer.subscription.updated":
        subscription = event["data"]["object"]
        await _handle_subscription_updated(db, subscription)
    elif event["type"] == "customer.subscription.deleted":
        subscription = event["data"]["object"]
        await _handle_subscription_deleted(db, subscription)
    elif event["type"] == "invoice.payment_failed":
        invoice = event["data"]["object"]
        await _handle_payment_failed(db, invoice)

    return {"received": True}


async def _handle_checkout_completed(db: AsyncSession, session: dict) -> None:
    user_id = session.get("metadata", {}).get("user_id")
    if not user_id:
        return

    customer_id = session.get("customer")
    subscription_id = session.get("subscription")
    if not subscription_id:
        return

    sub = stripe.Subscription.retrieve(subscription_id)
    price_id = sub["items"]["data"][0]["price"]["id"]
    plan = _price_to_plan(price_id)

    await crud.upsert_subscription(
        db,
        user_id,
        plan=plan,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=models.SubscriptionStatus.active,
        current_period_end=sub["current_period_end"],
    )


async def _handle_subscription_updated(db: AsyncSession, subscription: dict) -> None:
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")
    price_id = subscription["items"]["data"][0]["price"]["id"]
    plan = _price_to_plan(price_id)
    status = _stripe_status_to_our(subscription.get("status"))
    current_period_end = subscription.get("current_period_end")

    await crud.upsert_subscription(
        db,
        None,
        plan=plan,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription_id,
        status=status,
        current_period_end=current_period_end,
    )


async def _handle_subscription_deleted(db: AsyncSession, subscription: dict) -> None:
    customer_id = subscription.get("customer")
    await crud.upsert_subscription(
        db,
        None,
        plan=models.PlanType.free,
        stripe_customer_id=customer_id,
        stripe_subscription_id=subscription.get("id"),
        status=models.SubscriptionStatus.canceled,
        current_period_end=None,
    )


async def _handle_payment_failed(db: AsyncSession, invoice: dict) -> None:
    customer_id = invoice.get("customer")
    await crud.upsert_subscription(
        db,
        None,
        plan=models.PlanType.free,
        stripe_customer_id=customer_id,
        stripe_subscription_id=invoice.get("subscription"),
        status=models.SubscriptionStatus.past_due,
        current_period_end=None,
    )


def _price_to_plan(price_id: str) -> models.PlanType:
    if price_id == settings.stripe_price_pro:
        return models.PlanType.pro
    elif price_id == settings.stripe_price_team:
        return models.PlanType.team
    return models.PlanType.free


def _stripe_status_to_our(status: str) -> models.SubscriptionStatus:
    mapping = {
        "active": models.SubscriptionStatus.active,
        "trialing": models.SubscriptionStatus.trialing,
        "past_due": models.SubscriptionStatus.past_due,
        "canceled": models.SubscriptionStatus.canceled,
        "incomplete": models.SubscriptionStatus.incomplete,
    }
    return mapping.get(status, models.SubscriptionStatus.incomplete)


async def check_email_limit(db: AsyncSession, user_id: str) -> tuple[bool, dict]:
    sub = await crud.get_active_subscription(db, user_id)
    plan = sub.plan if sub else models.PlanType.free
    limits = get_plan_limits(plan)

    if limits["emails_per_month"] == -1:
        return True, {"limit": -1, "used": 0, "remaining": -1}

    from datetime import datetime, timedelta, timezone
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    used = await crud.count_emails_processed_this_month(db, user_id, start)
    remaining = max(0, limits["emails_per_month"] - used)

    return remaining > 0, {"limit": limits["emails_per_month"], "used": used, "remaining": remaining}


async def check_feature_access(db: AsyncSession, user_id: str, feature: str) -> bool:
    sub = await crud.get_active_subscription(db, user_id)
    plan = sub.plan if sub else models.PlanType.free
    limits = get_plan_limits(plan)
    return limits.get(feature, False)