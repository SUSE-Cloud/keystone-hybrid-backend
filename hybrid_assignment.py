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
from keystone.common import dependency
from keystone import exception

DEFAULT_PROJECT = 'openstack'
DEFAULT_ROLE = 'Member'
DEFAULT_DOMAIN = 'default'


@dependency.requires('identity_api')
class Assignment(sql_assign.Assignment):

    def list_projects_for_user(self, user_id, group_ids):
        projects = super(Assignment, self
                         ).list_projects_for_user(user_id, group_ids)

        # a False is_domain_aware value means LDAP (hopefully)
        if not projects and not self.identity_api.is_domain_aware():
            tenant_id = self.get_project_by_name(
                DEFAULT_PROJECT, DEFAULT_DOMAIN)['id']
            role_id = self._get_role_by_name(DEFAULT_ROLE).id

            self.add_role_to_user_and_project(user_id, tenant_id, role_id)

            projects = super(Assignment, self
                             ).list_projects_for_user(user_id, group_ids)

        return projects

    def _get_role_by_name(self, role):
        session = self.get_session()
        try:
            role = session.query(sql_assign.Role).filter_by(name=role).one()
        except sql.NotFound:
            raise exception.RoleNotFound(role_id=role)

        return role
