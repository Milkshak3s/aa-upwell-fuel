#!/usr/bin/env python
"""Run the test suite against the local test project.

    python runtests.py                     # everything
    python runtests.py upwellfuel.tests.test_calc
"""

import os
import sys

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "testauth.settings")
    from django.core.management import execute_from_command_line

    argv = sys.argv[:]
    argv.insert(1, "test")
    if len(argv) == 2:
        argv.append("upwellfuel")
    execute_from_command_line(argv)
