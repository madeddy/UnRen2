#!/usr/bin/env python3

"""
This is a wrapper app around tools for the works with RenPy files. It provides multiple
functionality through a simple text menu.

Requirements: python 3.6+

Abbilitys are unpacking rpa files, decompiling rpyc(py2!) files and enabling respectively
reactivating diverse RenPy functions by script commands.

This app is partly based on the first `unren` from user `Sam` and uses some of the code.
"""


import sys
import argparse
from pathlib import Path as pt
import shutil
import tempfile
from marshal import loads
from binascii import a2b_base64
import textwrap
import atexit
from time import sleep


tty_colors = True
if sys.platform.startswith('win32'):
    try:
        from colorama import init
        init(autoreset=True)
    except ImportError:
        tty_colors = False


__title__ = 'UnRen'
__license__ = 'Apache 2.0'
__author__ = 'madeddy'
__status__ = 'Development'
__version__ = 'vers_placeholder'


class UrPh:
    """This class exists so we can hold all the placeholder/embed vars in a
    shared location at script head."""

    # WARNING: Never change the placeholder formating/indentation!
    _toolstream = """tool_placeholder"""
    _tuilogo_enc = """ur_logo_placeholder"""

    console_code = """
        # ######### Developer menu and console ####
            config.developer = True
            config.console = True
    """
    quick_code = """
        # ######### Quick save and load ###########
            try:
                config.underlay[0].keymap['quickLoad'] = QuickLoad()
                config.keymap['quickLoad'] = 'K_F5'
                config.underlay[0].keymap['quickSave'] = QuickSave()
                config.keymap['quickSave'] = 'K_F9'
            except:
                print("Error: Quicksave/-load not working.")
    """
    rollback_code = """
        # ######### Rollback ######################
            renpy.config.rollback_enabled = True
            renpy.config.hard_rollback_limit = 256
            renpy.config.rollback_length = 256

            def unren_noblock( *args, **kwargs ):
                return
            renpy.block_rollback = unren_noblock

            try:
                config.keymap['rollback'] = [ 'K_PAGEUP', 'repeat_K_PAGEUP', 'K_AC_BACK', 'mousedown_4' ]
            except:
                print("Error: Rollback not working.")
    """
    skip_code = """
        # ######### Skipping ######################
            _preferences.skip_unseen = True
            renpy.game.preferences.skip_unseen = True
            renpy.config.allow_skipping = True
            renpy.config.fast_skipping = True
    """


