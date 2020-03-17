import versioneer
from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))
with open(path.join(here, "README.rst"), encoding="utf-8") as f:
    long_description = f.read()

requires = [
    "anndata",
    "Cython",
    "docopt",
    "fisher>=0.1.9",
    "forceatlas2-python",
    "harmony-pytorch",
    "hnswlib",
    "joblib",
    "lightgbm==2.2.1",
    "loompy",
    "louvain-github",
    "matplotlib>=2.0.0",
    "MulticoreTSNE-modified",
    "natsort",
    "numba",
    "numpy",
    "pandas>=0.24",
    "plotly",
    "pyarrow",
    "pybind11",
    "python-igraph",
    "scikit-learn>=0.21.3",
    "scikit-misc",
    "scipy<1.3",
    "scplot",
    "seaborn",
    "setuptools",
    "statsmodels",
    "tables",
    "torch",
    "umap-learn>=0.3.9",
    "xlsxwriter"
]

setup(
    name="pegasuspy",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="Pegasus is a Python package for analyzing sc/snRNA-seq data of millions of cells",
    long_description=long_description,
    url="https://github.com/klarman-cell-observatory/pegasus",
    author="Yiming Yang, Joshua Gould and Bo Li",
    author_email="cumulus-support@googlegroups.com",
    classifiers=[  # https://pypi.python.org/pypi?%3Aaction=list_classifiers
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "Topic :: Software Development :: Build Tools",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.5",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Framework :: Jupyter",
        "Natural Language :: English",
        "Operating System :: MacOS :: MacOS X",
        "Operating System :: POSIX :: Linux",
        "Topic :: Scientific/Engineering :: Bio-Informatics",
    ],
    keywords="single cell/nucleus genomics analysis",
    packages=find_packages(),
    install_requires=requires,
    extras_require=dict(
        fitsne=["fitsne"],
        leiden=['leidenalg'],
        mkl=["mkl"]
    ),
    python_requires="~=3.5",
    package_data={
        "pegasus.annotate_cluster": [
            "human_immune_cell_markers.json",
            "mouse_immune_cell_markers.json",
            "mouse_brain_cell_markers.json",
            "human_brain_cell_markers.json",
        ],
        "pegasus.check_sample_indexes": ["chromium-dna-sample-indexes-plate.json"],
    },
    entry_points={"console_scripts": ["pegasus=pegasus.__main__:main"]},
)