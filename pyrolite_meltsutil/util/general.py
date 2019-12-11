import logging
from pyrolite.util.meta import get_module_datafolder

logging.getLogger(__name__).addHandler(logging.NullHandler())
logger = logging.getLogger(__name__)


def pyrolite_meltsutil_datafolder(subfolder=None):
    """
    Returns the path of the pyrolite-meltsutil data folder.

    Parameters
    -----------
    subfolder : :class:`str`
        Subfolder within the pyrolite data folder.

    Returns
    -------
    :class:`pathlib.Path`
    """
    return get_module_datafolder(module="pyrolite_meltsutil", subfolder=subfolder)