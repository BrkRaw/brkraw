import toml
from pathlib import Path

class ConfigManager:
    """
    Manage the configuration settings.

    Notes:
        - Provides methods to ensure the existence of the config directory, load or create the configuration, set configuration values, and retrieve configuration values.
    """
    def __init__(self):
        """
        Initialize the configuration object.

        Notes:
            - Sets up the home directory, config directory, and config file paths.
            - Ensures the existence of the config directory and loads or creates the configuration.
        """
        self.home_dir = Path.home()
        self.config_dir = self.home_dir / '.brkraw'
        self.config_file = self.config_dir / 'config.toml'
        self.ensure_config_dir_exists()
        self.load_or_create_config()

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
            (self.config_dir / 'bids').mkdir()

    def load_or_create_config(self):
        """
        Load an existing configuration file or create a new one if it does not exist.

        Notes:
            - If the config file does not exist, a default configuration is created and saved.
            - Otherwise, the existing configuration is loaded from the file.
        """
        if not self.config_file.exists():
            default_config = {
                'spec': {
                    'pvdataset': {
                        'binary_files': [],
                        'parameter_files': ['subject', 'ResultState', 'AdjStatePerStudy', 'study.MR']
                    },
                    'pvscan': {
                        'binary_files': ['fid', 'rawdata.job0'],
                        'parameter_files': ['method', 'acqp', 'configscan', 'visu_pars', 'AdjStatePerScan']
                    },
                    'pvreco': {
                        'binary_files': ['2dseq'],
                        'parameter_files': ['reco', 'visu_pars', 'procs', 'methreco', 'id']
                    }
                }
            }
            with open(self.config_file, 'w') as f:
                toml.dump(default_config, f)
            self.config = default_config
        else:
            with open(self.config_file, 'r') as f:
                self.config = toml.load(f)

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
            toml.dump(self.config, f)

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
