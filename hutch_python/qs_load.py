import logging
import os.path
import re
import sys
from configparser import ConfigParser, NoOptionError
from dataclasses import dataclass

import happi
from happi.loader import load_devices
from prettytable import PrettyTable
from psdm_qs_cli import QuestionnaireClient

from .utils import safe_load

try:
    from happi.backends.qs_db import QSBackend
except ImportError:
    # Optional because not available on windows
    QSBackend = None

logger = logging.getLogger(__name__)


# Annotation with dataclass, making struct to help organize cds objects in prettytable
@dataclass
class QStruct:
    alias: str
    pvbase: str
    pvtype: str


# def pull_cds_items(exp, run):
def pull_cds_items(exp):
    """
    Gather all user obejcts from the CDS tab in the questionnaire.
    Parse objects and sperate them based on type.
    Display them in the console vie PrettyTable.

    Parameters
    ----------
    exp: ``str``
        The experiment's name e.g. xppx1003221
    run: ''str''
        The run number e.g. run21
    ----------
    Outputs
    -------
        PrettyTable visualization of cds objects
    -------

    """
    """
    pull run data from questionnaire api, then take the data and sort it
    create Pretty Table instance and if the values from the run data contain pcdssetup
    then put them into a seperate dictionary as they are cds items
    """

    logger.debug('pull_cds_items:', exp)
    client = QuestionnaireClient()

    formatted_run_id = ''

    # handle formatting of proposal id, want: e.g. X-10032
    # Case -  Expected Format: e.g. xppx1003221
    if re.match('^.{4}[0-9]{7}$', exp):
        logger.debug("experiment name format")
        run_num = 'run'+exp[-2:]
        logger.debug('run num', run_num)
        run_id = str(exp[3:-2])
        logger.debug('run_id', run_id)
        formatted_run_id = run_id.capitalize()
        formatted_run_id = formatted_run_id[:1] + '-' + formatted_run_id[1:]

    elif re.match('[A-Z]{1}-[0-9]{5}$', exp) or re.match('^[A-Z]{2}[0-9]{2}$', exp):
        # Case - Proposal ID Format, have user enter run num manually
        logger.debug("run_id format")
        formatted_run_id = exp
        run_num = 'run' + str(input('Please enter run number: '))
    else:
        print('Unrecognized format, please follow the prompts to find experiment data.')

        run_num = input('Please enter run number: ')
        formatted_run_id = input('Please enter proposal ID: ')

    logger.debug('formatted run_id', formatted_run_id)
    logger.debug('run_num', run_num)

    matchedKey = ''

    try:
        runDetails_Dict = client.getProposalsListForRun(run_num)
        for key, vals in runDetails_Dict.items():
            logger.debug(formatted_run_id, key)
            if str(key) == str(formatted_run_id):
                logger.debug('matched key', key)
                matchedKey = key

    except Exception as e:
        print("An invalid https request, please check the run number, proposal id and experiment number:", e)
        sys.exit()

    # questionnaireFlag = False
    try:
        runDetails_Dict = client.getProposalDetailsForRun(run_num, matchedKey)
        # questionnaireFlag = True
    except (Exception, UnboundLocalError) as e:
        print('Could not find experiment, please check to make sure information is correct.', e)
        sys.exit()

    sorted_runDetails_Dict = dict(sorted(runDetails_Dict.items()))
    cds_dict = {}
    myTable = PrettyTable(["Alias", "PV Base", "Type"])

    for keys, vals in sorted_runDetails_Dict.items():
        if "pcdssetup" in keys:
            cds_dict[keys] = vals

    # names are as follows:
    # pcdssetup-motors, pcdssetup-areadet, pcdssetup-ao, pcdssetup-devs
    # pcdssetup-ps, pcdssetup-trig, pcdssetup-vacuum, pcdssetup-temp

    # iterate through all cds items and label them based on their type
    # use the struct members to identify

    displayList = []
    for k, v in cds_dict.items():
        if re.match('pcdssetup-motors.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvbase', k), '')
            displayList.append(QStruct(v, pv, "motors"))
        elif re.match('pcdssetup-areadet.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvbase', k), '')
            displayList.append(QStruct(v, pv, "areadet"))
        elif re.match('pcdssetup-ao.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvbase', k), '')
            displayList.append(QStruct(v, pv, "analog output"))
        elif re.match('pcdssetup-devs.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvbase', k), '')
            displayList.append(QStruct(v, pv, "other devices"))
        elif re.match('pcdssetup-ps.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvname', k), '')
            displayList.append(QStruct(v, pv, "power supplies"))
        elif re.match('pcdssetup-trig.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvbase', k), '')
            displayList.append(QStruct(v, pv, "triggers"))
        elif re.match('pcdssetup-vacuum.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvbase', k), '')
            displayList.append(QStruct(v, pv, "vacuum"))
        elif re.match('pcdssetup-temp.*-name', k):
            pv = cds_dict.get(re.sub('name', 'pvbase', k), '')
            displayList.append(QStruct(v, pv, "temperature"))
    # logger.debug("displayList", displayList)

    for struct in displayList:
        myTable.add_row([struct.alias, struct.pvbase, struct.pvtype])
    print(myTable)


