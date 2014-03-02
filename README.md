# hybrid SQL and LDAP backends for OpenStack Keystone

This project provides two alternative backends for Keystone:

## The Identity Backend

This allows authentication with LDAP **and** SQL while using the SQL backend for all the usual operations. No users or groups are copied from LDAP. LDAP users are assigned a default role and tenant when they first login if they don't already have one (user_project_metadata table). For granting roles to users (`keystone user-role-add`), only the user id from LDAP is inserted into the SQL backend.

The code in this branch has only been tested on the **stable/havana** branch of OpenStack Keystone! Check out the other git branches if you need code for different OpenStack releases.

* * *

### Installation

Since this backend relies on both the LDAP and SQL backends, you have to configure both beforehand. Use the usual configuration options found in /etc/keystone/keystone.conf. However, from the LDAP backend's config, only the ldap.user* options will be used by the hybrid backend (so no tenant/role options).

You should try to see that user authentication works fine with the LDAP backend *before* trying on the hybrid backend. Also make sure that `keystone user-list` works using the LDAP identity backend.

Copy the `hybrid_identity.py` file to the `keystone/identity/backends/` folder of your installation (e.g. `/usr/lib/python/site-packages/keystone/identity/backends/hybrid_identity.py`).

Set the identity backend to `hybrid` (it will use both the LDAP and the SQL backends under the hood):

```
[identity]
driver = keystone.identity.backends.hybrid_identity.Identity
```

Restart keystone.

Now you can assign custom roles to users in LDAP. Make user you use one of the LDAP user-ids returned by the `keystone user-list` query.

```
keystone user-role-add --user-id=12345 --role-id <role-id> --tenant-id <tenant-id>
```


## The Assignment Backend

This allows setting a default role and project for users signing in via LDAP. It adds the new user-project-role association to the database (basically doing `keystone user-role-add`), the first time that an LDAP user successfully authenticates. This should be useful when you have a lot of LDAP users which you want to grant a default role to in OpenStack automatically only if/when they decide to use it. Caveat: this won't delete the user-role-project association from the database when users are deleted from LDAP. In fact it won't ever delete anything.

It uses the SQL assignment backend under the hood by default.


### Installation

Edit the `hybrid_assignment.py` file in this project and set the `DEFAULT_PROJECT`, `DEFAULT_ROLE` and `DEFAULT_DOMAIN` constants at the top of the file. These should already exist in the database!

Then copy the edited `hybrid_assignment.py` file to the `keystone/identity/backends/` folder of your installation (e.g. `/usr/lib/python/site-packages/keystone/assignment/backends/hybrid_assignment.py`).


Set this in your `keystone.conf` file:

```
[assignment]
driver = keystone.assignment.backends.hybrid_assignment.Assignment
```

Restart keystone.
