"""
This submodule contains functions for automated execution, plotting and reporting from
alphamelts 1.9.
"""
from pathlib import Path
import time, datetime
from tqdm import tqdm
import itertools

from pyrolite.geochem.ind import common_elements, common_oxides
from pyrolite.comp.codata import renormalise
from pyrolite.util.meta import ToLogger
from pyrolite.util.multip import combine_choices

from ..parse import read_envfile, read_meltsfile
from ..env import MELTS_Env
from ..meltsfile import dict_to_meltsfile

from .naming import exp_name
from .org import make_meltsfolder
from .process import MeltsProcess
from .timing import estimate_experiment_duration

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())
logger = logging.getLogger(__name__)


__chem__ = common_elements(as_set=True) | common_oxides(as_set=True)


class MeltsExperiment(object):
    """
    Melts Experiment Object. For a single call to melts, with one set of outputs.
    Autmatically creates the experiment folder, meltsfile and environment file, runs
    alphaMELTS and collects the results.

    Todo
    ----
        * Automated creation of folders for experiment results (see :func:`make_meltsfolder`)
        * Being able to run melts in an automated way (see :class:`MeltsProcess`)
        * Compressed export/save function
        * Post-processing functions for i) validation and ii) plotting
    """

    def __init__(self, title="MeltsExperiment", dir="./", meltsfile=None, env=None):
        self.title = title
        self.dir = dir
        self.log = []

        if meltsfile is not None:
            self.set_meltsfile(meltsfile)
        if env is not None:
            self.set_envfile(env)
        else:
            self.set_envfile(MELTS_Env())

        self._make_folder()

    def set_meltsfile(self, meltsfile, **kwargs):
        """
        Set the meltsfile for the experiment.

        Parameters
        ------------
        meltsfile : :class:`pandas.Series` | :class:`str` | :class:`pathlib.Path`
            Either a path to a valid melts file, a :class:`pandas.Series`, or a
            multiline string representation of a melts file object.
        """
        self.meltsfile, self.meltsfilepath = read_meltsfile(meltsfile)

    def set_envfile(self, env):
        """
        Set the environment for the experiment.

        Parameters
        ------------
        env : :class:`str` | :class:`pathlib.Path`
            Either a path to a valid environment file, a :class:`pandas.Series`, or a
            multiline string representation of a environment file object.
        """
        self.envfile, self.envfilepath = read_envfile(env)

    def _make_folder(self):
        """
        Create the experiment folder.
        """
        self.folder = make_meltsfolder(
            meltsfile=self.meltsfile, title=self.title, dir=self.dir, env=self.envfile
        )
        self.meltsfilepath = self.folder / (self.title + ".melts")
        self.envfilepath = self.folder / "environment.txt"

    def run(self, log=False, superliquidus_start=True):
        """
        Call 'run_alphamelts.command'.
        """
        self.mp = MeltsProcess(
            meltsfile=str(self.title) + ".melts",
            env="environment.txt",
            fromdir=str(self.folder),
        )
        self.mp.write([3, [0, 1][superliquidus_start], 4], wait=True, log=log)
        self.mp.terminate()

    def cleanup(self):
        pass


class MeltsBatch(object):
    """
    Batch of :class:`MeltsExperiment`, which may represent evaluation over a grid of
    parameters or configurations.

    Parameters
    -----------
    comp_df : :class:`pandas.DataFrame`
        Dataframe of compositions.
    default_config : :class:`dict`
        Dictionary of default parameters.
    config_grid : class:`dict`
        Dictionary of parameters to systematically vary.

    Attributes
    -----------

    compositions : :class:`list` of :class:`dict`
        Compositions to use for

    configs : :class:`list` of :class:`dict`

    experiments : :class:`list` of :class:`dict`

    Todo
    ------
        * Can start with a single composition or multiple compositions in a dataframe
        * Enable grid search for individual parameters
        * Improved output logging/reporting
        * Calculate relative number of calculations to be performed for the est duration

            This is currently about correct for an isobaric calcuation at 10 degree
            temperature steps over few hundred degrees - but won't work for different
            T steps.
    """

    def __init__(
        self,
        comp_df,
        fromdir=Path("./"),
        default_config={},
        config_grid={},
        env=None,
        logger=logger,
    ):
        self.logger = logger
        # make a file logger
        fh = logging.FileHandler("autolog.log")
        fh.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)
        self.dir = fromdir
        self.default = default_config
        self.env = env or MELTS_Env()
        # let's establish the grid of configurations
        self.configs = [{**self.default}]
        grid = combine_choices(config_grid)
        self.configs += [{**self.default, **i} for i in grid if i not in self.configs]
        self.compositions = comp_df.to_dict("records")
        # combine these to create full experiment configs
        exprs = [
            {**cfg, **cmp}
            for (cfg, cmp) in itertools.product(self.configs, self.compositions)
        ]
        self.experiments = [(exp_name(expr), expr, self.env) for expr in exprs]
        self.est_duration = str(
            datetime.timedelta(seconds=len(self.experiments) * 6)
        )  # 6s/run
        self.logger.info("Estimated Calculation Time: {}".format(self.est_duration))

    def run(self, overwrite=False, exclude=[], superliquidus_start=True):
        self.started = time.time()
        experiments = self.experiments
        if not overwrite:
            experiments = [
                (n, cfg, env)
                for (n, cfg, env) in experiments
                if not (self.dir / n).exists()
            ]

        self.logger.info("Starting {} Calculations.".format(len(experiments)))
        paths = []
        for name, exp, env in tqdm(
            experiments, file=ToLogger(self.logger), mininterval=2
        ):
            if "modifychem" in exp:
                modifications = exp.pop("modifychem")  # remove modify chem
                ek, mk = set(exp.keys()), set(modifications.keys())
                for k, v in exp["modifychem"].items():
                    exp[k] = v
                allchem = (ek | mk) & __chem__
                unmodified = (ek - mk) & __chem__
                offset = np.array(modifications.values()).sum()
                for uk in unmodified:
                    exp[uk] *= 100.0 - offset

            exp_exclude = exclude
            if "exclude" in exp:
                exp_exclude += exp.pop("exclude")  # remove exclude

            # expdir = self.dir / name  # experiment dir
            # paths.append(expdir)
            self.logger.info("Start {}.".format(name))
            meltsfile = dict_to_meltsfile(exp, modes=exp["modes"], exclude=exp_exclude)
            M = MeltsExperiment(meltsfile=meltsfile, title=name, env=env, dir=self.dir)
            M.run(superliquidus_start=superliquidus_start)
            self.logger.info("Finished {}.".format(name))
        self.duration = datetime.timedelta(seconds=time.time() - self.started)
        self.logger.info("Calculations Complete after {}".format(self.duration))
        self.paths = paths

    def cleanup(self):
        pass