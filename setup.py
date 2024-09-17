from setuptools import setup

setup(
    name='ts-scan',
    packages=[
        'ts_scan',
        'ts_scan.pm',
        'ts_scan.pm.maven',
        'ts_scan.spdx'
    ],
    version='0.3.0',
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
        'semanticversion',
        'build',
        'importlib-metadata',
        'alive-progress',
        'requests',
        'numpy',
        'wasabi',
        'ts-python-client==2.0.5',
        'ts-deepscan==2.1.1',
        'license-expression',
        'packageurl-python',
        'spdx-tools @ git+https://github.com/TrustSource/tools-python.git@trustsource/v0.7.0-rc0#egg=spdx-tools'
    ],
    scripts=['ts-scan'],
    entry_points={
        'console_scripts': ['ts-scan=ts_scan.cli:main'],
    }
)