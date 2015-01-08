# Copyright 2014 Hewlett-Packard Development Company, L.P.
# Copyright 2014 SUSE Linux Products GmbH
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

from oslo.config import cfg
from keystone import config
from keystone.assignment.backends import sql as sql_assign
from keystone.common import sql
from keystone import exception
from keystone.openstack.common.gettextutils import _


hybrid_opts = [
    cfg.ListOpt('default_roles',
                default=['_member_', ],
                help='List of roles assigned by default to an LDAP user'),
    cfg.StrOpt('default_project',
               default='demo',
               help='Default project'),
    cfg.StrOpt('default_domain',
               default='default',
               help='Default domain'),
]

CONF = config.CONF
CONF.register_opts(hybrid_opts, 'ldap_hybrid')


class Assignment(sql_assign.Assignment):
    _default_roles = list()
    _default_project = None

    def _get_metadata(self, user_id=None, tenant_id=None,
                      domain_id=None, group_id=None, session=None):
        try:
            res = super(Assignment, self)._get_metadata(
                user_id, tenant_id, domain_id, group_id, session)
        except exception.MetadataNotFound:
            if self.default_project_id == tenant_id:
                return {
                    'roles': [
                        {'id': role_id} for role_id in self.default_roles
                    ]
                }
            else:
                raise
        else:
            roles = res.get('roles', [])
            res['roles'] = roles + [
                {'id': role_id} for role_id in self.default_roles
            ]
            return res

    @property
    def default_project(self):
        if self._default_project is None:
            self._default_project = self.get_project_by_name(
                CONF.ldap_hybrid.default_project,
                CONF.ldap_hybrid.default_domain)
        return dict(self._default_project)

    @property
    def default_project_id(self):
        return self.default_project['id']

    @property
    def default_roles(self):
        if not self._default_roles:
            with sql.transaction() as session:
                query = session.query(sql_assign.Role)
                query = query.filter(sql_assign.Role.name.in_(
                    CONF.ldap_hybrid.default_roles))
                role_refs = query.all()

            if len(role_refs) != len(CONF.ldap_hybrid.default_roles):
                raise exception.RoleNotFound(
                    message=_('Could not find one or more roles: %s') %
                    ', '.join(CONF.ldap_hybrid.default_roles))

            self._default_roles = [role_ref.id for role_ref in role_refs]
        return self._default_roles

    def list_projects_for_user(self, user_id, group_ids, hints):
        projects = super(Assignment, self).list_projects_for_user(
            user_id, group_ids, hints)

        # Make sure the default project is in the project list for the user
        # user_id
        for project in projects:
            if project['id'] == self.default_project_id:
                return projects

        projects.append(self.default_project)
        return projects
