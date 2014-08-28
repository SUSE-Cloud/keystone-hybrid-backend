# Copyright 2012-2014 SUSE Linux Products GmbH
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

from keystone.common import dependency
from keystone.common import sql
from keystone.common import utils
from keystone import config
from keystone import exception
from keystone import identity
from keystone.identity.backends import ldap as ldap_backend
from keystone.identity.backends import sql as sql_ident
from keystone.openstack.common import log

CONF = config.CONF
LOG = log.getLogger(__name__)


@dependency.requires('assignment_api')
class Identity(sql_ident.Identity):
    def __init__(self, *args, **kwargs):
        super(Identity, self).__init__(*args, **kwargs)
        self.user = ldap_backend.UserApi(CONF)
        self.domain_aware = True

    # Identity interface
    def authenticate(self, user_id, password):
        """Authenticate based on a user and password.

        Tries to authenticate using the SQL backend first, if that fails
        it tries the LDAP backend.

        """
        session = sql.get_session()
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
            else:
                LOG.debug("Authenticated user with LDAP.")
                self.domain_aware = False
            finally:
                if conn:
                    conn.unbind_s()
        else:
            LOG.debug("Authenticated user with SQL.")
            # turn the SQLAlchemy User object into a dict to match what
            # LDAP would return
            user_ref = user_ref.to_dict()

        return identity.filter_user(user_ref)

    def is_domain_aware(self):
        return self.domain_aware

    def _get_user(self, session, user_id):
        # try SQL first
        try:
            user_ref = super(Identity, self)._get_user(session, user_id)
        except exception.UserNotFound:
            # then try LDAP
            return self.user.get(user_id)
        else:
            return user_ref

    def get_user(self, user_id):
        LOG.debug("Called get_user %s" % user_id)
        session = sql.get_session()
        user = self._get_user(session, user_id)
        try:
            user = user.to_dict()
        except AttributeError:
            # LDAP Users are already dicts which is fine
            pass
        return identity.filter_user(user)

    def get_user_by_name(self, user_name, domain_id):
        LOG.debug("Called get_user_by_name %s, %s" % (user_name, domain_id))
        # try SQL first
        try:
            user = super(Identity, self).get_user_by_name(user_name, domain_id)
        except exception.UserNotFound:
            # then try LDAP
            return identity.filter_user(self.user.get_by_name(user_name))
        else:
            return user

    def list_users(self, hints):
        sql_users = super(Identity, self).list_users(hints)
        ldap_users = self.user.get_all_filtered()
        return sql_users + ldap_users
