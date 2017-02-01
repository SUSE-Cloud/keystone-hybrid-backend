# Copyright 2012-2015 SUSE Linux Products GmbH
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
from keystone import exception
from keystone import identity
from keystone.identity.backends import ldap as ldap_backend
from keystone.identity.backends import sql as sql_ident

from oslo_config import cfg
from oslo_log import log

CONF = cfg.CONF
LOG = log.getLogger(__name__)


@dependency.requires('assignment_api')
class Identity(sql_ident.Identity):
    def __init__(self, *args, **kwargs):
        super(Identity, self).__init__(*args, **kwargs)
        self.ldap = ldap_backend.Identity(CONF)
        self.domain_aware = True

    # Identity interface
    def authenticate(self, user_id, password):
        """Authenticate based on a user and password.

        Tries to authenticate using the SQL backend first, if that fails
        it tries the LDAP backend.

        """
        if not password:
            raise AssertionError('Invalid user / password')

        session = sql.get_session()
        try:
            user_ref = self._get_user(session, user_id)
        except exception.UserNotFound:
            raise AssertionError('Invalid user / password')

        try:
            # if the user_ref has a password, it's from the SQL backend and
            # we can just check if it coincides with the one we got
            assert utils.check_password(password, user_ref['password']), \
                'Invalid user / password'
        except TypeError:
            raise AssertionError('Invalid user / password')
        except KeyError:  # if it doesn't have a password, it must be LDAP
            conn = None
            try:
                # get_connection does a bind for us which checks the password
                #conn = self.user.get_connection(self.user._id_to_dn(user_id),
                #                                password)
                dn = self.ldap.user._id_to_dn(user_id)
                conn = self.ldap.user.get_connection(dn, password)
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
        # XXX we only need domain_aware to be False when authenticating
        # as an LDAP user; after that, all operations will be done on
        # the SQL database and domain_aware needs to be True. This code
        # makes the assumption that the result of authenticate() should
        # be read as not domain_aware (for LDAP), after which
        # domain_aware should revert to True.
        domain_aware = self.domain_aware
        if not self.domain_aware:
            self.domain_aware = True
        return domain_aware

    def _get_user(self, session, user_id):
        # try SQL first
        try:
            user_ref = super(Identity, self)._get_user(session, user_id)
        except exception.UserNotFound:
            # then try LDAP
            user_ref = self.ldap.user.get(user_id)
            user_ref['domain_id'] = CONF.identity.default_domain_id
            # Above we assume no password is in the user_ref:
            # except KeyError:  # if it doesn't have a password, it must be LDAP
            # But if the LDAP server returns a password, this except
            # fails so we should remove it if it's there
            if 'password' in user_ref:
                del user_ref['password']
            return user_ref
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
            user = identity.filter_user(self.ldap.user.get_by_name(user_name))
            user['domain_id'] = CONF.identity.default_domain_id
            return user
        else:
            return user

    def list_users(self, hints):
        # get a copy of the filters to be able to pass them into the
        # ldap backends
        save_filters = list(hints.filters)
        sql_users = super(Identity, self).list_users(hints)
        hints.filters = save_filters
        # Assume that LDAP users are in the default domain, so only query ldap
        # when there's either no domain filter or when it matches the default
        # domain id.
        domain_filter = hints.get_exact_filter_by_name('domain_id')
        ldap_users = []
        if (not domain_filter or
                domain_filter['value'] == CONF.identity.default_domain_id):
            ldap_users = self.ldap.user.get_all_filtered(hints)
            for user in ldap_users:
                user['domain_id'] = CONF.identity.default_domain_id
        return sql_users + ldap_users

    def update_user(self, user_id, user):
        session = sql.get_session()
        user_ref = self._get_user(session, user_id)
        # LDAP user_ref is a dict. SQL user_ref is a User object
        if isinstance(user_ref, dict):
            return self.ldap.update_user(user_id, user)
        return super(Identity, self).update_user(user_id, user)
