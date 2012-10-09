# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 OpenStack LLC
# Copyright 2012 SUSE Linux Products GmbH
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

from keystone.identity.backends.sql import UserTenantMembership, Tenant


DEFAULT_TENANT = 'admin'


def tenants_for_user(session, user_id):
    """Return a list of tenant ids associated with a user

    :param session: SQLAlchemy database session object (from the SQL backend)
    :param user_id: a user_id string which identifies a User in the LDAP
    backend

    """
    # get the normal tenants from the database 
    membership_refs = session.query(UserTenantMembership)\
                          .filter_by(user_id=user_id)\
                          .all()
    tenant_ids = [x.tenant_id for x in membership_refs]

    # all users are also automatically part of this tenant
    try:
        tenant_ids.append(session.query(Tenant)\
                          .filter_by(name=DEFAULT_TENANT).first().id)
    except AttributeError:
        pass

    return tenant_ids
