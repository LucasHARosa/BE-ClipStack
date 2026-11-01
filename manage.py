#!/usr/bin/env python
"""Utilitário de linha de comando do Django (runserver, migrate, shell...)."""

import os
import sys


def main():
    # Sem DJANGO_SETTINGS_MODULE definido no ambiente, usa os settings de desenvolvimento.
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
