#!/usr/bin/python
#
# Copyright (c) 2011 Red Hat, Inc.
#
#
# This software is licensed to you under the GNU General Public
# License as published by the Free Software Foundation; either version
# 2 of the License (GPLv2) or (at your option) any later version.
# There is NO WARRANTY for this software, express or implied,
# including the implied warranties of MERCHANTABILITY,
# NON-INFRINGEMENT, or FITNESS FOR A PARTICULAR PURPOSE. You should
# have received a copy of GPLv2 along with this software; if not, see
# http://www.gnu.org/licenses/old-licenses/gpl-2.0.txt.

# Python
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)) + "/../common/")
import testutil

from pulp.server.content.conduits.repo_sync import RepoSyncConduit, RepoSyncConduitException
import pulp.server.content.types.database as types_database
import pulp.server.content.types.model as types_model
from pulp.server.db.model.gc_repository import Repo, RepoContentUnit
import pulp.server.managers.repo.cud as repo_manager
import pulp.server.managers.repo.importer as importer_manager
import pulp.server.managers.repo.sync as sync_manager
import pulp.server.managers.repo.unit_association as association_manager
import pulp.server.managers.content.cud as content_manager
import pulp.server.managers.content.query as query_manager

# constants --------------------------------------------------------------------

TYPE_1_DEF = types_model.TypeDefinition('type-1', 'Type 1', 'One', ['key-1'], ['search-1'], [])
TYPE_2_DEF = types_model.TypeDefinition('type-2', 'Type 2', 'Two', [('key-2a', 'key-2b')], [], ['type-1'])

# -- test cases ---------------------------------------------------------------

class RepoUnitAssociationManagerTests(testutil.PulpTest):

    def clean(self):
        super(RepoUnitAssociationManagerTests, self).clean()
        types_database.clean()

        RepoContentUnit.get_collection().remove()
        Repo.get_collection().remove()

    def setUp(self):
        super(RepoUnitAssociationManagerTests, self).setUp()
        types_database.update_database([TYPE_1_DEF, TYPE_2_DEF])

        self.repo_manager = repo_manager.RepoManager()
        self.importer_manager = importer_manager.RepoImporterManager()
        self.sync_manager = sync_manager.RepoSyncManager()
        self.association_manager = association_manager.RepoUnitAssociationManager()
        self.content_manager = content_manager.ContentManager()
        self.query_manager = query_manager.ContentQueryManager()

        self.repo_manager.create_repo('repo-1')
        self.conduit = self._conduit('repo-1')

    def test_init_save_units(self):
        """
        Tests using the init and save methods to add and associate content to a repository.
        """

        # Test - init_unit
        unit_1_key = {'key-1' : 'unit_1'}
        unit_1_metadata = {'meta_1' : 'value_1'}
        unit_1 = self.conduit.init_unit(TYPE_1_DEF.id, unit_1_key, unit_1_metadata, '/foo/bar')

        #   Verify that the returned unit is populated with the correct data
        self.assertTrue(unit_1 is not None)
        self.assertEqual(unit_1.unit_key, unit_1_key)
        self.assertEqual(unit_1.type_id, TYPE_1_DEF.id)
        self.assertEqual(unit_1.metadata, unit_1_metadata)
        self.assertTrue(unit_1.id is None)
        self.assertTrue(unit_1.storage_path is not None)
        self.assertTrue('/foo/bar' in unit_1.storage_path)

        # Test - save_unit
        unit_1 = self.conduit.save_unit(unit_1)

        #   Verify the returned unit
        self.assertTrue(unit_1 is not None)
        self.assertTrue(unit_1.id is not None)

        #   Verify the unit exists in the database
        db_unit = self.query_manager.get_content_unit_by_id(TYPE_1_DEF.id, unit_1.id)
        self.assertTrue(db_unit is not None)

        #   Verify the repo association exists
        associated_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(1, len(associated_units))

    def test_get_remove_unit(self):
        """
        Tests retrieving units through the conduit and removing them.
        """

        # Setup
        unit_1_key = {'key-1' : 'unit_1'}
        unit_1_metadata = {'meta_1' : 'value_1'}
        unit_1 = self.conduit.init_unit(TYPE_1_DEF.id, unit_1_key, unit_1_metadata, '/foo/bar')
        self.conduit.save_unit(unit_1)

        # Test - get_units
        units = self.conduit.get_units()

        #   Verify returned units
        self.assertEqual(1, len(units))
        self.assertEqual(unit_1_key, units[0].unit_key)
        self.assertTrue(units[0].id is not None)

        # Test - remove_units
        self.conduit.remove_unit(units[0])

        #   Verify repo association removed in the database
        associated_units = list(RepoContentUnit.get_collection().find({'repo_id' : 'repo-1'}))
        self.assertEqual(0, len(associated_units))

        #   Verify the unit itself is still in the database
        db_unit = self.query_manager.get_content_unit_by_id(TYPE_1_DEF.id, unit_1.id)
        self.assertTrue(db_unit is not None)

    def test_link_child_unit(self):
        """
        Tests creating a child unit association.
        """

        # Setup
        unit_1_key = {'key-1' : 'unit_1'}
        unit_1_metadata = {'meta_1' : 'value_1'}
        unit_1 = self.conduit.init_unit(TYPE_1_DEF.id, unit_1_key, unit_1_metadata, '/foo/bar')
        unit_1 = self.conduit.save_unit(unit_1)

        unit_2_key = {'key-2a' : 'unit_2', 'key-2b' : 'unit_2'}
        unit_2_metadata = {}
        unit_2 = self.conduit.init_unit(TYPE_2_DEF.id, unit_2_key, unit_2_metadata, '/foo/bar')
        unit_2 = self.conduit.save_unit(unit_2)

        # Test
        self.conduit.link_child_unit(unit_2, unit_1)

        # Verify
        parent = self.query_manager.get_content_unit_by_id(TYPE_2_DEF.id, unit_2.id)
        self.assertTrue('_type-1_children' in parent)
        self.assertTrue(unit_1.id in parent['_type-1_children'])

    # -- utilities ------------------------------------------------------------

    def _conduit(self, repo_id):
        """
        Convenience method for creating a conduit.
        """
        conduit = RepoSyncConduit(repo_id, self.repo_manager, self.importer_manager, self.sync_manager,
                                  self.association_manager, self.content_manager, self.query_manager)
        return conduit