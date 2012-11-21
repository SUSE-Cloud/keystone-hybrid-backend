keystone-hybrid-backend
=======================

hybrid SQL + LDAP backend for openstack keystone

Note: the hybrid backend currently relies on a new configuration option for determining the LDAP scope of the user query:

```diff
diff -ruN a/keystone/config.py b/keystone/config.py
--- a/keystone/config.py	2012-11-08 13:02:07.000000000 +0100
+++ b/keystone/config.py	2012-11-08 13:11:06.000000000 +0100
@@ -163,7 +163,7 @@
 register_str('suffix', group='ldap', default='cn=example,cn=com')
 register_bool('use_dumb_member', group='ldap', default=False)
 register_str('user_name_attribute', group='ldap', default='sn')
-
+register_int('user_search_scope', group='ldap', default=1)
 
 register_str('user_tree_dn', group='ldap', default=None)
 register_str('user_objectclass', group='ldap', default='inetOrgPerson')
```