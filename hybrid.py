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
from keystone.common import utils
from keystone import identity
from keystone.identity.backends import ldap as ldap_backend
from keystone.identity.backends import sql
from keystone.openstack.common import log
from keystone.openstack.gettextutils import _

DEFAULT_TENANT = 'default_tenant'
DEFAULT_DOMAIN = 'default'
DEFAULT_ROLE = 'default_role'
CONF = config.CONF
LOG = log.getLogger(__name__)


class Identity(sql.Identity):
    def __init__(self, *args, **kwargs):
        super(Identity, self).__init__(*args, **kwargs)
        self.user = ldap_backend.UserApi(CONF)

    # Identity interface
    def authenticate(self, user_id, password):
        """Authenticate based on a user and password.

        Tries to authenticate using the SQL backend first, if that fails
        it tries the LDAP backend.

        """
        session = self.get_session()
        try:
            user_ref = self._get_user(session, user_id)
        except exception.UserNotFound:
            raise AssertionError('Invalid user / password')

        # if the user_ref has a password, it's from the SQL backend and
        # we can just check if it coincides with the one we got
        conn = None
        try:
            assert utils.check_password(password, user_ref['password'])
        except TypeError:
            raise AssertionError('Invalid user / password')
        except KeyError:  # if it doesn't have a password, it must be LDAP
            try:
                # get_connection does a bind for us which checks the password
                conn = self.user.get_connection(self.user._id_to_dn(user_id),
                                                password)
                assert conn
            except Exception:
                raise AssertionError('Invalid user / password')
            finally:
                if conn:
                    conn.unbind_s()

        return _set_default_domain(identity.filter_user(user_ref))

    def _get_user(self, session, user_id):
        # try SQL first
        try:
            user_ref = super(Identity, self)._get_user(session, user_id)
        except exception.UserNotFound:
            # then try LDAP
            return _set_default_domain(self.user.get(user_id))
        else:
            return user_ref.to_dict()

    def get_user(self, user_id):
        LOG.debug("Called get_user %s" % user_id)
        session = self.get_session()
        return identity.filter_user(self._get_user(session, user_id))

    def get_user_by_name(self, user_name, domain_id):
        LOG.debug("Called get_user_by_name %s, %s" % (user_name, domain_id))
        # try SQL first
        try:
            user = super(Identity, self).get_user_by_name(user_name, domain_id)
        except exception.UserNotFound:
            # then try LDAP
            user_ref = identity.filter_user(self.user.get_by_name(user_name))
            _validate_default_domain_id(domain_id)
            return _set_default_domain(user_ref)
        else:
            return user

    def list_users(self):
        sql_users = super(Identity, self).list_users()
        ldap_users = self.user.get_all_filtered()
        return sql_users + ldap_users


# copied from keystone.assignment.core
def _set_default_domain(ref):
    """If the domain ID has not been set, set it to the default."""
    if isinstance(ref, dict):
        if 'domain_id' not in ref:
            ref = ref.copy()
            ref['domain_id'] = CONF.identity.default_domain_id
        return ref
    elif isinstance(ref, list):
        return [_set_default_domain(x) for x in ref]
    else:
        raise ValueError(_('Expected dict or list: %s') % type(ref))


def _validate_default_domain_id(domain_id):
    """Validate that the domain ID specified belongs to the default domain."""
    if domain_id != CONF.identity.default_domain_id:
        raise exception.DomainNotFound(domain_id=domain_id)
