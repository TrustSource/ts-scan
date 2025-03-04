# ts-scan Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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