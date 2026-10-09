import subprocess
import unittest
from unittest.mock import patch, MagicMock
import startup


class StartupTests(unittest.TestCase):
    def test_packaged_command_quotes_path_and_starts_hidden(self):
        with patch.object(startup.sys, 'frozen', True, create=True), \
             patch.object(startup.sys, 'executable', r'C:\Program Files\MagicC\MagicC.exe'):
            self.assertEqual(startup.startup_command(),
                             '"C:\\Program Files\\MagicC\\MagicC.exe" --startup')

    def test_enable_only_sets_current_users_startup_entry(self):
        with patch.object(startup.winreg, 'CreateKey') as create, \
             patch.object(startup.winreg, 'SetValueEx') as write, \
             patch.object(startup, 'startup_command', return_value='MagicC.exe --startup'):
            startup.set_enabled(True)
            create.assert_called_once_with(startup.winreg.HKEY_CURRENT_USER, startup.RUN_KEY)
            self.assertEqual(write.call_args.args[1:], ('MagicC', 0, startup.winreg.REG_SZ, 'MagicC.exe --startup'))

    def test_disable_is_idempotent_and_deletes_only_magicc(self):
        with patch.object(startup.winreg, 'CreateKey'), \
             patch.object(startup.winreg, 'DeleteValue', side_effect=FileNotFoundError) as delete:
            startup.set_enabled(False)
            self.assertEqual(delete.call_args.args[1], 'MagicC')

    def test_missing_registration_is_disabled(self):
        with patch.object(startup.winreg, 'OpenKey', side_effect=FileNotFoundError):
            self.assertFalse(startup.is_enabled())


if __name__ == '__main__':
    unittest.main()
