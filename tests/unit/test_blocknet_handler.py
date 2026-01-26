"""Tests for BlocknetHandler extra configuration options handling."""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open
import tempfile
import shutil
import requests

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utilities.bin_handlers.blocknet_handler import (
    BlocknetHandler,
    parse_conf_file,
    save_conf_to_file,
    get_blocknet_data_folder,
    generate_random_string,
    retrieve_xb_manifest,
    retrieve_remote_blocknet_conf,
    retrieve_remote_blocknet_xbridge_conf,
    retrieve_remote_conf,
    download_remote_conf,
    get_remote_file_size
)
from utilities.app_container import get_container


class TestExtraConfigHandling(unittest.TestCase):
    """Test suite for BlocknetHandler extra config handling."""

    def setUp(self):
        """Set up test fixtures before each test."""
        # Get the container and set up test config
        container = get_container()
        container.conf_data.extra_option_blocknet_core_conf = [
            {'addnode': 'node1.example.com:41412'},
            {'addnode': 'node2.example.com:41412'},
            {'rpcallowip': '192.168.1.1'},
            {'addnode': 'node3.example.com:41412'}
        ]

        # Mock all network calls and background operations
        with patch('utilities.bin_handlers.blocknet_handler.retrieve_xb_manifest'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_xbridge_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.threading.Thread'), \
                patch('utilities.bin_handlers.blocknet_handler.parse_conf_file'), \
                patch('utilities.bin_handlers.blocknet_handler.save_conf_to_file'):
            self.util = BlocknetHandler(custom_path="/test/path", container=container)

        # Set up initial blocknet configuration
        self.util.blocknet_conf_local = {
            'global': {
                'rpcuser': 'testuser',
                'addnode': 'existing.node:41412'
            }
        }

        # Mock the running flag to prevent background operations
        self.util.running = False

    def _execute_update(self):
        """Helper method to execute the update and return the result."""
        self.util._update_extra_config_options()
        return self.util.blocknet_conf_local['global']

    def test_list_conversion(self):
        """Test string-to-list conversion for existing keys."""
        config = self._execute_update()

        self.assertIsInstance(config['addnode'], list)
        self.assertEqual(len(config['addnode']), 4)

    def test_value_merging(self):
        """Test new values are appended correctly."""
        config = self._execute_update()
        nodes = config['addnode']

        self.assertIn('existing.node:41412', nodes)
        self.assertIn('node1.example.com:41412', nodes)
        self.assertIn('node3.example.com:41412', nodes)

    def test_duplicate_prevention(self):
        """Test duplicate values aren't added."""
        # Add duplicate entry
        container = get_container()
        container.conf_data.extra_option_blocknet_core_conf.append(
            {'addnode': 'existing.node:41412'}
        )

        config = self._execute_update()
        nodes = config['addnode']

        self.assertEqual(nodes.count('existing.node:41412'), 1)

    def test_new_key_handling(self):
        """Test new keys are created properly."""
        config = self._execute_update()

        self.assertIn('rpcallowip', config)
        self.assertEqual(config['rpcallowip'], ['192.168.1.1'])

    def test_special_characters(self):
        """Test special characters in values are preserved."""
        container = get_container()
        container.conf_data.extra_option_blocknet_core_conf.append(
            {'testkey': 'specialvalue:123_$%^@!~'}
        )

        config = self._execute_update()
        value = config['testkey']

        self.assertEqual(value[-1], 'specialvalue:123_$%^@!~')

    def test_empty_extra_config(self):
        """Test behavior when extra_option_blocknet_core_conf is empty."""
        container = get_container()
        container.conf_data.extra_option_blocknet_core_conf = []

        config = self._execute_update()

        # Should not modify existing config
        self.assertEqual(config['addnode'], 'existing.node:41412')

    def test_none_extra_config(self):
        """Test behavior when extra_option_blocknet_core_conf is None."""
        container = get_container()
        container.conf_data.extra_option_blocknet_core_conf = None

        config = self._execute_update()

        # Should not modify existing config
        self.assertEqual(config['addnode'], 'existing.node:41412')

    def test_empty_global_section(self):
        """Test behavior when global section doesn't exist."""
        self.util.blocknet_conf_local = {}

        config = self._execute_update()

        # Should create global section
        self.assertIn('global', self.util.blocknet_conf_local)
        self.assertIn('addnode', config)
        self.assertEqual(len(config['addnode']), 3)

    def test_comma_separated_value_conversion(self):
        """Test conversion of comma-separated string values to lists."""
        self.util.blocknet_conf_local['global']['addnode'] = 'node1:41412,node2:41412'

        config = self._execute_update()

        self.assertIsInstance(config['addnode'], list)
        self.assertIn('node1:41412', config['addnode'])
        self.assertIn('node2:41412', config['addnode'])
        self.assertIn('node1.example.com:41412', config['addnode'])

    def test_numeric_value_conversion(self):
        """Test conversion of numeric values to strings."""
        container = get_container()
        container.conf_data.extra_option_blocknet_core_conf.append(
            {'testport': 41412}
        )

        config = self._execute_update()

        self.assertIn('testport', config)
        self.assertEqual(config['testport'], ['41412'])

    def test_boolean_value_conversion(self):
        """Test conversion of boolean values to strings."""
        container = get_container()
        container.conf_data.extra_option_blocknet_core_conf.append(
            {'testflag': True}
        )

        config = self._execute_update()

        self.assertIn('testflag', config)
        self.assertIsNotNone(config['testflag'])
        self.assertEqual(config['testflag'], ['True'])


class TestParseConfFile(unittest.TestCase):
    """Test suite for parse_conf_file function."""

    def test_parse_conf_file_from_path(self):
        """Test parsing configuration from file path."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.conf', delete=False) as f:
            f.write("[global]\n")
            f.write("rpcuser=testuser\n")
            f.write("rpcpassword=testpass\n")
            f.write("addnode=node1:41412\n")
            f.write("addnode=node2:41412\n")
            f.write("[section2]\n")
            f.write("key=value\n")
            temp_path = f.name

        try:
            result = parse_conf_file(file_path=temp_path)

            self.assertIn('global', result)
            self.assertEqual(result['global']['rpcuser'], 'testuser')
            self.assertEqual(result['global']['rpcpassword'], 'testpass')
            self.assertEqual(result['global']['addnode'], ['node1:41412', 'node2:41412'])
            self.assertIn('section2', result)
            self.assertEqual(result['section2']['key'], 'value')
        finally:
            os.unlink(temp_path)

    def test_parse_conf_file_from_string(self):
        """Test parsing configuration from string."""
        conf_string = """[global]
rpcuser=testuser
rpcpassword=testpass
addnode=node1:41412
addnode=node2:41412

[section2]
key=value
"""
        result = parse_conf_file(input_string=conf_string)

        self.assertIn('global', result)
        self.assertEqual(result['global']['rpcuser'], 'testuser')
        self.assertEqual(result['global']['rpcpassword'], 'testpass')
        self.assertEqual(result['global']['addnode'], ['node1:41412', 'node2:41412'])
        self.assertIn('section2', result)
        self.assertEqual(result['section2']['key'], 'value')

    def test_parse_conf_file_with_comments(self):
        """Test parsing configuration with comments."""
        conf_string = """[global]
# This is a comment
rpcuser=testuser
# Another comment
rpcpassword=testpass
"""
        result = parse_conf_file(input_string=conf_string)

        self.assertEqual(result['global']['rpcuser'], 'testuser')
        self.assertEqual(result['global']['rpcpassword'], 'testpass')

    def test_parse_conf_file_empty_lines(self):
        """Test parsing configuration with empty lines."""
        conf_string = """[global]

rpcuser=testuser

rpcpassword=testpass

"""
        result = parse_conf_file(input_string=conf_string)

        self.assertEqual(result['global']['rpcuser'], 'testuser')
        self.assertEqual(result['global']['rpcpassword'], 'testpass')

    def test_parse_conf_file_no_addnode(self):
        """Test parsing configuration without addnode."""
        conf_string = """[global]
rpcuser=testuser
rpcpassword=testpass
"""
        result = parse_conf_file(input_string=conf_string)

        self.assertEqual(result['global']['rpcuser'], 'testuser')
        self.assertEqual(result['global']['rpcpassword'], 'testpass')
        self.assertNotIn('addnode', result['global'])


class TestSaveConfToFile(unittest.TestCase):
    """Test suite for save_conf_to_file function."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up test fixtures."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_save_conf_to_file(self):
        """Test saving configuration to file."""
        conf_data = {
            'global': {
                'rpcuser': 'testuser',
                'rpcpassword': 'testpass',
                'addnode': ['node1:41412', 'node2:41412']
            },
            'section2': {
                'key': 'value'
            }
        }

        file_path = os.path.join(self.temp_dir, 'test.conf')
        result = save_conf_to_file(conf_data, file_path)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(file_path))

        with open(file_path, 'r') as f:
            content = f.read()

        self.assertIn('rpcuser=testuser', content)
        self.assertIn('rpcpassword=testpass', content)
        self.assertIn('addnode=node1:41412', content)
        self.assertIn('addnode=node2:41412', content)
        self.assertIn('[section2]', content)
        self.assertIn('key=value', content)

    def test_save_conf_to_file_creates_directory(self):
        """Test saving configuration creates directory if it doesn't exist."""
        conf_data = {'global': {'rpcuser': 'testuser'}}
        file_path = os.path.join(self.temp_dir, 'subdir', 'test.conf')

        result = save_conf_to_file(conf_data, file_path)

        self.assertTrue(result)
        self.assertTrue(os.path.exists(file_path))

    def test_save_conf_to_file_error(self):
        """Test saving configuration with error."""
        conf_data = {'global': {'rpcuser': 'testuser'}}

        # Try to save to invalid path
        result = save_conf_to_file(conf_data, '/invalid/path/test.conf')

        self.assertFalse(result)


