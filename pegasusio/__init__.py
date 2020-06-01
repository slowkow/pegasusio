import sys
import logging
import warnings


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
ch.setFormatter(formatter)
logger.addHandler(ch)

warnings.filterwarnings("ignore", category=FutureWarning, module='anndata')


modalities = ['rna', 'citeseq', 'hashing', 'tcr', 'bcr', 'crispr', 'atac']

from .decorators import timer, run_gc

from .unimodal_data import UnimodalData
from .vdj_data import VDJData
from .citeseq_data import CITESeqData
from .cyto_data import CytoData
from .qc_utils import apply_qc_filters
from .multimodal_data import MultimodalData
from .aggr_data import AggrData
from .readwrite import infer_file_type, read_input, write_output
from .data_aggregation import aggregate_matrices

from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions
