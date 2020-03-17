import os
import re
import numpy as np
import pandas as pd
from scipy.io import mmread, mmwrite
from scipy.sparse import csr_matrix
import tempfile
import subprocess
import gzip
import shutil
from typing import List, Dict, Tuple, Union

import logging
logger = logging.getLogger("pegasusio")

from pegasusio import UnimodalData, MultimodalData, io_funcs



def _enumerate_files(path: str, parts: List[str], repl_list1: List[str], repl_list2: List[str] = None) -> str:
    """ Enumerate all possible file names """
    if len(parts) <= 2:
        for token in repl_list1:
            parts[-1] = token
            candidate = os.path.join(path, ''.join(parts))
            if os.path.isfile(candidate):
                return candidate
    else:
        assert len(parts) == 4
        for p2 in repl_list1:
            parts[1] = p2
            for p4 in repl_list2:
                parts[3] = p4
                candidate = os.path.join(path, ''.join(parts))
                if os.path.isfile(candidate):
                    return candidate
    return None


def _locate_barcode_and_feature_files(path: str, fname: str) -> Tuple[str, str]:
    """ Locate barcode and feature files (with path) based on mtx file name (no suffix)
    """
    barcode_file = feature_file = None
    if fname == "matrix":
        barcode_file = _enumerate_files(path, [''], ["cells.tsv.gz", "cells.tsv", "barcodes.tsv.gz", "barcodes.tsv"])
        feature_file = _enumerate_files(path, [''], ["genes.tsv.gz", "genes.tsv", "features.tsv.gz", "features.tsv"])
    else:
        p1, p2, p3 = fname.partition("matrix")
        if p2 == '' and p3 == '':
            barcode_file = _enumerate_files(path, [p1, ''], [".barcodes.tsv.gz", ".barcodes.tsv", ".cells.tsv.gz", ".cells.tsv", "_barcode.tsv", ".barcodes.txt"])
            feature_file = _enumerate_files(path, [p1, ''], [".genes.tsv.gz", ".genes.tsv", ".features.tsv.gz", ".features.tsv", "_gene.tsv", ".genes.txt"])
        else:
            barcode_file = _enumerate_files(path, [p1, '', p3, ''], ["barcodes", "cells"], [".tsv.gz", ".tsv"])
            feature_file = _enumerate_files(path, [p1, '', p3, ''], ["genes", "features"], [".tsv.gz", ".tsv"])

    if barcode_file is None:
        raise ValueError("Cannot find barcode file!")
    if feature_file is None:
        raise ValueError("Cannot find feature file!")

    return barcode_file, feature_file


def _load_barcode_metadata(barcode_file: str) -> Tuple[pd.DataFrame, str]:
    """ Load cell barcode information """
    format_type = None
    barcode_metadata = pd.read_csv(barcode_file, sep="\t", header=None)

    if "cellkey" in barcode_metadata.iloc[0].values:
        # HCA DCP format
        barcode_metadata = pd.DataFrame(data = barcode_metadata.iloc[1:].values, columns = barcode_metadata.iloc[0].values)
        barcode_metadata.rename(columns={"cellkey": "barcodekey"}, inplace=True)
        format_type = "HCA DCP"
    elif "barcodekey" in barcode_metadata.iloc[0].values:
        # Pegasus format
        barcode_metadata = pd.DataFrame(data = barcode_metadata.iloc[1:].values, columns = barcode_metadata.iloc[0].values)
        format_type = "Pegasus"
    else:
        # Other format, only one column containing the barcode is expected
        barcode_metadata = pd.read_csv(barcode_file, sep="\t", header=None, names=["barcodekey"])
        format_type = "other"

    return barcode_metadata, format_type


def _load_feature_metadata(feature_file: str, format_type: str) -> Tuple[pd.DataFrame, str]:
    """ Load feature information """
    feature_metadata = pd.read_csv(feature_file, sep="\t", header=None)

    if format_type == "HCA DCP":
        # HCA DCP format genes.tsv.gz
        series = feature_metadata.iloc[0]
        assert "featurekey" in series.values and "featurename" in series.values
        series[series.eq("featurekey")] = "featureid"
        series[series.eq("featurename")] = "featurekey"        
        feature_metadata = pd.DataFrame(data = feature_metadata.iloc[1:].values, columns = series.values)
    elif format_type == "Pegasus":
        # Pegasus format features.tsv.gz
        series = feature_metadata.iloc[0]
        assert "featurekey" in series.values
        feature_metadata = pd.DataFrame(data = feature_metadata.iloc[1:].values, columns = series.values)
    else:
        # Other format
        assert format_type == "other" and feature_metadata.shape[1] <= 3
        # shape[1] = 3 -> 10x v3, 2 -> 10x v2, 1 -> scumi, dropEst, BUStools
        if feature_metadata.shape[1] > 1:
            col_names = ["featureid", "featurekey", "featuretype"]
            format_type = "10x v3" if feature_metadata.shape[1] == 3 else "10x v2"
            feature_metadata.columns = col_names[:feature_metadata.shape[1]]
        else:
            assert feature_metadata.shape[1] == 1
            feature_metadata.columns = ["featurekey"]
            # Test if in scumi format
            if feature_metadata.iloc[0, 0].find('_') >= 0:
                format_type = "scumi"
                values = feature_metadata.values[:, 0].astype(str)
                arr = np.array(np.char.split(values, sep="_", maxsplit=1).tolist())
                feature_metadata = pd.DataFrame(data={"featureid": arr[:, 0], "featurekey": arr[:, 1]})
            else:
                format_type = "dropEst or BUStools"

    return feature_metadata, format_type


