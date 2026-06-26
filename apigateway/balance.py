from django.db import transaction
from django.db.models import F
from django.utils import timezone
from billing.models import Transaction, UserPackage
from users.models import User
from .models import ApiRequestRecord


@transaction.atomic
def deduct_balance(user, amount, description, api_model=None, tokens_consumed=0):
    user = User.objects.select_for_update().get(pk=user.pk)

    pkg = UserPackage.objects.filter(
        user=user, status='active'
    ).select_related('package').order_by('-created_at').first()

    if pkg and pkg.end_date and pkg.end_date < timezone.now():
        pkg.status = 'expired'
        pkg.save(update_fields=['status'])
        pkg = None

    if pkg:
        model_ok = True
        if pkg.package and pkg.package.model_restrict and api_model:
            model_ok = api_model.id in pkg.package.model_ids

        calls_ok = True
        if pkg.package and pkg.package.call_limit > 0:
            calls_ok = pkg.calls_used < pkg.package.call_limit

        tokens_ok = True
        if pkg.package and pkg.package.token_limit > 0 and tokens_consumed > 0:
            tokens_ok = (pkg.tokens_used + tokens_consumed) <= pkg.package.token_limit

        if model_ok and calls_ok and tokens_ok:
            pkg = UserPackage.objects.select_for_update().get(pk=pkg.pk)
            pkg.calls_used = F('calls_used') + 1
            if tokens_consumed > 0:
                pkg.tokens_used = F('tokens_used') + tokens_consumed
            pkg.save(update_fields=['calls_used'] if tokens_consumed == 0 else ['calls_used', 'tokens_used'])
            pkg.refresh_from_db()

            if pkg.package and pkg.package.call_limit > 0 and pkg.calls_used >= pkg.package.call_limit:
                pkg.status = 'used_up'
                pkg.save(update_fields=['status'])
            elif pkg.package and pkg.package.token_limit > 0 and pkg.tokens_used >= pkg.package.token_limit:
                pkg.status = 'used_up'
                pkg.save(update_fields=['status'])

        return True, user.balance

    if user.balance < amount:
        return False, user.balance

    user.balance = F('balance') - amount
    user.save(update_fields=['balance'])
    user.refresh_from_db()
    Transaction.objects.create(
        user=user, type='consume', amount=-amount,
        balance_after=user.balance, description=description,
    )
    return True, user.balance


@transaction.atomic
def credit_balance(user, amount, description, related_order=''):
    user = User.objects.select_for_update().get(pk=user.pk)
    user.balance = F('balance') + amount
    user.save(update_fields=['balance'])
    user.refresh_from_db()
    Transaction.objects.create(
        user=user, type='recharge', amount=amount,
        balance_after=user.balance, description=description,
        related_order=related_order,
    )
    return user.balance
