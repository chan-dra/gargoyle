from __future__ import absolute_import, division, print_function, unicode_literals

import datetime
import socket

import pytz
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, TestCase
from django.test.utils import override_settings
from django.utils import timezone
from freezegun import freeze_time

from gargoyle.builtins import (
    ActiveTimezoneTodayConditionSet, AppTodayConditionSet, ConditionSet, HostConditionSet, IPAddressConditionSet,
    UserConditionSet, UTCTodayConditionSet,
)
from gargoyle.conditions import Field
from gargoyle.constants import AB_TEST, FEATURE, INCLUDE
from gargoyle.manager import SwitchManager
from gargoyle.models import SELECTIVE, Switch


class IPAddressConditionSetTests(TestCase):
    condition_set = 'gargoyle.builtins.IPAddressConditionSet'

    def setUp(self):
        super(IPAddressConditionSetTests, self).setUp()
        self.gargoyle = SwitchManager(Switch, key='key', value='value', instances=True, auto_create=True)
        self.gargoyle.register(IPAddressConditionSet())
        self.request_factory = RequestFactory()

        Switch.objects.create(key='test', status=SELECTIVE)
        self.switch = self.gargoyle['test']
        assert not self.gargoyle.is_active('test')

    def test_percent(self):
        self.switch.add_condition(
            condition_set=self.condition_set,
            field_name='percent',
            condition='0-100',
        )

        request = self.request_factory.get('/', REMOTE_ADDR='1.0.0.0')
        assert self.gargoyle.is_active('test', request)

    def test_0_percent(self):
        self.switch.add_condition(
            condition_set=self.condition_set,
            field_name='percent',
            condition='0-0',
        )

        request = self.request_factory.get('/', REMOTE_ADDR='1.0.0.0')
        assert not self.gargoyle.is_active('test', request)

    def test_specific_address(self):
        self.switch.add_condition(
            condition_set=self.condition_set,
            field_name='ip_address',
            condition='1.1.1.1',
        )

        request = self.request_factory.get('/', REMOTE_ADDR='1.0.0.0')
        assert not self.gargoyle.is_active('test', request)

        request = self.request_factory.get('/', REMOTE_ADDR='1.1.1.1')
        assert self.gargoyle.is_active('test', request)

    @override_settings(INTERNAL_IPS=['1.0.0.0'])
    def test_internal_ip(self):
        self.switch.add_condition(
            condition_set=self.condition_set,
            field_name='internal_ip',
            condition='',
        )

        request = self.request_factory.get('/', REMOTE_ADDR='1.0.0.0')
        assert self.gargoyle.is_active('test', request)

        request = self.request_factory.get('/', REMOTE_ADDR='1.1.1.1')
        assert not self.gargoyle.is_active('test', request)

    @override_settings(INTERNAL_IPS=['1.0.0.0'])
    def test_not_internal_ip(self):
        self.switch.add_condition(
            condition_set=self.condition_set,
            field_name='internal_ip',
            condition='',
            exclude=True,
        )

        request = self.request_factory.get('/', REMOTE_ADDR='1.0.0.0')
        assert not self.gargoyle.is_active('test', request)

        request = self.request_factory.get('/', REMOTE_ADDR='1.1.1.1')
        assert self.gargoyle.is_active('test', request)


class HostConditionSetTests(TestCase):
    def setUp(self):
        self.gargoyle = SwitchManager(Switch, key='key', value='value', instances=True, auto_create=True)
        self.gargoyle.register(HostConditionSet())

    def test_simple(self):
        condition_set = 'gargoyle.builtins.HostConditionSet'

        # we need a better API for this (model dict isnt cutting it)
        switch = Switch.objects.create(
            key='test',
            status=SELECTIVE,
        )
        switch = self.gargoyle['test']

        assert not self.gargoyle.is_active('test')

        switch.add_condition(
            condition_set=condition_set,
            field_name='hostname',
            condition=socket.gethostname(),
        )

        assert self.gargoyle.is_active('test')


class UTCTodayConditionSetTests(TestCase):
    def setUp(self):
        """
        Assume we have:
        - server with `America/Chicago` timezone
        - app with `America/New_York` timezone (if Django timezone support enabled)
        - current timezone `Europe/Moscow` (if active)
        - then it is 2016-01-01T00:00:00 at server
        """
        self.condition_set = UTCTodayConditionSet()
        self.server_dt = datetime.datetime(2016, 1, 1, 0, 0, 0)
        self.server_tz = pytz.timezone('America/Chicago')
        self.server_dt_aware = self.server_tz.localize(self.server_dt)
        self.server_tz_offset = -6
        self.utc_dt = self.server_dt - datetime.timedelta(hours=self.server_tz_offset)

    @override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
    @timezone.override('Europe/Moscow')
    def test_use_tz_with_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.utc_dt

    @override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
    @timezone.override(None)
    def test_use_tz_no_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.utc_dt

    @override_settings(USE_TZ=False, TIME_ZONE=None)
    @timezone.override('Europe/Moscow')
    def test_no_use_tz_with_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.utc_dt

    @override_settings(USE_TZ=False, TIME_ZONE=None)
    @timezone.override(None)
    def test_no_use_tz_without_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.utc_dt


