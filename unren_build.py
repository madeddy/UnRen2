#!/usr/bin/env python3

"""
This is a helper app for "UnRen" to collect, pack and embed different module files
into the main script.

Requirements: py 3.6+
Step 1:
Reads the content of RenPy script files and stores it temporary. Now are the
tool files collected by a dir walker, filepath and data are collected as pairs in
a dict. The dict is pickled (#1), base64 encoded (#2) and also stored.

The different data streams are now embedded in prepaired placeholder locations in
the main script.
#1 The encoder func needs `bytes-like`
#2 Output of compression algorythms would confuse python(error).

Step 2:
Embeds the previously prepaired python script into a Win command file.
"""

import sys
import argparse
from marshal import dumps
from binascii import b2a_base64
from pathlib import Path as pt

import _ur_vers

__title__ = 'UnRen builder'
__license__ = 'Apache-2'
__author__ = 'madeddy'
__status__ = 'Development'
__version__ = _ur_vers.__version__


class UrBuild:
    """
    Constructs from raw base files and different code parts the final
    executable scripts.
    (Class acts rather as wrapper for easier var sharing without global.)
    """

    name = __title__

    tools_pth_py2 = pt('ur_tools/t_py2').resolve(strict=True)
    tools_pth_py3 = pt('ur_tools/t_py3').resolve(strict=True)
    tool_plh = b'tool_placeholder'
    vers_plh = b'vers_placeholder'
    logo_plh = b'ur_logo_placeholder'
    batch_plh = b'batch_placeholder'

    ur_logo = r"""
       __  __        ____                  ___
      / / / /____   / __ \ ___   ____     |__ \
     / / / // __ \ / /_/ // _ \ / __ \    __/ /
    / /_/ // / / // _, _//  __// / / /   / __/
    \____//_/ /_//_/ |_| \___//_/ /_/   /____/  """

    raw_py2 = pt('ur_raw_27.py').resolve(strict=True)
    raw_py3 = pt('ur_raw_36.py').resolve(strict=True)
    base_cmd = pt('ur_base.cmd').resolve(strict=True)

    cpl_py2 = pt('unren_py27.py')
    cpl_py3 = pt('unren_py36.py')
    dst_cmd2 = pt('unren_27.cmd')
    dst_cmd3 = pt('unren_36.cmd')

    def __init__(self):
        self.tool_fl_lst = []
        self.emb_stream = None
        self._tmp = None

    @staticmethod
    def write_outfile(dst_file, data):
        """Writes a new file with given content."""
        out_pt = pt('operable').joinpath(dst_file).resolve()
        with out_pt.open('wb') as ofi:
            ofi.write(data)

    def embed_vers(self):
        """Embeds current project version number in dest file."""
        self.emb_in_stream(UrBuild.vers_plh, __version__.encode())

    def emb_in_stream(self, placeholder, embed_data):
        """Embed's the given data in target datastream."""
        self._tmp = self._tmp.replace(placeholder, embed_data)

    def read_srcdata(self, src_file):
        """Opens a given file and returns the content as bytes type."""
        with src_file.open('rb') as ofi:
            self._tmp = ofi.read()

    def stream_encoder(self, raw_str):
        """Packs a raw datastream to a pickled and encoded stream."""
        # To reduce output size a compressor *¹ can be used between pickle and
        # encoder; As last element it is NOT py-code safe
        # *¹ Use just a archive type(zlib, bz2...) renpy supports!
        return b2a_base64(dumps(raw_str, 2))

    # Step 1b; pack tools to py
    def stream_packer(self, src_pth):
        """Collects tool files in a variable and passes it in the encoder."""
        store = {}
        for f_item in self.tool_fl_lst:
            with f_item.open('rb') as ofi:
                d_chunk = ofi.read()

            rel_fp = f_item.relative_to(src_pth)
            store[str(rel_fp)] = d_chunk

        self.tool_fl_lst.clear()
        return self.stream_encoder(store)

    # Step 1a; find tools
    def path_search(self, search_path):
        """Walks the tools directory and collects a list of py files."""
        for entry in search_path.rglob('*.py'):
            self.tool_fl_lst.append(entry.resolve())

    # Step 1: Make py
    def build_py(self):
        """Constructs a stream and embeds the tools and other data in it.
        Writes the complete stream then as new py file. """
        py_vers_sets = ((UrBuild.tools_pth_py2, UrBuild.raw_py2, UrBuild.cpl_py2),
                        (UrBuild.tools_pth_py3, UrBuild.raw_py3, UrBuild.cpl_py3))

        # we loop over the different pth/src/dst version sets
        for tool_pth, raw_py, cpl_py in py_vers_sets:
            self.path_search(tool_pth)
            tool_stream = self.stream_packer(tool_pth)
            logo_stream = self.stream_encoder(UrBuild.ur_logo)

            self.read_srcdata(raw_py)
            self.emb_in_stream(UrBuild.tool_plh, tool_stream)
            self.emb_in_stream(UrBuild.logo_plh, logo_stream)
            self.embed_vers()
            self.write_outfile(cpl_py, self._tmp)

    # Step 2: Make cmd  - optional (just for the win cmd)
    def build_cmd(self):
        """Constructs the py stream and embeds it in the cmd file."""
        cmd_vers_set = ((UrBuild.cpl_py2, UrBuild.dst_cmd2),
                        (UrBuild.cpl_py3, UrBuild.dst_cmd3))

        for cpl_py, dst_cmd in cmd_vers_set:
            self.read_srcdata(cpl_py)
            # The next step is needed because _tmp holds now the src data but
            # is after overwritten by dst file stream
            cpl_py_stream = self._tmp

            self.read_srcdata(UrBuild.base_cmd)
            self.emb_in_stream(UrBuild.batch_plh, cpl_py_stream)
            self.embed_vers()
            self.write_outfile(dst_cmd, self._tmp)


def parse_args():
    """Provides argument parsing functionality on CLI. Obviously."""
    aps = argparse.ArgumentParser(
        description="Helper app to build the release versions of UnRen.",
        epilog="")
    switch = aps.add_mutually_exclusive_group(required=True)
    switch.add_argument('-p', '--makepy',
                        dest='task',
                        action='store_const',
                        const='part_1',
                        help="Executes step 1: embeds the tools into the raw Python scripts.")
    switch.add_argument('-c', '--makecmd',
                        dest='task',
                        action='store_const',
                        const='part_2',
                        help="Executes step 2: embeds the Python script into the cmd.")
    aps.add_argument('--version',
                     action='version',
                     version=f"%(prog)s : { __title__} {__version__}")
    args = aps.parse_args()
    return args


def build_main(cfg):
    """This executes all program steps."""
    if not sys.version_info[:2] >= (3, 6):
        raise Exception("Must be executed in Python 3.6 or later.\n"
                        "You are running {}".format(sys.version))

    urb = UrBuild()
    # Step 1 embed rpy cfg & tools in the raw py files
    if cfg.task == 'part_1':
        urb.build_py()
        print("\nUnRen builder:>> Embed `tools in py` task completed!\n")
    # Step 2 - embed py files in the cmd file
    elif cfg.task == 'part_2':
        urb.build_cmd()
        print("\nUnRen builder:>> Embed `py in cmd` task completed!\n")


if __name__ == '__main__':
    build_main(parse_args())
