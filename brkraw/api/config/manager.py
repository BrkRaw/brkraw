from __future__ import annotations
import yaml
from pathlib import Path
from brkraw import __version__
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Literal

class Manager:
    """
    Make this configuration works internally without create file but if user use cli to create, do it so (create on home folder)
    Manage the configuration settings.

    Notes:
        - Provides methods to ensure the existence of the config directory, load or create the configuration, 
        set configuration values, and retrieve configuration values.
    """
    def __init__(self):
        """
        Initialize the configuration object.

        Notes:
            - Sets up the home directory, config directory, and config file paths.
            - Ensures the existence of the config directory and loads or creates the configuration.
        """
        self.home = Path.home()
        self.package = Path(__file__).absolute().parent
        self.local_dir = Path.cwd()
        self.global_dir = self.home_dir / '.brkraw'
        self.fname = 'config.yaml'

    def config_file(self, target: Literal['local', 'global'] = 'global'):
        dir = self.global_dir if target == 'global' else self.local_dir
        if dir.exists() and (dir / self.fname).exists():
            return dir / self.fname
        else:
            return self.package / self.fname            

    def ensure_config_dir_exists(self):
        """
        Ensure the existence of the configuration directory.

        Notes:
            - Creates the config directory if it does not already exist.
            - Also creates 'plugin' and 'bids' directories within the config directory.
        """
        if not self.config_dir.exists():
            self.config_dir.mkdir()
            (self.config_dir / 'plugin').mkdir()
            (self.config_dir / 'preset').mkdir()
            (self.config_dir / 'bids').mkdir()

    def load(self, target: Literal['local', 'global'] = 'global'):
        """
        Load an existing configuration file or create a new one if it does not exist.

        Notes:
            - If the config file does not exist, a default configuration is created and saved.
            - Otherwise, the existing configuration is loaded from the file.
        """
        if not self.config_file.exists():
            with open(self.installed_dir / 'config.yalm') as f:
                self.config = yaml.safe_load(f)
    
    def create(self, target: Literal['local', 'global'] = 'global'):
        """_summary_

        Returns:
            _type_: _description_
        """
        
    # use default config if no configure created,
    # for downloading location, if no configuration folder created (~/.brkraw), use local folder
    # also check local folder first (plugin, preset, bids), where you run a command
    def set(self, key, value):
        """
        Set a key-value pair in the configuration and save the updated configuration to the file.

        Args:
            key: The key to set in the configuration.
            value: The value to associate with the key.

        Notes:
            - Updates the configuration with the provided key-value pair.
            - Persists the updated configuration to the config file.
        """
        self.config[key] = value
        with open(self.config_file, 'w') as f:
            yaml.dump(self.config, f, sort_keys=False)

    def get(self, key):
        """
        Retrieve the value associated with the given key from the configuration.

        Args:
            key: The key to retrieve the value for.

        Returns:
            The value associated with the key in the configuration, or None if the key is not found.

        Notes:
            - Returns the value corresponding to the provided key from the configuration.
        """
        return self.config.get(key)

# def get_scan_time(self, visu_pars=None):
#         import datetime as dt
#         subject_date = get_value(self._subject, 'SUBJECT_date')
#         subject_date = subject_date[0] if isinstance(subject_date, list) else subject_date
#         pattern_1 = r'(\d{2}:\d{2}:\d{2})\s+(\d+\s\w+\s\d{4})'
#         pattern_2 = r'(\d{4}-\d{2}-\d{2})[T](\d{2}:\d{2}:\d{2})'
#         if re.match(pattern_1, subject_date):
#             # start time
#             start_time = dt.time(*map(int, re.sub(pattern_1, r'\1', subject_date).split(':')))
#             # date
#             date = dt.datetime.strptime(re.sub(pattern_1, r'\2', subject_date), '%d %b %Y').date()
#             # end time
#             if visu_pars != None:
#                 last_scan_time = get_value(visu_pars, 'VisuAcqDate')
#                 last_scan_time = dt.time(*map(int, re.sub(pattern_1, r'\1', last_scan_time).split(':')))
#                 acq_time = get_value(visu_pars, 'VisuAcqScanTime') / 1000.0
#                 time_delta = dt.timedelta(0, acq_time)
#                 scan_time = (dt.datetime.combine(date, last_scan_time) + time_delta).time()
#                 return dict(date=date,
#                             start_time=start_time,
#                             scan_time=scan_time)
#         elif re.match(pattern_2, subject_date):
#             # start time
#             # subject_date = get_value(self._subject, 'SUBJECT_date')[0]
#             start_time = dt.time(*map(int, re.sub(pattern_2, r'\2', subject_date).split(':')))
#             # date
#             date = dt.date(*map(int, re.sub(pattern_2, r'\1', subject_date).split('-')))

#             # end date
#             if visu_pars != None:
#                 scan_time = get_value(visu_pars, 'VisuCreationDate')[0]
#                 scan_time = dt.time(*map(int, re.sub(pattern_2, r'\2', scan_time).split(':')))
#                 return dict(date=date,
#                             start_time=start_time,
#                             scan_time=scan_time)
#         else:
#             raise Exception(ERROR_MESSAGES['NotIntegrated'])

#         return dict(date=date,
#                     start_time=start_time)