class AppTodayConditionSetTests(TestCase):
    def setUp(self):
        """
        Assume we have:
        - server with `America/Chicago` timezone
        - app with `America/New_York` timezone (if Django timezone support enabled)
        - current timezone `Europe/Moscow` (if active)
        - then it is 2016-01-01T00:00:00 at server
        """
        self.condition_set = AppTodayConditionSet()
        self.server_dt = datetime.datetime(2016, 1, 1, 0, 0, 0)
        self.server_tz = pytz.timezone('America/Chicago')
        self.server_dt_aware = self.server_tz.localize(self.server_dt)
        self.server_tz_offset = -6
        self.app_to_server_tz_offset = datetime.timedelta(hours=1)

    @override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
    @timezone.override('Europe/Moscow')
    def test_use_tz_with_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert (
                self.condition_set.get_field_value(None, 'now_is_on_or_after') ==
                self.server_dt + self.app_to_server_tz_offset
            )

    @override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
    @timezone.override(None)
    def test_use_tz_no_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert (
                self.condition_set.get_field_value(None, 'now_is_on_or_after') ==
                self.server_dt + self.app_to_server_tz_offset
            )

    @override_settings(USE_TZ=False, TIME_ZONE=None)
    @timezone.override('Europe/Moscow')
    def test_no_use_tz_with_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.server_dt

    @override_settings(USE_TZ=False, TIME_ZONE=None)
    @timezone.override(None)
    def test_no_use_tz_without_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.server_dt


class ActiveTimezoneTodayConditionSetTests(TestCase):
    def setUp(self):
        """
        Assume we have:
        - server with `America/Chicago` timezone
        - app with `America/New_York` timezone (if Django timezone support enabled)
        - current timezone `Europe/Moscow` (if active)
        - then it is 2016-01-01T00:00:00 at server
        """
        self.condition_set = ActiveTimezoneTodayConditionSet()
        self.server_dt = datetime.datetime(2016, 1, 1, 0, 0, 0)
        self.server_tz = pytz.timezone('America/Chicago')
        self.server_dt_aware = self.server_tz.localize(self.server_dt)
        self.server_tz_offset = -6
        self.app_to_server_tz_offset = datetime.timedelta(hours=1)
        self.active_to_server_tz_offset = datetime.timedelta(hours=9)

    @override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
    @timezone.override('Europe/Moscow')
    def test_use_tz_with_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert (
                self.condition_set.get_field_value(None, 'now_is_on_or_after') ==
                self.server_dt + self.active_to_server_tz_offset
            )

    @override_settings(USE_TZ=True, TIME_ZONE="America/New_York")
    @timezone.override(None)
    def test_use_tz_no_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert (
                self.condition_set.get_field_value(None, 'now_is_on_or_after') ==
                self.server_dt + self.app_to_server_tz_offset
            )

    @override_settings(USE_TZ=False, TIME_ZONE=None)
    @timezone.override('Europe/Moscow')
    def test_no_use_tz_with_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.server_dt

    @override_settings(USE_TZ=False, TIME_ZONE=None)
    @timezone.override(None)
    def test_no_use_tz_without_active(self):
        with freeze_time(self.server_dt_aware, tz_offset=self.server_tz_offset):
            assert self.condition_set.get_field_value(None, 'now_is_on_or_after') == self.server_dt


