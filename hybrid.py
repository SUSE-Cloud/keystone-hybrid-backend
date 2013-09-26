# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012-2013 SUSE Linux Products GmbH
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

from keystone import config
from keystone import exception
from keystone.common import sql
from keystone.common import utils
from keystone.common import logging
from keystone import identity
from keystone.identity.backends import ldap as ldap_backend
from keystone.identity.backends import sql

DEFAULT_TENANT = 'default_tenant'
DEFAULT_DOMAIN = 'default'
CONF = config.CONF
LOG = logging.getLogger(__name__)

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
            # we've hacked get_projects_for_user to return a tenant that
            # is not assigned to this user in the database, so we have
            # to set it here as well
            tenant_id = tenants[0]
        except KeyError:
            pass

        try:
            tenant_ref = self.get_project(tenant_id)
            # if the tenant was not found, then there will be no metadata either
            metadata_ref = self.get_metadata(user_id, tenant_id)
        except exception.ProjectNotFound:
            tenant_ref = None
            metadata_ref = {}
        except exception.MetadataNotFound:
            metadata_ref = {}

        user_ref = _set_default_domain(identity.filter_user(user_ref))
        return (user_ref, tenant_ref, metadata_ref)

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
        LOG.debug("Called get_user %s" % user_id)
        user_ref = identity.filter_user(self._get_user(user_id))
        return _set_default_domain(user_ref)

    def get_user_by_name(self, user_name, domain_id):
        LOG.debug("Called get_user_by_name %s, %s" % (user_name, domain_id))
        # try SQL first
        try:
            user = super(Identity, self).get_user_by_name(user_name, domain_id)
        except exception.UserNotFound:
            pass
        else:
            return user

        # then try LDAP
        _validate_domain_id(domain_id)
        ref = identity.filter_user(self.user.get_by_name(user_name))
        return _set_default_domain(ref)

    def list_users(self):
        sql_users = super(Identity, self).list_users()
        ldap_users = _set_default_domain(self.user.get_all())
        return sql_users + ldap_users

    def get_projects_for_user(self, user_id):
        project_ids = super(Identity, self).get_projects_for_user(user_id)
        default_project = self.get_project_by_name(DEFAULT_TENANT, DEFAULT_DOMAIN)
        project_ids.append(default_project['id'])
        LOG.debug("get_projects_for_user returns %s" % project_ids)

        return project_ids


def _validate_domain_id(domain_id):
    """Validate that the domain ID specified belongs to the default domain.

    """
    if domain_id != CONF.identity.default_domain_id:
        raise exception.DomainNotFound(domain_id=domain_id)

def _set_default_domain(ref):
    """Overrides any domain reference with the default domain."""
    if isinstance(ref, dict):
        ref = ref.copy()
        ref['domain_id'] = CONF.identity.default_domain_id
        return ref
    elif isinstance(ref, list):
        return [_set_default_domain(x) for x in ref]
    else:
        raise ValueError(_('Expected dict or list: %s') % type(ref))
