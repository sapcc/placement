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
"""Unit tests for code in the trait handler that gabbi cannot easily cover."""


from unittest import mock

import microversion_parse
import webob

from placement import context
from placement import exception
from placement.handlers import trait
from placement.tests.unit import base


class TestTraitHandler(base.ContextTestCase):

    @mock.patch('placement.objects.trait.Trait.create')
    @mock.patch('placement.objects.trait.Trait.get_by_name')
    @mock.patch('placement.context.RequestContext.can')
    @mock.patch('placement.util.wsgi_path_item', return_value='CUSTOM_FOOBAR')
    def test_trait_create_ordering(
            self, mock_path, mock_can, mock_get_by_name, mock_create):
        """Test that we call Trait.create when get_by_name has a TraitNotFound
        and that if create can't create, we assume 204.
        """
        # The trait doesn't initially exist.
        mock_get_by_name.side_effect = exception.TraitNotFound(
            name='CUSTOM_FOOBAR')
        # But we fake that it does after first not finding it.
        mock_create.side_effect = exception.TraitExists(
            name='CUSTOM_FOOBAR')
        fake_context = context.RequestContext(
            user_id='fake', project_id='fake')

        req = webob.Request.blank('/traits/CUSTOM_FOOBAR')
        req.environ['placement.context'] = fake_context

        parse_version = microversion_parse.parse_version_string
        microversion = parse_version('1.15')
        microversion.max_version = parse_version('9.99')
        microversion.min_version = parse_version('1.0')
        req.environ['placement.microversion'] = microversion

        response = req.get_response(trait.put_trait)

        # Trait was assumed to exist.
        self.assertEqual('204 No Content', response.status)

        # We get a last modified header, even though we don't know the exact
        # create_at time (it is None on the Trait object and we fall back to
        # now)
        self.assertIn('last-modified', response.headers)

        # Confirm we checked to see if the trait exists, but the
        # side_effect happens
        mock_get_by_name.assert_called_once_with(fake_context, 'CUSTOM_FOOBAR')

        # Confirm we attempt to create the trait.
        mock_create.assert_called_once_with()

    @mock.patch('placement.objects.trait.get_all')
    @mock.patch('placement.objects.resource_provider.ResourceProvider.'
                'get_by_uuid')
    @mock.patch('placement.context.RequestContext.can')
    @mock.patch('placement.util.extract_json')
    @mock.patch('placement.util.wsgi_path_item')
    def test_trait_update_concurrent(
            self, mock_path, mock_json, mock_can, mock_get_rp_by_uuid,
            mock_trait_get_all):
        """Test that we call update_traits concurrently that we handle a
        potential ConcurrentUpdateDetected
        """
        fake_context = context.RequestContext(
            user_id='fake', project_id='fake')

        req = webob.Request.blank(
            '/resource_providers/uuid/traits',
            method='POST',
            content_type='application/json')

        req.environ['placement.context'] = fake_context
        req.body = b'{}'

        mock_rp = mock.MagicMock(
            generation=mock.sentinel.rp_gen,
        )
        mock_rp.set_traits.side_effect = exception.ConcurrentUpdateDetected
        mock_get_rp_by_uuid.return_value = mock_rp

        existing_traits = [mock.MagicMock(name="fake")]
        mock_trait_get_all.return_value = existing_traits

        parse_version = microversion_parse.parse_version_string
        microversion = parse_version('1.15')
        microversion.max_version = parse_version('9.99')
        microversion.min_version = parse_version('1.0')
        req.environ['placement.microversion'] = microversion

        mock_json.return_value = {
            'resource_provider_generation': mock.sentinel.rp_gen,
            'traits': [t.name for t in existing_traits],
        }

        response = req.get_response(trait.update_traits_for_resource_provider)

        # We expect a 409 error to be returned
        self.assertEqual('409 Conflict', response.status)