class TestGetBlocknetDataFolder(unittest.TestCase):
    """Test suite for get_blocknet_data_folder function."""

    def test_get_blocknet_data_folder_with_custom_path(self):
        """Test getting data folder with custom path."""
        custom_path = "/custom/path"
        result = get_blocknet_data_folder(custom_path)

        self.assertEqual(result, "/custom/path")

    def test_get_blocknet_data_folder_with_default_path(self):
        """Test getting data folder with default path."""
        mock_container = MagicMock()
        mock_container.conf_data.blocknet_default_paths = {'Linux': '/default/path'}
        mock_container.system = 'Linux'

        with patch('utilities.bin_handlers.blocknet_handler.get_container', return_value=mock_container):
            result = get_blocknet_data_folder()

            self.assertEqual(result, '/default/path')

    def test_get_blocknet_data_folder_with_env_vars(self):
        """Test getting data folder with environment variables."""
        custom_path = "$HOME/blocknet"
        result = get_blocknet_data_folder(custom_path)

        # Should expand environment variables
        self.assertNotIn('$HOME', result)


class TestGenerateRandomString(unittest.TestCase):
    """Test suite for generate_random_string function."""

    def test_generate_random_string_length(self):
        """Test that generated string has correct length."""
        length = 32
        result = generate_random_string(length)

        self.assertEqual(len(result), length)

    def test_generate_random_string_content(self):
        """Test that generated string contains only alphanumeric characters."""
        result = generate_random_string(32)

        self.assertTrue(result.isalnum())

    def test_generate_random_string_uniqueness(self):
        """Test that generated strings are unique."""
        result1 = generate_random_string(32)
        result2 = generate_random_string(32)

        self.assertNotEqual(result1, result2)


