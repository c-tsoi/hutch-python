"""Module to help create the epicsArch file that will be read by the DAQ."""
import argparse
import logging
import os
import subprocess
import sys

from .constants import EPICS_ARCH_FILE_PATH
from .qs_load import get_qs_client, pull_cds_items

logger = logging.getLogger(__name__)
logging.basicConfig(level="INFO")


def _create_parser():
    """Argument Parser Setup. Define shell commands."""
    parser = argparse.ArgumentParser(description='Create an epicsArch file '
                                                 'from the Quesionnaire')

    parser.add_argument('experiment', help='Experiment name to'
                        ' create the epicsArch file from. E.g.: xpplv6818')

    parser.add_argument('--hutch', action="store",
                        help='Overrides hutch detection from the experiment '
                        'name. E.g.: xpp', default=None)

    parser.add_argument('--path', action="store",
                        help='Directory path where to create the epicsArch '
                        'file. E.g.: /path/to/the/directory/', default=None)

    parser.add_argument('--dry-run', action='store_true', default=False,
                        help='Print to stdout what would be written in the '
                        'archFile.')

    parser.add_argument('--level', '-l', required=False, type=str, default="INFO",
                        help='Show the debug logging stream')

    parser.add_argument('--cds-items', action='store_true', default=None,
                        help="Pulls all data from CDS tab. E.g.: xppx1003221 run21 X-10032")

    parser.add_argument('--link', '-sl', action='store_true', default=None, help="create softlink for experiement")
    return parser


def main():
    """Entry point."""
    parser = _create_parser()
    parsed_args = parser.parse_args()
    kwargs = vars(parsed_args)
    logger_setup(parsed_args)
    logger.debug("\nepicsarch-qs test script, git")
    create_arch_file(**kwargs)


def logger_setup(args):
    # Setting up the logger, to show the level when enabled
    logging.getLogger().addHandler(logging.NullHandler())
    shown_logger = logging.getLogger('epicsarch-qs')
    logger.setLevel(args.level)
    logger.debug("Logger Level: ", logger.getEffectiveLevel())
    logger.debug("Set logging level of %r to %r", shown_logger.name, args.level)


def create_arch_file(experiment, level=None, hutch=None, path=None, dry_run=False, update=False, cds_items=None, link=None):
    """
    Create an epicsArch file for the experiment.

    Parameter
    ---------
    experiment : str
        Experiment name, e.g.: `xpplv6818`
    hutch : str
        Hutch name if other than the one from the experiment, e.g.: `xcs`
    path : str
        Directory where to create the file if other than the default one which
        is `/cds/group/pcds/dist/pds/{}/misc/`
    dry_run : bool
        To indicate if only print to stdout the data that would be stored
        in the epicsArch file and not create the file.
    update : bool
        To look into the qsdata and update the epicsArch file instead of overwriting it.

    Examples
    --------
    Create the epicsArch file for experiment `xpplv6818`. If no `--path` or
    `--hutch` provided, write the file at the default path:
    `/cds/group/pcds/dist/pds/{}/misc/` whre {} is the hutch name from the
    experiment (`xpp`):

    >>> epicsarch-qs xpplv6818

    Would write: `/cds/group/pcds/dist/pds/xpp/misc/epicsArch_xpplv6818.txt`

    To change the path where you want to write the epicsArch file:

    >>> epicsarch-qs xpplv6818 --path /my/new/path/

    Would write: `/my/new/path/epicsArch_xpplv6818.txt`

    To change only the hutch name in the path:

    >>> epicsarch-qs xpplv6818 --hutch xcs

    Would write: `/cds/group/pcds/dist/pds/xcs/misc/epicsArch_xpplv6818.txt`

    To print to standard output what would be written in the epicsArch file:

    >>> epicsarch-qs xpplv6818 --dry-run
    """
    file_path = None
    if experiment and not dry_run:
        # set the path to write the epicsArch file to.
        if path:
            if path and not os.path.exists(path):
                raise OSError('Invalid path: %s' % path)
            file_path = path
        elif hutch:
            file_path = EPICS_ARCH_FILE_PATH.format(hutch.lower())
        elif cds_items:
            pull_cds_data(experiment)
            return
        elif link:
            update_file(exp_name=experiment, path=EPICS_ARCH_FILE_PATH.format(experiment[0:3]))
            create_softlink(experiment)
            return
        else:
            file_path = EPICS_ARCH_FILE_PATH.format(experiment[0:3])
        update_file(exp_name=experiment, path=file_path)
    elif dry_run:
        print_dry_run(experiment)


