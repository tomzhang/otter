"""Tests for convergence."""

import json

from pyrsistent import freeze, pmap

from twisted.trial.unittest import SynchronousTestCase

from otter.convergence.composition import (
    get_desired_group_state,
    json_to_LBConfigs,
    tenant_is_enabled)
from otter.convergence.model import CLBDescription, DesiredGroupState


class JsonToLBConfigTests(SynchronousTestCase):
    """
    Tests for :func:`json_to_LBConfigs`
    """
    def test_without_rackconnect(self):
        """
        LB config without rackconnect
        """
        self.assertEqual(
            json_to_LBConfigs([{'loadBalancerId': 20, 'port': 80},
                               {'loadBalancerId': 20, 'port': 800},
                               {'loadBalancerId': 21, 'port': 81}]),
            freeze({20: [CLBDescription(lb_id='20', port=80),
                         CLBDescription(lb_id='20', port=800)],
                    21: [CLBDescription(lb_id='21', port=81)]}))

    def test_with_rackconnect(self):
        """
        LB config with rackconnect
        """
        self.assertEqual(
            json_to_LBConfigs(
                [{'loadBalancerId': 20, 'port': 80},
                 {'loadBalancerId': 200, 'type': 'RackConnectV3'},
                 {'loadBalancerId': 21, 'port': 81}]),
            freeze({20: [CLBDescription(lb_id='20', port=80)],
                    21: [CLBDescription(lb_id='21', port=81)]}))


class GetDesiredGroupStateTests(SynchronousTestCase):
    """Tests for :func:`get_desired_group_state`."""

    def test_convert(self):
        """
        An Otter launch config a :obj:`DesiredGroupState`, ignoring extra
        config information.
        """
        server_config = {'name': 'test', 'flavorRef': 'f'}
        lc = {'args': {'server': server_config,
                       'loadBalancers': [{'loadBalancerId': 23, 'port': 80,
                                          'whatsit': 'invalid'},
                                         {'loadBalancerId': 23, 'port': 90}]}}

        expected_server_config = {
            'server': {
                'name': 'test',
                'flavorRef': 'f',
                'metadata': {
                    'rax:auto_scaling_group_id': 'uuid',
                    'rax:autoscale:lb:23': json.dumps(
                        [{"port": 80, "type": "CloudLoadBalancer"},
                         {"port": 90, "type": "CloudLoadBalancer"}])
                }
            }
        }
        state = get_desired_group_state('uuid', lc, 2)
        self.assertEqual(
            state,
            DesiredGroupState(
                server_config=expected_server_config,
                capacity=2,
                desired_lbs=freeze({23: [
                    CLBDescription(lb_id='23', port=80),
                    CLBDescription(lb_id='23', port=90)]})))

    def test_no_lbs(self):
        """
        When no loadBalancers are specified, the returned DesiredGroupState has
        an empty mapping for desired_lbs.
        """
        server_config = {'name': 'test', 'flavorRef': 'f'}
        lc = {'args': {'server': server_config}}

        expected_server_config = {
            'server': {
                'name': 'test',
                'flavorRef': 'f',
                'metadata': {
                    'rax:auto_scaling_group_id': 'uuid'}}}
        state = get_desired_group_state('uuid', lc, 2)
        self.assertEqual(
            state,
            DesiredGroupState(
                server_config=expected_server_config,
                capacity=2,
                desired_lbs=pmap()))


class FeatureFlagTest(SynchronousTestCase):
    """
    Tests for determining which tenants should have convergence enabled.
    """

    def test_tenant_is_enabled(self):
        """
        :obj:`convergence.tenant_is_enabled` should return ``True`` when a
        given tenant ID has convergence behavior turned on.
        """
        enabled_tenant_id = "some-tenant"

        def get_config_value(config_key):
            self.assertEqual(config_key, "convergence-tenants")
            return [enabled_tenant_id]
        self.assertEqual(tenant_is_enabled(enabled_tenant_id,
                                           get_config_value),
                         True)

    def test_tenant_is_not_enabled(self):
        """
        :obj:`convergence.tenant_is_enabled` should return ``False`` when a
        given tenant ID has convergence behavior turned off.
        """
        enabled_tenant_id = "some-tenant"

        def get_config_value(config_key):
            self.assertEqual(config_key, "convergence-tenants")
            return [enabled_tenant_id + "-nope"]
        self.assertEqual(tenant_is_enabled(enabled_tenant_id,
                                           get_config_value),
                         False)

    def test_unconfigured(self):
        """
        When no `convergence-tenants` key is available in the config, False is
        returned.
        """
        self.assertEqual(tenant_is_enabled('foo', lambda x: None), False)
