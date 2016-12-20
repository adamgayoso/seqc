import os
import shutil
from jinja2 import Environment, PackageLoader
from collections import OrderedDict, namedtuple
import numpy as np
import pandas as pd
from seqc import plot


ImageContent = namedtuple('ImageContent', ['image', 'caption', 'legend'])

TextContent = namedtuple('TextContent', ['text'])

DataContent = namedtuple('DataContent', ['keys', 'values'])


class Section:

    __slots__ = ['name', 'content', 'filename']

    def __init__(self, name, content, filename):
        """

        :param str name: Section name
        :param OrderedDict content: ordered dictionary containing keys corresponding to
          header information and values which are Content classes
        """
        self.name = name
        self.content = content
        self.filename = filename

    def render(self, prefix='', link_sections=None, index_section=None):
        """renders this sub-section

        :param str prefix: prefix for the rendered html file
        :param list link_sections: list of Section objects to link to in the sidebar
          of this section
        :param index_section: section which serves as index.html file
        :return None:
        """
        env = Environment(loader=PackageLoader('seqc.summary', 'templates'))
        section_template = env.get_template('section_content.html')
        if link_sections is None:
            link_sections = [self]
        rendered_section = section_template.render(
            sections=link_sections, section=self,
            index_section_link=index_section.filename)
        with open(prefix + self.filename, 'w') as f:
            f.write(rendered_section)

    @classmethod
    def from_alignment_summary(cls, alignment_summary, filename):
        """Create a summary section from an alignment summary file produced by STAR

        :param str alignment_summary: STAR alignment summary
        :param str filename: html file name for this section
        :return:
        """
        with open(alignment_summary, 'r') as f:
            data = f.read()
        categories = OrderedDict()

        def split_lines(block):
            keys, values = zip(*(l.split('|') for l in block.split('\n') if '|' in l))
            keys = [k.strip() for k in keys if k.strip()]
            values = [v.strip() for v in values if v.strip()]
            return DataContent(keys, values)

        # time and input read numbers
        time, _, data = data.partition('UNIQUE READS:')
        categories['Run Time'] = split_lines(time)

        # unique reads and splicing
        splicing, _, data = data.partition('MULTI-MAPPING READS:')
        categories['Unique Reads and Splicing'] = split_lines(splicing)

        # multimapping reads
        multimapping, _, unmapped = data.partition('UNMAPPED READS:')
        categories['Multimapping Reads'] = split_lines(multimapping)
        categories['Unmapped Reads'] = split_lines(unmapped)

        return cls('STAR Alignment Summary', categories, filename)

    @classmethod
    def from_status_filters(cls, ra, filename):
        """run after ReadArray is initialized and initial_filtering() has been run.

        :param ra: ReadArray object
        :param str filename: html file name for this section
        :return cls: Section containing initial filtering results
        """
        # todo replace whitespace characters with html equiv, add space b/w lines
        description = (
            'Initial filters are run over the sam file while our ReadArray database is '
            'being constructed. These filters indicate heuristic reasons why reads '
            'should be omitted from downstream operations:\n'
            'no gene: Regardless of the read\'s genomic alignment status, there was no '
            'transcriptomic alignment for this read.\n'
            'gene not unique: this indicates that more than one alignment was recovered '
            'for this read. We attempt to resolve these multi-alignments downstream. '
            'primer missing: This is an in-drop specific filter, it indices that the '
            'spacer sequence could not be identified, and thus neither a cell barcode '
            'nor an rmt were recorded for this read.\n'
            'low poly t: the primer did not display enough t-sequence in the primer '
            'tail, where these nucleotides are expected. This indicates an increased '
            'probability that this primer randomly primed, instead of hybridizing with '
            'the poly-a tail of an mRNA molecule.')
        description_section = TextContent(description)

        keys = ('length of read array',  'no gene', 'gene not unique', 'primer missing', 'low poly t')
        values = (
            len(ra.data),
            np.sum(ra.data['status'] & ra.filter_codes['no_gene'] > 0),
            np.sum(ra.data['status'] & ra.filter_codes['gene_not_unique'] > 0),
            np.sum(ra.data['status'] & ra.filter_codes['primer_missing'] > 0),
            np.sum(ra.data['status'] & ra.filter_codes['low_polyt'] > 0)
        )
        data_section = DataContent(keys, values)
        return cls(
            'Initial Filtering',
            {'Description': description_section, 'Results': data_section},
            filename)

    @classmethod
    def from_cell_barcode_correction(cls, ra, filename):
        """Status page for cell barcode correction

        later, should add a figure for error rates, which will need to be returned by
        ra.apply_barcode_correction()

        :param ra:
        :param str filename: html file name for this section
        :return:
        """
        description = 'description for cell barcode correction'  # todo implement
        description_section = TextContent(description)
        data_section = DataContent(
            ['cell error'],
            [np.sum(ra.data['status'] & ra.filter_codes['cell_error'] > 0)])
        return cls(
            'Cell Barcode Correction',
            {'Description': description_section, 'Results': data_section},
            filename)

    @classmethod
    def from_rmt_correction(cls, ra, filename):
        """Status page for error correction

        For now, returns the number of errors returned and a description of the rationale

        :param ra:
        :param str filename: html file name for this section
        :return:
        """

        description = 'description for rmt correction'  # todo implement
        description_section = TextContent(description)
        data_section = DataContent(
            ['rmt error'],
            [np.sum(ra.data['status'] & ra.filter_codes['rmt_error'])])
        return cls(
            'RMT Barcode Correction',
            {'Description': description_section, 'Results': data_section},
            filename)

    @classmethod
    def from_resolve_multiple_alignments(cls, results, filename):
        """

        reports the number of corrected alignments

        :param dict results:
        :param str filename: html file name for this section
        :return:
        """
        description = 'description for multialignment correction'  # todo implement
        description_section = TextContent(description)
        keys, values = zip(*results.items())
        data_section = DataContent(keys, values)
        return cls(
            'Multialignment Resolution',
            {'Description': description_section, 'Results': data_section},
            filename)

    @classmethod
    def from_cell_filtering(cls, figure_path, filename):
        """

        This is the figure, but it needs a caption!

        :param str figure_path:
        :param str filename: html file name for this section
        :return:
        """
        description = 'description for cell filtering'  # todo implement
        description_section = TextContent(description)
        image_legend = 'image legend'  # todo implement
        image_section = ImageContent(figure_path, 'cell filtering figure', image_legend)
        return cls(
            'Cell Filtering',
            {'Description': description_section, 'Results': image_section},
            filename)

    @classmethod
    def from_final_matrix(cls, counts_matrix, figure_path, filename):
        """Create a histogram of cell sizes, a tSNE projection, and a diffusion map.

        save this data in a .h5 file accessible to pandas.

        :param filename:
        :param figure_path:
        :param pd.DataFrame counts_matrix:
        :return:
        """
        plot.Diagnostics.cell_size_histogram(counts_matrix, save=figure_path)
        image_legend = 'histogram legend'
        image_section = ImageContent(figure_path, 'cell size figure', image_legend)
        return cls('Cell Summary',
                   {'Library Size Distribution': image_section},
                   filename)

    @classmethod
    def from_run_time(cls, log_file, filename):
        """

        :param filename:
        :param log_file:  seqc log file
        :return:
        """
        with open(log_file) as f:
            log = f.readlines()
        text_section = TextContent('<br>'.join(log))
        return cls('SEQC Log', {'Log Content': text_section}, filename)

    @classmethod
    def from_basic_clustering_and_projection(cls):
        """What if anything do we want to do here?

        # parameterize (default = True?)
        user could specify desire for median norm, PCA + tsne.

        :return:
        """
        raise NotImplementedError

    @classmethod
    def from_overall_yield(cls):
        """

        % losses from original yield summary, can wait.

        :return:
        """
        raise NotImplementedError


