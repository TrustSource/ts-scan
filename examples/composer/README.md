# Composer example project

A minimal PHP application used by the regression tests of the Composer scanner.
It ships a committed `composer.lock`, so the example can be scanned without a
Composer installation and without network access.

The example covers the cases the scanner has to handle:

* a root package (`acme/inventory-app`) with a vendor namespace,
* a transitive dependency (`monolog/monolog` → `psr/log`),
* a virtual requirement (`psr/log-implementation`) resolved through `provide`,
* an abandoned package (`acme/legacy-mailer`),
* development dependencies (`phpunit/phpunit` → `sebastian/diff`),
* platform requirements (`php`, `ext-json`).

Scan it with:

```shell
ts-scan scan -o scan.json examples/composer
```

To include development dependencies and the platform requirements:

```shell
ts-scan scan --composer:includeDevDependencies --composer:includePlatformPackages \
    -o scan.json examples/composer
```