def get_qs_objs(expname):
    """
    Gather user objects from the experiment questionnaire.

    Parameters
    ----------
    expname: ``str``
        The experiment's name from the elog

    Returns
    -------
    objs: ``dict``
        Mapping from questionnaire ``python name`` to loaded object.
    """
    logger.debug('get_qs_client(%s)', expname)
    with safe_load('questionnaire'):
        expname = expname.lower()
        qs_client = get_qs_client(expname)
        # Create namespace
        if not qs_client.all_items:
            logger.warning("No items found in PCDS Questionnaire for %s",
                           expname)
            return dict()
        dev_namespace = load_devices(*qs_client.all_items, pprint=False)
        return dev_namespace.__dict__
    return {}


def get_qs_client(expname):
    """
    Create a `happi.Client` from the experiment questionnaire.

    Connects to the questionnaire webservice via the ``happi`` ``QSBackend``
    using ``psdm_qs_cli`` to collect well-defined devices.

    There are two possible methods of authentication to the
    ``QuestionnaireClient``, ``Kerberos`` and ``WS-Auth``. The first is simpler
    but is not possible for all users, we therefore search for a configuration
    file named ``web.cfg``, either hidden in the current directory or the users
    home directory. This should contain the username and password needed to
    authenticate into the ``QuestionnaireClient``. The format of this
    configuration file is the standard ``.ini`` structure and should define the
    username and password like:

    .. code:: ini

        [DEFAULT]
        user = MY_USERNAME
        pw = MY_PASSWORD

    Parameters
    ----------
    expname: ``str``
        The experiment's name from the elog

    Returns
    -------
    qs_client: `happi.Client`
        Mapping from questionnaire ``python name`` to loaded object.
    """
    if QSBackend is None:
        raise RuntimeError('psdm_qs_cli library unavailable')
    # Determine which method of authentication we are going to use.
    # Search for a configuration file, either in the current directory
    # or hidden in the users home directory. If not found, attempt to
    # launch the client via Kerberos
    cfg = ConfigParser()
    cfgs = cfg.read(['qs.cfg', '.qs.cfg',
                     os.path.expanduser('~/.qs.cfg'),
                     'web.cfg', '.web.cfg',
                     os.path.expanduser('~/.web.cfg')])
    # Ws-auth
    if cfgs:
        user = cfg.get('DEFAULT', 'user', fallback=None)
        try:
            pw = cfg.get('DEFAULT', 'pw')
        except NoOptionError as exc:
            raise ValueError("Must specify password as 'pw' in "
                             "configuration file") from exc
        qs_client = happi.Client(database=QSBackend(expname,
                                                    use_kerberos=False,
                                                    user=user, pw=pw))
    # Kerberos
    else:
        qs_client = happi.Client(database=QSBackend(expname,
                                                    use_kerberos=True))
    return qs_client
