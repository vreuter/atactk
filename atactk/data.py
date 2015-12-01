#
# atactk: ATAC-seq toolkit
#
# Copyright 2015 The Parker Lab at the University of Michigan
#
# Licensed under Version 3 of the GPL or any later version
#


"""
Code for reading and manipulating data commonly used in ATAC-seq pipelines.
"""

from __future__ import print_function

import csv
import gzip
import sys


NUCLEOTIDE_COMPLEMENTS = {
    "A": "T",
    "C": "G",
    "G": "C",
    "N": "N",
    "T": "A",
    "a": "t",
    "c": "g",
    "g": "c",
    "n": "n",
    "t": "a",
}


class ExtendedFeature(object):
    """A feature plus a fixed extended region, usually read from a BED file.

    You can define the region by passing the `extension` parameter to the constructor, e.g.::

        feature = ExtendedFeature(extension=100, **bed_record)

    You can also move features on the reverse strand upstream with `reverse_feature_shift`::

        feature = ExtendedFeature(extension=100, reverse_feature_shift=1 **bed_record)

    Most of :class:`ExtendedFeature`'s attributes map directly to BED
    format fields. Some of them aren't of course used here, but we
    accept them when parsing input files. Where our names for the
    fields differ, the name in the BED format description at
    https://genome.ucsc.edu/FAQ/FAQformat.html is included in
    parentheses below.

    Attributes
    ----------

    reference: str
        The reference sequence on which the feature is located. (``chrom``)
    feature_start: int
        The starting position of the feature in the reference sequence, zero-based. (``chromStart``)
    feature_end: int
        The ending position of the feature in the reference sequence, which is one past the last base in the feature. (``chromEnd``)
    name: str
        The name of the feature.
    score: float
        A numeric score.
    strand: str
        Either ``+`` or ``-``.
    thick_start: int
        The starting position at which the feature would be drawn thickly. (``thickStart``)
    thick_end: int
        The ending position at which the feature would be drawn thickly. (``thickEnd``)
    color: str
        A string representing the RGB color with which the feature would be drawn. (``itemRgb``)
    block_count: int
        The number of blocks in the feature. (``blockCount``)
    block_sizes: str
        A comma-separated list of the sizes of blocks. (``blockSizes``)
    block_starts: str
        A comma-separated list of the starting positions of blocks, relative to the start of the feature. (``blockStarts``)

    """

    def __init__(self, reference=None, start=None, end=None, name=None, score=0, strand=None, thick_start=None, thick_end=None, color='0,0,0', block_count=None, block_sizes=None, block_starts=None, extension=100, reverse_feature_shift=0):

        # required BED fields
        self.reference = reference
        self.feature_start = int(start)
        self.feature_end = int(end)

        # optional BED fields
        self.name = name
        self.score = float(score)
        self.strand = strand
        self.thick_start = thick_start
        self.thick_end = thick_end
        self.color = color
        self.block_count = block_count
        self.block_sizes = block_sizes
        self.block_starts = block_starts

        # region adjustments
        self.extension = int(extension)
        self.reverse_feature_shift = reverse_feature_shift
        self.is_reverse = strand == '-'
        self.region_start = self.feature_start - self.extension
        self.region_end = self.feature_end + self.extension
        if self.is_reverse and reverse_feature_shift > 0:
            self.region_start -= reverse_feature_shift
            self.region_end -= reverse_feature_shift

    def __str__(self):
        return '\t'.join(str(attribute or '') for attribute in [
            self.reference,
            self.feature_start,
            self.feature_end,
            self.name,
            self.score,
            self.strand,
            self.thick_start,
            self.thick_end,
            self.color,
            self.block_count,
            self.block_sizes,
            self.block_starts,
            self.extension,
            self.reverse_feature_shift
        ])


def complement(seq):
    """
    Return the complement of the supplied nucleic sequence.

    Nucleic of course implies that the only recognized bases are A, C,
    G, T and N. Case will be preserved.

    Parameters
    ----------
    seq: str
        A nucleic sequence.

    Returns
    -------
    str
        The complement of the given sequence.
    """
    return ''.join(NUCLEOTIDE_COMPLEMENTS[base] for base in seq)


def reverse_complement(seq):
    """
    Return the reverse complement of the supplied nucleic sequence.

    Parameters
    ----------
    seq: str
        A nucleic sequence.

    Returns
    -------
    str
        The reverse complement of the given sequence.

    See also
    --------
    :func:`~atactk.data.complement`
    """
    return complement(reversed(seq))