class TestRetrieveRemoteConf(unittest.TestCase):
    """Test suite for retrieve_remote_conf function."""

    @patch('utilities.bin_handlers.blocknet_handler.os.path.exists')
    @patch('utilities.bin_handlers.blocknet_handler.open', new_callable=mock_open)
    def test_retrieve_remote_conf_local_exists(self, mock_open_file, mock_exists):
        """Test retrieving remote conf when local file exists."""
        mock_exists.return_value = True
        mock_open_file.return_value.read.return_value = "[global]\nrpcuser=test\n"

        with patch('utilities.bin_handlers.blocknet_handler.parse_conf_file') as mock_parse:
            mock_parse.return_value = {'global': {'rpcuser': 'test'}}

            result = retrieve_remote_conf('http://example.com/conf', 'subfolder', 'test.conf')

            self.assertEqual(result, {'global': {'rpcuser': 'test'}})

    @patch('utilities.bin_handlers.blocknet_handler.os.path.exists')
    def test_retrieve_remote_conf_local_not_exists(self, mock_exists):
        """Test retrieving remote conf when local file doesn't exist."""
        mock_exists.return_value = False

        with patch('utilities.bin_handlers.blocknet_handler.download_remote_conf') as mock_download:
            mock_download.return_value = {'global': {'rpcuser': 'test'}}

            result = retrieve_remote_conf('http://example.com/conf', 'subfolder', 'test.conf')

            self.assertEqual(result, {'global': {'rpcuser': 'test'}})


class TestDownloadRemoteConf(unittest.TestCase):
    """Test suite for download_remote_conf function."""

    @patch('utilities.bin_handlers.blocknet_handler.requests.get')
    def test_download_remote_conf_success(self, mock_get):
        """Test downloading remote conf successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "[global]\nrpcuser=test\n"
        mock_get.return_value = mock_response

        with patch('utilities.bin_handlers.blocknet_handler.parse_conf_file') as mock_parse:
            with patch('utilities.bin_handlers.blocknet_handler.save_conf_to_file') as mock_save:
                mock_parse.return_value = {'global': {'rpcuser': 'test'}}
                mock_save.return_value = True

                result = download_remote_conf('http://example.com/conf', '/tmp/test.conf')

                self.assertEqual(result, {'global': {'rpcuser': 'test'}})

    @patch('utilities.bin_handlers.blocknet_handler.requests.get')
    def test_download_remote_conf_http_error(self, mock_get):
        """Test downloading remote conf with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = download_remote_conf('http://example.com/conf', '/tmp/test.conf')

        self.assertIsNone(result)

    @patch('utilities.bin_handlers.blocknet_handler.requests.get')
    def test_download_remote_conf_parse_error(self, mock_get):
        """Test downloading remote conf with parse error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "invalid conf"
        mock_get.return_value = mock_response

        with patch('utilities.bin_handlers.blocknet_handler.parse_conf_file') as mock_parse:
            mock_parse.return_value = None

            result = download_remote_conf('http://example.com/conf', '/tmp/test.conf')

            self.assertIsNone(result)

    @patch('utilities.bin_handlers.blocknet_handler.requests.get')
    def test_download_remote_conf_request_exception(self, mock_get):
        """Test downloading remote conf with request exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        result = download_remote_conf('http://example.com/conf', '/tmp/test.conf')

        self.assertIsNone(result)


class TestGetRemoteFileSize(unittest.TestCase):
    """Test suite for get_remote_file_size function."""

    @patch('utilities.bin_handlers.blocknet_handler.requests.head')
    def test_get_remote_file_size_success(self, mock_head):
        """Test getting remote file size successfully."""
        mock_response = MagicMock()
        mock_response.headers = {'content-length': '1024'}
        mock_head.return_value = mock_response

        result = get_remote_file_size('http://example.com/file.zip')

        self.assertEqual(result, 1024)

    @patch('utilities.bin_handlers.blocknet_handler.requests.head')
    def test_get_remote_file_size_no_content_length(self, mock_head):
        """Test getting remote file size with no content-length header."""
        mock_response = MagicMock()
        mock_response.headers = {}
        mock_head.return_value = mock_response

        result = get_remote_file_size('http://example.com/file.zip')

        self.assertEqual(result, 0)


