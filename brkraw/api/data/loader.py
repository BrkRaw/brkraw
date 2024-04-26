from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Tuple
    from pathlib import Path


class Loader:
    def __init__(self, *path: Path):
        if len(path) == 1:
            self.scan = path[0]