def load_one_mtx_file(path: str, file_name: str, genome: str, exptype: str, ngene: int = None) -> UnimodalData:
    """Load one gene-count matrix in mtx format into an Array2D object
    """
    fname = re.sub('(.mtx|.mtx.gz)$', '', file_name)
    barcode_file, feature_file = _locate_barcode_and_feature_files(path, fname)

    barcode_metadata, format_type = _load_barcode_metadata(barcode_file)
    feature_metadata, format_type = _load_feature_metadata(feature_file, format_type)
    logger.info("Detected mtx file in {} format.".format(format_type))

    mtx_file = os.path.join(path, file_name)
    if file_name.endswith(".gz"):
        mtx_fifo = os.path.join(tempfile.gettempdir(), file_name + ".fifo")
        os.mkfifo(mtx_fifo)
        subprocess.Popen("gunzip -c {0} > {1}".format(mtx_file, mtx_fifo), shell = True)
        row_ind, col_ind, data, shape = io_funcs.read_mtx(mtx_fifo)
        os.unlink(mtx_fifo)
    else:
        row_ind, col_ind, data, shape = io_funcs.read_mtx(mtx_file)

    if shape[1] == barcode_metadata.shape[0]: # Column is barcode, swap the coordinates
        row_ind, col_ind = col_ind, row_ind
        shape = (shape[1], shape[0])

    mat = csr_matrix((data, (row_ind, col_ind)), shape = shape)
    mat.eliminate_zeros()

    unidata = UnimodalData(barcode_metadata, feature_metadata, {"X": mat}, metadata = {"experiment_type": exptype, "genome": genome})
    unidata.filter(ngene=ngene)
    if format_type == "10x v3" or format_type == "10x v2":
        unidata.separate_channels()

    return unidata


def _locate_mtx_file(path: str) -> str:
    """ Locate one mtx file in the path directory; first choose matrix.mtx.gz or matrix.mtx if multiple mtx files exist."""
    file_names = []    
    with os.scandir(path) as dir_iter:
        for dir_entry in dir_iter:
            file_name = dir_entry.name
            if file_name.endswith(".mtx.gz") or file_name.endswith(".mtx"):
                if file_name == "matrix.mtx.gz" or file_name == "matrix.mtx":
                    return file_name
                file_names.append(file_name)
    return file_names[0] if len(file_names) > 0 else None


def load_mtx_file(path: str, genome: str = None, exptype: str = "rna", ngene: int = None) -> MultimodalData:
    """Load gene-count matrix from Market Matrix files (10x v2, v3 and HCA DCP formats)

    Parameters
    ----------

    path : `str`
        Path to mtx files. The directory implied by path should either contain matrix, feature and barcode information, or folders containing these information.
    genome : `str`, optional (default: None)
        Genome name of the matrix. If None, genome will be inferred from path.
    exptype: `str`, optional (default: 'rna')
        Experiment type, choosing from 'rna', 'citeseq', 'hashing', 'tcr', 'bcr', 'crispr' or 'atac'
    ngene : `int`, optional (default: None)
        Minimum number of genes to keep a barcode. Default is to keep all barcodes.

    Returns
    -------

    An MemData object containing a genome-Array2D pair.

    Examples
    --------
    >>> io.load_mtx_file('example.mtx.gz', genome = 'mm10')
    """

    orig_file = path
    if os.path.isdir(orig_file):
        path = orig_file.rstrip('/')
        file_name = _locate_mtx_file(path)
    else:
        if (not orig_file.endswith(".mtx")) and (not orig_file.endswith(".mtx.gz")):
            raise ValueError("File {} does not end with suffix .mtx or .mtx.gz!".format(orig_file))
        path, file_name = os.path.split(orig_file)

    data = MultimodalData()

    if file_name is not None:
        if genome is None:
            genome = os.path.basename(path)
        data.add_data(
            genome,
            load_one_mtx_file(
                path,
                file_name,
                genome,
                exptype,
                ngene=ngene,
            ),
        )
    else:
        for dir_entry in os.scandir(path):
            if dir_entry.is_dir():
                file_name = _locate_mtx_file(dir_entry.path)
                if file_name is None:
                    raise ValueError("Folder {} does not contain a mtx file!".format(dir_entry.path))
                data.add_data(dir_entry.name, load_one_mtx_file(dir_entry.path, file_name, dir_entry.name, exptype, ngene=ngene))

    return data



def _write_mtx(unidata: UnimodalData, output_dir: str):
    """ Write Unimodal data to mtx
    """
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    
    for key in unidata.list_keys():
        mtx_file = os.path.join(output_dir, ("matrix" if key == "X" else key) + ".mtx")
        mmwrite(mtx_file, unidata.matrices[key], precision = 2)
        mtx_file_gz = mtx_file + ".gz"
        with open(mtx_file, "rb") as fin:
            with gzip.open(mtx_file_gz, "wb") as gout:
                shutil.copyfileobj(fin, gout)
        os.remove(mtx_file)
        logger.info("{} is written.".format(mtx_file_gz))

    unidata.barcode_metadata.to_csv(os.path.join(output_dir, "barcodes.tsv.gz"), sep = '\t')
    logger.info("barcodes.tsv.gz is written.")

    unidata.feature_metadata.to_csv(os.path.join(output_dir, "features.tsv.gz"), sep = '\t')
    logger.info("features.tsv.gz is written.")

    logger.info("Mtx for {} is written.".format(unidata.get_genome()))


def write_mtx_file(data: MultimodalData, output_directory: str):
    """ Write output to mtx files in output_directory
    """
    output_dir = os.path.abspath(output_directory)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    for key in data.list_data():
        _write_mtx(data.get_data(key), os.path.join(output_dir, key))
    
    logger.info("Mtx files are written.")