class Summary:

    def __init__(self, archive_name, sections, index_section=None):
        """

        :param str archive_name: filepath for the archive to be constructed
        :param list sections: dictionary of str filename: Section objects
        :param index_section: section to be produced as the index.html page.
        """
        self.archive_name = archive_name
        self.sections = sections
        self.reference_directory = os.path.dirname(__file__)
        self.index_section = index_section

    def prepare_archive(self):
        """

        :return:
        """
        if os.path.isdir(self.archive_name):
            shutil.rmtree(self.archive_name)
        shutil.copytree(self.reference_directory, self.archive_name)

    def import_image(self, image_path):
        filename = os.path.split(image_path)[1]
        shutil.copy(image_path, self.archive_name + '/img/' + filename)

    def render(self):
        """loop over sections and render them to filename keys within archive_name

        :return str zipped_archive_location:
        """
        html_location = self.archive_name + '/html/'
        self.index_section.render(html_location, self.sections, self.index_section)
        for section in self.sections:
            section.render(html_location, self.sections, self.index_section)
        # todo this is not currently working.
        # os.symlink(html_location + self.index_section.filename,
        #            self.archive_name + '/index.html')

    def compress_archive(self):
        root_dir, _, base_dir = self.archive_name.rpartition('/')
        shutil.make_archive(
            self.archive_name, 'gztar', root_dir, base_dir)
        return self.archive_name + '.tar.gz'