class TestRetrieveXbManifest(unittest.TestCase):
    """Test suite for retrieve_xb_manifest function."""

    @patch('utilities.bin_handlers.blocknet_handler.requests.get')
    def test_retrieve_xb_manifest_success(self, mock_get):
        """Test retrieving XB manifest successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [{'ticker': 'BTC', 'ver_id': 1}]
        mock_get.return_value = mock_response

        mock_container = MagicMock()
        mock_container.aio_folder = '/tmp/aio'
        mock_container.conf_data.remote_manifest_url = 'http://example.com/manifest.json'

        with patch('utilities.bin_handlers.blocknet_handler.get_container', return_value=mock_container):
            result = retrieve_xb_manifest()

            self.assertEqual(result, [{'ticker': 'BTC', 'ver_id': 1}])

    @patch('utilities.bin_handlers.blocknet_handler.requests.get')
    def test_retrieve_xb_manifest_http_error(self, mock_get):
        """Test retrieving XB manifest with HTTP error."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        mock_container = MagicMock()
        mock_container.conf_data.remote_manifest_url = 'http://example.com/manifest.json'

        with patch('utilities.bin_handlers.blocknet_handler.get_container', return_value=mock_container):
            result = retrieve_xb_manifest()

            self.assertIsNone(result)

    @patch('utilities.bin_handlers.blocknet_handler.requests.get')
    def test_retrieve_xb_manifest_request_exception(self, mock_get):
        """Test retrieving XB manifest with request exception."""
        mock_get.side_effect = requests.exceptions.RequestException("Network error")

        mock_container = MagicMock()
        mock_container.conf_data.remote_manifest_url = 'http://example.com/manifest.json'

        with patch('utilities.bin_handlers.blocknet_handler.get_container', return_value=mock_container):
            result = retrieve_xb_manifest()

            self.assertIsNone(result)


class TestRetrieveRemoteBlocknetConf(unittest.TestCase):
    """Test suite for retrieve_remote_blocknet_conf function."""

    @patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_conf')
    def test_retrieve_remote_blocknet_conf(self, mock_retrieve):
        """Test retrieving remote blocknet conf."""
        mock_retrieve.return_value = {'global': {'rpcuser': 'test'}}

        mock_container = MagicMock()
        mock_container.conf_data.remote_blocknet_conf_url = 'http://example.com/blocknet.conf'

        with patch('utilities.bin_handlers.blocknet_handler.get_container', return_value=mock_container):
            result = retrieve_remote_blocknet_conf()

            self.assertEqual(result, {'global': {'rpcuser': 'test'}})


class TestRetrieveRemoteBlocknetXbridgeConf(unittest.TestCase):
    """Test suite for retrieve_remote_blocknet_xbridge_conf function."""

    @patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_conf')
    def test_retrieve_remote_blocknet_xbridge_conf(self, mock_retrieve):
        """Test retrieving remote blocknet xbridge conf."""
        mock_retrieve.return_value = {'Main': {'Username': 'test'}}

        mock_container = MagicMock()
        mock_container.conf_data.remote_xbridge_conf_url = 'http://example.com/xbridge.conf'

        with patch('utilities.bin_handlers.blocknet_handler.get_container', return_value=mock_container):
            result = retrieve_remote_blocknet_xbridge_conf()

            self.assertEqual(result, {'Main': {'Username': 'test'}})


