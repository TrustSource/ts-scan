# ts-scan Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### New Features
    * Added dependency scanning for PHP projects managed with Composer
    * Added `--composer:includeDevDependencies` to include Composer development dependencies
    * Added `--composer:includePlatformPackages` to include PHP platform requirements (`php`, `ext-*`, `lib-*`, `composer-*`) together with their well-known licenses
    * Added `--composer:enableMetadataRetrieval` to enrich packages with metadata from Packagist

## [1.9.1] - 2026-08-28

### Fixes
    * Continued package-manager scans when dependency resolution produces no lockfile
    * Used NuGet `project.assets.json` as a resolved dependency fallback, including solution scans
    * Handled missing NuGet global-package-path output without failing the scan
    * Added an NLog fallback example and regression coverage

## [1.9.0] - 2026-08-27

### New Features
    * Added `--nuget:separateProjectScans` to create one module scan per project in a NuGet solution

### Improvements
    * Changed the scanner interface to return an iterable of scans, allowing every scanner to produce zero, one, or multiple modules
    * Preserved NuGet solution projects as graph roots and derived module identities from NuGet and MSBuild metadata
    * Added multi-scan handling and regression coverage for analysis, vulnerability checking, conversion, and ordered uploads

### Fixes
    * Improved NuGet project-reference resolution using assets files with project-file fallbacks
    * Preserved exact lockfile-resolved versions and dependency relationships for transitive NuGet packages
    * Prevented vulnerability checks from failing for small or empty scans
    * Prevented SPDX and CycloneDX exports from silently dropping additional scans

## [1.8.0] - 2026-08-17

### New Features
    * Added dependency scanning for Dart and Flutter projects
    * Made in-depth analysis optional through the `analyse` extra, keeping the command visible with installation guidance when unavailable
    * Added a CI/CD guide for failing pipelines when scan-result uploads fail

### Improvements
    * Made the base installation self-contained and moved `ts-deepscan` and SCANOSS into the optional analysis dependency set
    * Added Pyright configuration and corrected typing issues throughout the project
    * Updated security policy links and contact information

### Fixes
    * Fixed NuGet project-reference resolution using project paths and assembly names
    * Preserved actual path casing when locating packages in the global NuGet cache
    * Preferred `dotnet` for SDK-style projects while retaining NuGet CLI support for legacy `packages.config` projects
    * Restored NuGet dependencies into the same persistent cache used for package lookup
    * Installed the complete analysis dependency set in the Docker image

## [1.1.0] - 2025-03-04

### New Features
    * Added "analyse" and "convert" commands
    * Enhanced results enrichment using the SCANOSS API
    * Implemented vulnerability checks for scans using the TrustSource API
    * Added support for SPDX and CycloneDX as input/output formats
    * Published documentation as GitHub Pages
    

## [1.0.0] - 2024-11-06
### New Features

    * Forwarding parameters to PM tools
    * Specifying executable paths
    * Ignoring package managers while scanning
    * Improved import of results produced by the Syft scanner
    * Scan target can be now an URI that can be scanned by Syft enabling docker image scanning

### Fixes
    * Fixed scanning of NPM and NuGet packages
    * Fixed scanning of Maven projects with submodules

## [0.3.0] - 2024-01-22
### New Features
    * Add support for the Syft scanner. The option '--use-syft' enables dependency scanning using Syft
    * Added options '--tag' and '--branch' to the scan command to attach the VCS's tag/branch to the module   

## [0.2.2] - 2023-10-04
### Fixes
    * Fix Maven issues on Windows
### New Features
    * Improved resolution of remote repositories for Maven

## [0.2.1] - 2023-09-10
### Fixes
    * Fix package's setup

## [0.2.0] - 2023-09-08
### New Features
    * Add support for Maven, NPM and Nuget package managers
    * Extraction of sources URLs for Maven packages

## [0.1.2] - 2023-04-04
### New Features
    * Improve/adjust interfaces for adding new pakcage managers

### Fixes
    * Minor bug fixes

## [0.1.1] - 2023-04-03
### New Features
    * License identification in license files from Python's wheel packages

## [0.1.0] - 2023-03-13
### New Features
    * Scanning of PyPi packages
    * Uploading of TS scans
    * Importing of SPDX (JSON and RDF) and CycloneDX SBOMs