# def pull_cds_data(exp, run):
def pull_cds_data(exp):
    logger.debug("in client")
    # pull_cds_items(exp, run)
    pull_cds_items(exp)


def create_softlink(experiment):
    logger.debug("in softlink")
    # remove the old soft link and add a new one (update), *THIS HAS NOT BEEN TESTED YET*
    # this removes the softlink in the /cds/group/pcds/dist/pds/{}/misc/
    # rm_result = subprocess.run(['unlink', EPICS_ARCH_FILE_PATH.format(experiment[0:3]) + 'epicsArch_' + experiment[0:3].upper() + '_exp_specific.txt'])

    # This adds a new softlink in /cds/group/pcds/dist/pds/{}/misc/
    subprocess.run(['ln', '-sf', EPICS_ARCH_FILE_PATH.format(experiment[0:3]) + 'epicsArch_' + experiment + '.txt', EPICS_ARCH_FILE_PATH.format(experiment[0:3]) + 'epicsArch_' + experiment[0:3].upper() + '_exp_specific.txt'])


def check_for_duplicates(qs_data, af_data):

    """
    Check for duplicate PVs in the questionnaire, the code already throws a warning for duplicate aliases.
    If duplicates (PV or Alias) are found in the questionnaire throw error and prompt user to fix and re-run. If they are found in the epicsArch file then step through each match and update accordingly.

    Parameters
    ----------
    qs_data : list
    af_data : list

    Examples
    --------
    >>> epicsarch-qs xpplv6818 --dry-run

    Returns
    -------
    updatea_arch_list : list
        Updated list containing sorted alias, PVs.

    """

    """
    Part 1: Parse Data from the questionnaire and the archfile
    Part 2: Check the questionnaire for pv duplicates
    """

    # PART 1

    # Convert lists to dictionaries to sort as a key - value pair while also removing any whitespice in the aliases.

    # Questionnaire Data, removing whitespaces and newline chars
    qsDict = dict(zip(qs_data[::2], qs_data[1::2]))
    qsDict = {k.replace(" ", ""): v for k, v in qsDict.items()}
    qsDict = {k.replace("\n", ""): v for k, v in qsDict.items()}
    qsDict = {k: v.replace(" ", "") for k, v in qsDict.items()}
    qsDict = {k: v.replace("\n", "") for k, v in qsDict.items()}
    sorted_qsDict = dict(sorted(qsDict.items()))

    # If the archfile is not empty then clean it if not ,skip
    if len(af_data) > 0:
        # ArchFile Data, removing whitespaces and newline chars
        afDict = dict(zip(af_data[::2], af_data[1::2]))
        afDict = {k.replace(" ", ""): v for k, v in afDict.items()}
        afDict = {k.replace("\n", ""): v for k, v in afDict.items()}
        afDict = {k: v.replace(" ", "") for k, v in afDict.items()}
        afDict = {k: v.replace("\n", "") for k, v in afDict.items()}
        sorted_afDict = dict(sorted(afDict.items()))

    # PART 2

    # Check the questionaire for duplicate PVs
    # Making reverse multidict to help identify duplicate values in questionnaire.
    rev_keyDict = {}
    for key, value in sorted_qsDict.items():
        rev_keyDict.setdefault(value, list()).append(key)

    pvDuplicate = [key for key, values in rev_keyDict.items() if len(values) > 1]
    # Looking for duplicates of PVs in the questionaire
    # also print out the alias for PV, change removing to warning operater to remove dup then rerun
    for dup in pvDuplicate:
        logger.debug("!Duplicate PV in questionnaire!:" + str(dup))
        for value in rev_keyDict[dup][1:]:
            logger.debug("Found PV duplicate(s) from questionnaire: " + value + ", " + sorted_qsDict[value])
        raise Exception("Please remove duplicates and re-run script!")

    # Check to see if the archfile has any data in it
    if len(af_data) == 0:
        logger.debug("CFD: Case: no archfile given, returning cleaned questionnaire data\n")
        cleaned_qs_data = [x for item in sorted_qsDict.items() for x in item]
        return cleaned_qs_data

    # Once we have cleared any duplicates in the questionnaire we moving on to updating values according to the which field matches.

    # Checking for matching PVs in questionnaire and archfile
    # if the PV matches update the alias by removing the old key and making a new one
    for (k, val) in sorted_qsDict.items():
        # this looks up the key in the af Dictionary by finding the value
        foundKey = get_key(val, sorted_afDict)
        if k in sorted_afDict:
            logger.debug("!Alias Match in questionnaire and archfile! Updating PV: " + k + ", " + sorted_qsDict[k])
            sorted_afDict[k] = sorted_qsDict[k]
        elif foundKey:
            del sorted_afDict[foundKey]
            sorted_afDict[k] = val
            logger.debug("!PV Match in questionnaire and archfile! Updating Alias: " + k + ", " + val)

    sorted_afDict = dict(sorted(sorted_afDict.items()))
    updated_arch_list = [x for item in sorted_afDict.items() for x in item]
    logger.debug("\nUpdated Arch List:\n")
    logger.debug(updated_arch_list)
    return updated_arch_list


