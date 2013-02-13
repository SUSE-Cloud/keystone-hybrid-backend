keystone-hybrid-backend
=======================

hybrid SQL + LDAP backend for openstack keystone

Since this backend relies on both the LDAP and SQL backends, you have to configure both beforehand. Use the usual configuration options found in /etc/keystone/keystone.conf. However, from the LDAP backend's config, only the ldap.user* options will be used by the hybrid backend (so no tenant/role options). You might even want to test that everything is working fine before switching to the hybrid backend by trying to login with the LDAP backend first.


You will probably need to create new roles/tenants which reference the
users in the LDAP backend, you have to remove a database Foreign Key
constraint which disallows user_id values which are not present in the
SQL backend.

```SQL
$ pgsql keystone -U keystone -W
ALTER TABLE user_project_membership DROP CONSTRAINT user_project_membership_user_id_fkey;
```

or for MySQL:

```SQL
$ mysql keystone
SHOW CREATE TABLE user_project_membership; --look for the constraint name
ALTER TABLE user_project_membership DROP FOREIGN KEY user_project_membership_ibfk_1;
```

Set the identity backend to `hybrid` (it will use both the LDAP and the SQL backends under the hood):

```
[identity]
driver = keystone.identity.backends.hybrid.Identity
```

Restart keystone.

N.B. Be careful with the case sensitivity of postgresql when modifying
user roles. If the user is capitalized in LDAP, then it should be
capitalized in `keystone`, too e.g. `JDoe`, instead of `jdoe`

```
keystone user-role-add --user-id=JDoe --role-id <role-id> --tenant-id <tenant-id>
```