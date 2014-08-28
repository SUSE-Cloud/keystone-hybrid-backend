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

from keystone.assignment.backends import sql as sql_assign
from keystone.common import sql
from keystone import exception

DEFAULT_PROJECT = 'openstack'
DEFAULT_ROLE = 'Member'
DEFAULT_DOMAIN = 'default'


class Assignment(sql_assign.Assignment):
    _default_role = None
    _default_project = None

    def _get_metadata(self, user_id=None, tenant_id=None,
                      domain_id=None, group_id=None, session=None):
        try:
            res = super(Assignment, self)._get_metadata(
                user_id, tenant_id, domain_id, group_id, session)
        except exception.MetadataNotFound:
            if self.default_project == tenant_id:
                return {'roles': [{'id': self.default_role}]}
            else:
                raise
        else:
            roles = res.get('roles', [])
            roles.append({'id': self.default_role})
            res['roles'] = roles
            return res

    @property
    def default_project(self):
        if self._default_project is None:
            self._default_project = self.get_project_by_name(
                DEFAULT_PROJECT, DEFAULT_DOMAIN)['id']
        return self._default_project

    @property
    def default_role(self):
        if self._default_role is None:
            session = sql.get_session()
            try:
                role = session.query(sql_assign.Role).filter_by(
                    name=DEFAULT_ROLE).one()
            except sql.NotFound:
                raise exception.RoleNotFound(role_id=role)
            self._default_role = role.id

        return self._default_role
