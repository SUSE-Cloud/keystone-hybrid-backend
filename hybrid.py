# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 SUSE Linux Products GmbH
# Copyright 2012 OpenStack LLC
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.


"""Hybrid Identity backend for Keystone on top of the LDAP and SQL backends"""

from __future__ import absolute_import

import ldap
from ldap import filter as ldap_filter

from keystone import config
from keystone import exception
from keystone.common import sql
from keystone.common import utils
from keystone import identity
from keystone.identity.backends import ldap as ldap_backend
from keystone.identity.backends import sql


CONF = config.CONF


class Identity(sql.Identity):
    def __init__(self, *args, **kwargs):
        super(Identity, self).__init__(*args, **kwargs)
        self.user = ldap_backend.UserApi(CONF)
        
    # Identity interface
    def authenticate(self, user_id=None, tenant_id=None, password=None):
        """Authenticate based on a user, tenant and password.

        Expects the user object to have a password field and the tenant to be
        in the list of tenants on the user.

        """
        try:
            user_ref = self._get_user(user_id)
        except exception.UserNotFound:
            raise AssertionError('Invalid user / password')

        # if the user_ref has a password, it's from the SQL backend and
        # we can just check if it coincides with the one we got
        try:
            assert utils.check_password(password, user_ref['password'])
        except TypeError:
            raise AssertionError('Invalid user / password')
        except KeyError:  # if it doesn't have a password, it must be LDAP
            try:
                # get_connection does a bind for us which checks the password
                assert self.user.get_connection(self.user._id_to_dn(user_id),
                                                password)
            except Exception:
                raise AssertionError('Invalid user / password')

        tenants = self.get_projects_for_user(user_id)
        if tenant_id and tenant_id not in tenants:
            raise AssertionError('Invalid tenant')

        try:
            tenant_ref = self.get_project(tenant_id)
            # if the tenant was not found, then there will be no metadata either
            metadata_ref = self.get_metadata(user_id, tenant_id)
        except exception.ProjectNotFound:
            tenant_ref = None
            metadata_ref = {}
        except exception.MetadataNotFound:
            metadata_ref = {}

        return (identity.filter_user(user_ref), tenant_ref, metadata_ref)

    def _get_user(self, user_id):
        # try SQL first
        try:
            user = super(Identity, self)._get_user(user_id)
        except exception.UserNotFound:
            pass
        else:
            return user

        # then try LDAP
        return self.user.get(user_id)

    def get_user(self, user_id):
        user_ref = self._get_user(user_id)
        return identity.filter_user(user_ref)

    def get_user_by_name(self, user_name):
        # try SQL first
        try:
            user = super(Identity, self).get_user_by_name(user_name)
        except exception.UserNotFound:
            pass
        else:
            return user

        # then try LDAP
        try:
            return identity.filter_user(self.user.get_by_name(user_name))
        except exception.NotFound:
            raise exception.UserNotFound(user_id=user_name)