class UnRen(UrPh):
    """
    UnRen main class for all the core functionality. Arguments:
        Positional: {targetpath} takes a `pathlike` or string
        Keyword: {verbose=[0|1|2]} information output level; defaults to 1
    """
    # TODO IDEA: Maybe we can run this in tkinter window or such

    name = __title__
    verbosity = 1
    count = {'rpa_found': 0, 'rpyc_found': 0, 'rpyc_done': 0}
    decomp_lst = []
    # tty color code shorthands
    std, ul, red, gre, ora, blu, ylw, bblu, bred = '\x1b[0m', '\x1b[03m', '\x1b[31m', '\x1b[32m', '\x1b[33m', '\x1b[34m', '\x1b[93m', '\x1b[44;30m', '\x1b[45;30m' if tty_colors else ''

    tui_menu_logo = None
    tui_menu_opts = f"""
      {ul}Available Options:{std}

      {blu}1{std}  Extract all RPA packages
      {blu}2{std}  Decompile rpyc files

      {gre}5{std}  Enable Console and Developer Menu
      {gre}6{std}  Enable Quick Save and Quick Load
      {gre}7{std}  Force enable skipping of unseen content
      {gre}8{std}  Force enable rollback (scroll wheel)
      {std}s{std}  Options 5 to 8

      {ora}x{std}  Exit this application
    """
    menu_opts = {
        # '0': 'unused',
        '1': 'extract',
        '2': 'decompile',
        # '3': 'unused',
        # '4': 'unused',
        '5': 'console',
        '6': 'quick',
        '7': 'skip',
        '8': 'rollback',
        # '9': 'unused',
        's': 'all_snips',
        'x': '_exit'
    }

    def __init__(self, target='', verbose=None):
        if verbose is not None:
            UnRen.verbosity = verbose
        self.in_pth = pt(target)
        self.game_pth = None
        self._tmp_dir = None
        self.ur_tmp_dir = None
        self.rpakit = None
        # self.unrpyc = None  # NOTE: Unneeded till it supports py3
        atexit.register(self.cleanup)

    # FIXME: newline with textwrap... how?
    # test inf functionality some more
    @classmethod
    def inf(cls, inf_level, msg, m_sort=None):
        """Outputs by the current verboseness level allowed self.infos."""
        if cls.verbosity >= inf_level:  # self.tty ?
            if m_sort == 'warn':
                ind1 = f"{cls.name}:{cls.ylw} WARNING {cls.std}> "
                ind2 = " " * 13
            elif m_sort == 'err':
                ind1 = f"{cls.name}:{cls.red} ERROR {cls.std}> "
                ind2 = " " * 17
            else:
                ind1 = "{}:{} >> {}".format(cls.name, cls.gre, cls.std)
                ind2 = " " * 10
            print(textwrap.fill(msg, width=90, initial_indent=ind1,
                                subsequent_indent=ind2, replace_whitespace=False))

    @classmethod
    def telltale(cls, fraction, total, obj):
        """Returns a percentage-meter like output for use in tty."""
        return f"[{cls.bblu}{fraction / float(total):05.1%}{cls.std}] {str(obj):>4}"

    def import_tools(self):
        """This runs a deferred import of the tools due to the tools just usable
        after our script runs already."""
        try:
            sys.path.append(str(self.ur_tmp_dir))
            self.rpakit = __import__('rpakit', globals(), locals())

            # WARNING: Dont import `unrpyc`. As of Feb'21 still no py3 support!
            # self.unrpyc = __import__('unrpyc', globals(), locals())
        except ImportError:
            raise ImportError("Unable to import the tools from temp directory.")

    @staticmethod
    def stream_dec(enc_stream):
        """Returns given stream decoded, deserialized."""
        return loads(a2b_base64(enc_stream))

    def stream_handler(self):
        """Loads and unpacks the stream to usable source state in a tempdir."""
        UnRen.tui_menu_logo = self.stream_dec(UrPh._tuilogo_enc)
        store = self.stream_dec(UnRen._toolstream)

        self._tmp_dir = tempfile.TemporaryDirectory(prefix='UnRen.', suffix='.tmp')
        self.ur_tmp_dir = pt(self._tmp_dir.name).resolve(strict=True)

        for rel_fp, f_data in store.items():
            f_pth = self.ur_tmp_dir.joinpath(rel_fp)
            f_pth.parent.mkdir(parents=True, exist_ok=True)

            with f_pth.open('wb') as ofi:
                ofi.write(f_data)

    def path_check(self):
        """Path work like location checks."""
        # NOTE: There should be better location checks.

        # Without "in-path" we take the script loc, otherwise the given path
        # from CLI arg
        script_dir = pt(__file__).resolve(strict=True).parent if not self.in_pth \
            else self.in_pth.resolve(strict=True)

        # control print
        # print(f"script {script_dir}")
        # print(f"cwd {pt.cwd()}")

        if script_dir.joinpath("lib").is_dir() and script_dir.joinpath("renpy").is_dir():
            base_pth = script_dir
            # control print
            print("script_dir is base dir")
        elif script_dir.name == "game" and pt(script_dir).joinpath("cache").is_dir():
            base_pth = script_dir.parent
            # control print
            print("script_dir is game dir")
        else:
            raise FileNotFoundError(
                "The given target path is incorrect or Unren is not located in the "
                f"correct directory! Current dir is: > {script_dir}")

        self.game_pth = base_pth.joinpath("game")

        # control print
        # print(f"script_dir: {script_dir}  base: {base_pth}  type: {type(base_pth)}  gamepth: {self.game_pth}")

    def find_valid_files(self):
        """Determines if rpa and rpyc files are present in the gamedir."""
        for fln in self.game_pth.rglob("*"):
            if fln.suffix in ('.rpa', '.rpi'):
                UnRen.count["rpa_found"] += 1
            elif fln.suffix in ('.rpyc', '.rpymc'):
                self.decomp_lst.append(fln)
                UnRen.count["rpyc_found"] += 1

    def cleanup(self):
        # TODO: perhaps deleting the tempdir tree without shutil
        # shutil.rmtree(self.ur_tmp_dir)
        self._tmp_dir.cleanup()
        if not self.ur_tmp_dir.is_dir():
            self.inf(1, "Tempdir was successful removed.")
        else:
            self.inf(0, "Tempdir {} could not be removed!".format(self.ur_tmp_dir),
                     m_sort='err')

    def _exit(self):
        self.inf(0, "Exiting UnRen by user request.")
        for i in range(3, -1, -1):
            print(f"{UnRen.bred}{i}%{UnRen.std}", end='\r')
            sleep(1)
        sys.exit(0)

    @staticmethod
    def make_rpy_cfg(outfile):
        """Constructs the rpy config file and adds header code."""
        header_txt = """\
            # RenPy script file
            # Config changes; written by UnRen

            init 999 python:
        """.rstrip()
        with outfile.open('w') as ofi:
            ofi.write(textwrap.dedent(header_txt))

    # IDEA: Rework write config functionality to less complexity, fewer methods...
    def write_rpy_cfg(self, cfg_code, cfg_inf):
        """Writes given text to the file."""
        outfile = pt(self.game_pth).joinpath("unren_cfg.rpy").resolve()
        if not outfile.exists():
            self.make_rpy_cfg(outfile)

        with outfile.open('r+') as ofi:
            if cfg_code[12:40] in ofi.read():
                self.inf(1, "Option already active. Skipped.")
                return
            ofi.write(textwrap.dedent(cfg_code))
            self.inf(2, cfg_inf)

    def extract(self):
        """Extracts content from RenPy archives by use of Rpa Kit."""
        if UnRen.count["rpa_found"] == 0:
            self.inf(0, "Could not find any valid target files in the directory tree.", m_sort='warn')
            return
        rkm = self.rpakit.RkMain(self.game_pth, task="exp")
        rkm.rk_control()
        self.inf(2, "Extracting of RPA files done.")

        # we need to call this again after extract to collect new files
        self.find_valid_files()

    def decompile(self):
        """Decompiles RenPy script files."""
        # TODO: reactivate rpyc decompiler if py3 is supported
        self.inf(0, "For now `unrpyc` does not support python 3! Stay tuned for news on this.", m_sort='warn')

        # if UnRen.count["rpyc_found"] == 0:
        #     self.inf(0, "Could not find any valid target files in the directory tree.", m_sort='warn')
        #     return

        # while True:
        #     userinp = raw_input("Should already existing rpyc files be overwritten? Type  {}y/n{}: ".format(cls.gre, cls.std)).lower()  # noqa
        #     if userinp in "yn":
        #         break
        # ow = True if userinp == "y" else False

        # for dec_file in self.decomp_lst:
        #     self.inf(1, f"{self.telltale(UnRen.count['rpyc_done'], UnRen.count['rpyc_found'], dec_file)}")
        #     self.unrpyc.decompile_rpyc(dec_file, overwrite=ow)
        #     UnRen.count['rpyc_done'] += 1

        # self.inf(2, "Decompling of rpyc files done.")

    def console(self):
        """Enables the RenPy console and developer menu."""
        console_inf = "Added access to developer menu and debug console with the \
        following keybindings: Console: SHIFT+O; Dev Menu: SHIFT+D"
        self.write_rpy_cfg(UnRen.console_code, console_inf)

    def quick(self):
        """Enable Quick Save and Quick Load."""
        quick_inf = "Added ability to quick-load and -save with the following \
        keybindings: Quick Save: F5; Quick Load: F9"
        self.write_rpy_cfg(UnRen.quick_code, quick_inf)

    def rollback(self):
        """Enable rollback fuctionality."""
        rollback_inf = "Rollback with use of the mousewheel is now activated."
        self.write_rpy_cfg(UnRen.rollback_code, rollback_inf)

    def skip(self):
        """Enables skipping of unseen content."""
        skip_inf = "Added the abbility to skip all text using TAB and CTRL keys."
        self.write_rpy_cfg(UnRen.skip_code, skip_inf)

    def all_snips(self):
        """Runs all available options."""
        runall_l = {getattr(self, val) for key, val in UnRen.menu_opts.items()
                    if key in "5678"}
        [item() for item in runall_l]
        self.inf(2, "All requested options finished.")

    def main_menu(self):
        """Displays a console text menu and allows choices from the available
        options."""
        while True:
            print("\n", UnRen.tui_menu_logo, f"Version {__version__}\n", UnRen.tui_menu_opts, "\nType at the prompt the corresponding key character to the task you want to execute.")
            userinp = input("Task: ").lower()
            if userinp in UnRen.menu_opts.keys():
                self.inf(1, "Input is valid. Continuing with option "
                         f"{UnRen.menu_opts[userinp]} ...")
                break
            self.inf(0, "\x1b[0;30;43mInvalid\x1b[0m key used. Try again.")

        meth_call = getattr(self, UnRen.menu_opts[userinp])
        meth_call()
        self.main_menu()


def parse_args():
    """Provides argument parsing functionality on CLI. Obviously."""
    aps = argparse.ArgumentParser(description="A app which provides different functions for the works with RenPy files.", epilog="")
    aps.add_argument('targetpath',
                     type=str,
                     help="Base path of the target game to work with.")
    aps.add_argument('--verbose',
                     metavar='level [0-2]',
                     type=int,
                     choices=range(0, 3),
                     help='Amount of info output. 0:none, 2:much, default:1')
    aps.add_argument('--version',
                     action='version',
                     version=f'%(prog)s : { __title__} {__version__}')
    return aps.parse_args()


def ur_main(cfg):
    """This executes all program steps."""
    if not sys.version_info[:2] >= (3, 6):
        raise Exception("Must be executed in Python 3.6 or later.\n"
                        "You are running {}".format(sys.version))

    _ur = UnRen(target=cfg.targetpath, verbose=cfg.verbose)

    _ur.path_check()
    _ur.find_valid_files()

    _ur.stream_handler()
    _ur.import_tools()

    _ur.main_menu()

    print("\nMain function was irregular completed! This should not happen.\n")


if __name__ == '__main__':
    ur_main(parse_args())
