"""
.. include:: ../docs/datasets.md
"""

from os import environ

# Tensorflow C++ backend logging verbosity
environ["TF_CPP_MIN_LOG_LEVEL"] = "2"  # NOQA

import csv
from os import mkdir
from os.path import dirname, exists, isfile, join
from typing import Tuple

import numpy as np
import sklearn.cluster
from numpy.typing import NDArray

seed: int = 1234
LABELS_PER_DATA_POINT = 1

def set_seed(new_seed: int):
    """
    Set the global seed that will be used for all functions that include
    randomness.
    """
    global seed
    seed = new_seed


class DatasetFiles:
    """
    Paths to files that hold the content of a datset as numpy arrays.
    """

    def __init__(self, datasetName: str) -> None:
        """
        Construct the paths of the dataset files from its name.
        """

        currentDirectoryName = dirname(__file__)

        self.dataDirectory: str = join(
            currentDirectoryName,
            f"../data/{datasetName}")
        self.numpyFeatures: str = join(self.dataDirectory, "features.npy")
        self.numpyLabels: str = join(self.dataDirectory, "labels.npy")


class DatasetBaseClass:
    """
    Base class for dataset representation.

    The attribute `datasetName` determines the file names where the dataset will
    be stored. When subclassing this base class, each subclass should use a
    different `datasetName`.
    Numpy arrays can be loaded either from file, or "externally", which means
    potential downloading and/or preprocessing. Since the latter depends on the
    dataset and source, the corresponding method `load_external` must be
    implemented by the subclass.
    """
    size: int = 1
    train_size: int = 1
    dataDimensions: list[int] = [1]
    datasetName: str = "default"

    def __init__(self) -> None:
        """
        Set up numpy arrays to hold the dataset, using the dataset format.
        """

        # This base class should not be instantiated, subclass it instead
        assert self.__class__ != DatasetBaseClass

        self.files: DatasetFiles = DatasetFiles(self.datasetName)

        labelsArrayShape: list[int] = [LABELS_PER_DATA_POINT]
        labelsArrayShape.insert(0, self.size)
        featuresArrayShape: list[int] = self.dataDimensions.copy()
        featuresArrayShape.insert(0, self.size)

        self.labels: NDArray = np.zeros(labelsArrayShape)
        self.features: NDArray = np.zeros(featuresArrayShape)
        self.load()

        # self.features should not be flattened or its shape changed otherwise
        assert list(self.features.shape) == featuresArrayShape

    def load(self):
        """
        Load the dataset into the numpy arrays, either from file or "externally".
        """
        if exists(self.files.numpyFeatures) and exists(self.files.numpyLabels):
            self.load_numpy_from_file()
        else:
            self.load_external()
            self.save()

    def load_external(self):
        """
        Using an external source (e.g. file on disk or download), load the
        dataset.
        """
        raise NotImplementedError("Must be implemented by subclass.")

    def load_numpy_from_file(self):
        """
        Load the numpy arrays from the respective files.
        """
        self.features: NDArray = np.load(self.files.numpyFeatures)
        self.labels: NDArray = np.load(self.files.numpyLabels)

    def split(self, train_size: int | None = None,
              random: bool = False) -> Tuple[Tuple[NDArray, NDArray], Tuple[NDArray, NDArray]]:
        """
        Returns a split: (x_train,y_train),(x_test,y_test).

        The amount of images to be used in each partition is determined by each
        individual dataset. Alternatively, a parameter `train_size` can be
        given, which determines the sizes of `x_train` and `y_train`. The rest
        of the data is put into `x_test` and `y_test`.
        If `random` is set to True, it randomly samples from the entire
        dataset to determine which data points are put into the "train"-sets.
        No data point is chosen twice.

        """

        if train_size is None:
            train_size = self.train_size

        if train_size > self.size:
            raise ValueError("train_size must be at most dataset size.")

        allIndices: NDArray = np.arange(self.size)

        if random:
            global seed
            rng = np.random.default_rng(seed)
            randomIndices: NDArray = rng.choice(
                allIndices,
                self.train_size,
                replace=False)
            trainIndices: NDArray = np.sort(randomIndices)
        else:
            trainIndices: NDArray = np.arange(self.train_size)

        testIndices: NDArray = np.setdiff1d(allIndices, trainIndices)

        x_train: NDArray = self.features[trainIndices]
        y_train: NDArray = self.labels[trainIndices]
        x_test: NDArray = self.features[testIndices]
        y_test: NDArray = self.labels[testIndices]
        return (x_train, y_train), (x_test, y_test)

    def save(self):
        """
        Save the arrays that hold the dataset to disk.
        """
        if not exists(self.files.dataDirectory):
            mkdir(self.files.dataDirectory)
        np.save(self.files.numpyFeatures, self.features)
        np.save(self.files.numpyLabels, self.labels)


