__authors__ = ["Tobias Marschall", "Marcel Martin", "Johannes Köster"]
__copyright__ = "Copyright 2015, Johannes Köster"
__email__ = "koester@jimmy.harvard.edu"
__license__ = "MIT"

import sys
import os
from os.path import join
from subprocess import call
from tempfile import mkdtemp
import hashlib
import urllib
from shutil import rmtree
from shlex import quote

from snakemake import snakemake


def dpath(path):
    """get path to a data file (relative to the directory this
	test lives in)"""
    return os.path.realpath(join(os.path.dirname(__file__), path))


SCRIPTPATH = dpath("../bin/snakemake")


def md5sum(filename):
    data = open(filename, 'rb').read()
    return hashlib.md5(data).hexdigest()


def is_connected():
    try:
        urllib.request.urlopen("http://www.google.com", timeout=1)
        return True
    except urllib.request.URLError:
        return False


def run(path,
        shouldfail=False,
        needs_connection=False,
        snakefile="Snakefile",
        subpath=None,
        check_md5=True, cores=3, **params):
    """
    Test the Snakefile in path.
    There must be a Snakefile in the path and a subdirectory named
    expected-results.
    """
    if needs_connection and not is_connected():
        print("Skipping test because of missing internet connection",
              file=sys.stderr)
        return False

    results_dir = join(path, 'expected-results')
    snakefile = join(path, snakefile)
    assert os.path.exists(snakefile)
    assert os.path.exists(results_dir) and os.path.isdir(
        results_dir), '{} does not exist'.format(results_dir)
    tmpdir = mkdtemp()
    try:
        config = {}
        if subpath is not None:
            # set up a working directory for the subworkflow and pass it in `config`
            # for now, only one subworkflow is supported
            assert os.path.exists(subpath) and os.path.isdir(
                subpath), '{} does not exist'.format(subpath)
            subworkdir = os.path.join(tmpdir, "subworkdir")
            os.mkdir(subworkdir)
            call('find {} -maxdepth 1 -type f -print0 | xargs -0 cp -t {}'.format(
                quote(subpath), quote(subworkdir)),
                 shell=True)
            config['subworkdir'] = subworkdir

        call('find {} -maxdepth 1 -type f -print0 | xargs -0 cp -t {}'.format(
            quote(path), quote(tmpdir)),
             shell=True)
        success = snakemake(snakefile,
                            cores=cores,
                            workdir=tmpdir,
                            stats="stats.txt",
                            snakemakepath=SCRIPTPATH,
                            config=config, **params)
        if shouldfail:
            assert not success, "expected error on execution"
        else:
            assert success, "expected successful execution"
            for resultfile in os.listdir(results_dir):
                if resultfile == ".gitignore" or not os.path.isfile(
                    os.path.join(results_dir, resultfile)):
                    # this means tests cannot use directories as output files
                    continue
                targetfile = join(tmpdir, resultfile)
                expectedfile = join(results_dir, resultfile)
                assert os.path.exists(
                    targetfile), 'expected file "{}" not produced'.format(
                        resultfile)
                if check_md5:
                    assert md5sum(targetfile) == md5sum(
                        expectedfile), 'wrong result produced for file "{}"'.format(
                            resultfile)
    finally:
        rmtree(tmpdir)


def test01():
    run(dpath("test01"))


def test02():
    run(dpath("test02"))


def test03():
    run(dpath("test03"), targets=['test.out'])


def test04():
    run(dpath("test04"), targets=['test.out'])


def test05():
    run(dpath("test05"))


def test06():
    run(dpath("test06"), targets=['test.bla.out'])


def test07():
    run(dpath("test07"), targets=['test.out', 'test2.out'])


def test08():
    run(dpath("test08"), targets=['test.out', 'test2.out'])


def test09():
    run(dpath("test09"), shouldfail=True)


def test10():
    run(dpath("test10"))


def test11():
    run(dpath("test11"))


def test12():
    run(dpath("test12"))


def test13():
    run(dpath("test13"))


def test14():
    run(dpath("test14"), snakefile="Snakefile.nonstandard", cluster="./qsub")


def test15():
    run(dpath("test15"))


def test_report():
    run(dpath("test_report"), check_md5=False)


def test_dynamic():
    run(dpath("test_dynamic"))


def test_params():
    run(dpath("test_params"))


