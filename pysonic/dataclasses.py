from dataclasses import dataclass, field
from typing import Optional, List

import pysonic


@dataclass
class State:
    vlc: Optional['pysonic.VLCInterface'] = None
    enabled_servers: List['pysonic.Server'] = field(default_factory=list)
    all_servers: List['pysonic.Server'] = field(default_factory=list)
    cols: int = 80
    root_dir: str = None
