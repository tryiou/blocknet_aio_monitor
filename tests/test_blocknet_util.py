import os
import sys
import threading
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.blocknet_util import BlocknetUtility
from utilities import global_variables


class TestExtraConfigHandling(unittest.TestCase):
    def setUp(self):
        # Reset config before each test                                                                                                                                                  
        global_variables.conf_data.extra_option_blocknet_core_conf = [
            {'addnode': 'node1.example.com:41412'},
            {'addnode': 'node2.example.com:41412'},
            {'rpcallowip': '192.168.1.1'},
            {'addnode': 'node3.example.com:41412'}
        ]

        # Mock BlocknetUtility instance                                                                                                                                                  
        self.util = BlocknetUtility(custom_path="/test/path")
        self.util.blocknet_conf_local = {
            'global': {
                'rpcuser': 'testuser',
                'addnode': 'existing.node:41412'
                # Existing single value
            }
        }

    def tearDown(self):
        # Set running flag to False to stop the background thread                                                                                                                        
        self.util.running = False

        # Find and join the background thread                                                                                                                                            
        for thread in threading.enumerate():
            if thread._target == self.util.check_blocknet_rpc:
                thread.join(timeout=2.0)
                break

    def test_list_conversion(self):
        """Test string-to-list conversion for existing keys"""
        self.util._update_extra_config_options()
        self.assertIsInstance(self.util.blocknet_conf_local['global']['addnode'], list)
        self.assertEqual(len(self.util.blocknet_conf_local['global']['addnode']), 4)

    def test_value_merging(self):
        """Test new values are appended correctly"""
        self.util._update_extra_config_options()
        nodes = self.util.blocknet_conf_local['global']['addnode']
        self.assertIn('existing.node:41412', nodes)
        self.assertIn('node1.example.com:41412', nodes)
        self.assertIn('node3.example.com:41412', nodes)

    def test_duplicate_prevention(self):
        """Test duplicate values aren't added"""
        # Add duplicate entry                                                                                                                                                            
        global_variables.conf_data.extra_option_blocknet_core_conf.append(
            {'addnode': 'existing.node:41412'}
        )

        self.util._update_extra_config_options()
        nodes = self.util.blocknet_conf_local['global']['addnode']
        self.assertEqual(nodes.count('existing.node:41412'), 1)

    def test_new_key_handling(self):
        """Test new keys are created properly"""
        self.util._update_extra_config_options()
        self.assertIn('rpcallowip', self.util.blocknet_conf_local['global'])
        self.assertEqual(self.util.blocknet_conf_local['global']['rpcallowip'], ['192.168.1.1'])

    def test_special_characters(self):
        """Test special characters in values"""
        global_variables.conf_data.extra_option_blocknet_core_conf.append(
            {'testkey': 'specialvalue:123_$%^@!~'}
        )
        self.util._update_extra_config_options()
        value = self.util.blocknet_conf_local['global']['testkey']
        self.assertEqual(value[-1], 'specialvalue:123_$%^@!~')


if __name__ == '__main__':
    unittest.main()
