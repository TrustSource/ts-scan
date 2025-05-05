import typing as t

from scanoss.scanossapi import ScanossApi
from scanoss.scanossgrpc import ScanossGrpc, DEFAULT_URL2

from tqdm import tqdm
from ts_deepscan import Scan as DSScan

from .. import __version__, msg
from ..pm import DependencyScan

__scanoss_api = None
__ts_scan_user_agent = f'ts-scan/{__version__}'


def get_scanoss_api() -> ScanossApi:
    global __scanoss_api

    if not __scanoss_api:
        __scanoss_api = ScanossApi()
        __scanoss_api.headers['User-Agent'] = __ts_scan_user_agent
        __scanoss_api.headers['user-agent'] = __ts_scan_user_agent

    return __scanoss_api


def extend_ds(ds: DSScan, api_key: t.Optional[str]):
    wfps = []
    for res in ds.result.values():
        if (scanoss := res.get('scanoss')) and (wfp := scanoss.get('wfp')):
            wfps.append(wfp)

    api = get_scanoss_api()

    linked_comps: t.Dict[str, t.Set[str]] = {}

    if wfps:
        wfps_results = {}
        wfps_chunk_size = 999

        for i in range(0, len(wfps), wfps_chunk_size):
            try:
                wfps_results.update(api.scan('\n'.join(wfps[i:i + wfps_chunk_size])))
            except:
                continue

        if wfps_results:
            for path, wfp_res in wfps_results.items():
                links = []
                for wfp_comp in wfp_res:
                    if purl := wfp_comp.get('purl'):
                        version = wfp_comp.get('version')

                        link = {'purl': purl}

                        if version:
                            link['version'] = version

                        if lics := wfp_comp.get('licenses'):
                            link['licenses'] = list(set(lic['name'] for lic in lics))

                        for p in purl:
                            p_vers = linked_comps.get(p, set())
                            if version:
                                p_vers.add(version)
                            linked_comps[p] = p_vers

                        links.append(link)

                if links:
                    ds.result[path]['links'] = links

    ds.summary['links'] = {purl: list(vers) for purl, vers in linked_comps.items()}


def analyse_scan(scan: DependencyScan, api_key: t.Optional[str]):
    for comp, ds in tqdm(scan.deepscans.items(), desc="Requesting fingerprints information from SCANOSS"):
        if 'links' not in ds.summary:
            extend_ds(ds, api_key)

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

