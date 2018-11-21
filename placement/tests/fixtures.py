# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Fixtures for Nova tests."""
from __future__ import absolute_import


import fixtures
from oslo_config import cfg

from placement.db.sqlalchemy import migration
from placement import db_api as placement_db
from placement import deploy
from placement.objects import resource_provider


CONF = cfg.CONF
session_configured = False


def reset():
    """Call this to allow the placement db fixture to be reconfigured
    in the same process.
    """
    global session_configured
    session_configured = False
    placement_db.placement_context_manager.dispose_pool()
    # TODO(cdent): Future handling in sqlalchemy may allow doing this
    # in a less hacky way.
    placement_db.placement_context_manager._factory._started = False
    # Reset the run once decorator.
    placement_db.configure.reset()


class Database(fixtures.Fixture):
    def __init__(self, set_config=False):
        """Create a database fixture."""
        super(Database, self).__init__()
        global session_configured
        if not session_configured:
            if set_config:
                try:
                    CONF.register_opt(cfg.StrOpt('connection'),
                                      group='placement_database')
                except cfg.DuplicateOptError:
                    # already registered
                    pass
                CONF.set_override('connection', 'sqlite://',
                                  group='placement_database')
            placement_db.configure(CONF)
            session_configured = True
        self.get_engine = placement_db.get_placement_engine

    def setUp(self):
        super(Database, self).setUp()
        migration.create_schema()
        resource_provider._TRAITS_SYNCED = False
        resource_provider._RC_CACHE = None
        deploy.update_database()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        reset()
        resource_provider._TRAITS_SYNCED = False
        resource_provider._RC_CACHE = None