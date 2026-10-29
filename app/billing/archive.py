"""Anonymous financial records survive self-service account deletion."""

from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.billing.models import ArchivedPayment, CardPayment, StarPayment


async def archive_user_payments(session: AsyncSession, user_id: UUID) -> None:
    # Match the callback lock order: payment first, then user.
    for model in (CardPayment, StarPayment):
        await session.execute(
            select(model.id).where(model.user_id == user_id).order_by(model.id).with_for_update()
        )
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    # Preserve amount/status/provider, but no name, email, invoice payload or URL.
    columns = [
        "id",
        "buyer_id",
        "provider",
        "reference",
        "product_code",
        "currency",
        "amount",
        "status",
        "occurred_at",
        "refunded_at",
        "is_test",
    ]
    from sqlalchemy import case, false, func, literal

    await session.execute(
        insert(ArchivedPayment).from_select(
            columns,
            select(
                CardPayment.id,
                CardPayment.user_id,
                CardPayment.provider,
                CardPayment.provider_payment_id,
                CardPayment.product_code,
                literal("RUB"),
                CardPayment.amount_kopecks,
                case((CardPayment.status == "succeeded", "paid"), else_=CardPayment.status),
                func.coalesce(CardPayment.paid_at, CardPayment.created_at),
                CardPayment.refunded_at,
                CardPayment.is_test,
            ).where(CardPayment.user_id == user_id),
        )
    )
    await session.execute(
        insert(ArchivedPayment).from_select(
            columns,
            select(
                StarPayment.id,
                StarPayment.user_id,
                literal("stars"),
                StarPayment.telegram_payment_charge_id,
                StarPayment.product_code,
                literal("XTR"),
                StarPayment.stars_amount,
                StarPayment.status,
                StarPayment.created_at,
                StarPayment.refunded_at,
                false(),
            ).where(StarPayment.user_id == user_id),
        )
    )