class TestBlocknetHandlerCoreMethods(unittest.TestCase):
    """Test suite for BlocknetHandler core methods."""

    def setUp(self):
        """Set up test fixtures."""
        # Set up mock container
        self.mock_container = MagicMock()
        self.mock_container.aio_folder = '/aio/path'
        
        # Mock all external dependencies
        with patch('utilities.bin_handlers.blocknet_handler.retrieve_xb_manifest'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_xbridge_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.threading.Thread'), \
                patch('utilities.bin_handlers.blocknet_handler.parse_conf_file'), \
                patch('utilities.bin_handlers.blocknet_handler.save_conf_to_file'), \
                patch('utilities.bin_handlers.blocknet_handler.get_container', return_value=self.mock_container), \
                patch.object(self.mock_container, 'get_blocknet_executable_path', return_value='/aio/path/blocknet-4.4.1/blocknetd'):
            self.handler = BlocknetHandler(custom_path="/test/path")

        self.handler.running = False
        self.handler.blocknet_conf_local = {
            'global': {
                'rpcuser': 'testuser',
                'rpcpassword': 'testpass',
                'rpcport': '41412'
            }
        }

    def test_create_data_folder(self):
        """Test creating data folder when it doesn't exist."""
        with patch('os.path.exists', return_value=False), \
                patch('os.makedirs') as mock_makedirs:
            self.handler.create_data_folder()

            mock_makedirs.assert_called_once_with("/test/path")

    def test_create_data_folder_exists(self):
        """Test creating data folder when it already exists."""
        with patch('os.path.exists', return_value=True), \
                patch('os.makedirs') as mock_makedirs:
            self.handler.create_data_folder()

            mock_makedirs.assert_not_called()

    def test_create_aio_folder(self):
        """Test creating AIO folder."""
        with patch('os.path.exists', return_value=False), \
                patch('os.makedirs') as mock_makedirs:
            self.handler.container.aio_folder = '/aio/path'
            self.handler.create_aio_folder()

            mock_makedirs.assert_called_once_with('/aio/path')

    def test_check_data_folder_existence(self):
        """Test checking if data folder exists."""
        with patch('os.path.exists', return_value=True):
            result = self.handler.check_data_folder_existence()
            self.assertTrue(result)

        with patch('os.path.exists', return_value=False):
            result = self.handler.check_data_folder_existence()
            self.assertFalse(result)

    def test_close_blocknet_with_process(self):
        """Test closing blocknet when process exists."""
        self.handler.blocknet_process = MagicMock()
        self.handler.graceful_terminate = MagicMock()

        self.handler.close_blocknet()

        self.handler.graceful_terminate.assert_called_once_with(timeout=60)

    def test_close_blocknet_without_process(self):
        """Test closing blocknet when no process exists."""
        self.handler.blocknet_process = None
        self.handler.close_blocknet_pids = MagicMock()

        self.handler.close_blocknet()

        self.handler.close_blocknet_pids.assert_called_once()

    def test_kill_blocknet(self):
        """Test killing blocknet."""
        self.handler.force_kill = MagicMock()

        self.handler.kill_blocknet()

        self.handler.force_kill.assert_called_once()

    def test_set_custom_data_path(self):
        """Test setting custom data path."""
        with patch('os.path.exists', return_value=False), \
                patch('os.makedirs') as mock_makedirs, \
                patch.object(self.handler, 'parse_blocknet_conf') as mock_parse_blocknet, \
                patch.object(self.handler, 'parse_xbridge_conf') as mock_parse_xbridge, \
                patch.object(self.handler, 'init_blocknet_rpc') as mock_init_rpc:
            self.handler.set_custom_data_path('/new/path')

            mock_makedirs.assert_called_once_with('/new/path')
            self.assertEqual(self.handler.data_folder, '/new/path')
            mock_parse_blocknet.assert_called_once()
            mock_parse_xbridge.assert_called_once()
            mock_init_rpc.assert_called_once()

    def test_start_blocknet(self):
        """Test starting blocknet."""
        with patch('os.path.exists', return_value=True), \
                patch.object(self.handler, 'create_data_folder'), \
                patch.object(self.handler, 'start_process') as mock_start_process:
            mock_start_process.return_value = MagicMock()

            self.handler.start_blocknet()

            self.handler.create_data_folder.assert_called_once()
            mock_start_process.assert_called_once()

    def test_start_blocknet_downloads_if_missing(self):
        """Test starting blocknet downloads binary if missing."""
        with patch('os.path.exists', return_value=False), \
                patch.object(self.handler, 'create_data_folder'), \
                patch.object(self.handler, 'download_blocknet_bin') as mock_download, \
                patch.object(self.handler, 'start_process') as mock_start_process:
            mock_start_process.return_value = MagicMock()

            self.handler.start_blocknet()

            mock_download.assert_called_once()
            mock_start_process.assert_called_once()

    def test_check_blocknet_conf_success(self):
        """Test check_blocknet_conf with successful update."""
        self.handler.blocknet_conf_remote = {
            'global': {
                'rpcuser': 'newuser',
                'rpcpassword': 'newpass'
            }
        }

        with patch.object(self.handler, 'parse_blocknet_conf'), \
                patch.object(self.handler, 'save_blocknet_conf'), \
                patch.object(self.handler, 'init_blocknet_rpc'), \
                patch('utilities.bin_handlers.blocknet_handler.generate_random_string', return_value='random123'):
            result = self.handler.check_blocknet_conf()

            self.assertTrue(result)
            self.handler.save_blocknet_conf.assert_called_once()

    def test_check_blocknet_conf_no_change(self):
        """Test check_blocknet_conf when no changes needed."""
        self.handler.blocknet_conf_remote = {
            'global': {
                'rpcuser': 'testuser',
                'rpcpassword': 'testpass'
            }
        }

        with patch.object(self.handler, 'parse_blocknet_conf'), \
                patch.object(self.handler, 'save_blocknet_conf') as mock_save, \
                patch('utilities.bin_handlers.blocknet_handler.generate_random_string', return_value='random123'):
            result = self.handler.check_blocknet_conf()

            # Result is True because rpcuser/rpcpassword are generated
            self.assertTrue(result)
            mock_save.assert_called_once()

    def test_check_blocknet_conf_remote_none(self):
        """Test check_blocknet_conf when remote conf is None."""
        self.handler.blocknet_conf_remote = None

        with patch.object(self.handler, 'parse_blocknet_conf'):
            result = self.handler.check_blocknet_conf()
            self.assertFalse(result)

    def test_check_blocknet_conf_local_none(self):
        """Test check_blocknet_conf when local conf is None."""
        self.handler.blocknet_conf_local = None
        self.handler.blocknet_conf_remote = {'global': {}}

        with patch.object(self.handler, 'parse_blocknet_conf'):
            result = self.handler.check_blocknet_conf()
            self.assertFalse(result)

    def test_check_blocknet_conf_creates_global_section(self):
        """Test check_blocknet_conf creates global section if missing."""
        self.handler.blocknet_conf_local = {}
        self.handler.blocknet_conf_remote = {'global': {'rpcuser': 'test'}}

        with patch.object(self.handler, 'parse_blocknet_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.generate_random_string', return_value='random123'):
            self.handler.check_blocknet_conf()

            self.assertIn('global', self.handler.blocknet_conf_local)

    def test_check_blocknet_conf_rpcallowip_special_handling(self):
        """Test check_blocknet_conf handles rpcallowip specially."""
        self.handler.blocknet_conf_local = {'global': {}}
        self.handler.blocknet_conf_remote = {'global': {'rpcallowip': '192.168.1.1'}}

        with patch.object(self.handler, 'parse_blocknet_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.generate_random_string', return_value='random123'):
            self.handler.check_blocknet_conf()

            # rpcallowip is set to 127.0.0.1 in check_blocknet_conf
            # Then _update_extra_config_options adds 192.168.1.1 to the list
            self.assertIn('127.0.0.1', self.handler.blocknet_conf_local['global']['rpcallowip'])
            self.assertIn('192.168.1.1', self.handler.blocknet_conf_local['global']['rpcallowip'])

    def test_check_xbridge_conf_success(self):
        """Test check_xbridge_conf with successful update."""
        self.handler.xbridge_conf_local = {}
        self.handler.blocknet_xbridge_conf_remote = {'BLOCK': {'Username': 'test'}}
        self.handler.blocknet_conf_local = {'global': {'rpcuser': 'user', 'rpcpassword': 'pass', 'rpcport': '41412'}}

        with patch.object(self.handler, 'parse_xbridge_conf'), \
                patch.object(self.handler, 'save_xbridge_conf') as mock_save:
            result = self.handler.check_xbridge_conf(None)

            self.assertTrue(result)
            mock_save.assert_called_once()

    def test_check_xbridge_conf_no_change(self):
        """Test check_xbridge_conf when no changes needed."""
        self.handler.xbridge_conf_local = {'Main': {'ExchangeWallets': ''}}
        self.handler.blocknet_xbridge_conf_remote = {}

        with patch.object(self.handler, 'parse_xbridge_conf'), \
                patch.object(self.handler, 'save_xbridge_conf') as mock_save:
            result = self.handler.check_xbridge_conf(None)

            self.assertFalse(result)
            mock_save.assert_not_called()

    def test_check_xbridge_conf_with_xlite_daemon(self):
        """Test check_xbridge_conf with xlite daemon config."""
        self.handler.xbridge_conf_local = {}
        self.handler.blocknet_xbridge_conf_remote = {'BLOCK': {'Username': 'test'}}
        self.handler.blocknet_conf_local = {'global': {'rpcuser': 'user', 'rpcpassword': 'pass', 'rpcport': '41412'}}

        xlite_conf = {
            'BTC': {
                'rpcUsername': 'btcuser',
                'rpcPassword': 'btcpass',
                'rpcPort': '18332'
            }
        }

        with patch.object(self.handler, 'parse_xbridge_conf'), \
                patch.object(self.handler, 'retrieve_coin_conf'), \
                patch.object(self.handler, 'save_xbridge_conf'):
            self.handler.parsed_xbridge_confs = {'BTC': {'BTC': {'Username': 'old'}}}

            result = self.handler.check_xbridge_conf(xlite_conf)

            self.assertTrue(result)

    def test_compare_and_update_local_conf(self):
        """Test compare_and_update_local_conf."""
        with patch.object(self.handler, 'check_blocknet_conf'), \
                patch.object(self.handler, 'check_xbridge_conf') as mock_check_xbridge:
            self.handler.compare_and_update_local_conf()

            self.handler.check_blocknet_conf.assert_called_once()
            mock_check_xbridge.assert_called_once_with(None)

    def test_retrieve_coin_conf(self):
        """Test retrieve_coin_conf."""
        self.handler.xb_manifest = [
            {'ticker': 'BTC', 'ver_id': 1, 'xbridge_conf': 'btc.conf', 'wallet_conf': 'btcwallet.conf'},
            {'ticker': 'BTC', 'ver_id': 2, 'xbridge_conf': 'btc2.conf', 'wallet_conf': 'btcwallet2.conf'}
        ]

        with patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_conf') as mock_retrieve:
            mock_retrieve.side_effect = [{'BTC': {}}, {'BTC': {}}]

            self.handler.retrieve_coin_conf('BTC')

            self.assertIn('BTC', self.handler.parsed_xbridge_confs)
            self.assertEqual(mock_retrieve.call_count, 2)

    def test_retrieve_coin_conf_no_entries(self):
        """Test retrieve_coin_conf with no matching entries."""
        self.handler.xb_manifest = [{'ticker': 'ETH', 'ver_id': 1}]

        with patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_conf') as mock_retrieve:
            self.handler.retrieve_coin_conf('BTC')

            mock_retrieve.assert_not_called()
            self.assertNotIn('BTC', self.handler.parsed_xbridge_confs)


class TestBlocknetHandlerBootstrap(unittest.TestCase):
    """Test suite for BlocknetHandler bootstrap methods."""

    def setUp(self):
        """Set up test fixtures."""
        with patch('utilities.bin_handlers.blocknet_handler.retrieve_xb_manifest'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_xbridge_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.threading.Thread'), \
                patch('utilities.bin_handlers.blocknet_handler.parse_conf_file'), \
                patch('utilities.bin_handlers.blocknet_handler.save_conf_to_file'):
            self.handler = BlocknetHandler(custom_path="/test/path")

        self.handler.running = False

    def test_download_bootstrap_downloads_new_file(self):
        """Test downloading bootstrap when file doesn't exist."""
        with patch('os.path.exists', return_value=False), \
                patch('utilities.bin_handlers.blocknet_handler.get_remote_file_size', return_value=1000), \
                patch('requests.get') as mock_get, \
                patch('zipfile.ZipFile'), \
                patch.object(self.handler, 'create_data_folder'), \
                patch.object(self.handler, 'create_aio_folder'):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b'x' * 8192]
            mock_get.return_value = mock_response

            self.handler.container.aio_folder = '/aio'
            self.handler.container.conf_data.blocknet_bootstrap_url = 'http://example.com/bootstrap.zip'

            with patch('builtins.open', MagicMock()):
                self.handler.download_bootstrap()

            self.assertFalse(self.handler.bootstrap_checking)
            self.assertIsNone(self.handler.bootstrap_percent_download)

    def test_download_bootstrap_file_exists_same_size(self):
        """Test bootstrap when file exists with same size."""
        with patch('os.path.exists', return_value=True), \
                patch('os.path.getsize', return_value=1000), \
                patch('utilities.bin_handlers.blocknet_handler.get_remote_file_size', return_value=1000), \
                patch('zipfile.ZipFile'), \
                patch.object(self.handler, 'create_data_folder'), \
                patch.object(self.handler, 'create_aio_folder'):
            self.handler.container.aio_folder = '/aio'

            self.handler.download_bootstrap()

            self.assertFalse(self.handler.bootstrap_checking)

    def test_download_bootstrap_file_exists_different_size(self):
        """Test bootstrap when file exists with different size."""
        with patch('os.path.exists', return_value=True), \
                patch('os.path.getsize', side_effect=[500, 1000]), \
                patch('utilities.bin_handlers.blocknet_handler.get_remote_file_size', return_value=1000), \
                patch('os.remove') as mock_remove, \
                patch('requests.get') as mock_get, \
                patch('zipfile.ZipFile'), \
                patch.object(self.handler, 'create_data_folder'), \
                patch.object(self.handler, 'create_aio_folder'), \
                patch('builtins.open', MagicMock()):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b'x' * 8192]
            mock_get.return_value = mock_response

            self.handler.container.aio_folder = '/aio'
            self.handler.container.conf_data.blocknet_bootstrap_url = 'http://example.com/bootstrap.zip'

            self.handler.download_bootstrap()

            # os.remove is called for the bootstrap file and all data files
            self.assertGreater(mock_remove.call_count, 0)

    def test_download_bootstrap_deletes_existing_data(self):
        """Test bootstrap deletes existing blockchain data."""
        with patch('utilities.bin_handlers.blocknet_handler.os.path.exists',
                      side_effect=[False, True, True, True, False, False, False]), \
                patch('utilities.bin_handlers.blocknet_handler.os.path.isdir', return_value=True), \
                patch('utilities.bin_handlers.blocknet_handler.os.path.getsize', return_value=1000), \
                patch('utilities.bin_handlers.blocknet_handler.get_remote_file_size', return_value=1000), \
                patch('requests.get') as mock_get, \
                patch('zipfile.ZipFile'), \
                patch('utilities.bin_handlers.blocknet_handler.shutil.rmtree') as mock_rmtree, \
                patch('utilities.bin_handlers.blocknet_handler.os.remove') as mock_remove_file, \
                patch.object(self.handler, 'create_data_folder'), \
                patch.object(self.handler, 'create_aio_folder'), \
                patch('builtins.open', MagicMock()):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.iter_content.return_value = [b'x' * 8192]
            mock_get.return_value = mock_response

            self.handler.container.aio_folder = '/aio'
            self.handler.container.conf_data.blocknet_bootstrap_url = 'http://example.com/bootstrap.zip'
            self.handler.data_folder = '/data'

            self.handler.download_bootstrap()

            # Should delete blocks, chainstate, and indexes folders (directories)
            # Note: shutil.rmtree is called for directories, os.remove for files
            self.assertEqual(mock_rmtree.call_count, 3)
            self.assertEqual(mock_remove_file.call_count, 0)

    def test_download_bootstrap_error_handling(self):
        """Test bootstrap error handling."""
        with patch('os.path.exists', return_value=False), \
                patch('utilities.bin_handlers.blocknet_handler.get_remote_file_size', return_value=1000), \
                patch('requests.get', side_effect=Exception("Network error")), \
                patch.object(self.handler, 'create_data_folder'), \
                patch.object(self.handler, 'create_aio_folder'):
            self.handler.container.aio_folder = '/aio'
            self.handler.container.conf_data.blocknet_bootstrap_url = 'http://example.com/bootstrap.zip'

            self.handler.download_bootstrap()

            self.assertFalse(self.handler.bootstrap_checking)
            self.assertIsNone(self.handler.bootstrap_percent_download)

    def test_download_blocknet_bin(self):
        """Test downloading blocknet binary."""
        with patch.object(self.handler, 'download_binary') as mock_download:
            self.handler.container.system = 'Linux'
            self.handler.container.machine = 'x86_64'
            self.handler.container.blocknet_release_url = 'http://example.com/blocknet.tar.gz'
            self.handler.container.aio_folder = '/aio'

            self.handler.download_blocknet_bin()

            mock_download.assert_called_once_with(
                'http://example.com/blocknet.tar.gz',
                'blocknet.tar.gz',
                self.handler.blocknet_exe,
                '/aio'
            )

    def test_download_blocknet_bin_unsupported(self):
        """Test downloading blocknet binary on unsupported platform."""
        self.handler.container.system = 'Unsupported'
        self.handler.container.machine = 'x86_64'
        self.handler.container.blocknet_release_url = None

        with self.assertRaises(ValueError):
            self.handler.download_blocknet_bin()