class KagglePurchaseDataset(DatasetBaseClass):
    """
    Kaggle's Acquire Valued Shoppers Challenge dataset of binary features.
    """

    datasetName: str = "kaggle"
    size: int = 197324
    train_size: int = 10000
    dataDimensions: list[int] = [600]

    def __init__(self) -> None:
        super().__init__()

    def load_external(self):
        self.load_raw_data_from_file()

    def load_raw_data_from_file(self):
        """
        Load the dataset from the raw text file, that is provided by Shokri et
        al.
        It is a CSV file with 601 columns, where the first column represents the
        label, and a row represents a data record.
        """
        rawData: str = join(self.files.dataDirectory, "raw_data")
        assert isfile(rawData), "Use set_up.py to download Kaggle data."

        with open(rawData) as file:
            reader = csv.reader(file)
            for index, row in enumerate(reader):
                self.labels[index, 0] = row[0]
                self.features[index, :] = row[1:]


class KagglePurchaseDatasetClustered(DatasetBaseClass):
    """
    Kaggle's Acquire Valued Shoppers Challenge dataset, clustered into
    partitions.
    """

    numberOfClusters = 5

    size: int = 197324
    train_size: int = 10000
    dataDimensions: list[int] = [600]

    def __init__(self, numberOfClusters: int = 5) -> None:
        self.numberOfClusters: int = numberOfClusters
        self.datasetName: str = "kaggle_clustered_" + \
            str(self.numberOfClusters)
        super().__init__()

    def load_external(self):
        """
        Load the unaltered Kaggle dataset, using the respective Class. Then use
        k-means clustering, to cluster the data into the given number of
        clusters, which is also the new number of labels.
        """
        kaggle_unclustered: DatasetBaseClass = KagglePurchaseDataset()
        # TODO: use real KMeans, not MiniBatch
        kmeans = sklearn.cluster.MiniBatchKMeans(
            n_clusters=self.numberOfClusters)
        self.features: NDArray = kaggle_unclustered.features.copy()
        self.labels: NDArray = kmeans.fit_predict(self.features)


class Cifar10Dataset(DatasetBaseClass):
    """
    CIFAR-10 dataset of small RGB images.
    """

    datasetName: str = "cifar10"
    size: int = 60000
    train_size: int = 50000
    dataDimensions: list[int] = [32, 32, 3]

    def __init__(self) -> None:
        super().__init__()

    def load_external(self):
        self.load_from_tensorflow()

    def load_from_tensorflow(self):
        """
        Invoke the calls to tensorflow that automatically download and cache the
        dataset.
        """
        import tensorflow as tf
        (x_train, y_train), (x_test, y_test) = \
            tf.keras.datasets.cifar10.load_data()
        self.features: NDArray = np.append(x_train, x_test, axis=0)
        self.labels: NDArray = np.append(y_train, y_test, axis=0)


class Cifar100Dataset(DatasetBaseClass):
    """
    CIFAR-100 dataset of small RGB images.
    """

    datasetName: str = "cifar100"
    size: int = 60000
    train_size: int = 50000
    dataDimensions: list[int] = [32, 32, 3]

    def __init__(self) -> None:
        super().__init__()

    def load_external(self):
        self.load_from_tensorflow()

    def load_from_tensorflow(self):
        """
        Invoke the calls to tensorflow that automatically download and cache the
        dataset.
        """
        import tensorflow as tf
        # "Fine" label_mode for 100 classes as in MIA paper
        (x_train, y_train), (x_test, y_test) = \
            tf.keras.datasets.cifar100.load_data(label_mode='fine')

        self.features: NDArray = np.append(x_train, x_test, axis=0)
        self.labels: NDArray = np.append(y_train, y_test, axis=0)
