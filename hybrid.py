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
from keystone.identity.backends.ldap import UserApi
from keystone.identity.backends.sql import User
from keystone.identity.backends.sql import Identity as SQLIdentity
from keystone.identity.backends.hybrid_config import tenants_for_user


def _filter_user(user_ref):
    if user_ref:
        user_ref.pop('password', None)
    return user_ref


class Identity(SQLIdentity):
    def __init__(self, *args, **kwargs):
        super(Identity, self).__init__(*args, **kwargs)
        self.user = UserApi(config.CONF)
        
    # Identity interface
    def authenticate(self, user_id=None, tenant_id=None, password=None):
        """Authenticate based on a user, tenant and password.

        Expects the user object to have a password field and the tenant to be
        in the list of tenants on the user.

        """
        user_ref = self._get_user(user_id)

        # if the user_ref has a password, it's from the SQL backend and
        # we can just check if it coincides with the one we got
        try:
            assert utils.check_password(password, user_ref['password'])
        except TypeError:
            raise AssertionError('Invalid user / password')
        except KeyError:  # if it doesn't have a password, it must be LDAP
            try:
                # get_connection does a bind for us which checks the password
                assert self.user.get_connection(self.user_dn, password)
            except Exception:
                raise AssertionError('Invalid user / password')

        tenants = self.get_tenants_for_user(user_id)
        if tenant_id and tenant_id not in tenants:
            raise AssertionError('Invalid tenant')

        tenant_ref = self.get_tenant(tenant_id)
        if tenant_ref:
            metadata_ref = self.get_metadata(user_id, tenant_id)
        else:
            metadata_ref = {}
        return (_filter_user(user_ref), tenant_ref, metadata_ref)

    def _get_user(self, user_id):
        # try SQL first
        session = self.get_session()
        user_ref = session.query(User).filter_by(id=user_id).first()
        if user_ref:
            return user_ref.to_dict()

        # then try LDAP
        conn = self.user.get_connection()
        query = '(objectClass=%s)' % self.user.object_class
        try:
            users = conn.search_s(self.user_dn, ldap.SCOPE_BASE, query)
        except AttributeError, ldap.NO_SUCH_OBJECT:
            return None

        if users:
            return self.user._ldap_res_to_model(users[0])

    def get_user(self, user_id):
        user_ref = self._get_user(user_id)
        if not user_ref:
            return None
        return _filter_user(user_ref)

    def get_user_by_name(self, user_name):
        # try SQL first
        session = self.get_session()
        user_ref = session.query(User).filter_by(name=user_name).first()
        if user_ref:
            return _filter_user(user_ref.to_dict())

        # then try LDAP
        conn = self.user.get_connection()
        query = '(&(objectClass=%s)(%s=%s))' % (
            self.user.object_class,
            self.user.attribute_mapping['name'],
            ldap_filter.escape_filter_chars(user_name))

        try:
            users = conn.search_s(self.user.tree_dn,
                                  config.CONF.ldap.user_search_scope,
                                  query)
        except ldap.NO_SUCH_OBJECT:
            return None

        if not users:
            return None

        user_ref = self.user._ldap_res_to_model(users[0])

        # the DN is the first element in the returned user tuple
        self.user_dn = users[0][0]

        return _filter_user(user_ref)

    def get_tenants_for_user(self, user_id):
        session = self.get_session()
        return tenants_for_user(session, user_id)
