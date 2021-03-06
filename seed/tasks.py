# !/usr/bin/env python
# encoding: utf-8
"""
:copyright (c) 2014 - 2018, The Regents of the University of California, through Lawrence Berkeley National Laboratory (subject to receipt of any required approvals from the U.S. Department of Energy) and contributors. All rights reserved.  # NOQA
:author
"""
from __future__ import absolute_import

import sys

from celery import chord, chain
from celery import shared_task
from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.mail import send_mail
from django.core.urlresolvers import reverse_lazy
from django.template import loader
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from seed.decorators import lock_and_track
from seed.landing.models import SEEDUser as User
from seed.lib.mcm.utils import batch
from seed.lib.superperms.orgs.models import Organization, OrganizationUser
from seed.models import (
    Property, PropertyState,
    TaxLot, TaxLotState
)
from seed.utils.cache import set_cache, increment_cache

logger = get_task_logger(__name__)


@shared_task
def invite_to_seed(domain, email_address, token, user_pk, first_name):
    """Send invitation email to newly created user.

    domain -- The domain name of the running seed instance
    email_address -- The address to send the invitation to
    token -- generated by Django's default_token_generator
    user_pk --primary key for this user record
    first_name -- First name of the new user

    Returns: nothing
    """
    signup_url = reverse_lazy('landing:signup', kwargs={
        'uidb64': urlsafe_base64_encode(force_bytes(user_pk)),
        'token': token
    })
    context = {
        'email': email_address,
        'domain': domain,
        'protocol': 'https',
        'first_name': first_name,
        'signup_url': signup_url
    }

    subject = 'New SEED account'
    email_body = loader.render_to_string(
        'seed/account_create_email.html',
        context
    )
    reset_email = settings.SERVER_EMAIL
    send_mail(subject, email_body, reset_email, [email_address])
    try:
        bcc_address = settings.SEED_ACCOUNT_CREATION_BCC
        new_subject = "{} ({})".format(subject, email_address)
        send_mail(new_subject, email_body, reset_email, [bcc_address])
    except AttributeError:
        pass


@shared_task
@lock_and_track
def delete_organization(org_pk, deleting_cache_key, chunk_size=100, *args, **kwargs):
    result = {
        'status': 'success',
        'progress': 0,
        'progress_key': deleting_cache_key
    }
    set_cache(deleting_cache_key, result['status'], result)

    chain(
        delete_organization_inventory.si(org_pk, deleting_cache_key),
        _delete_organization_related_data.si(org_pk, deleting_cache_key),
        _finish_delete.si(None, org_pk, deleting_cache_key)
    )()


@shared_task
@lock_and_track
def _delete_organization_related_data(org_pk, prog_key):
    # Get all org users
    user_ids = OrganizationUser.objects.filter(
        organization_id=org_pk).values_list('user_id', flat=True)
    users = list(User.objects.filter(pk__in=user_ids))

    Organization.objects.get(pk=org_pk).delete()

    # TODO: Delete measures in BRICR branch

    # Delete any abandoned users.
    for user in users:
        if not OrganizationUser.objects.filter(user_id=user.pk).exists():
            user.delete()

    result = {
        'status': 'success',
        'progress': 100,
        'progress_key': prog_key
    }
    set_cache(prog_key, result['status'], result)


@shared_task
def _finish_delete(results, org_pk, prog_key):
    result = {
        'status': 'success',
        'progress': 100,
        'progress_key': prog_key
    }

    # set recursion limits back to 1000
    sys.setrecursionlimit(1000)
    set_cache(prog_key, result['status'], result)


@shared_task
@lock_and_track
def delete_organization_inventory(org_pk, deleting_cache_key, chunk_size=100, *args, **kwargs):
    """Deletes all properties & taxlots within an organization."""
    sys.setrecursionlimit(5000)  # default is 1000

    result = {
        'status': 'success',
        'progress_key': deleting_cache_key,
        'progress': 0
    }

    property_ids = list(
        Property.objects.filter(organization_id=org_pk).values_list('id', flat=True)
    )
    property_state_ids = list(
        PropertyState.objects.filter(organization_id=org_pk).values_list('id', flat=True)
    )
    taxlot_ids = list(
        TaxLot.objects.filter(organization_id=org_pk).values_list('id', flat=True)
    )
    taxlot_state_ids = list(
        TaxLotState.objects.filter(organization_id=org_pk).values_list('id', flat=True)
    )

    total = len(property_ids) + len(property_state_ids) + len(taxlot_ids) + len(taxlot_state_ids)

    if total == 0:
        result['progress'] = 100

    set_cache(deleting_cache_key, result['status'], result)

    if total == 0:
        return

    step = float(chunk_size) / total
    tasks = []
    # we could also use .s instead of .subtask and not wrap the *args
    for del_ids in batch(property_ids, chunk_size):
        tasks.append(
            _delete_organization_property_chunk.subtask(
                (del_ids, deleting_cache_key, step, org_pk)
            )
        )
    for del_ids in batch(property_state_ids, chunk_size):
        tasks.append(
            _delete_organization_property_state_chunk.subtask(
                (del_ids, deleting_cache_key, step, org_pk)
            )
        )
    for del_ids in batch(taxlot_ids, chunk_size):
        tasks.append(
            _delete_organization_taxlot_chunk.subtask(
                (del_ids, deleting_cache_key, step, org_pk)
            )
        )
    for del_ids in batch(taxlot_state_ids, chunk_size):
        tasks.append(
            _delete_organization_taxlot_state_chunk.subtask(
                (del_ids, deleting_cache_key, step, org_pk)
            )
        )
    chord(tasks, interval=15)(
        _finish_delete.subtask([org_pk, deleting_cache_key]))


@shared_task
def _delete_organization_property_chunk(del_ids, prog_key, increment, org_pk, *args, **kwargs):
    """deletes a list of ``del_ids`` and increments the cache"""
    Property.objects.filter(organization_id=org_pk, pk__in=del_ids).delete()
    increment_cache(prog_key, increment * 100)


@shared_task
def _delete_organization_property_state_chunk(del_ids, prog_key, increment, org_pk, *args,
                                              **kwargs):
    """deletes a list of ``del_ids`` and increments the cache"""
    PropertyState.objects.filter(pk__in=del_ids).delete()
    increment_cache(prog_key, increment * 100)


@shared_task
def _delete_organization_taxlot_chunk(del_ids, prog_key, increment, org_pk, *args, **kwargs):
    """deletes a list of ``del_ids`` and increments the cache"""
    TaxLot.objects.filter(organization_id=org_pk, pk__in=del_ids).delete()
    increment_cache(prog_key, increment * 100)


@shared_task
def _delete_organization_taxlot_state_chunk(del_ids, prog_key, increment, org_pk, *args, **kwargs):
    """deletes a list of ``del_ids`` and increments the cache"""
    TaxLotState.objects.filter(organization_id=org_pk, pk__in=del_ids).delete()
    increment_cache(prog_key, increment * 100)
