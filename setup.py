from setuptools import setup

setup(
    name='ts-scan',
    packages=[
        'ts_scan',
        'ts_scan.pm',
        'ts_scan.pm.maven',
        'ts_scan.spdx',
        'ts_scan.syft'
    ],
    version='1.0.4',
    description='TrustSource PM scanner',
    author='EACG GmbH',
    license='Apache-2.0',
    url='https://github.com/trustsource/ts-scan.git',
    download_url='',
    keywords=['scanning', 'dependencies', 'modules', 'compliance', 'TrustSource'],
    classifiers=[],
    install_requires=[
        'wheel',
        'defusedxml',
        'semantic_version',
        'build',
        'importlib-metadata',
        'alive-progress',
        "requests==2.32.3",
        'numpy',
        'wasabi',
        'ts-python-client==2.0.6',
        'ts-deepscan==2.2.2',
        'license-expression',
        'packageurl-python',
        'spdx-tools==0.7.0rc0'
    ],
    scripts=['ts-scan'],
    entry_points={
        'console_scripts': ['ts-scan=ts_scan.cli:main'],
    }
)