def open_maybe_gzipped(filename):
    """
    Open a possibly gzipped file.

    Parameters
    ----------
    filename: str
        The name of the file to open.

    Returns
    -------
    file
        An open file object.
    """
    with open(filename, 'rb') as test_read:
        byte1, byte2 = ord(test_read.read(1)), ord(test_read.read(1))
        if byte1 == 0x1f and byte2 == 0x8b:
            f = gzip.open(filename, mode='rt')
        else:
            f = open(filename, 'rt')
    return f


def read_features(filename, extension=100, reverse_feature_shift=0, feature_class=ExtendedFeature):
    """Return a generator of :class:`ExtendedFeature` instances from the named BED file.

    Parameters
    ----------
    filename: str
        The (optionally gzipped) BED file from which to read features.
    extension: int
        The number of bases to score on either side of each feature.
    reverse_feature_shift: int
        If not zero, regions around features on the reverse strand will be shifted upstream by this number of bases.
    feature_class: class
        Each row of the BED file will be instantiated with this class.

    Yields
    ------
    feature
        An :class:`ExtendedFeature` instance for each row of the BED file.
    """

    mimetype = None
    bed_fieldnames = [
        'reference',
        'start',
        'end',
        'name',
        'score',
        'strand',
        'thick_start',
        'thick_end',
        'color',
        'block_count',
        'block_sizes',
        'block_starts'
    ]
    source = open_maybe_gzipped(filename)
    reader = csv.DictReader(source, fieldnames=bed_fieldnames, dialect='excel-tab')
    for row in reader:
        yield feature_class(extension=extension, reverse_feature_shift=reverse_feature_shift, **row)


def filter_aligned_segments(aligned_segments, include_flags, exclude_flags, quality, verbose=False):
    """
    Filter aligned segments using SAM flags and mapping quality.

    Parameters
    ----------
    aligned_segments: list
        Aligned reads to filter.
    include_flags: list
        Reads matching any include flag will be returned.
    exclude_flags: list
        Reads matching any exclude flag will not be returned.
    quality: int
        Only reads with at least this mapping quality will be returned.
    verbose: bool
        Be more communicative.

    Returns
    -------
    filtered_aligned_segments: list
        The set of the aligned segments supplied to the function which
        meet the specified criteria.

    Examples
    --------

    You probably want `include_flags` of [83, 99, 147, 163] and
    `exclude_flags` of [4, 8].

    Flag 4 means the read is unmapped, 8 means the mate is unmapped.

    Properly paired and mapped forward aligned segments have flags in [99, 163]

    99:
       -   1: read paired
       -   2: read mapped in proper pair
       -  32: mate reverse strand
       -  64: first in pair

    163:
       -   1: read paired
       -   2: read mapped in proper pair
       -  32: mate reverse strand
       - 128: second in pair

    Properly paired and mapped reverse aligned segments have flags in [83, 147].

    83:
       -   1: read paired
       -   2: read mapped in proper pair
       -  16: read reverse strand
       -  64: first in pair

    147:
       -   1: read paired
       -   2: read mapped in proper pair
       -  16: read reverse strand
       - 128: second in pair
    """

    filtered_aligned_segments = [a for a in aligned_segments if all([
        a.mapping_quality >= quality,
        any(map(lambda f: (a.flag & f) == f, include_flags)),
        all(map(lambda f: (a.flag & f) == 0, exclude_flags))
    ])]
    return filtered_aligned_segments


def make_fastq_pair_reader(fastq_file1, fastq_file2):
    """
    Return a generator producing pairs of records from two FASTQ files.

    The intent is to produce read pairs from paired-end sequence data.

    Parameters
    ----------
    fastq_file1: str
        The name of the first FASTQ file.

    fastq_file2: str
        The name of the second FASTQ file.

    Yields
    ------
    tuple
        A tuple containing two 4-element lists, one for each FASTQ
        record, representing the ID, sequence, comment, and quality lines.
    """

    mimetype = None
    f1 = open_maybe_gzipped(fastq_file1)
    f2 = open_maybe_gzipped(fastq_file2)
    while True:
        yield (
            [
                next(f1).strip(),  # name
                next(f1).strip(),  # sequence
                next(f1).strip(),  # comment ('+' line)
                next(f1).strip()   # quality
            ],
            [
                next(f2).strip(),  # name
                next(f2).strip(),  # sequence
                next(f2).strip(),  # comment ('+' line)
                next(f2).strip()   # quality
            ],
        )