def read_archfile(exp_path):
    if os.path.exists(exp_path):
        with open(exp_path, "r") as experiment:
            lines = experiment.readlines()
        return lines
    else:
        raise OSError('ArchFile not found: %s' % exp_path)


def print_dry_run(exp_name):
    """
    Print to stdout the data that would be stored in the epicsArch file.

    Parameters
    ----------
    exp_name : str
        Experiment name, e.g.: xpplv6818

    Examples
    --------
    >>> epicsarch-qs xpplv6818 --dry-run
    """

    qs_data = get_questionnaire_data(exp_name)

    """
    Updating experiment file.
    """
    af_path = EPICS_ARCH_FILE_PATH.format(exp_name[0:3]) + 'epicsArch_' + exp_name + '.txt'
    af_data = read_archfile(af_path)
    if not os.path.exists(af_path):
        raise OSError('print_dry_run, invalid path: %s' % af_path)
    elif os.path.exists(af_path):
        updated_archFile = check_for_duplicates(qs_data, af_data)

        for item in updated_archFile:
            print(item)


def get_key(val, my_dict):
    for k, v in my_dict.items():
        if val == v:
            return k
    strError = ""
    return strError


def get_questionnaire_data(exp_name):
    """
    Return a list of items that would be written in the epicsArch file.

    Parameters
    ----------
    exp_name : str
        Experiment name, e.g.: xpplv6818

    Returns
    -------
    data_list : list
        List containing the names ans prefixes of items in the Questionnaire.
    """
    data_list = []
    items = get_items(exp_name)

    if items:
        for item in items:
            name = ''.join(('* ', item.name))
            data_list.append(name)
            data_list.append(item.prefix)
    return data_list


def get_items(exp_name):
    """
    Get all_items from Questionnaire.

    Parameters
    ----------
    exp_name : str
        Experiment name, e.g.: xpplv6818

    Returns
    -------
    items : list
        List of all_items from Questionnaire.
    """
    try:
        qs_client = get_qs_client(exp_name)
    except Exception as ex:
        logger.error('Failed to load the Questionnaire, %s', ex)
        raise ex
        sys.exit()
    items = qs_client.all_items
    if not items:
        logger.warning("No devices found in PCDS Questionnaire for %s",
                       exp_name)
        return
    return items


def update_file(exp_name, path):
    """
    Create a file with aliases and pvs from the questionnaire.

    Parameters
    ----------
    exp_name : str
        Experiment name, e.g.: `xpplv6818`
    path : str
        Directory where to create the epicsArch file.
    """
    qs_data = get_questionnaire_data(exp_name)

    logger.debug("UpdateFile: qs_data:\n" + str(qs_data))

    logger.debug("\nPath: " + str(path))
    af_path = str(path) + "epicsArch_" + str(exp_name) + ".txt"
    logger.debug("\nAF Path: " + str(af_path))
    exp_name = str(exp_name)
    file_path = ''.join((str(path), 'epicsArch_', str(exp_name), '.txt'))
    if not os.path.exists(str(path)):
        raise OSError('Invalid path: %s' % path)
    # if the path exists but archfile does not, create af and pull qsd
    elif os.path.exists(path) and not os.path.exists(af_path):
        logger.debug("UpdateFile: Path is valid, creating archfile\n")
        logger.debug('Creating epicsArch file for experiment: %s', exp_name)
        cleaned_data = check_for_duplicates(qs_data, {})

    # if the path and archfile exists, update af and pull
    elif os.path.exists(path) and os.path.exists(af_path):
        logger.debug("UpdateFile: Path exists and archfile exists\n")
        af_data = read_archfile(af_path)
        cleaned_data = check_for_duplicates(qs_data, af_data)

    # Write updates to the corresponding file
    with open(file_path, 'w') as f:
        for data in cleaned_data:
            try:
                f.write(f'{data}\n')
            except OSError as ex:
                logger.error('Could not write file %s, %s', file_path, ex)


if __name__ == '__main__':
    main()
