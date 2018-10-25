"""
gargoyle.builtins
~~~~~~~~~~~~~~~~~

:copyright: (c) 2010 DISQUS.
:license: Apache License 2.0, see LICENSE for more details.
"""
from __future__ import absolute_import, division, print_function, unicode_literals

import socket
import struct
from datetime import datetime

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.validators import validate_ipv4_address
from django.utils import timezone

from gargoyle import gargoyle
from gargoyle.constants import FEATURE
from gargoyle.conditions import (
    BeforeDate, Boolean, ConditionSet, ModelConditionSet, OnOrAfterDate, Percent, RequestConditionSet, String,
)

User = get_user_model()


class UserConditionSet(ModelConditionSet):
    username = String()
    email = String()
    is_anonymous = Boolean(label='Anonymous')
    is_active = Boolean(label='Active')
    is_staff = Boolean(label='Staff')
    is_superuser = Boolean(label='Superuser')
    date_joined = OnOrAfterDate(label='Joined on or after')

    def can_execute(self, instance):
        return isinstance(instance, (User, AnonymousUser))

    def is_active(self, instance, conditions, switch_type=FEATURE):
        """
        If is AnonymousUser we only check the value of the switch.
        Otherwise we call the parent's `is_active` method to validate the 'is_anonymous' field.
        """
        if isinstance(instance, AnonymousUser):
            conditions = conditions.get(self.get_namespace(), {}).get('is_anonymous', [])
            for condition in conditions:
                value = condition[1]
                if condition:
                    return bool(value)
            return None

        return super(UserConditionSet, self).is_active(instance, conditions, switch_type)



gargoyle.register(UserConditionSet(User))


class IPAddress(String):
    def clean(self, value):
        validate_ipv4_address(value)
        return value


@gargoyle.register
class IPAddressConditionSet(RequestConditionSet):
    percent = Percent()
    ip_address = IPAddress(label='IP Address')
    internal_ip = Boolean(label='Internal IPs')

    def get_namespace(self):
        return 'ip'

    def get_field_value(self, instance, field_name):
        # XXX: can we come up w/ a better API?
        # Ensure we map ``percent`` to the ``id`` column
        if field_name == 'percent':
            return self._ip_to_int(instance.META['REMOTE_ADDR'])
        elif field_name == 'ip_address':
            return instance.META['REMOTE_ADDR']
        elif field_name == 'internal_ip':
            return instance.META['REMOTE_ADDR'] in settings.INTERNAL_IPS
        return super(IPAddressConditionSet, self).get_field_value(instance, field_name)

    def _ip_to_int(self, ip):
        if '.' in ip:
            # IPv4
            return sum([int(x) for x in ip.split('.')])
        if ':' in ip:
            # IPv6
            hi, lo = struct.unpack('!QQ', socket.inet_pton(socket.AF_INET6, ip))
            return (hi << 64) | lo
        raise ValueError('Invalid IP Address %r' % ip)

    def get_group_label(self):
        return 'IP Address'


@gargoyle.register
class HostConditionSet(ConditionSet):
    hostname = String()

    def get_namespace(self):
        return 'host'

    def can_execute(self, instance):
        return instance is None

    def get_field_value(self, instance, field_name):
        if field_name == 'hostname':
            return socket.gethostname()

    def get_group_label(self):
        return 'Host'


@gargoyle.register
class UTCTodayConditionSet(ConditionSet):
    """
    Checks conditions against current time in UTC
    """
    today_is_on_or_after = OnOrAfterDate('in UTC on or after')
    today_is_before = BeforeDate('in UTC before')

    def get_namespace(self):
        return 'now_utc'

    def can_execute(self, instance):
        return instance is None

    def get_field_value(self, instance, field_name):
        return datetime.utcnow()

    def get_group_label(self):
        return 'Today'


@gargoyle.register
class AppTodayConditionSet(ConditionSet):
    """
    Checks conditions against current app timezone time or
    against current server time if Django timezone support disabled (USE_TZ=False)
    """
    today_is_on_or_after = OnOrAfterDate('in default timezone on or after')
    today_is_before = BeforeDate('in default timezone before')

    def get_namespace(self):
        return 'now_app_tz'

    def can_execute(self, instance):
        return instance is None

    def get_field_value(self, instance, field_name):
        now_dt = timezone.now()
        if timezone.is_aware(now_dt):
            now_dt = timezone.make_naive(now_dt, timezone.get_default_timezone())
        return now_dt

    def get_group_label(self):
        return 'Today'


@gargoyle.register
class ActiveTimezoneTodayConditionSet(ConditionSet):
    """
    Checks conditions against current time of active timezone or
    against current server time if Django timezone support disabled (USE_TZ=False)
    """
    today_is_on_or_after = OnOrAfterDate('in active timezone on or after')
    today_is_before = BeforeDate('in active timezone before')

    def get_namespace(self):
        return 'now_active_tz'

    def can_execute(self, instance):
        return instance is None

    def get_field_value(self, instance, field_name):
        now_dt = timezone.now()
        if timezone.is_aware(now_dt):
            now_dt = timezone.make_naive(now_dt)
        return now_dt

    def get_group_label(self):
        return 'Today'