def test_same_wildcard():
    run(dpath("test_same_wildcard"))


def test_conditional():
    run(dpath("test_conditional"),
        targets="test.out test.0.out test.1.out test.2.out".split())


def test_shell():
    run(dpath("test_shell"))


def test_temp():
    run(dpath("test_temp"),
        cluster="./qsub",
        targets="test.realigned.bam".split())


def test_keyword_list():
    run(dpath("test_keyword_list"))


def test_subworkflows():
    run(dpath("test_subworkflows"), subpath=dpath("test02"))


def test_globwildcards():
    run(dpath("test_globwildcards"))


def test_local_import():
    run(dpath("test_local_import"))


def test_ruledeps():
    run(dpath("test_ruledeps"))


def test_persistent_dict():
    run(dpath("test_persistent_dict"))


def test_url_include():
    run(dpath("test_url_include"), needs_connection=True)


def test_touch():
    run(dpath("test_touch"))


def test_config():
    run(dpath("test_config"))


def test_update_config():
    run(dpath("test_update_config"))


def test_wildcard_keyword():
    run(dpath("test_wildcard_keyword"))


def test_benchmark():
    run(dpath("test_benchmark"), check_md5=False)


def test_temp_expand():
    run(dpath("test_temp_expand"))


def test_wildcard_count_ambiguity():
    run(dpath("test_wildcard_count_ambiguity"))


def test_cluster_dynamic():
    run(dpath("test_cluster_dynamic"), cluster="./qsub")


def test_dynamic_complex():
    run(dpath("test_dynamic_complex"))


def test_srcdir():
    run(dpath("test_srcdir"))


def test_multiple_includes():
    run(dpath("test_multiple_includes"))


def test_yaml_config():
    run(dpath("test_yaml_config"))


def test_remote():
    try:
        import moto
        import boto
        import filechunkio

        # only run the remote file test if the dependencies
        # are installed, otherwise do nothing
        run(dpath("test_remote"), cores=1)
    except ImportError:
        pass


def test_cluster_sync():
    run(dpath("test14"),
        snakefile="Snakefile.nonstandard",
        cluster_sync="./qsub")


def test_symlink_temp():
    run(dpath("test_symlink_temp"), shouldfail=True)


def test_empty_include():
    run(dpath("test_empty_include"))


def test_script():
    run(dpath("test_script"))


def test_shadow():
    run(dpath("test_shadow"))


def test_until():
    run(dpath("test_until"),
        until=["leveltwo_first", # rule name
               "leveltwo_second.txt", # file name
               "second_wildcard"]) # wildcard rule


def test_omitfrom():
    run(dpath("test_omitfrom"),
        omit_from=["leveltwo_first", # rule name
                   "leveltwo_second.txt", # file name
                   "second_wildcard"]) # wildcard rule


def test_nonstr_params():
    run(dpath("test_nonstr_params"))


def test_delete_output():
    run(dpath("test_delete_output"))


def test_input_generator():
    run(dpath("test_input_generator"))


def test_symlink_time_handling():
    #See Snakefile for notes on why this fails on some systems
    if os.utime in os.supports_follow_symlinks:
        run(dpath("test_symlink_time_handling"))


def test_issue328():
    run(dpath("test_issue328"), forcerun=["split"])


def test_get_log_none():
    run(dpath("test_get_log_none"))


def test_get_log_both():
    run(dpath("test_get_log_both"))


def test_get_log_stderr():
    run(dpath("test_get_log_stderr"))


def test_get_log_stdout():
    run(dpath("test_get_log_stdout"))


def test_get_log_complex():
    run(dpath("test_get_log_complex"))


def test_spaces_in_fnames():
    run(dpath("test_spaces_in_fnames"),
        # cluster="./qsub",
        targets=["test bam file realigned.bam"],
        verbose=True,
        printshellcmds=True)


def test_static_remote():
    try:
        import moto
        import boto
        import filechunkio

        # only run the remote file test if the dependencies
        # are installed, otherwise do nothing
        run(dpath("test_static_remote"), cores=1)
    except ImportError:
        pass


def test_deferred_func_eval():
    run(dpath("test_deferred_func_eval"))


def test_format_params():
    run(dpath("test_format_params"), check_md5=True)


if __name__ == '__main__':
    import nose
    nose.run(defaultTest=__name__)
