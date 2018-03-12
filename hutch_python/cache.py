"""
This module is responsible for accumulating all loaded objects and making sure
they are available in the ``xxx.db`` virtual module. It is used extensively in
`load_conf.load_conf`.
"""
from pathlib import Path
import datetime
import sys

from .utils import IterableNamespace


class LoadCache:
    """
    Class that accumulates objects in a virtual module.

    This virtual module can be imported from as if it were a normal module.

    Parameters
    ----------
    module: ``str``
        Name of the virtual module to create. If the module has the same
        name as a real module, the real module will be masked.

    hutch_dir: ``Path``, optional
        This allows us to write a ``db.txt`` file to let the user know what
        objects get imported.

    **objs: kwargs
        Initial objects to place into the namespace

    Attributes
    ----------
    objs: `IterableNamespace`
        This is a namespace containing all the objects that have been attached
        to the ``LoadCache``.
    """
    def __init__(self, module, hutch_dir=None, **objs):
        self.objs = IterableNamespace(**objs)
        self.hutch_dir = hutch_dir
        self.module = module
        sys.modules[module] = self.objs
        sys.modules['hutch_python.db'] = self.objs

    def __call__(self, **objs):
        """
        Add objects to the namespace.

        Parameters
        ----------
        **objs: kwargs
            The key will is the namespace-accessible name, and the object
            is the object we are adding.
        """
        self.objs.__dict__.update(**objs)

    def write_file(self):
        """
        Write a ``db.txt`` file in the hutch's directory. This file informs
        the user which objects get loaded by ``hutch-python``.
        """
        if self.hutch_dir is not None:
            parts = self.module.split('.')
            parts[-1] = parts[-1] + '.txt'
            db_path = self.hutch_dir / Path('/'.join(parts))
            text = (header.format(parts[0])
                    + body.format(datetime.datetime.now()))
            for name, obj in self.objs.__dict__.items():
                text += '{:<20} {}\n'.format(name, obj.__class__)
            with db_path.open('w') as f:
                f.write(text)


# For writing the files
header = """
The objects referenced in this file are populated by the {0}python\n
initialization. If you wish to use devices from this file, import\n
them from {0}.db after calling the {0}python startup script.\n\n
"""
body = ('hutch-python last loaded on {}\n'
        'with the following objects:\n\n')
