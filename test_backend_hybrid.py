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

from keystone.common import ldap as common_ldap
from keystone import tests
from keystone.tests import fakeldap
from keystone.tests import test_backend
from keystone.tests import test_backend_sql


class HybridIdentity(test_backend_sql.SqlIdentity, test_backend.IdentityTests):
    def setUp(self):
        super(HybridIdentity, self).setUp()
        common_ldap.register_handler('fake://', fakeldap.FakeLdap)

    def config_files(self):
        config_files = super(HybridIdentity, self).config_files()
        config_files.append(tests.dirs.tests_conf('backend_hybrid.conf'))
        return config_files

    def config_overrides(self):
        super(HybridIdentity, self).config_overrides()
        self.config_fixture.config(
            group='identity',
            driver='keystone.identity.backends.hybrid.Identity')
