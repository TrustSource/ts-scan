from setuptools import setup

setup(
    name='ts-scan',
    packages=[
        'ts_scan',
        'ts_scan.pm'
    ],
    version='0.1.0',
    description='TrustSource PM scanner',
    author='EACG GmbH',
    license='Apache-2.0',
    url='https://github.com/trustsource/ts-scan.git',
    download_url='',
    keywords=['scanning', 'dependencies', 'modules', 'compliance', 'TrustSource'],
    classifiers=[],
    install_requires=[
        'wheel',
        'build',
        'importlib-metadata',
        'alive-progress',
        'ts-python-client>=2.0.0',
        'ts-deepscan>=2.0.0'
    ],
    scripts=['ts-scan'],
    entry_points={
        'console_scripts': ['ts-scan=ts_scan:main'],
    }
)