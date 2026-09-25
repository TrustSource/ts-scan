from ts_scan.pm.cocoapods import CocoaPodsScanner


PODFILE_LOCK = """
PODS:
  - Alamofire (5.6.4)
  - SDWebImage (5.15.5):
    - SDWebImage/Core (= 5.15.5)
  - SDWebImage/Core (5.15.5)
  - SnapKit (5.6.0)

DEPENDENCIES:
  - Alamofire
  - SDWebImage (~> 5.0)
  - SnapKit

SPEC REPOS:
  trunk:
    - Alamofire
    - SDWebImage
    - SDWebImage/Core
    - SnapKit

SPEC CHECKSUMS:
  Alamofire: 3ec537f71edc9804815215393ae2b1a8ea33553
  SDWebImage: 750adf017a716fe6f235d0c8d95406e358be216
  SDWebImage/Core: 750adf017a716fe6f235d0c8d95406e358be216
  SnapKit: e01d55c485784659ecfa9f1adf88bc4629990e0

PODFILE CHECKSUM: 1234567890abcdef1234567890abcdef12345678

COCOAPODS: 1.11.3
"""


def test_accepts_requires_podfile_lock(tmp_path):
    scanner = CocoaPodsScanner()

    assert not scanner.accepts(tmp_path)

    (tmp_path / 'Podfile.lock').write_text(PODFILE_LOCK)

    assert scanner.accepts(tmp_path)


def test_scan_parses_dependency_tree_and_checksums(tmp_path):
    project = tmp_path / 'MyApp'
    project.mkdir()
    (project / 'Podfile.lock').write_text(PODFILE_LOCK)

    scanner = CocoaPodsScanner()
    scans = list(scanner.scan(project))

    assert len(scans) == 1

    scan = scans[0]
    assert scan.module == 'MyApp'
    assert scan.moduleId == 'cocoapods:MyApp'

    root = scan.dependencies[0]
    assert {d.name for d in root.dependencies} == {'Alamofire', 'SDWebImage', 'SnapKit'}

    alamofire = next(d for d in root.dependencies if d.name == 'Alamofire')
    assert alamofire.versions == ['5.6.4']
    assert alamofire.checksum == '3ec537f71edc9804815215393ae2b1a8ea33553'
    assert alamofire.key == 'cocoapods:Alamofire'

    sdwebimage = next(d for d in root.dependencies if d.name == 'SDWebImage')
    assert sdwebimage.versions == ['5.15.5']
    assert [d.name for d in sdwebimage.dependencies] == ['SDWebImage/Core']

    core = sdwebimage.dependencies[0]
    assert core.versions == ['5.15.5']
    assert core.checksum == '750adf017a716fe6f235d0c8d95406e358be216'


def test_scan_returns_no_scans_when_lockfile_is_empty(tmp_path):
    project = tmp_path / 'Empty'
    project.mkdir()
    (project / 'Podfile.lock').write_text('')

    scanner = CocoaPodsScanner()

    assert list(scanner.scan(project)) == []
