# -*- coding: utf-8 -*-

# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import mock

from osc_lib.tests import utils

from tripleoclient import exceptions
from tripleoclient.tests.fakes import FakeStackObject
from tripleoclient.workflows import deployment


class TestDeploymentWorkflows(utils.TestCommand):

    def setUp(self):
        super(TestDeploymentWorkflows, self).setUp()

        self.app.client_manager.workflow_engine = self.workflow = mock.Mock()
        self.tripleoclient = mock.Mock()
        self.websocket = mock.Mock()
        self.websocket.__enter__ = lambda s: self.websocket
        self.websocket.__exit__ = lambda s, *exc: None
        self.tripleoclient.messaging_websocket.return_value = self.websocket
        self.app.client_manager.tripleoclient = self.tripleoclient

        self.message_success = iter([{
            "execution": {"id": "IDID"},
            "status": "SUCCESS",
            "message": "Success.",
            "registered_nodes": [],
        }])
        self.message_failed = iter([{
            "execution": {"id": "IDID"},
            "status": "FAIL",
            "message": "Fail.",
        }])

    @mock.patch('shutil.rmtree')
    @mock.patch('os.chdir')
    @mock.patch('tripleoclient.utils.tempfile')
    @mock.patch('tripleoclient.utils.run_ansible_playbook',
                autospec=True)
    def test_enable_ssh_admin(self, mock_rmtree, mock_chdir, mock_tempfile,
                              mock_playbook):
        hosts = 'a', 'b', 'c'
        ssh_user = 'test-user'
        ssh_key = 'test-key'
        timeout = 30

        deployment.enable_ssh_admin(
            FakeStackObject,
            hosts,
            ssh_user,
            ssh_key,
            timeout
        )

        # once for ssh-keygen, then twice per host
        self.assertEqual(1, mock_playbook.call_count)

    @mock.patch('tripleoclient.utils.get_blacklisted_ip_addresses')
    @mock.patch('tripleoclient.utils.get_role_net_ip_map')
    def test_get_overcloud_hosts(self, mock_role_net_ip_map,
                                 mock_blacklisted_ip_addresses):
        stack = mock.Mock()
        mock_role_net_ip_map.return_value = {
            'Controller': {
                'ctlplane': ['1.1.1.1', '2.2.2.2', '3.3.3.3'],
                'external': ['4.4.4.4', '5.5.5.5', '6.6.6.6']},
            'Compute': {
                'ctlplane': ['7.7.7.7', '8.8.8.8', '9.9.9.9'],
                'external': ['10.10.10.10', '11.11.11.11', '12.12.12.12']},
        }
        mock_blacklisted_ip_addresses.return_value = []

        ips = deployment.get_overcloud_hosts(stack, 'ctlplane')
        expected = ['1.1.1.1', '2.2.2.2', '3.3.3.3',
                    '7.7.7.7', '8.8.8.8', '9.9.9.9']
        self.assertEqual(sorted(expected), sorted(ips))

        ips = deployment.get_overcloud_hosts(stack, 'external')
        expected = ['4.4.4.4', '5.5.5.5', '6.6.6.6',
                    '10.10.10.10', '11.11.11.11', '12.12.12.12']
        self.assertEqual(sorted(expected), sorted(ips))

    @mock.patch('tripleoclient.utils.get_blacklisted_ip_addresses')
    @mock.patch('tripleoclient.utils.get_role_net_ip_map')
    def test_get_overcloud_hosts_with_blacklist(
            self, mock_role_net_ip_map,
            mock_blacklisted_ip_addresses):
        stack = mock.Mock()
        mock_role_net_ip_map.return_value = {
            'Controller': {
                'ctlplane': ['1.1.1.1', '2.2.2.2', '3.3.3.3'],
                'external': ['4.4.4.4', '5.5.5.5', '6.6.6.6']},
            'Compute': {
                'ctlplane': ['7.7.7.7', '8.8.8.8', '9.9.9.9'],
                'external': ['10.10.10.10', '11.11.11.11', '12.12.12.12']},
        }

        mock_blacklisted_ip_addresses.return_value = ['8.8.8.8']
        ips = deployment.get_overcloud_hosts(stack, 'ctlplane')
        expected = ['1.1.1.1', '2.2.2.2', '3.3.3.3',
                    '7.7.7.7', '9.9.9.9']
        self.assertEqual(sorted(expected), sorted(ips))

        ips = deployment.get_overcloud_hosts(stack, 'external')
        expected = ['4.4.4.4', '5.5.5.5', '6.6.6.6',
                    '10.10.10.10', '12.12.12.12']
        self.assertEqual(sorted(expected), sorted(ips))

        mock_blacklisted_ip_addresses.return_value = ['7.7.7.7', '9.9.9.9',
                                                      '2.2.2.2']
        ips = deployment.get_overcloud_hosts(stack, 'external')
        expected = ['4.4.4.4', '6.6.6.6', '11.11.11.11']
        self.assertEqual(sorted(expected), sorted(ips))

    def test_config_download_already_in_progress(
            self):
        log = mock.Mock()
        stack = mock.Mock()
        stack.stack_name = 'stacktest'
        clients = mock.Mock()
        mock_execution = mock.Mock()
        mock_execution.input = '{"plan_name": "stacktest"}'
        mock_return = mock.Mock(return_value=[mock_execution])
        clients.workflow_engine.executions.find = mock_return

        self.assertRaises(exceptions.ConfigDownloadInProgress,
                          deployment.config_download,
                          log, clients, stack, 'templates', 'ssh_user',
                          'ssh_key', 'ssh_networks', 'output_dir', False,
                          'timeout')

    @mock.patch('tripleoclient.workflows.deployment.base')
    def test_config_download_already_in_progress_for_diff_stack(
            self, mock_base):
        log = mock.Mock()
        stack = mock.Mock()
        stack.stack_name = 'stacktest'
        clients = mock.Mock()
        mock_execution = mock.Mock()
        mock_execution.input = '{"plan_name": "someotherstack"}'
        mock_return = mock.Mock(return_value=[mock_execution])
        clients.workflow_engine.executions.find = mock_return
        mock_exit = mock.Mock()
        mock_exit.__exit__ = mock.Mock()
        mock_exit.__enter__ = mock.Mock()
        clients.tripleoclient.messaging_websocket = mock.Mock(
            return_value=mock_exit)
        mock_base.wait_for_messages = mock.Mock(
            return_value=[dict(status='SUCCESS')])

        deployment.config_download(
            log, clients, stack, 'templates', 'ssh_user',
            'ssh_key', 'ssh_networks', 'output_dir', False,
            'timeout')