class UserConditionSetTests(TestCase):
    """ Regression tests (before adding AB_TEST) """

    def _create_condition(self, name, condition):
        """
        :param name: string
        :param condition: tuple (status, condition, [condition_type])
        :return:
        """
        conditions = {}
        namespace = self.condition_set.get_namespace()
        conditions[namespace] = {}
        conditions[namespace][name] = condition
        return conditions

    def setUp(self):
        self.User = get_user_model()
        self.condition_set = UserConditionSet(model=self.User)
        self.date = datetime.date(year=2018, month=10, day=23)
        self.yesterday = self.date - datetime.timedelta(days=1)
        self.tomorrow = self.date + datetime.timedelta(days=1)
        self.date_str = '2018-10-23'

    def test_user_has_username(self):
        conditions = self._create_condition('username', [(INCLUDE, 'test.user')])
        user = self.User(username='test.user')
        assert self.condition_set.is_active(user, conditions) is True

    def test_user_doesnt_have_username(self):
        conditions = self._create_condition('username', [(INCLUDE, 'test.user')])
        user = self.User(username='another.user')
        assert not self.condition_set.is_active(user, conditions)

    def test_user_has_email(self):
        conditions = self._create_condition('email', [(INCLUDE, 'test@email.com')])
        user = self.User(email='test@email.com')
        assert self.condition_set.is_active(user, conditions) is True

    def test_user_doesnt_have_email(self):
        conditions = self._create_condition('email', [(INCLUDE, 'test@email.com')])
        user = self.User(email='another@email.com')
        assert not self.condition_set.is_active(user, conditions)

    def test_user_is_staff(self):
        conditions = self._create_condition('is_staff', [(INCLUDE, True)])
        user = self.User(is_staff=True)
        assert self.condition_set.is_active(user, conditions) is True

    def test_user_is_no_staff(self):
        conditions = self._create_condition('is_staff', [(INCLUDE, True)])
        user = self.User(is_staff=False)
        assert not self.condition_set.is_active(user, conditions)

    def test_user_is_superuser(self):
        conditions = self._create_condition('is_superuser', [(INCLUDE, True)])
        user = self.User(is_superuser=True)
        assert self.condition_set.is_active(user, conditions) is True

    def test_user_is_no_superuser(self):
        conditions = self._create_condition('is_superuser', [(INCLUDE, True)])
        user = self.User(is_superuser=False)
        assert not self.condition_set.is_active(user, conditions)

    def test_user_date_joined_after(self):
        conditions = self._create_condition('date_joined', [(INCLUDE, self.date_str)])
        user = self.User(date_joined=self.tomorrow)
        assert self.condition_set.is_active(user, conditions) is True

    def test_user_date_joined_before(self):
        conditions = self._create_condition('date_joined', [(INCLUDE, self.date_str)])
        user = self.User(date_joined=self.yesterday)
        assert not self.condition_set.is_active(user, conditions)

    def test_user_in_percent_range(self):
        conditions = self._create_condition('percent', [(INCLUDE, '0-50')])
        user = self.User(id=25)
        assert self.condition_set.is_active(user, conditions) is True

    def test_user_out_percent_range(self):
        conditions = self._create_condition('percent', [(INCLUDE, '0-50')])
        user = self.User(id=75)
        assert not self.condition_set.is_active(user, conditions)

    def test_user_is_anonymous(self):
        conditions = self._create_condition('is_anonymous', [(INCLUDE, True)])
        user = AnonymousUser()
        assert self.condition_set.is_active(user, conditions) is True

    def test_user_is_not_anonymous(self):
        conditions = self._create_condition('is_anonymous', [(INCLUDE, True)])
        user = self.User(id=75)
        assert not self.condition_set.is_active(user, conditions)


class ConditionSetABTestTests(TestCase):
    def _create_instance(self):
        """ Returns an empty object which can get new fields in execution time """
        return type(str(""), (), {})

    def _create_contitions(self, conditions):
        """
        :param conditions = {'field_1: [tuple_condition_1, ..., tuple_condition_n],
                              field_2: [tuple_condition_1, ..., tuple_condition_m]
                              ...
                            }
        :return: {namespace: conditions}
        """
        namespace = self.condition_set.get_namespace()
        return dict([(namespace, conditions)])

    def setUp(self):
        self.condition_set = ConditionSet()
        self.condition_set.fields = {"field_ab_test": Field(), "field_feature": Field()}
        self.conditions = self._create_contitions({'field_ab_test': [('i', True, AB_TEST)],
                                                   'field_feature': [('i', True, FEATURE)],
                                                   })

    def test_is_only_ab_test_enabled(self):
        instance = self._create_instance()
        instance.field_ab_test = True
        instance.field_feature = False
        assert self.condition_set.is_active(instance, self.conditions, switch_type=AB_TEST) is True
        assert not self.condition_set.is_active(instance, self.conditions, switch_type=FEATURE)

    def test_is_only_feature_enabled(self):
        instance = self._create_instance()
        instance.field_ab_test = False
        instance.field_feature = True
        assert not self.condition_set.is_active(instance, self.conditions, switch_type=AB_TEST)
        assert self.condition_set.is_active(instance, self.conditions, switch_type=FEATURE) is True

    def test_both_feature_and_ab_test_are_enabled(self):
        instance = self._create_instance()
        instance.field_ab_test = True
        instance.field_feature = True
        assert self.condition_set.is_active(instance, self.conditions, switch_type=AB_TEST) is True
        assert self.condition_set.is_active(instance, self.conditions, switch_type=FEATURE) is True

    def test_neither_feature_nor_ab_test_are_enabled(self):
        instance = self._create_instance()
        instance.field_ab_test = False
        instance.field_feature = False
        assert not self.condition_set.is_active(instance, self.conditions, switch_type=AB_TEST)
        assert not self.condition_set.is_active(instance, self.conditions, switch_type=FEATURE)

    def test_is_ab_test_enabled_with_some_ab_test_condition_disabled(self):
        condition_set = ConditionSet()
        condition_set.fields = {"field_1": Field()}
        conditions = self._create_contitions({'field_1': [('i', True, AB_TEST), ('i', False, AB_TEST)]})
        instance = self._create_instance()
        instance.field_1 = True
        assert condition_set.is_active(instance, conditions, switch_type=AB_TEST) is True
