import sys
import os

this_module = os.path.abspath(sys.modules[__name__].__file__)
parent_dir = os.path.dirname(os.path.dirname(this_module))
sys.path.append(parent_dir)


if __name__ == "__main__":
    """Grabs args for when this module is run as a script
    """
    # TODO: convert to argparse. not doing that yet, because it is not included
    # in python until 2.7... could do optparse...
    assert len(sys.argv) > 1, "You must pass a command"
    command = sys.argv[1]

    if command == 'send':
        import gozbruh.zbrush_tools
        gozbruh.zbrush_tools.ZBrushToMayaClient.send(sys.argv[2], sys.argv[3])
    elif command == 'serve':
        import gozbruh.zbrush_tools
        gozbruh.zbrush_tools.start_zbrush_server()
    elif command == 'install':
        gozbruh.utils
        # FIXME: I don't think this is used anymore...
        # We are performing a part of the installation
        gozbruh.utils.install_goz()
    elif command == 'start_server':
        # Start the server on a new background thread (i.e. don't call
        # communicate)
        # This code is reached from a ShellExecute command in
        # DefaultZScript.txt
        #
        # NOTE: it seems like there should be a better way to do this, but
        # to improve it we first have to confirm/dispell a few things that
        # this code seems to assume:
        #  - assumption 1: it is not possible to create a background
        #    sub-process in zscript using ShellExecute, and we therefore need
        #    to create a second shell sub-process from here.
        #  - assumption 2: an executable script that is pip installed on osx
        #    cannot import its corresponding python module given the env
        #    provided when calling ShellExecute from ZBrush, and we
        #    therefore need to make our modules double as executables
        import subprocess
        this_module = os.path.abspath(sys.modules[__name__].__file__)
        subprocess.Popen('python %s %s' % (this_module, 'serve'), shell=True)
