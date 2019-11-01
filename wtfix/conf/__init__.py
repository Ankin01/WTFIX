# This file is a part of WTFIX.
#
# Copyright (C) 2018,2019 John Cass <john.cass77@gmail.com>
#
# WTFIX is free software; you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# WTFIX is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General Public
# License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""
Settings and configuration for wtfix.

Read values from the module specified by the WTFIX_SETTINGS_MODULE environment variable
"""

import importlib
import os
import logging
from typing import Type

from wtfix.conf import global_settings
from wtfix.core.exceptions import ImproperlyConfigured

from dotenv import load_dotenv

from pathlib import Path  # python3 only

env_path = Path(".") / ".env"
load_dotenv(dotenv_path=env_path)

ENVIRONMENT_VARIABLE = "WTFIX_SETTINGS_MODULE"


class Settings:
    def __init__(self, settings_module=None):

        self._logger = None
        if settings_module is None:
            settings_module = os.environ.get(ENVIRONMENT_VARIABLE)

            if not settings_module:
                raise ImproperlyConfigured(
                    f"Settings are not configured. You must either define the environment variable "
                    f"{ENVIRONMENT_VARIABLE} or call settings.configure() before accessing settings."
                )
        # update this dict from global settings (but only for ALL_CAPS settings)
        for setting in dir(global_settings):
            if setting.isupper():
                setattr(self, setting, getattr(global_settings, setting))

        # store the settings module in case someone later cares
        self.WTFIX_SETTINGS_MODULE = settings_module

        mod = importlib.import_module(self.WTFIX_SETTINGS_MODULE)

        self._explicit_settings = set()

        for setting in dir(mod):
            if setting.isupper():
                setting_value = getattr(mod, setting)

                # Check settings that should consist of collections of key / value pairs
                if setting in ("PIPELINE_APPS",) and not isinstance(
                    setting_value, (list, tuple)
                ):
                    raise ImproperlyConfigured(
                        f"The {setting} setting must be a list or a tuple. "
                    )
                setattr(self, setting, setting_value)
                self._explicit_settings.add(setting)

        self._active_protocol = None

    @property
    def has_safe_defaults(self):
        return len(self.CONNECTIONS) == 1

    @property
    def default_connection_name(self):
        if self.has_safe_defaults:
            return next(iter(self.CONNECTIONS))

        raise ImproperlyConfigured(
            f"Cannot fall back to using session defaults as more than one session has been configured "
            f"using the 'SESSIONS' parameter. You MUST specify which sessions' configuration settings to use."
        )

    @property
    def default_connection(self):
        return SessionSettings(self.default_connection_name)

    @property
    def active_protocol(self):
        if self._active_protocol is None:
            mod_name, class_name = self.default_connection.PROTOCOL.rsplit(".", 1)
            module = importlib.import_module(mod_name)
            protocol_class = getattr(module, class_name)

            self._active_protocol = protocol_class

        return self._active_protocol

    @active_protocol.setter
    def active_protocol(self, protocol_class: Type):
        self._active_protocol = protocol_class

    @property
    def logger(self):
        if self._logger is None:
            self._logger = logging.getLogger(settings.LOGGER)

        return self._logger

    @logger.setter
    def logger(self, value):
        self._logger = value

    def get_group_templates(self, connection_name=None, identifiers=None):
        if connection_name is None:
            connection_name = self.default_connection_name

        session_templates = self.CONNECTIONS[connection_name]["GROUP_TEMPLATES"]
        if identifiers is None:
            # Return all templates that have been defined.
            return session_templates

        # Look up the specified identifiers
        templates = {
            identifier: template
            for identifier, template in session_templates.items()
            if identifier in identifiers
        }

        if len(templates) != len(identifiers):
            missing_identifiers = identifiers - templates.keys()
            # Some templates could not be found!
            raise ImproperlyConfigured(
                f"No group template defined for identifier(s): {missing_identifiers}."
            )

        return templates

    def __repr__(self):
        return '<%(cls)s "%(settings_module)s">' % {
            "cls": self.__class__.__name__,
            "settings_module": self.WTFIX_SETTINGS_MODULE,
        }


settings = Settings()


class SessionSettings:
    """
    Used to promote the settings for a specific session so that it's properties can be accessed
    in the same way as 'Settings' above.
    """

    def __init__(self, connection_name=None):
        if connection_name is None:
            connection_name = settings.default_connection[0]

        for setting, setting_value in settings.CONNECTIONS[connection_name].items():
            if setting == "PROTOCOL":
                mod_name, class_name = setting_value.rsplit(".", 1)
                module = importlib.import_module(mod_name)
                protocol_class = getattr(module, class_name)

                settings.active_protocol = protocol_class

            setattr(self, setting, setting_value)
