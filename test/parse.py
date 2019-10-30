import unittest
import numpy as np
import periodictable as pt
from pyrolite_meltsutil.download import install_melts
from pyrolite.util.meta import stream_log
from pyrolite.util.general import check_perl, temp_path, remove_tempdir
from pyrolite_meltsutil.parse import *
from pyrolite_meltsutil.util import pyrolite_meltsutil_datafolder

_env = (
    pyrolite_meltsutil_datafolder(subfolder="localinstall")
    / "examples"
    / "alphamelts_default_env.txt"
)

_melts = (
    pyrolite_meltsutil_datafolder(subfolder="localinstall") / "examples" / "Morb.melts"
)

if not pyrolite_meltsutil_datafolder(subfolder="localinstall").exists():
    stream_log("pyrolite.ext.alphamelts")
    install_melts(local=True)  # install melts for example files etc


class TestReadMeltsfile(unittest.TestCase):
    def setUp(self):
        pass

    def test_default(self):
        file, path = read_meltsfile(_melts)


class TestReadEnvfile(unittest.TestCase):
    def setUp(self):
        pass

    def test_default(self):
        file, path = read_meltsfile(_env)


class TestParseMELTSComposition(unittest.TestCase):
    def setUp(self):
        self.cstring = """Fe''0.18Mg0.83Fe'''0.04Al1.43Cr0.52Ti0.01O4"""

    def test_parse_dict(self):
        ret = from_melts_cstr(self.cstring, formula=False)
        self.assertTrue(isinstance(ret, dict))
        self.assertTrue("Fe{2+}" in ret.keys())
        self.assertTrue(np.isclose(ret["Fe{2+}"], 0.18))

    def test_parse_formula(self):
        ret = from_melts_cstr(self.cstring, formula=True)
        self.assertTrue(isinstance(ret, pt.formulas.Formula))


if __name__ == "__main__":
    unittest.main()
