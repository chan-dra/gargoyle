# -*- encoding:utf-8 -*-
from __future__ import absolute_import, division, print_function, unicode_literals

import django
from django.core.management import call_command
from django.test import TestCase

from gargoyle import gargoyle
from gargoyle.constants import AB_TEST
from gargoyle.models import Switch


def test_no_migrations_required(db):
    if django.VERSION >= (1, 10):
        try:
            call_command('makemigrations', 'gargoyle', check=1)
        except SystemExit:
            raise AssertionError('Migrations required')
    else:
        try:
            call_command('makemigrations', 'gargoyle', exit=1)
        except SystemExit:
            pass
        else:
            raise AssertionError('Migrations required')


class SwitchTest(TestCase):
    def test_get_active_conditions(self):
        switch = Switch.objects.create(key='key')
        switch.add_condition(gargoyle, 'gargoyle.builtins.IPAddressConditionSet', 'ip_address', '1.1.1.1',
                             condition_type=AB_TEST)
        active_conditions = switch.get_active_conditions(gargoyle)
        condition_set_id, group, field, data, excludes, condition_type = next(iter(active_conditions))
        assert condition_set_id == 'gargoyle.builtins.IPAddressConditionSet'
        assert group == 'IP Address'
        assert field.name == 'ip_address'
        assert data == '1.1.1.1'
        assert condition_type == AB_TEST

    def test_switch_to_dict(self):
        switch = Switch.objects.create(key='key1')
        switch_data = switch.to_dict(manager=gargoyle)
        assert len(switch_data['conditions']) == 0

        switch.add_condition(gargoyle, 'gargoyle.builtins.IPAddressConditionSet', 'ip_address', '1.1.1.1',
                             condition_type=AB_TEST)

        switch_data = switch.to_dict(manager=gargoyle)
        assert len(switch_data['conditions']) == 1
        name, value, field_value, exclude, condition_type = switch_data['conditions'][0]['conditions'][0]
        assert name == 'ip_address'
        assert value == '1.1.1.1'
        assert field_value == '1.1.1.1'
        assert exclude is False
        assert condition_type == AB_TEST

    def test_condition_stored_in_db(self):
        switch = Switch.objects.create(key='key')
        switch_data = switch.to_dict(manager=gargoyle)
        assert len(switch_data['conditions']) == 0
        switch.add_condition(gargoyle, 'gargoyle.builtins.IPAddressConditionSet', 'ip_address', '1.1.1.1',
                             condition_type=AB_TEST)

        switch = Switch.objects.get(key='key')
        switch_data = switch.to_dict(manager=gargoyle)
        assert len(switch_data['conditions']) == 1
