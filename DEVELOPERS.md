## Modifying CI

### IMPORTANT!
This document is a work in progress and will be updated as bugs are resolved and enhancements are added.

### Files that can be modified at runtime
The following files are located under the irods_docker_files directory.
- Dockerfile.install_and_test
    - On every run, a new image is built. The build is instructed to not use any cached layers so that changes to files are seen.
- docker_cmds_utilities.py
- run_test.py
    - Invokes **docker_cmds_utilities.build_irods_zone** to build the iRODS test runner image.
    - Invokes **run_tests_in_parallel.py**.
- run_tests_in_parallel.py
    - Invokes `run_command_in_container` which is defined in **docker_cmds_utilities.py**.
- build_irods.py
- Dockerfile.build_irods