class TestBlocknetHandlerRPC(unittest.TestCase):
    """Test suite for BlocknetHandler RPC methods."""

    def setUp(self):
        """Set up test fixtures."""
        with patch('utilities.bin_handlers.blocknet_handler.retrieve_xb_manifest'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.retrieve_remote_blocknet_xbridge_conf'), \
                patch('utilities.bin_handlers.blocknet_handler.threading.Thread'), \
                patch('utilities.bin_handlers.blocknet_handler.parse_conf_file'), \
                patch('utilities.bin_handlers.blocknet_handler.save_conf_to_file'):
            self.handler = BlocknetHandler(custom_path="/test/path")

        self.handler.running = False

    def test_init_blocknet_rpc_success(self):
        """Test initializing RPC client successfully."""
        self.handler.blocknet_conf_local = {
            'global': {
                'rpcuser': 'testuser',
                'rpcpassword': 'testpass',
                'rpcport': '41412'
            }
        }

        with patch('utilities.bin_handlers.blocknet_handler.RPCClient') as mock_rpc_client:
            self.handler.init_blocknet_rpc()

            mock_rpc_client.assert_called_once_with('testuser', 'testpass', 41412)
            self.assertIsNotNone(self.handler.blocknet_rpc)

    def test_init_blocknet_rpc_missing_config(self):
        """Test initializing RPC client with missing config."""
        self.handler.blocknet_conf_local = {}

        with patch('utilities.bin_handlers.blocknet_handler.RPCClient') as mock_rpc_client:
            self.handler.init_blocknet_rpc()

            mock_rpc_client.assert_not_called()
            self.assertIsNone(self.handler.blocknet_rpc)

    def test_init_blocknet_rpc_zero_port(self):
        """Test initializing RPC client with zero port."""
        self.handler.blocknet_conf_local = {
            'global': {
                'rpcuser': 'testuser',
                'rpcpassword': 'testpass',
                'rpcport': '0'
            }
        }

        with patch('utilities.bin_handlers.blocknet_handler.RPCClient') as mock_rpc_client:
            self.handler.init_blocknet_rpc()

            mock_rpc_client.assert_not_called()
            self.assertIsNone(self.handler.blocknet_rpc)

    def test_check_blocknet_rpc(self):
        """Test RPC checking thread."""
        self.handler.running = True
        self.handler.blocknet_rpc = MagicMock()
        self.handler.blocknet_rpc.send_rpc_request.return_value = {'result': 'success'}

        with patch('time.sleep', side_effect=KeyboardInterrupt):
            try:
                self.handler.check_blocknet_rpc()
            except KeyboardInterrupt:
                pass

        self.assertTrue(self.handler.valid_rpc)


class TestGetRemoteFileSizeExtended(unittest.TestCase):
    """Extended tests for get_remote_file_size function."""

    @patch('utilities.bin_handlers.blocknet_handler.requests.head')
    def test_get_remote_file_size_with_zero_content_length(self, mock_head):
        """Test getting remote file size with zero content-length."""
        mock_response = MagicMock()
        mock_response.headers = {'content-length': '0'}
        mock_head.return_value = mock_response

        result = get_remote_file_size('http://example.com/file.zip')

        self.assertEqual(result, 0)

    @patch('utilities.bin_handlers.blocknet_handler.requests.head')
    def test_get_remote_file_size_raises_on_error(self, mock_head):
        """Test get_remote_file_size raises exception on HTTP error."""
        mock_head.side_effect = requests.exceptions.RequestException("404 Not Found")

        with self.assertRaises(requests.exceptions.RequestException):
            get_remote_file_size('http://example.com/missing.zip')


if __name__ == '__main__':
    unittest.main()
