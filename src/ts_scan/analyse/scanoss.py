import typing as t

from scanoss.scanossapi import ScanossApi
from scanoss.scanossgrpc import ScanossGrpc, DEFAULT_URL2

from tqdm import tqdm
from ts_deepscan import Scan as DSScan

from .. import __version__, msg
from ..pm import DependencyScan


__ts_scan_user_agent = f'ts-scan/{__version__}'

def analyse_scan(scan: DependencyScan, api_key: t.Optional[str]):
    scan_purls = scan.as_purls_dict()

    if scan_purls and api_key:
        msg.info("Requesting cryptographic algorithms from SCANOSS")

        grpc_api = ScanossGrpc(url=DEFAULT_URL2, api_key=api_key)
        grpc_api.metadata.append(('user-agent', __ts_scan_user_agent))

        purls = {
            'purls': [{'purl': purl} for purl in scan_purls.keys()]
        }

        if crypto_info := grpc_api.get_crypto_json(purls=purls):
            for purl_crypto in crypto_info.get('purls', []):
                if (purl := purl_crypto.get('purl')) and (algorithms := purl_crypto.get('algorithms')):
                    if dep := scan_purls.get(purl):
                        for alg in algorithms:
                            dep.add_crypto_algorithm(algorithm=alg['algorithm'], strength=alg['strength'])

